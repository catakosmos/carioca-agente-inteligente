"""
experimentos.py -- Taller 5: evaluacion del agente base (TEL351).

Uso:
  python experimentos.py --cond A --n 500 --seed0 0 --out base_A.csv   # rival aleatorio
  python experimentos.py --cond B --n 500 --seed0 0 --out base_B.csv   # rival con estilo de retencion
  python experimentos.py --resumen base_A.csv base_B.csv               # tabla de resultados

Condiciones (Ronda 1, 108 cartas, 12 cartas por jugador):
  A: rival = PoliticaAleatoria (semilla propia por ronda)
  B: rival = PoliticaRetencion (heuristica con R5 invertida: suelta primero la carta de MENOR puntaje)
El agente base es siempre jugador_0 con PoliticaHeuristica (Taller 4). Una semilla fija el
barajado (env.reset) y el generador del rival aleatorio; primer_jugador = semilla % 2.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics as st

from carioca_agente import CariocaEnv, PoliticaAleatoria, PoliticaHeuristica, ReglasCarioca

CLASES = ("baja", "media", "alta")
AGENTE, RIVAL = "jugador_0", "jugador_1"


def clase_valor(carta, reglas) -> str:
    """Clase por puntaje v(c): baja <=5 (2-5), media 6-9, alta >=10 (10, J, Q, K, A, comodin)."""
    v = reglas.valor_rango(carta.rango)
    return "baja" if v <= 5 else ("media" if v <= 9 else "alta")


class PoliticaRetencion(PoliticaHeuristica):
    """Rival C_B: igual a PoliticaHeuristica (R1-R4) pero con R5 invertida (descarta lo de MENOR puntaje)."""
    nombre = "retencion"

    def _descartar(self, obs, legales, por_id):
        reglas = obs["reglas"]
        cand = [(i, por_id[a[1]]) for i, a in enumerate(legales) if a[0] == "descartar"]
        pool = [t for t in cand if not t[1].es_comodin] or cand
        seguras = [t for t in pool
                   if not (obs["B_rival"] and self._calza_en_mesa(t[1], obs, solo_propias=False))]
        if obs["B"] == 0:
            libres = [t for t in seguras if not self._es_proyecto(t[1], obs["mano"], obs["contrato"])]
        else:
            libres = seguras
        for grupo in (libres, seguras, pool):
            if grupo:
                return min(grupo, key=lambda t: reglas.valor_rango(t[1].rango))[0]
        return cand[0][0]


def jugar(cond: str, seed: int, ronda: int = 1) -> dict:
    reglas = ReglasCarioca()
    env = CariocaEnv(reglas)
    rival = PoliticaAleatoria(seed=10**6 + seed) if cond == "A" else PoliticaRetencion()
    pols = {AGENTE: PoliticaHeuristica(), RIVAL: rival}
    env.reset(seed=seed, options={"ronda": ronda, "primer_jugador": seed % 2})

    G = {a: 0.0 for a in env.possible_agents}
    turnos_ag = 0
    pendiente = None                                   # clase del ultimo descarte del agente, aun sin respuesta
    desc = {c: 0 for c in CLASES}                      # descartes del agente por clase
    rec = {c: 0 for c in CLASES}                       # ... recogidos por el rival en su turno siguiente
    for ag in env.agent_iter():
        obs, rew, term, trunc, _ = env.last()
        G[ag] += rew
        if term or trunc:
            env.step(None)
            continue
        idx = pols[ag](obs)
        act = obs["acciones_legales"][idx]
        if act[0] in ("robar_mazo", "robar_descarte"):
            if ag == AGENTE:
                turnos_ag += 1
            elif pendiente is not None:                # primera accion del rival tras un descarte del agente
                if act[0] == "robar_descarte":
                    rec[pendiente] += 1
                pendiente = None
        elif act[0] == "descartar" and ag == AGENTE:
            carta = next(c for c in obs["mano"] if c.id == act[1])
            pendiente = clase_valor(carta, reglas)
            desc[pendiente] += 1
        env.step(idx)

    res = env.resultado
    exito = int(res["ganador"] == AGENTE)
    fila = {"cond": cond, "seed": seed, "ganador": res["ganador"] or "ninguno", "causa": res["causa"],
            "TE": exito, "P": 0 if exito else res["puntos"][AGENTE],
            "turnos": turnos_ag, "G_H": G[AGENTE]}
    for c in CLASES:
        fila[f"desc_{c}"], fila[f"rec_{c}"] = desc[c], rec[c]
    return fila


# ------------------------------------------------------------------ resumen
def wilson(k: int, n: int, z: float = 1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def ms(xs):
    return f"{st.mean(xs):.1f} ± {st.stdev(xs):.1f}" if len(xs) > 1 else f"{xs[0]:.1f}"


def resumen(archivos):
    for f in archivos:
        filas = list(csv.DictReader(open(f, encoding="utf8")))
        n = len(filas)
        te = [int(r["TE"]) for r in filas]
        P = [float(r["P"]) for r in filas]
        T = [float(r["turnos"]) for r in filas]
        G = [float(r["G_H"]) for r in filas]
        lo, hi = wilson(sum(te), n)
        causas = {c: sum(r["causa"] == c for r in filas) for c in {r["causa"] for r in filas}}
        print(f"\n== {f}  (cond {filas[0]['cond']}, n={n}) ==")
        print(f"TE = {100*sum(te)/n:.1f}%  IC95% Wilson [{100*lo:.1f}, {100*hi:.1f}]")
        print(f"P (puntos retenidos): {ms(P)}  (min {min(P):.0f} - max {max(P):.0f})")
        print(f"Turnos del agente:    {ms(T)}  (min {min(T):.0f} - max {max(T):.0f})")
        print(f"G_H:                  {ms(G)}  (min {min(G):.0f} - max {max(G):.0f})")
        rho = []
        for c in CLASES:
            d, r = sum(int(x[f"desc_{c}"]) for x in filas), sum(int(x[f"rec_{c}"]) for x in filas)
            rho.append(f"{c}: {100*r/d:.1f}% ({r}/{d})" if d else f"{c}: n/a (0 descartes)")
        print("rho por clase -> " + " | ".join(rho))
        print(f"Causas de término: {causas}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", choices=["A", "B"])
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--resumen", nargs="+", metavar="CSV")
    a = ap.parse_args()
    if a.resumen:
        return resumen(a.resumen)
    if not (a.cond and a.out):
        ap.error("indique --cond y --out (o use --resumen)")
    filas = [jugar(a.cond, s) for s in range(a.seed0, a.seed0 + a.n)]
    with open(a.out, "w", newline="", encoding="utf8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} rondas -> {a.out}")


if __name__ == "__main__":
    main()