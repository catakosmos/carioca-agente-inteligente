"""
carioca_agente.py  

Contenido
  1. Reglas y constantes configurables      (ReglasCarioca)
  2. Cartas, combinaciones y generador de bajadas
  3. CariocaEnv(AECEnv)                      (PettingZoo, 1 ronda = 1 episodio)
  4. ModeloRobo                              (Taller 3: P(carta_robada | R_t))
  5. Politicas: aleatoria y heuristica       (Taller 4: politica inicial pi)
  6. Utilidades: jugar ronda / partida, evaluar, verificar P(robo)

Dependencias: pip install pettingzoo gymnasium numpy
"""
from __future__ import annotations

import itertools
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
from gymnasium import spaces
from pettingzoo import AECEnv

# ----------------------------------------------------------------------------
# 1. REGLAS Y CONSTANTES
# ----------------------------------------------------------------------------
PALOS = ("P", "C", "D", "T")            # Picas, Corazones, Diamantes, Treboles
COMODIN_KEY = (0, "J")                  # clave (rango, palo) de un comodin
_NOMBRE_RANGO = {0: "JK", 1: "A", 11: "J", 12: "Q", 13: "K"}

# ronda -> (n_trios, n_escalas)   [Taller 3, tabla de contratos]
CONTRATOS = {1: (2, 0), 2: (1, 1), 3: (0, 2), 4: (3, 0),
             5: (2, 1), 6: (1, 2), 7: (0, 3), 8: (4, 0)}

MAX_ACCIONES = 256                      # tamano fijo del espacio de acciones


@dataclass
class ReglasCarioca:
    n_mazos: int = 2
    n_comodines: int = 4                 # 108 cartas en total con 2 mazos
    cartas_iniciales: int = 12
    largo_trio: int = 3
    largo_escala: int = 4
    agregar_a_rival: bool = True         # permitir agregar a combinaciones del rival
    al_agotar_mazo: str = "terminar"     # "terminar" (Taller 4) | "rebarajar"
    max_turnos: int = 300                # truncamiento de seguridad (turnos totales)
    max_planes_bajada: int = 12          # cuantas formas de bajar se ofrecen
    # Recompensas (Taller 4, valores ilustrativos)
    r_turno: float = -1.0
    r_bajar: float = 10.0
    r_victoria: float = 50.0
    r_descarte_util: float = -5.0        # si el rival recoge el descarte del agente
    penalizar_descarte_util: bool = True

    def valor_rango(self, rango: int) -> int:
        """Puntaje de una carta segun su rango (PENDIENTE de confirmar)."""
        if rango == 0:
            return 25                    # comodin
        if rango == 1:
            return 15                    # as
        if rango >= 10:
            return 10                    # 10, J, Q, K
        return rango                     # 2..9

    def comodines_ok(self, n_naturales: int, n_comodines: int) -> bool:
        """Una combinacion necesita mas naturales que comodines (PENDIENTE)."""
        return n_comodines == 0 or (n_naturales >= 2 and n_comodines < n_naturales)


# ----------------------------------------------------------------------------
# 2. CARTAS Y COMBINACIONES
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Carta:
    id: int                              # unico (hay cartas duplicadas por 2 mazos)
    rango: int                           # 0 = comodin, 1 = A, 2..10, 11 = J, 12 = Q, 13 = K
    palo: str                            # "P","C","D","T" o "J"

    @property
    def es_comodin(self) -> bool:
        return self.rango == 0

    @property
    def clave(self) -> tuple:
        return (self.rango, self.palo)

    def __repr__(self) -> str:
        return "JK" if self.es_comodin else f"{_NOMBRE_RANGO.get(self.rango, self.rango)}{self.palo}"


def construir_baraja(reglas: ReglasCarioca) -> list:
    cartas, i = [], 0
    for _ in range(reglas.n_mazos):
        for palo in PALOS:
            for rango in range(1, 14):
                cartas.append(Carta(i, rango, palo)); i += 1
    for _ in range(reglas.n_comodines):
        cartas.append(Carta(i, 0, "J")); i += 1
    return cartas


def puntaje_mano(cartas, reglas: ReglasCarioca) -> int:
    return sum(reglas.valor_rango(c.rango) for c in cartas)


def _rango_de_pos(pos: int) -> int:
    """Posicion en una escala (1..14) -> rango. El As vale 1 (inicio) o 14 (final)."""
    return 1 if pos in (1, 14) else pos


@dataclass
class Combinacion:
    """Trio o escala en mesa."""
    tipo: str                            # "trio" | "escala"
    dueno: int                           # indice del jugador que la bajo
    cartas: list = field(default_factory=list)
    rango: int = 0                       # solo trio
    palo: str = ""                       # solo escala
    pos: list = field(default_factory=list)   # solo escala: posicion (1..14) de cada carta

    def n_comodines(self) -> int:
        return sum(c.es_comodin for c in self.cartas)

    def n_naturales(self) -> int:
        return len(self.cartas) - self.n_comodines()

    def extremos_para(self, carta: Carta, reglas: ReglasCarioca) -> list:
        """Extremos donde 'carta' puede agregarse: ['-'] (trio), ['ini'], ['fin'] o ambos."""
        n_nat, n_com = self.n_naturales(), self.n_comodines()
        if carta.es_comodin:
            if not reglas.comodines_ok(n_nat, n_com + 1):
                return []
        if self.tipo == "trio":
            if carta.es_comodin or carta.rango == self.rango:
                return ["-"]
            return []
        res = []
        lo, hi = self.pos[0], self.pos[-1]
        if hi + 1 <= 14 and (carta.es_comodin or
                             (carta.palo == self.palo and carta.rango == _rango_de_pos(hi + 1))):
            res.append("fin")
        if lo - 1 >= 1 and (carta.es_comodin or
                            (carta.palo == self.palo and carta.rango == _rango_de_pos(lo - 1))):
            res.append("ini")
        return res

    def agregar(self, carta: Carta, extremo: str) -> None:
        if self.tipo == "trio":
            self.cartas.append(carta)
        elif extremo == "fin":
            self.cartas.append(carta); self.pos.append(self.pos[-1] + 1)
        else:
            self.cartas.insert(0, carta); self.pos.insert(0, self.pos[0] - 1)

    def copiar(self) -> "Combinacion":
        return Combinacion(self.tipo, self.dueno, list(self.cartas), self.rango, self.palo, list(self.pos))

    def __repr__(self) -> str:
        return f"{self.tipo}(j{self.dueno}:{' '.join(map(repr, self.cartas))})"


# ---- Generador de formas de "bajar contrato" -------------------------------
@dataclass(frozen=True)
class _Spec:
    tipo: str
    claves: tuple                        # claves (rango, palo) requeridas (con repeticion)
    datos: tuple                         # trio: (rango,)  escala: (palo, posiciones, pos_comodin)


def _cabe(inv: Counter, need: Counter) -> bool:
    return all(inv[k] >= v for k, v in need.items())


def _cands_trio(inv: Counter, reglas: ReglasCarioca) -> list:
    out = []
    n = reglas.largo_trio
    for r in range(1, 14):
        for n_nat in (n, n - 1):                     # 3 naturales  o  2 + 1 comodin
            n_com = n - n_nat
            if not reglas.comodines_ok(n_nat, n_com):
                continue
            for palos in itertools.combinations_with_replacement(PALOS, n_nat):
                claves = [(r, p) for p in palos] + [COMODIN_KEY] * n_com
                if _cabe(inv, Counter(claves)):
                    out.append(_Spec("trio", tuple(sorted(claves)), (r,)))
    return out


def _cands_escala(inv: Counter, reglas: ReglasCarioca) -> list:
    out, L = [], reglas.largo_escala
    for palo in PALOS:
        for ini in range(1, 16 - L):                 # ini + L - 1 <= 14
            posiciones = tuple(range(ini, ini + L))
            for w in range(0, L + 1):
                if not reglas.comodines_ok(L - w, w):
                    continue
                for pos_com in itertools.combinations(posiciones, w):
                    claves = [COMODIN_KEY if p in pos_com else (_rango_de_pos(p), palo)
                              for p in posiciones]
                    if _cabe(inv, Counter(claves)):
                        out.append(_Spec("escala", tuple(sorted(claves)), (palo, posiciones, pos_com)))
    return out


def generar_planes(mano, contrato: tuple, reglas: ReglasCarioca,
                   max_planes: int = 12, max_crudos: int = 3000) -> list:
    """Formas distintas de cumplir el contrato con cartas de 'mano'.

    Devuelve planes ordenados (mejor primero). Cada plan es una tupla de descriptores:
        ("trio",   ids, rango)
        ("escala", ids_ordenados_por_posicion, (palo, posiciones))
    Se usan combinaciones de largo minimo; el resto se agrega luego con 'agregar'.
    """
    n_trios, n_escalas = contrato
    inv = Counter(c.clave for c in mano)
    ct = _cands_trio(inv, reglas) if n_trios else []
    ce = _cands_escala(inv, reglas) if n_escalas else []
    encontrados: dict = {}

    def rec(it, ie, rt, re_, inv_act, elegidos):
        if len(encontrados) >= max_crudos:
            return
        if rt == 0 and re_ == 0:
            firma = tuple(sorted((s.tipo, s.claves, s.datos) for s in elegidos))
            encontrados.setdefault(firma, list(elegidos))
            return
        if rt > 0:
            for i in range(it, len(ct)):
                need = Counter(ct[i].claves)
                if _cabe(inv_act, need):
                    rec(i, ie, rt - 1, re_, inv_act - need, elegidos + [ct[i]])
        else:
            for i in range(ie, len(ce)):
                need = Counter(ce[i].claves)
                if _cabe(inv_act, need):
                    rec(it, i, rt, re_ - 1, inv_act - need, elegidos + [ce[i]])

    rec(0, 0, n_trios, n_escalas, inv, [])

    def costo(specs):
        claves = [k for s in specs for k in s.claves]
        usados = sum(reglas.valor_rango(k[0]) for k in claves)
        return (sum(k == COMODIN_KEY for k in claves), -usados)   # pocos comodines, bajar valor alto

    ordenados = sorted(encontrados.values(), key=costo)[:max_planes]
    return [_resolver(p, mano) for p in ordenados]


def _resolver(specs, mano) -> tuple:
    pool = defaultdict(list)
    for c in mano:
        pool[c.clave].append(c)
    plan = []
    for s in specs:
        if s.tipo == "trio":
            ids = tuple(pool[k].pop().id for k in s.claves)
            plan.append(("trio", ids, s.datos[0]))
        else:
            palo, posiciones, pos_com = s.datos
            ids = tuple(pool[COMODIN_KEY if p in pos_com else (_rango_de_pos(p), palo)].pop().id
                        for p in posiciones)
            plan.append(("escala", ids, (palo, posiciones)))
    return tuple(plan)


def hay_plan(mano, contrato, reglas) -> bool:
    return bool(generar_planes(mano, contrato, reglas, max_planes=1, max_crudos=1))


# ----------------------------------------------------------------------------
# 3. ENTORNO PETTINGZOO
# ----------------------------------------------------------------------------
class CariocaEnv(AECEnv):
    """Una ronda de Carioca (contrato fijo) entre 2 jugadores. API AECEnv.

    Un turno = robar -> [bajar] -> [agregar]* -> descartar. Cada una de esas acciones
    es un step(). La accion que se pasa a step() es un INDICE dentro de
    obs["acciones_legales"] (lista dinamica); obs["action_mask"] marca los validos.
    """
    metadata = {"name": "carioca_v0", "is_parallelizable": False}

    def __init__(self, reglas: Optional[ReglasCarioca] = None, ronda: int = 1):
        super().__init__()
        self.reglas = reglas or ReglasCarioca()
        self.ronda = ronda
        self.possible_agents = ["jugador_0", "jugador_1"]
        self.action_spaces = {a: spaces.Discrete(MAX_ACCIONES) for a in self.possible_agents}
        # Observacion estructurada (dict de Python); se declara un espacio minimo.
        self.observation_spaces = {
            a: spaces.Dict({"action_mask": spaces.Box(0, 1, (MAX_ACCIONES,), np.int8)})
            for a in self.possible_agents}
        self.rng = random.Random()
        self.resultado: Optional[dict] = None

    # ---- utilidades ---------------------------------------------------------
    @staticmethod
    def _i(agente: str) -> int:
        return int(agente[-1])

    def _otro(self, agente: str) -> str:
        return "jugador_1" if agente == "jugador_0" else "jugador_0"

    # ---- reset --------------------------------------------------------------
    def reset(self, seed=None, options=None):
        options = options or {}
        if seed is not None:
            self.rng = random.Random(seed)
        self.ronda = options.get("ronda", self.ronda)
        self.contrato = CONTRATOS[self.ronda]
        self.agents = self.possible_agents[:]
        self.rewards = {a: 0.0 for a in self.agents}
        self._cumulative_rewards = {a: 0.0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}
        self._skip_agent_selection = None
        self.resultado = None

        self.mazo = construir_baraja(self.reglas)
        self.rng.shuffle(self.mazo)
        self.manos = {a: [self.mazo.pop() for _ in range(self.reglas.cartas_iniciales)]
                      for a in self.agents}
        self.descarte = [self.mazo.pop()]
        self.mesa: list = []
        self.bajado = {a: False for a in self.agents}
        self.turnos = 0
        self.fase = "robar"
        self.agent_selection = self.agents[options.get("primer_jugador", 0)]
        self._iniciar_turno()

    # ---- observacion --------------------------------------------------------
    def observe(self, agente: str) -> dict:
        otro = self._otro(agente)
        yo = self._i(agente)
        propio = (agente == self.agent_selection) and not self.resultado
        legales = list(self._legales) if propio else []
        mask = np.zeros(MAX_ACCIONES, dtype=np.int8)
        mask[:len(legales)] = 1
        return {
            "yo": yo,
            "ronda": self.ronda,
            "contrato": self.contrato,
            "fase": self.fase if propio else None,
            "mano": tuple(sorted(self.manos[agente], key=lambda c: (c.palo, c.rango))),
            "B": int(self.bajado[agente]),                          # B_t
            "B_rival": int(self.bajado[otro]),                      # deducible de T_t
            "n_rival": len(self.manos[otro]),                       # N_t^rival
            "mesa": tuple(m.copiar() for m in self.mesa),           # T_t
            "tope_descarte": self.descarte[-1] if self.descarte else None,   # D_t
            "descarte_publico": tuple(self.descarte[:-1]),          # supuesto Taller 4
            "n_mazo": len(self.mazo),                               # |R_t|
            "reglas": self.reglas,
            "acciones_legales": legales,
            "action_mask": mask,
        }

    # ---- generacion de acciones legales ------------------------------------
    def _generar_legales(self, agente: str) -> list:
        mano = self.manos[agente]
        yo = self._i(agente)
        legales: list = []
        if self.fase == "robar":
            if self.mazo:
                legales.append(("robar_mazo",))
            if self.descarte:
                legales.append(("robar_descarte",))
            return legales
        if not self.bajado[agente]:
            for plan in generar_planes(mano, self.contrato, self.reglas,
                                       max_planes=self.reglas.max_planes_bajada):
                legales.append(("bajar", plan))
        else:
            vistos = set()
            for c in mano:
                for idx, m in enumerate(self.mesa):
                    if m.dueno != yo and not self.reglas.agregar_a_rival:
                        continue
                    for ext in m.extremos_para(c, self.reglas):
                        k = (c.clave, idx, ext)
                        if k not in vistos:
                            vistos.add(k)
                            legales.append(("agregar", c.id, idx, ext))
        vistos = set()
        for c in mano:
            if c.clave not in vistos:
                vistos.add(c.clave)
                legales.append(("descartar", c.id))
        assert len(legales) <= MAX_ACCIONES
        return legales

    # ---- turnos -------------------------------------------------------------
    def _iniciar_turno(self) -> None:
        """Deja al agente actual en fase 'robar' (maneja mazo agotado y truncamiento)."""
        self.fase = "robar"
        if self.turnos >= self.reglas.max_turnos:
            return self._terminar(None, "max_turnos", truncar=True)
        if not self.mazo:
            if self.reglas.al_agotar_mazo == "rebarajar" and len(self.descarte) > 1:
                tope = self.descarte.pop()
                self.mazo, self.descarte = self.descarte, [tope]
                self.rng.shuffle(self.mazo)
            else:
                return self._terminar(None, "mazo_agotado")
        self._legales = self._generar_legales(self.agent_selection)

    def _terminar(self, ganador: Optional[str], causa: str, truncar: bool = False) -> None:
        pts = {a: puntaje_mano(self.manos[a], self.reglas) for a in self.possible_agents}
        for a in self.possible_agents:
            if a == ganador:
                self.rewards[a] += self.reglas.r_victoria
            else:
                self.rewards[a] += -pts[a]
        self.resultado = {"ganador": ganador, "causa": causa, "puntos": pts,
                          "turnos": self.turnos, "ronda": self.ronda}
        for a in self.possible_agents:
            (self.truncations if truncar else self.terminations)[a] = True
            self.infos[a] = {"resultado": self.resultado}
        self._legales = []

    # ---- step ---------------------------------------------------------------
    def step(self, accion):
        agente = self.agent_selection
        if self.terminations[agente] or self.truncations[agente]:
            self._was_dead_step(accion)
            return
        if not isinstance(accion, (int, np.integer)) or not (0 <= accion < len(self._legales)):
            raise ValueError(f"Accion invalida {accion!r}; legales: {len(self._legales)}")
        self._cumulative_rewards[agente] = 0
        self._clear_rewards()

        act = self._legales[int(accion)]
        mano, r = self.manos[agente], self.reglas
        yo, otro = self._i(agente), self._otro(agente)
        por_id = {c.id: c for c in mano}
        fin_turno = False

        if act[0] == "robar_mazo":
            mano.append(self.mazo.pop()); self.fase = "jugar"
        elif act[0] == "robar_descarte":
            mano.append(self.descarte.pop()); self.fase = "jugar"
            if r.penalizar_descarte_util:                 # el rival recogio mi descarte
                self.rewards[otro] += r.r_descarte_util
        elif act[0] == "bajar":
            for tipo, ids, extra in act[1]:
                cartas = [por_id[i] for i in ids]
                if tipo == "trio":
                    self.mesa.append(Combinacion("trio", yo, cartas, rango=extra))
                else:
                    palo, posiciones = extra
                    self.mesa.append(Combinacion("escala", yo, cartas, palo=palo, pos=list(posiciones)))
                for c in cartas:
                    mano.remove(c)
            self.bajado[agente] = True
            self.rewards[agente] += r.r_bajar
        elif act[0] == "agregar":
            _, cid, idx, ext = act
            carta = por_id[cid]
            self.mesa[idx].agregar(carta, ext)
            mano.remove(carta)
        elif act[0] == "descartar":
            carta = por_id[act[1]]
            mano.remove(carta)
            self.descarte.append(carta)
            fin_turno = True

        if not mano:                                         # M_t = vacio -> cierra la ronda
            self._terminar(agente, "cierre")
        elif fin_turno:
            self.rewards[agente] += r.r_turno
            self.turnos += 1
            self.agent_selection = otro
            self._iniciar_turno()
        else:
            self._legales = self._generar_legales(agente)

        self._accumulate_rewards()

    def render(self):
        print(f"Ronda {self.ronda} contrato={self.contrato} turno de {self.agent_selection} "
              f"fase={self.fase} mazo={len(self.mazo)} descarte={self.descarte[-1:]}")
        for a in self.possible_agents:
            print(f"  {a}: {self.manos[a]}  bajado={self.bajado[a]}")
        print(f"  mesa: {self.mesa}")


# ----------------------------------------------------------------------------
# 4. MODELO PROBABILISTICO MINIMO (Taller 3):  P(carta_robada | R_t)
# ----------------------------------------------------------------------------
class ModeloRobo:
    """Cartas no vistas = baraja - mano - mesa - descarte conocido  (|R_t| + N_rival cartas).
    Bajo la aproximacion del Taller 4 son equiprobables para el proximo robo del mazo."""

    def __init__(self, reglas: ReglasCarioca):
        self.reglas = reglas
        self.total = Counter(c.clave for c in construir_baraja(reglas))

    def no_vistas(self, obs: dict) -> Counter:
        vistas = Counter(c.clave for c in obs["mano"])
        for m in obs["mesa"]:
            vistas.update(c.clave for c in m.cartas)
        vistas.update(c.clave for c in obs["descarte_publico"])
        if obs["tope_descarte"] is not None:
            vistas[obs["tope_descarte"].clave] += 1
        return self.total - vistas

    def distribucion(self, obs: dict) -> dict:
        nv = self.no_vistas(obs)
        n = sum(nv.values())
        return {k: v / n for k, v in nv.items()} if n else {}

    def prob(self, obs: dict, predicado: Callable[[tuple], bool]) -> float:
        return sum(p for k, p in self.distribucion(obs).items() if predicado(k))

    def prob_habilita_bajada(self, obs: dict) -> float:
        """P(la carta robada completa el contrato), 0 si ya se puede bajar o ya se bajo."""
        if obs["B"] or hay_plan(obs["mano"], obs["contrato"], self.reglas):
            return 0.0
        return self.prob(obs, lambda k: hay_plan(
            list(obs["mano"]) + [Carta(-1, k[0], k[1])], obs["contrato"], self.reglas))


# ----------------------------------------------------------------------------
# 5. POLITICAS
# ----------------------------------------------------------------------------
class PoliticaAleatoria:
    nombre = "aleatoria"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def __call__(self, obs: dict) -> int:
        return self.rng.randrange(len(obs["acciones_legales"]))


class PoliticaHeuristica:
    """Politica inicial determinista pi: S -> A del Taller 4 (reglas 1-5).
    Solo usa variables de S (mano, B, mesa, tope, |R|, contrato) y el descarte publico."""
    nombre = "heuristica"

    # -- helpers
    @staticmethod
    def _idx(legales, nombre):
        for i, a in enumerate(legales):
            if a[0] == nombre:
                return i
        return None

    @staticmethod
    def _calza_en_mesa(carta, obs, solo_propias: bool) -> bool:
        reglas = obs["reglas"]
        for m in obs["mesa"]:
            if solo_propias and m.dueno != obs["yo"]:
                continue
            if m.dueno != obs["yo"] and not reglas.agregar_a_rival:
                continue
            if m.extremos_para(carta, reglas):
                return True
        return False

    @staticmethod
    def _es_proyecto(carta, mano, contrato) -> bool:
        n_trios, n_escalas = contrato
        otras = [c for c in mano if c.id != carta.id and not c.es_comodin]
        if n_trios and any(c.rango == carta.rango for c in otras):
            return True                                         # par -> posible trio
        if n_escalas:
            r = carta.rango
            for c in otras:
                if c.palo == carta.palo:
                    d = abs(c.rango - r)
                    if 0 < d <= 2 or (r == 1 and c.rango >= 12) or (c.rango == 1 and r >= 12):
                        return True                             # vecinas del mismo palo
        return False

    # -- politica
    def __call__(self, obs: dict) -> int:
        legales = obs["acciones_legales"]
        return self._robar(obs, legales) if obs["fase"] == "robar" else self._jugar(obs, legales)

    def _robar(self, obs, legales) -> int:
        i_d, i_m = self._idx(legales, "robar_descarte"), self._idx(legales, "robar_mazo")
        tope, mano, reglas = obs["tope_descarte"], list(obs["mano"]), obs["reglas"]
        if i_d is not None and tope is not None:
            if obs["B"] == 0:                                   # Regla 1: completa el contrato
                if not hay_plan(mano, obs["contrato"], reglas) and \
                        hay_plan(mano + [tope], obs["contrato"], reglas):
                    return i_d
            elif self._calza_en_mesa(tope, obs, solo_propias=True):   # Regla 1: calza en T_t propia
                return i_d
        return i_m if i_m is not None else i_d                  # Regla 2 (y mazo agotado)

    def _jugar(self, obs, legales) -> int:
        i_b = self._idx(legales, "bajar")
        if i_b is not None:                                     # Regla 3: bajar (mejor plan primero)
            return i_b
        por_id = {c.id: c for c in obs["mano"]}
        reglas = obs["reglas"]
        agregados = [(i, a) for i, a in enumerate(legales)
                     if a[0] == "agregar" and not por_id[a[1]].es_comodin]   # no inmovilizar comodines
        if agregados:                                           # Regla 4: vaciado acelerado
            return max(agregados, key=lambda t: reglas.valor_rango(por_id[t[1][1]].rango))[0]
        return self._descartar(obs, legales, por_id)            # Regla 5

    def _descartar(self, obs, legales, por_id) -> int:
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
                return max(grupo, key=lambda t: reglas.valor_rango(t[1].rango))[0]
        return cand[0][0]


# ----------------------------------------------------------------------------
# 6. UTILIDADES DE SIMULACION
# ----------------------------------------------------------------------------
def jugar_ronda(env: CariocaEnv, politicas: dict, ronda: int = 1,
                primer_jugador: int = 0, seed=None, verbose: bool = False) -> dict:
    """Juega una ronda. politicas = {"jugador_0": callable, "jugador_1": callable}.
    Devuelve el resultado + retorno acumulado G_H por agente."""
    env.reset(seed=seed, options={"ronda": ronda, "primer_jugador": primer_jugador})
    G = {a: 0.0 for a in env.possible_agents}
    for ag in env.agent_iter():
        obs, rew, term, trunc, info = env.last()
        G[ag] += rew
        if term or trunc:
            env.step(None)
            continue
        accion = politicas[ag](obs)
        if verbose:
            print(f"[t={env.turnos:3d}] {ag} {obs['fase']:6s} -> {obs['acciones_legales'][accion]}")
        env.step(accion)
    res = dict(env.resultado)
    res["G"] = G
    return res


def jugar_partida(politicas: dict, rondas=range(1, 9), seed=None, reglas=None) -> dict:
    """Partida completa (8 rondas). Gana quien acumule MENOS puntos."""
    env = CariocaEnv(reglas)
    rng = random.Random(seed)
    total = {a: 0 for a in env.possible_agents}
    detalle = []
    for k, ronda in enumerate(rondas):
        res = jugar_ronda(env, politicas, ronda, primer_jugador=k % 2, seed=rng.randrange(2**31))
        for a in total:
            total[a] += 0 if a == res["ganador"] else res["puntos"][a]
        detalle.append(res)
    return {"total": total, "rondas": detalle}


def evaluar(pol_a, pol_b, n_rondas: int = 200, ronda: int = 1, seed: int = 0, reglas=None) -> dict:
    """Enfrenta A vs B en una ronda dada, alternando asiento y quien parte."""
    env = CariocaEnv(reglas)
    rng = random.Random(seed)
    vic = {"A": 0, "B": 0, "sin_ganador": 0}
    G = {"A": 0.0, "B": 0.0}
    turnos = 0
    for k in range(n_rondas):
        a_es_0 = (k % 2 == 0)
        pols = {"jugador_0": pol_a if a_es_0 else pol_b, "jugador_1": pol_b if a_es_0 else pol_a}
        nombre = {"jugador_0": "A" if a_es_0 else "B", "jugador_1": "B" if a_es_0 else "A"}
        res = jugar_ronda(env, pols, ronda, primer_jugador=(k // 2) % 2, seed=rng.randrange(2**31))
        vic[nombre[res["ganador"]] if res["ganador"] else "sin_ganador"] += 1
        for ag, g in res["G"].items():
            G[nombre[ag]] += g
        turnos += res["turnos"]
    return {"victorias": vic, "G_medio": {k: v / n_rondas for k, v in G.items()},
            "turnos_medios": turnos / n_rondas}


def verificar_prob_robo(n: int = 5000, rango: int = 7, seed: int = 1) -> tuple:
    """Taller 4: compara P(carta robada tenga 'rango') segun el modelo contra la
    frecuencia empirica de la cima del mazo en n repartos simulados."""
    env = CariocaEnv()
    modelo = ModeloRobo(env.reglas)
    rng = random.Random(seed)
    p_modelo, hits = 0.0, 0
    for _ in range(n):
        env.reset(seed=rng.randrange(2**31))
        obs = env.observe(env.agent_selection)
        p_modelo += modelo.prob(obs, lambda k: k[0] == rango)
        hits += env.mazo[-1].rango == rango
    return p_modelo / n, hits / n


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    pols = {"jugador_0": PoliticaHeuristica(), "jugador_1": PoliticaAleatoria(seed=0)}
    print(jugar_ronda(CariocaEnv(), pols, ronda=1, seed=42, verbose=True))
    print("Heuristica vs Aleatoria, ronda 1:",
          evaluar(PoliticaHeuristica(), PoliticaAleatoria(1), n_rondas=200, ronda=1))
    print("P(7) modelo vs empirica:", verificar_prob_robo())