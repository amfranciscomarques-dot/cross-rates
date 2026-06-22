"""Camada de serviço (aplicação) da calculadora de cross-rates.

Faz a ponte entre o input do utilizador (texto livre) e o núcleo puro
(``cross_rates.nucleo``), de forma **agnóstica à interface**: estas funções
não dependem de Textual nem de FastAPI, por isso são partilhadas pela TUI e
pela web. O parsing e a orquestração vivem aqui (e não em cada frontend),
evitando duplicar lógica.

* ``operacoes`` — parse + orquestração (devolvem objetos do núcleo).
* ``serial``    — view-model: resultado do núcleo → dict serializável (JSON-safe).
* ``formato``   — formatação de ``Decimal`` para apresentação.
* ``exemplos``  — conjuntos de cotações de arranque rápido (do caderno).
"""

from .exemplos import (
    EXEMPLO_FORWARD_INPUT,
    EXEMPLO_OPCAO_INPUT,
    EXEMPLOS_ARBITRAGEM,
    EXEMPLOS_CROSS,
    EXEMPLOS_FORWARD_SPOT,
    EXEMPLOS_GEOGRAFICA,
    EXEMPLOS_OPCAO_SPOT,
)
from .formato import fmt
from .operacoes import (
    adicionar_cotacao,
    analisar_arbitragem,
    calcular_cross,
    calcular_forward,
    calcular_hedge,
    calcular_opcao,
    calcular_swap,
    parse_montante,
    spot_para,
)
from .serial import para_dict

__all__ = [
    "fmt",
    "adicionar_cotacao",
    "analisar_arbitragem",
    "calcular_cross",
    "calcular_forward",
    "calcular_hedge",
    "calcular_opcao",
    "calcular_swap",
    "parse_montante",
    "spot_para",
    "para_dict",
    "EXEMPLOS_CROSS",
    "EXEMPLOS_ARBITRAGEM",
    "EXEMPLOS_GEOGRAFICA",
    "EXEMPLOS_FORWARD_SPOT",
    "EXEMPLO_FORWARD_INPUT",
    "EXEMPLOS_OPCAO_SPOT",
    "EXEMPLO_OPCAO_INPUT",
]
