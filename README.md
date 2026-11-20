# Agente Inteligente para Carioca (Multi-Agent RL & MDP)

Implementación completa de un entorno multiagente por turnos basado en **PettingZoo (`AECEnv`)**, un modelo probabilístico de cartas no vistas, un agente basado en políticas heurísticas y una interfaz gráfica interactiva desarrollada en **Tkinter** para jugar **Carioca** (rummy por contrato de 8 rondas).

Proyecto desarrollado en el marco de la asignatura **TEL351 — Seminario de Telemática I** en la **Universidad Técnica Federico Santa María (UTFSM)**.

---

## Características principales

* **Entorno Multiagente (`CariocaEnv`):** Implementado sobre la API `AECEnv` de PettingZoo con máscara de acciones válidas (`action_mask`), soporte para las 8 rondas oficiales de contratos (tríos y escalas), 2 mazos ingleses + 4 comodines (108 cartas) y sistema de recompensas configurable.
* **Modelo Probabilístico (`ModeloRobo`):** Calcula en tiempo real el conjunto de cartas no vistas ($R_t \cup M_t^{\text{rival}}$) y estima la probabilidad exacta de robar una carta útil del mazo o de completar el contrato en el turno actual: $P(\text{carta robada} \mid R_t)$.
* **Agentes Implementados:**
  * `PoliticaHeuristica`: Política determinista $\pi: S \to A$ basada en 5 reglas estratégicas (explotación de descarte útil, robo exploratorio, bajada prioritaria, vaciado acelerado en mesa sin inmovilizar comodines y descarte seguro de alto puntaje).
  * `PoliticaAleatoria`: Agente baseline que selecciona uniformemente entre las acciones legales disponibles.
* **Interfaz Gráfica (`CariocaGUI`):** Tablero visual en `tkinter` que permite jugar Humano vs. Agente o Agente vs. Agente, arrastrar y soltar cartas, ordenar la mano por pinta o valor, consultar sugerencias de jugada (*Pista*) y visualizar probabilidades en vivo.
* **Motor de Simulación y Evaluación:** Funciones para simular rondas individuales, partidas completas de 8 rondas, torneos comparativos entre políticas y validación empírica de probabilidades mediante Monte Carlo.

---

## Estructura del repositorio

```text
carioca-agente-inteligente/
├── docs/                       # Informes teóricos y de diseño (Talleres 1 al 4)
│   ├── README.md
│   ├── Seminario_Tarea_1.pdf
│   ├── Seminario_Tarea_2.pdf
│   ├── Seminario_Tarea_3.pdf
│   └── Seminario_Tarea_4.pdf
├── carioca_agente.py           # Entorno PettingZoo, reglas, modelo probabilístico y agentes
├── carioca_gui.py              # Interfaz gráfica interactiva en Tkinter
├── requirements.txt            # Dependencias del proyecto
├── LICENSE                     # Licencia MIT
└── README.md
