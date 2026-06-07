"""Núcleo puro do cálculo cambial (sem dependências de interface).

Totalmente testável de forma isolada. A TUI (e, mais tarde, motores de
arbitragem e feeds de preços em tempo real) assentam sobre estas classes.
"""

from .arbitragem import Arbitragem, Passo, arbitragens_triangulares
from .cotacao import Cotacao, CotacaoInvalida, normaliza_moeda
from .cross import ResultadoCross, cross
from .grafo import GrafoCambial, SemPercurso

__all__ = [
    "Cotacao",
    "CotacaoInvalida",
    "normaliza_moeda",
    "GrafoCambial",
    "SemPercurso",
    "ResultadoCross",
    "cross",
    "Arbitragem",
    "Passo",
    "arbitragens_triangulares",
]
