"""Formatação de ``Decimal`` para apresentação (partilhada por TUI e web)."""

from __future__ import annotations

from decimal import Decimal


def fmt(valor: Decimal, casas: int | None = None) -> str:
    """Formata um ``Decimal``; com ``casas`` arredonda, senão remove zeros supérfluos."""
    if casas is not None:
        cota = Decimal(1).scaleb(-casas)
        return f"{valor.quantize(cota)}"
    return f"{valor.normalize():f}"
