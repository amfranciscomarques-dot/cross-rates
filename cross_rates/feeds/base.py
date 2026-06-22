"""Contrato dos feeds de cotações: o protocolo ``FonteCotacoes`` e os erros.

Um *feed* é qualquer fonte que devolva cotações já no formato do núcleo
(:class:`cross_rates.nucleo.Cotacao`). A web/TUI dependem apenas deste
protocolo — não da implementação concreta —, pelo que trocar um feed ao vivo
por uma fixture estática (ver :mod:`cross_rates.feeds.simulado`) não toca no
resto da aplicação.
"""

from __future__ import annotations

from typing import Protocol

from cross_rates.nucleo import Cotacao


class FeedError(RuntimeError):
    """Erro genérico de um feed de cotações."""


class FeedIndisponivel(FeedError):
    """O feed não conseguiu obter ou interpretar as cotações.

    Cobre falhas de rede, respostas mal formadas e dados que não produzem uma
    cotação válida. A camada web trata isto como uma degradação graciosa
    (abre a tabela vazia) em vez de devolver um erro 500.
    """


class FonteCotacoes(Protocol):
    """Fonte de cotações cambiais (feed ao vivo, fixture, ficheiro, etc.)."""

    def cotacoes(self) -> list[Cotacao]:
        """Devolve as cotações atuais; levanta :class:`FeedError` em falha."""
        ...
