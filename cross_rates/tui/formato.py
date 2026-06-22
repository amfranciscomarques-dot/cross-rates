"""Formatação de ``Decimal`` para a TUI.

Mantido por compatibilidade: ``fmt`` vive agora em ``cross_rates.servico.formato``
(partilhado com a web). Reexporta-se aqui para não quebrar os imports da TUI.
"""

from cross_rates.servico.formato import fmt

__all__ = ["fmt"]
