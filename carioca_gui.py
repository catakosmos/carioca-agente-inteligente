"""
carioca_gui.py  --  Interfaz grafica (tkinter) para CariocaEnv.

Requiere carioca_agente.py en la misma carpeta. Ejecutar:  python carioca_gui.py

Como se juega (tu eres abajo, el rival arriba con las cartas boca abajo):
  - Tu turno: clic en el MAZO (carta oculta) o en el DESCARTE (carta visible).
  - Para bajar el contrato: elige el plan con  <  >  y pulsa "Bajar contrato".
  - Arrastra una carta a una COMBINACION de la mesa para agregarla (solo tras bajar).
    Doble clic sobre una carta la agrega sola si calza en alguna combinacion.
  - Arrastra una carta al DESCARTE (o seleccionala y haz clic en el descarte) para terminar el turno.
  - Arrastra dentro de tu mano para reordenar.   "Pista" te sugiere la jugada del agente.
"""
from __future__ import annotations

import random
import tkinter as tk
from tkinter import messagebox

from carioca_agente import (CariocaEnv, ModeloRobo, PoliticaAleatoria, PoliticaHeuristica)

# ---------------------------------------------------------------- estilo
FIELTRO, FIELTRO_OSC, FIELTRO_BORDE = "#0a6c3b", "#085a31", "#0d8a4a"
SOMBRA = "#06502b"
SIMBOLO = {"P": "♠", "C": "♥", "D": "♦", "T": "♣"}
COLOR_PALO = {"P": "#161616", "T": "#161616", "C": "#c0182b", "D": "#c0182b"}
NOMBRE = {1: "A", 11: "J", 12: "Q", 13: "K"}
VERDE_OK, DORADO, CIAN = "#7CFC00", "#ffd21f", "#35e0ff"
CW, CH = 74, 104        # carta de la mano / pilas
MW, MH = 52, 74         # carta en la mesa
RW, RH = 56, 78         # carta del rival
W, H = 1100, 600
HAND_Y, RIVAL_Y = 462, 14
PILA_Y, MAZO_X, DESC_X = 130, 40, 134
ZONAS = {1: (240, 112, 1076, 226), 0: (240, 236, 1076, 350)}   # dueno -> zona de combinaciones
FUENTE = "Segoe UI"


def _rango(c):
    return NOMBRE.get(c.rango, str(c.rango))


def texto_contrato(contrato):
    nt, ne = contrato
    partes = []
    if nt:
        partes.append(f"{nt} {'trio' if nt == 1 else 'trios'}".replace("trio", "trío"))
    if ne:
        partes.append(f"{ne} {'escala' if ne == 1 else 'escalas'}")
    return " + ".join(partes)


def rrect(cv, x1, y1, x2, y2, r=8, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def dibujar_carta(cv, x, y, c, w, h, glow=None, rep=None, tags=()):
    """Carta con cara visible. rep: rango que representa un comodin dentro de una combinacion."""
    if glow:
        rrect(cv, x - 4, y - 4, x + w + 4, y + h + 4, 10, fill=glow, outline="", tags=tags)
    rrect(cv, x + 2, y + 2, x + w + 2, y + h + 2, 8, fill=SOMBRA, outline="", tags=tags)
    fondo = "#fff3c4" if c.es_comodin else "#fdfdfd"
    rrect(cv, x, y, x + w, y + h, 8, fill=fondo, outline="#4a4a4a", tags=tags)
    fs = max(8, int(w * 0.21))
    if c.es_comodin:
        cv.create_text(x + 6, y + 4, text="★", anchor="nw", fill="#c47f00",
                       font=(FUENTE, fs + 2, "bold"), tags=tags)
        if rep:
            cv.create_text(x + 6, y + 6 + fs + 6, text=f"={rep}", anchor="nw", fill="#7a4b00",
                           font=(FUENTE, max(7, fs - 3), "bold"), tags=tags)
        else:
            cv.create_text(x + 6, y + 6 + fs + 6, text="JK", anchor="nw", fill="#7a4b00",
                           font=(FUENTE, max(7, fs - 2), "bold"), tags=tags)
            if w >= 60:
                cv.create_text(x + w / 2, y + h / 2 + 6, text="★", fill="#e0a000",
                               font=(FUENTE, int(w * 0.5)), tags=tags)
        return
    col, sim = COLOR_PALO[c.palo], SIMBOLO[c.palo]
    cv.create_text(x + 5, y + 3, text=_rango(c), anchor="nw", fill=col,
                   font=(FUENTE, fs + 1, "bold"), tags=tags)
    cv.create_text(x + 6, y + 3 + fs + 5, text=sim, anchor="nw", fill=col,
                   font=(FUENTE, fs), tags=tags)
    if w >= 60:
        cv.create_text(x + w / 2, y + h / 2 + 6, text=sim, fill=col,
                       font=(FUENTE, int(w * 0.5)), tags=tags)
        cv.create_text(x + w - 5, y + h - 3, text=_rango(c), anchor="se", fill=col,
                       font=(FUENTE, fs + 1, "bold"), tags=tags)


def dibujar_dorso(cv, x, y, w, h, tags=()):
    rrect(cv, x + 2, y + 2, x + w + 2, y + h + 2, 8, fill=SOMBRA, outline="", tags=tags)
    rrect(cv, x, y, x + w, y + h, 8, fill="#ffffff", outline="#4a4a4a", tags=tags)
    rrect(cv, x + 4, y + 4, x + w - 4, y + h - 4, 6, fill="#1f4fa3", outline="#102e6b", tags=tags)
    cx, cy = x + w / 2, y + h / 2
    cv.create_oval(cx - w * .22, cy - h * .16, cx + w * .22, cy + h * .16,
                   outline="#9ec1ff", width=2, tags=tags)
    cv.create_polygon(cx, cy - h * .3, cx + w * .3, cy, cx, cy + h * .3, cx - w * .3, cy,
                      outline="#6f98e8", fill="", width=1, tags=tags)


def describir(act, por_id, tope=None):
    t = act[0]
    if t == "robar_mazo":
        return "robó del mazo"
    if t == "robar_descarte":
        return f"tomó {tope!r} del descarte"
    if t == "bajar":
        return "bajó el contrato (" + texto_plan(act[1], por_id) + ")"
    if t == "agregar":
        return f"agregó {por_id[act[1]]!r} a la mesa"
    return f"descartó {por_id[act[1]]!r}"


def texto_plan(plan, por_id):
    return " | ".join(("trío " if tipo == "trio" else "escala ") +
                      " ".join(repr(por_id[i]) for i in ids) for tipo, ids, _ in plan)


# ================================================================== GUI
class CariocaGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Carioca — Agente inteligente (TEL351)")
        root.resizable(False, False)
        root.configure(bg="#05381f")
        self.env = CariocaEnv()
        self.modelo = ModeloRobo(self.env.reglas)
        self.ctrl = {"jugador_0": None, "jugador_1": PoliticaHeuristica()}   # None = humano
        self.delay = 650
        self.gen, self._pend = 0, False
        self.ronda, self.totales = 1, {"jugador_0": 0, "jugador_1": 0}
        self.modo_orden = "palo"
        self.hits, self.meld_bbox = [], {}
        self.arr = self.press = None
        self.sel = None
        self.pista = None
        self.aviso = ""
        self.plan_idx = 0
        self.orden = []
        self.log = {"jugador_0": "", "jugador_1": ""}
        self.cerrada = False
        self._widgets()
        self.nueva_partida()

    # ------------------------------------------------------------ widgets
    def _widgets(self):
        top = tk.Frame(self.root, bg="#05381f"); top.pack(fill="x", padx=8, pady=(6, 2))
        bt = dict(bg="#e8e8e8", relief="flat", padx=10, pady=3)
        tk.Button(top, text="Nueva partida", command=self.nueva_partida, **bt).pack(side="left")
        tk.Label(top, text="  Tú:", bg="#05381f", fg="white").pack(side="left")
        self.var_yo = tk.StringVar(value="Humano")
        tk.OptionMenu(top, self.var_yo, "Humano", "Agente (heurística)",
                      command=lambda *_: self.cambiar_ctrl()).pack(side="left")
        tk.Label(top, text="  Rival:", bg="#05381f", fg="white").pack(side="left")
        self.var_riv = tk.StringVar(value="Heurística")
        tk.OptionMenu(top, self.var_riv, "Heurística", "Aleatorio",
                      command=lambda *_: self.cambiar_ctrl()).pack(side="left")
        self.var_prob = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="Mostrar probabilidades", variable=self.var_prob, bg="#05381f",
                       fg="white", selectcolor="#05381f", activebackground="#05381f",
                       activeforeground="white", command=self.dibujar).pack(side="left", padx=8)
        self.lbl_info = tk.Label(top, text="", bg="#05381f", fg="#ffe9a8", font=(FUENTE, 11, "bold"))
        self.lbl_info.pack(side="right")

        self.cv = tk.Canvas(self.root, width=W, height=H, bg=FIELTRO, highlightthickness=0)
        self.cv.pack(padx=8)
        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_motion)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        self.cv.bind("<Double-Button-1>", self.on_double)

        bot = tk.Frame(self.root, bg="#05381f"); bot.pack(fill="x", padx=8, pady=(4, 2))
        self.b_prev = tk.Button(bot, text="◀", command=lambda: self.cambiar_plan(-1), width=3, **bt)
        self.b_baj = tk.Button(bot, text="Bajar contrato", command=self.bajar, **bt)
        self.b_next = tk.Button(bot, text="▶", command=lambda: self.cambiar_plan(1), width=3, **bt)
        for b in (self.b_prev, self.b_baj, self.b_next):
            b.pack(side="left", padx=1)
        tk.Button(bot, text="\U0001F4A1 Pista", command=self.dar_pista, **bt).pack(side="left", padx=(14, 2))
        tk.Button(bot, text="Jugar por mí", command=self.jugar_por_mi, **bt).pack(side="left", padx=2)
        tk.Button(bot, text="Ordenar mano", command=self.ordenar, **bt).pack(side="left", padx=2)
        self.btn_sig = tk.Button(bot, text="Siguiente ronda ▶", command=self.siguiente_ronda,
                                 state="disabled", **bt)
        self.btn_sig.pack(side="right")
        self.lbl_estado = tk.Label(self.root, text="", bg="#05381f", fg="white", anchor="w",
                                   justify="left", wraplength=W - 20, font=(FUENTE, 11))
        self.lbl_estado.pack(fill="x", padx=10, pady=(0, 6))

    # ------------------------------------------------------------ flujo de partida
    def nueva_partida(self):
        self.ronda = 1
        self.totales = {"jugador_0": 0, "jugador_1": 0}
        self.cambiar_ctrl(refrescar=False)
        self.iniciar_ronda()

    def cambiar_ctrl(self, refrescar=True):
        self.ctrl["jugador_0"] = None if self.var_yo.get() == "Humano" else PoliticaHeuristica()
        self.ctrl["jugador_1"] = (PoliticaHeuristica() if self.var_riv.get().startswith("Heur")
                                  else PoliticaAleatoria())
        if refrescar:
            self.refrescar()

    def iniciar_ronda(self):
        self.gen += 1
        self._pend = False
        self.env.reset(seed=random.randrange(2 ** 31),
                       options={"ronda": self.ronda, "primer_jugador": (self.ronda - 1) % 2})
        self.orden, self.sel, self.arr, self.pista = [], None, None, None
        self.aviso, self.plan_idx, self.cerrada = "", 0, False
        self.log = {"jugador_0": "", "jugador_1": ""}
        self.btn_sig.config(state="disabled")
        self.refrescar()

    def siguiente_ronda(self):
        if self.ronda < 8:
            self.ronda += 1
            self.iniciar_ronda()
        else:
            a, b = self.totales["jugador_0"], self.totales["jugador_1"]
            quien = "¡Ganaste la partida!" if a < b else ("Ganó el rival." if b < a else "Empate.")
            messagebox.showinfo("Fin de la partida",
                                f"{quien}\n\nPuntos acumulados (menos es mejor)\nTú: {a}\nRival: {b}")

    def fin_ronda(self):
        if self.cerrada:
            return
        self.cerrada = True
        res = self.env.resultado
        for a in self.totales:
            self.totales[a] += 0 if a == res["ganador"] else res["puntos"][a]
        self.btn_sig.config(text="Siguiente ronda ▶" if self.ronda < 8 else "Ver resultado final",
                            state="normal")
        self.dibujar()
        self.actualizar_ui()

    def mi_turno(self):
        return (not self.env.resultado and self.env.agent_selection == "jugador_0"
                and self.ctrl["jugador_0"] is None)

    def refrescar(self):
        self.dibujar()
        self.siguiente()

    def siguiente(self):
        """Avanza hasta que le toque a un humano, o agenda la jugada de un agente."""
        if self.env.resultado:
            return self.fin_ronda()
        ag = self.env.agent_selection
        if self.ctrl[ag] is None:
            self.actualizar_ui()
            return
        self.actualizar_ui()
        if not self._pend:
            self._pend = True
            g = self.gen
            self.root.after(self.delay, lambda: self._auto(ag, g))

    def _auto(self, ag, g):
        self._pend = False
        pol = self.ctrl[ag]
        if g != self.gen or self.env.resultado or self.env.agent_selection != ag or pol is None:
            return
        obs = self.env.observe(ag)
        idx = pol(obs)
        act = obs["acciones_legales"][idx]
        por_id = {c.id: c for c in obs["mano"]}
        if obs["fase"] == "robar":
            self.log[ag] = ""
        txt = describir(act, por_id, obs["tope_descarte"])
        self.log[ag] += (" → " if self.log[ag] else "") + txt
        self.pista, self.aviso = None, ""
        self.env.step(idx)
        self.plan_idx = 0
        self.refrescar()

    # ------------------------------------------------------------ acciones del humano
    def _legales(self):
        return self.obs["acciones_legales"]

    def _por_id(self):
        return {c.id: c for c in self.obs["mano"]}

    def _aplicar(self, act, carta=None):
        legales = self._legales()
        idx = legales.index(act)
        if carta is not None and act[0] in ("descartar", "agregar") and act[1] != carta.id:
            # misma carta (mismo valor/palo) pero otro id: intercambia posiciones en la mano
            if act[1] in self.orden and carta.id in self.orden:
                i, j = self.orden.index(act[1]), self.orden.index(carta.id)
                self.orden[i], self.orden[j] = self.orden[j], self.orden[i]
        self.sel, self.pista, self.aviso, self.plan_idx = None, None, "", 0
        self.env.step(idx)
        self.refrescar()

    def _avisar(self, texto):
        self.aviso = texto
        self.dibujar()
        self.actualizar_ui()

    def robar(self, tipo):
        if self.env.fase != "robar":
            return self._avisar("Ya robaste en este turno: ahora juega o descarta.")
        act = (tipo,)
        if act not in self._legales():
            return self._avisar("No puedes robar de ahí.")
        self._aplicar(act)

    def planes(self):
        return [a for a in self._legales() if a[0] == "bajar"]

    def cambiar_plan(self, d):
        pl = self.planes()
        if pl:
            self.plan_idx = (self.plan_idx + d) % len(pl)
            self.pista = None
            self.dibujar(); self.actualizar_ui()

    def bajar(self):
        pl = self.planes()
        if self.mi_turno() and pl:
            self._aplicar(pl[self.plan_idx % len(pl)])

    def descartar(self, c):
        if self.env.fase != "jugar":
            return self._avisar("Primero roba una carta (mazo o descarte).")
        for a in self._legales():
            if a[0] == "descartar" and self._por_id()[a[1]].clave == c.clave:
                return self._aplicar(a, c)

    def agregar(self, c, idx, x):
        if self.env.fase != "jugar":
            return self._avisar("Primero roba una carta (mazo o descarte).")
        if not self.obs["B"]:
            return self._avisar("Debes bajar tu contrato antes de agregar cartas a la mesa.")
        por_id = self._por_id()
        opts = [a for a in self._legales() if a[0] == "agregar" and a[2] == idx
                and por_id[a[1]].clave == c.clave]
        if not opts:
            return self._avisar(f"{c!r} no calza en esa combinación.")
        act = opts[0]
        if len(opts) > 1:
            x1, _, x2, _ = self.meld_bbox[idx]
            act = next(a for a in opts if a[3] == ("ini" if x < (x1 + x2) / 2 else "fin"))
        self._aplicar(act, c)

    def auto_agregar(self, c):
        por_id = self._por_id()
        for a in self._legales():
            if a[0] == "agregar" and por_id[a[1]].clave == c.clave:
                return self._aplicar(a, c)
        self._avisar(f"{c!r} no calza en ninguna combinación de la mesa.")

    def ordenar(self):
        self.modo_orden = "numero" if self.modo_orden == "palo" else "palo"
        mano = self.env.manos["jugador_0"]
        if self.modo_orden == "palo":
            key = lambda c: (c.es_comodin, c.palo, c.rango)
        else:
            key = lambda c: (c.es_comodin, c.rango, c.palo)
        self.orden = [c.id for c in sorted(mano, key=key)]
        self.dibujar()

    def dar_pista(self):
        if not self.mi_turno():
            return
        obs = self.env.observe("jugador_0")
        idx = PoliticaHeuristica()(obs)
        act = obs["acciones_legales"][idx]
        por_id = {c.id: c for c in obs["mano"]}
        self.pista = act
        if act[0] == "bajar":
            self.plan_idx = self.planes().index(act)
        self.aviso = "\U0001F4A1 El agente sugiere: " + describir(act, por_id, obs["tope_descarte"]).replace(
            "robó", "robar").replace("tomó", "tomar").replace("bajó", "bajar").replace(
            "agregó", "agregar").replace("descartó", "descartar")
        self.dibujar(); self.actualizar_ui()

    def jugar_por_mi(self):
        if not self.mi_turno():
            return
        obs = self.env.observe("jugador_0")
        act = obs["acciones_legales"][PoliticaHeuristica()(obs)]
        self._aplicar(act)

    # ------------------------------------------------------------ eventos del mouse
    def hit_at(self, x, y):
        for h in reversed(self.hits):
            x1, y1, x2, y2 = h[2]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return h
        return None

    def carta_por_id(self, cid):
        return next(c for c in self.obs["mano"] if c.id == cid)

    def on_press(self, e):
        self.arr = self.press = None
        if not self.mi_turno():
            return
        h = self.hit_at(e.x, e.y)
        self.press = h
        if h and h[0] == "mano" and self.env.fase == "jugar":
            x1, y1 = h[2][:2]
            self.arr = {"c": self.carta_por_id(h[1]), "x": e.x, "y": e.y, "dx": e.x - x1,
                        "dy": e.y - y1, "x0": e.x, "y0": e.y, "mov": False}

    def on_motion(self, e):
        a = self.arr
        if not a:
            return
        a["x"], a["y"] = e.x, e.y
        if not a["mov"] and abs(e.x - a["x0"]) + abs(e.y - a["y0"]) > 8:
            a["mov"] = True
            self.sel = None
            self.dibujar()
        elif a["mov"]:
            self._sprite()

    def on_release(self, e):
        if not self.mi_turno():
            self.arr = None
            return
        a, self.arr = self.arr, None
        if a and a["mov"]:
            return self.soltar(a["c"], e.x, e.y)
        self.clic(self.press, e.x)

    def on_double(self, e):
        if not self.mi_turno():
            return
        h = self.hit_at(e.x, e.y)
        self.arr = None
        if h and h[0] == "mano" and self.env.fase == "jugar":
            self.auto_agregar(self.carta_por_id(h[1]))

    def clic(self, h, x):
        self.aviso = ""
        if h is None:
            self.sel = None
            return self.dibujar(), self.actualizar_ui()
        tipo = h[0]
        if tipo == "mazo":
            self.robar("robar_mazo")
        elif tipo == "descarte":
            if self.env.fase == "robar":
                self.robar("robar_descarte")
            elif self.sel is not None:
                self.descartar(self.sel)
            else:
                self._avisar("Selecciona o arrastra una carta para descartarla.")
        elif tipo == "meld":
            if self.sel is not None:
                self.agregar(self.sel, h[1], x)
            else:
                self._avisar("Arrastra una carta de tu mano hasta la combinación.")
        elif tipo == "mano":
            if self.env.fase != "jugar":
                return self._avisar("Primero roba una carta (mazo o descarte).")
            c = self.carta_por_id(h[1])
            self.sel = None if (self.sel and self.sel.id == c.id) else c
            self.dibujar(); self.actualizar_ui()

    def soltar(self, c, x, y):
        self.aviso = ""
        h = self.hit_at(x, y)
        if h and h[0] == "descarte":
            return self.descartar(c)
        if h and h[0] == "meld":
            return self.agregar(c, h[1], x)
        if y >= HAND_Y - 40:                      # reordenar dentro de la mano
            otros = [cid for cid in self.orden if cid != c.id]
            n_izq = sum(1 for cid in otros if self.pos_x.get(cid, 0) + CW / 2 < x)
            otros.insert(n_izq, c.id)
            self.orden = otros
        self.dibujar(); self.actualizar_ui()

    # ------------------------------------------------------------ dibujo
    def _orden_mano(self, mano):
        ids = {c.id: c for c in mano}
        self.orden = [i for i in self.orden if i in ids]
        nuevos = sorted((c for c in mano if c.id not in self.orden),
                        key=lambda c: (c.es_comodin, c.palo, c.rango))
        self.orden += [c.id for c in nuevos]
        return [ids[i] for i in self.orden]

    def _legales_ref(self):
        """(carta de referencia, idx de combinaciones validas, descarte valido)."""
        c = self.arr["c"] if (self.arr and self.arr["mov"]) else self.sel
        if c is None or not self.mi_turno() or self.env.fase != "jugar":
            return None, set(), False
        por_id = self._por_id()
        melds = {a[2] for a in self._legales() if a[0] == "agregar" and por_id[a[1]].clave == c.clave}
        return c, melds, True

    def dibujar(self):
        cv = self.cv
        cv.delete("all")
        self.hits, self.meld_bbox, self.pos_x = [], {}, {}
        self.obs = obs = self.env.observe("jugador_0")
        env, fin = self.env, bool(self.env.resultado)
        mi = self.mi_turno()
        ref, melds_ok, desc_ok = self._legales_ref()
        pista = self.pista if mi else None
        glow_mano, glow_pila, glow_meld = {}, {}, {}
        # --- resaltados
        if mi and env.fase == "jugar" and not pista:
            pl = self.planes()
            if pl:
                for _, ids, _ in pl[self.plan_idx % len(pl)][1]:
                    for i in ids:
                        glow_mano[i] = DORADO
        if pista:
            if pista[0] == "robar_mazo":
                glow_pila["mazo"] = CIAN
            elif pista[0] == "robar_descarte":
                glow_pila["descarte"] = CIAN
            elif pista[0] == "bajar":
                for _, ids, _ in pista[1]:
                    for i in ids:
                        glow_mano[i] = CIAN
            elif pista[0] == "agregar":
                glow_mano[pista[1]] = CIAN; glow_meld[pista[2]] = CIAN
            elif pista[0] == "descartar":
                glow_mano[pista[1]] = CIAN; glow_pila["descarte"] = CIAN
        if mi and env.fase == "robar" and not pista:
            glow_pila["mazo"] = glow_pila["descarte"] = VERDE_OK
        if desc_ok:
            glow_pila["descarte"] = VERDE_OK
        for i in melds_ok:
            glow_meld[i] = VERDE_OK

        # --- rival (arriba, boca abajo)
        n_riv = obs["n_rival"]
        cv.create_text(24, RIVAL_Y + 4, text="RIVAL", anchor="nw", fill="white", font=(FUENTE, 13, "bold"))
        cv.create_text(24, RIVAL_Y + 26, text=f"{n_riv} carta{'s' if n_riv != 1 else ''}", anchor="nw", fill="#cfe9d8", font=(FUENTE, 11))
        if obs["B_rival"]:
            cv.create_text(24, RIVAL_Y + 46, text="✔ contrato bajado", anchor="nw",
                           fill="#9dff9d", font=(FUENTE, 10))
        if n_riv:
            cartas = sorted(env.manos["jugador_1"], key=lambda c: (c.es_comodin, c.palo, c.rango)) if fin else None
            paso = min(28 if fin else 22, (W - 360 - RW) / max(1, n_riv - 1))
            x0 = (W - ((n_riv - 1) * paso + RW)) / 2
            for k in range(n_riv):
                if fin:
                    dibujar_carta(cv, x0 + k * paso, RIVAL_Y, cartas[k], RW, RH)
                else:
                    dibujar_dorso(cv, x0 + k * paso, RIVAL_Y, RW, RH)

        # --- zonas de combinaciones
        for dueno, (zx1, zy1, zx2, zy2) in ZONAS.items():
            rrect(cv, zx1, zy1, zx2, zy2, 12, fill=FIELTRO_OSC, outline=FIELTRO_BORDE)
            cv.create_text(zx1 + 10, zy1 + 6, anchor="nw", fill="#8fd1a9", font=(FUENTE, 9, "bold"),
                           text="MESA DEL RIVAL" if dueno == 1 else "TU MESA")
            lista = [(i, m) for i, m in enumerate(env.mesa) if m.dueno == dueno]
            if not lista:
                continue
            gap, avail = 18, (zx2 - zx1) - 24
            extra = sum(len(m.cartas) - 1 for _, m in lista)
            off = max(10, min(24, (avail - len(lista) * MW - gap * (len(lista) - 1)) / max(1, extra)))
            x = zx1 + 12
            y = zy1 + 30
            for i, m in lista:
                ancho = (len(m.cartas) - 1) * off + MW
                bb = (x, y, x + ancho, y + MH)
                self.meld_bbox[i] = bb
                self.hits.append(("meld", i, bb))
                if i in glow_meld:
                    rrect(cv, x - 6, y - 6, x + ancho + 6, y + MH + 6, 10, fill=glow_meld[i], outline="")
                for k, c in enumerate(m.cartas):
                    rep = None
                    if c.es_comodin:
                        rep = NOMBRE.get(m.rango, m.rango) if m.tipo == "trio" else \
                            NOMBRE.get(_rp(m.pos[k]), _rp(m.pos[k]))
                    dibujar_carta(cv, x + k * off, y, c, MW, MH, rep=rep)
                x += ancho + gap

        # --- pilas
        n_mazo = obs["n_mazo"]
        bb_mazo = (MAZO_X, PILA_Y, MAZO_X + CW, PILA_Y + CH)
        if "mazo" in glow_pila:
            rrect(cv, MAZO_X - 6, PILA_Y - 6, MAZO_X + CW + 6, PILA_Y + CH + 6, 12, fill=glow_pila["mazo"], outline="")
        if n_mazo:
            for k in range(min(3, 1 + n_mazo // 12), -1, -1):      # efecto de pila
                dibujar_dorso(cv, MAZO_X + k, PILA_Y - k, CW, CH)
            self.hits.append(("mazo", None, bb_mazo))
        else:
            rrect(cv, *bb_mazo, 8, fill="", outline="#8fd1a9", dash=(4, 3))
        cv.create_text(MAZO_X + CW / 2, PILA_Y + CH + 14, text=f"Mazo ({n_mazo})", fill="white", font=(FUENTE, 10))
        bb_desc = (DESC_X, PILA_Y, DESC_X + CW, PILA_Y + CH)
        if "descarte" in glow_pila:
            rrect(cv, DESC_X - 6, PILA_Y - 6, DESC_X + CW + 6, PILA_Y + CH + 6, 12, fill=glow_pila["descarte"], outline="")
        tope = obs["tope_descarte"]
        if tope is not None:
            dibujar_carta(cv, DESC_X, PILA_Y, tope, CW, CH)
        else:
            rrect(cv, *bb_desc, 8, fill="", outline="#8fd1a9", dash=(4, 3))
        self.hits.append(("descarte", None, (DESC_X - 18, PILA_Y - 18, DESC_X + CW + 18, PILA_Y + CH + 18)))
        cv.create_text(DESC_X + CW / 2, PILA_Y + CH + 14,
                       text=f"Descarte ({len(obs['descarte_publico']) + (tope is not None)})",
                       fill="white", font=(FUENTE, 10))

        # --- probabilidades (Taller 3)
        if self.var_prob.get() and not fin:
            nv = sum(self.modelo.no_vistas(obs).values())
            lineas = [f"Cartas no vistas: {nv}"]
            if mi and env.fase == "robar" and not obs["B"]:
                lineas.append(f"P(mazo completa contrato): {self.modelo.prob_habilita_bajada(obs):.1%}")
            cv.create_text(24, 276, anchor="nw", fill="#d9f2e2", font=(FUENTE, 10), width=200,
                           text="\n".join(lineas))

        # --- registro de jugadas / banner
        y_log = 362
        if self.log["jugador_1"]:
            cv.create_text(240, y_log, anchor="nw", fill="#ffe9a8", font=(FUENTE, 11, "italic"),
                           width=836, text="Rival " + self.log["jugador_1"])
            y_log += 22
        if self.log["jugador_0"]:
            cv.create_text(240, y_log, anchor="nw", fill="#cfe9d8", font=(FUENTE, 11, "italic"),
                           width=836, text="Agente (tú) " + self.log["jugador_0"])
        if fin:
            self._banner()

        # --- mi mano
        mano = self._orden_mano(list(obs["mano"]))
        n = len(mano)
        cv.create_text(24, HAND_Y - 26, anchor="nw", fill="white", font=(FUENTE, 12, "bold"),
                       text=f"TU MANO ({n} carta{'s' if n != 1 else ''})" + ("   ✔ contrato bajado" if obs["B"] else ""))
        if n:
            paso = min(CW - 12, (W - 100 - CW) / max(1, n - 1))
            x0 = (W - ((n - 1) * paso + CW)) / 2
            arrastrada = self.arr["c"].id if (self.arr and self.arr["mov"]) else None
            for k, c in enumerate(mano):
                x = x0 + k * paso
                self.pos_x[c.id] = x
                if c.id == arrastrada:
                    continue
                y = HAND_Y - (16 if (self.sel and self.sel.id == c.id) else 0)
                dibujar_carta(cv, x, y, c, CW, CH, glow=glow_mano.get(c.id))
                self.hits.append(("mano", c.id, (x, y, x + (paso if k < n - 1 else CW), y + CH)))
        if self.arr and self.arr["mov"]:
            self._sprite()

    def _sprite(self):
        self.cv.delete("drag")
        a = self.arr
        dibujar_carta(self.cv, a["x"] - a["dx"], a["y"] - a["dy"], a["c"], CW, CH, glow="#ffffff", tags=("drag",))

    def _banner(self):
        res = self.env.resultado
        if res["ganador"] == "jugador_0":
            t = f"¡Ganaste la ronda!  El rival se queda con {res['puntos']['jugador_1']} puntos."
        elif res["ganador"] == "jugador_1":
            t = f"El rival cerró la ronda.  Te quedaron {res['puntos']['jugador_0']} puntos."
        else:
            motivo = "Se agotó el mazo" if res["causa"] == "mazo_agotado" else "Límite de turnos"
            t = (f"{motivo}: sin ganador.  Tú {res['puntos']['jugador_0']} pts · "
                 f"Rival {res['puntos']['jugador_1']} pts.")
        rrect(self.cv, 240, 360, 1076, 410, 12, fill="#fff7d6", outline="#c9a227", width=2)
        self.cv.create_text(658, 385, text=t, fill="#4a3600", font=(FUENTE, 13, "bold"))

    # ------------------------------------------------------------ textos de estado
    def actualizar_ui(self):
        env = self.env
        self.lbl_info.config(
            text=f"Ronda {self.ronda}/8 · Contrato: {texto_contrato(env.contrato)} · "
                 f"Puntos → Tú: {self.totales['jugador_0']}  Rival: {self.totales['jugador_1']}")
        pl = self.planes() if self.mi_turno() and env.fase == "jugar" else []
        estado = "normal" if pl else "disabled"
        for b in (self.b_prev, self.b_baj, self.b_next):
            b.config(state=estado)
        self.b_baj.config(text=f"Bajar contrato ({self.plan_idx % len(pl) + 1}/{len(pl)})" if pl else "Bajar contrato")
        if env.resultado:
            msg = "Ronda terminada. Pulsa «Siguiente ronda»."
        elif not self.mi_turno():
            msg = "Turno del rival…" if env.agent_selection == "jugador_1" else "El agente juega por ti…"
        elif env.fase == "robar":
            tope = env.descarte[-1]
            msg = (f"Tu turno: haz clic en el MAZO (carta oculta) o en el DESCARTE ({tope!r}).")
        elif pl:
            por_id = {c.id: c for c in self.obs["mano"]}
            msg = (f"Puedes bajar tu contrato — plan {self.plan_idx % len(pl) + 1}/{len(pl)}: "
                   f"{texto_plan(pl[self.plan_idx % len(pl)][1], por_id)}.  "
                   f"(◀ ▶ cambian de plan). O descarta para terminar el turno.")
        elif not self.obs["B"]:
            msg = f"Todavía no completas el contrato ({texto_contrato(env.contrato)}). Arrastra una carta al DESCARTE para terminar el turno."
        else:
            msg = "Arrastra cartas a una combinación de la mesa para agregarlas, o una al DESCARTE para terminar el turno."
        self.lbl_estado.config(text=(self.aviso + "\n" if self.aviso else "") + msg)


def _rp(pos):
    return 1 if pos in (1, 14) else pos


def main():
    root = tk.Tk()
    CariocaGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()