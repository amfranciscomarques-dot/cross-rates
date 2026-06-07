"""Cotação cambial de um par BASE/COTADA, com bid e ask.

Convenção (igual à do caderno de Finanças Internacionais):
na notação ``BASE/COTADA`` a moeda **BASE** está *ao certo* e a **COTADA**
*ao incerto* — o preço diz quantas unidades de COTADA valem 1 unidade de BASE.
O par mostra-se como ``bid – ask`` com ``bid <= ask``.

    | Quem               | Compra a base | Vende a base |
    | ------------------ | ------------- | ------------ |
    | Banco/market maker | ao bid        | ao ask       |
    | Cliente            | ao ask        | ao bid       |
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class CotacaoInvalida(ValueError):
    """Erro de validação de uma cotação cambial."""


def normaliza_moeda(codigo: str) -> str:
    """Devolve o código ISO em maiúsculas, validando o formato (3 letras)."""
    c = codigo.strip().upper()
    if len(c) != 3 or not c.isalpha():
        raise CotacaoInvalida(
            f"Código de moeda inválido: {codigo!r} (esperam-se 3 letras, ex.: EUR)."
        )
    return c


def _para_decimal(valor) -> Decimal:
    try:
        # passar por str evita o ruído binário do float (1.0852 != 1.0852000001).
        return Decimal(str(valor))
    except (InvalidOperation, ValueError) as exc:
        raise CotacaoInvalida(f"Valor numérico inválido: {valor!r}.") from exc


@dataclass(frozen=True)
class Cotacao:
    """Cotação de um par BASE/COTADA com bid e ask."""

    base: str
    cotada: str
    bid: Decimal
    ask: Decimal

    def __post_init__(self) -> None:
        # dataclass frozen: usa-se object.__setattr__ para normalizar os campos.
        object.__setattr__(self, "base", normaliza_moeda(self.base))
        object.__setattr__(self, "cotada", normaliza_moeda(self.cotada))
        object.__setattr__(self, "bid", _para_decimal(self.bid))
        object.__setattr__(self, "ask", _para_decimal(self.ask))

        if self.base == self.cotada:
            raise CotacaoInvalida("A base e a cotada não podem ser a mesma moeda.")
        if self.bid <= 0 or self.ask <= 0:
            raise CotacaoInvalida("bid e ask têm de ser positivos.")
        if self.bid > self.ask:
            raise CotacaoInvalida(
                f"bid ({self.bid}) não pode ser superior ao ask ({self.ask})."
            )

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"

    @property
    def spread(self) -> Decimal:
        """Spread = ask - bid."""
        return self.ask - self.bid

    @classmethod
    def de_texto(cls, texto: str) -> "Cotacao":
        """Cria uma cotação a partir de ``"EUR USD 1.0850 1.0852"``."""
        partes = texto.replace(",", ".").split()
        if len(partes) != 4:
            raise CotacaoInvalida(
                "Formato esperado: BASE COTADA bid ask (ex.: EUR USD 1.0850 1.0852)."
            )
        base, cotada, bid, ask = partes
        return cls(base=base, cotada=cotada, bid=bid, ask=ask)

    def __str__(self) -> str:
        return f"{self.par} = {self.bid} – {self.ask}"
