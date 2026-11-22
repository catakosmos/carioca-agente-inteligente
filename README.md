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
- **Motor de Simulación y Evaluación (`experimentos.py`):** Ejecución reproducible por semillas de rondas pareadas en condiciones $C_A$ y $C_B$, registro por episodio en CSV y cálculo de métricas ($\text{TE}$ con IC95 % de Wilson, puntaje retenido $P$, turnos, recompensa acumulada $G_H$ y tasa de recolección $\rho$).

---

## Estructura del repositorio

```text
carioca-agente-inteligente/
├── docs/                       # Informes teóricos y de diseño (Talleres 1 al 5)
│   ├── README.md
│   ├── Seminario_Tarea_1.pdf
│   ├── Seminario_Tarea_2.pdf
│   ├── Seminario_Tarea_3.pdf
│   ├── Seminario_Tarea_4.pdf
│   └── Seminario_Tarea_5.pdf
├── base_A.csv                  # Resultados medidos del agente base en C_A (n = 500)
├── base_B.csv                  # Resultados medidos del agente base en C_B (n = 500)
├── carioca_agente.py           # Entorno PettingZoo, reglas, modelo probabilístico y agentes
├── carioca_gui.py              # Interfaz gráfica interactiva en Tkinter
├── experimentos.py             # Evaluación experimental del agente base (Taller 5)
├── requirements.txt            # Dependencias del proyecto
├── LICENSE                     # Licencia MIT
└── README.md
