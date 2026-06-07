"""Taxas a prazo (forward) por Paridade das Taxas de Juro coberta (PTJ/CIP).

Enquadramento (caderno, Ex. 21–29): a taxa forward de equilíbrio não é uma
previsão da cotação futura, mas a taxa que **impede a arbitragem** entre fazer o
forward direto e replicá-lo no Mercado Monetário Internacional (MMI). Para o par
``A/B`` (A = base, ao certo; B = cotada, ao incerto), com prazo de ``n`` dias na
base ``n/360``::

    F = S × (1 + i_B · n/360) / (1 + i_A · n/360)

A moeda B (cotada, ao incerto) vai no **numerador**; a moeda A (base, ao certo)
no **denominador**. Se ``i_B > i_A`` então ``F > S`` (a base cotiza-se a prémio);
se ``i_B < i_A`` então ``F < S`` (a base a desconto).

Com bid/ask, cada ponta combina as pernas que desfavorecem o cliente na réplica
MMI::

    F_bid = S_bid × (1 + i_bid_B · n/360) / (1 + i_ask_A · n/360)
    F_ask = S_ask × (1 + i_ask_B · n/360) / (1 + i_bid_A · n/360)

A **arbitragem a prazo** (covered interest arbitrage) explora o desalinhamento
entre o forward cotado no mercado e este forward de equilíbrio.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .cotacao import Cotacao, CotacaoInvalida, _para_decimal, normaliza_moeda

CEM = Decimal(100)
BASE_ANO = Decimal(360)


@dataclass(frozen=True)
class TaxaJuro:
    """Taxa de juro anual de uma moeda no MMI, com bid/ask (em %, base 360).

    ``bid`` e ``ask`` exprimem-se em **percentagem anual** (ex.: ``Decimal("4.2")``
    para 4,2%). O ``bid`` é a taxa a que o banco se financia / aplica do lado
    favorável; mantém-se a convenção ``bid <= ask``.
    """

    moeda: str
    bid: Decimal
    ask: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "moeda", normaliza_moeda(self.moeda))
        object.__setattr__(self, "bid", _para_decimal(self.bid))
        object.__setattr__(self, "ask", _para_decimal(self.ask))
        if self.bid < 0 or self.ask < 0:
            raise CotacaoInvalida("As taxas de juro não podem ser negativas.")
        if self.bid > self.ask:
            raise CotacaoInvalida(
                f"i_bid ({self.bid}) não pode ser superior a i_ask ({self.ask})."
            )

    @property
    def media(self) -> Decimal:
        return (self.bid + self.ask) / Decimal(2)

    def fator(self, ponta: str, dias: int) -> Decimal:
        """Fator de capitalização ``1 + i · n/360`` para a ponta indicada."""
        taxa = self.bid if ponta == "bid" else self.ask
        return Decimal(1) + (taxa / CEM) * Decimal(dias) / BASE_ANO

    @classmethod
    def de_texto(cls, texto: str) -> "TaxaJuro":
        """Cria a partir de ``"GBP 4.2006 4.2012"`` (moeda, i_bid, i_ask em %)."""
        partes = texto.replace(",", ".").split()
        if len(partes) != 3:
            raise CotacaoInvalida(
                "Formato esperado: MOEDA i_bid i_ask (ex.: GBP 4.2006 4.2012)."
            )
        return cls(partes[0], partes[1], partes[2])


@dataclass(frozen=True)
class ResultadoForward:
    """Taxa forward bid/ask (PTJ) com fórmulas, pontos e prémio/desconto."""

    base: str
    cotada: str
    dias: int
    spot_bid: Decimal
    spot_ask: Decimal
    bid: Decimal
    ask: Decimal
    bid_formula: str
    ask_formula: str
    sinal: str  # "prémio" / "desconto" / "neutro" (referente à base)
    nota: str

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def pontos_bid(self) -> Decimal:
        """Pontos forward do bid (F_bid − S_bid)."""
        return self.bid - self.spot_bid

    @property
    def pontos_ask(self) -> Decimal:
        return self.ask - self.spot_ask


def _valida_moedas(spot: Cotacao, juro_base: TaxaJuro, juro_cotada: TaxaJuro) -> None:
    if juro_base.moeda != spot.base:
        raise CotacaoInvalida(
            f"A taxa de juro da base ({juro_base.moeda}) não corresponde à base "
            f"do spot ({spot.base})."
        )
    if juro_cotada.moeda != spot.cotada:
        raise CotacaoInvalida(
            f"A taxa de juro da cotada ({juro_cotada.moeda}) não corresponde à "
            f"cotada do spot ({spot.cotada})."
        )


def forward(
    spot: Cotacao, juro_base: TaxaJuro, juro_cotada: TaxaJuro, dias: int
) -> ResultadoForward:
    """Taxa forward de equilíbrio (PTJ) do par ``spot``, a ``dias`` dias.

    ``juro_base`` é a taxa da moeda-base (ao certo) e ``juro_cotada`` a da
    cotada (ao incerto). O prazo do forward e o das taxas de juro coincidem.
    """
    if dias <= 0:
        raise CotacaoInvalida("O prazo (dias) tem de ser positivo.")
    _valida_moedas(spot, juro_base, juro_cotada)

    # F_bid usa i_bid da cotada (B) e i_ask da base (A); F_ask troca as pontas.
    bid = spot.bid * juro_cotada.fator("bid", dias) / juro_base.fator("ask", dias)
    ask = spot.ask * juro_cotada.fator("ask", dias) / juro_base.fator("bid", dias)

    sinal = _sinal(juro_base, juro_cotada)
    bid_formula = (
        f"F_bid = {spot.bid} × (1 + i_bid({spot.cotada})·{dias}/360) "
        f"÷ (1 + i_ask({spot.base})·{dias}/360)"
    )
    ask_formula = (
        f"F_ask = {spot.ask} × (1 + i_ask({spot.cotada})·{dias}/360) "
        f"÷ (1 + i_bid({spot.base})·{dias}/360)"
    )
    return ResultadoForward(
        spot.base,
        spot.cotada,
        dias,
        spot.bid,
        spot.ask,
        bid,
        ask,
        bid_formula,
        ask_formula,
        sinal,
        _nota(spot, sinal),
    )


def _sinal(juro_base: TaxaJuro, juro_cotada: TaxaJuro) -> str:
    """Prémio/desconto da base: i_cotada > i_base → prémio; i_cotada < i_base → desconto."""
    if juro_cotada.media > juro_base.media:
        return "prémio"
    if juro_cotada.media < juro_base.media:
        return "desconto"
    return "neutro"


def _nota(spot: Cotacao, sinal: str) -> str:
    principio = (
        "PTJ: o forward é a taxa que anula a arbitragem entre o forward direto e "
        "a réplica via MMI (não é uma previsão)."
    )
    if sinal == "prémio":
        return (
            f"i({spot.cotada}) > i({spot.base}) → F > S: a base {spot.base} cotiza-se "
            f"a [b]prémio[/b] (vale mais {spot.cotada} a prazo). {principio}"
        )
    if sinal == "desconto":
        return (
            f"i({spot.cotada}) < i({spot.base}) → F < S: a base {spot.base} cotiza-se "
            f"a [b]desconto[/b] (vale menos {spot.cotada} a prazo). {principio}"
        )
    return f"Juros iguais → F ≈ S (sem prémio nem desconto). {principio}"


# --------------------------------------------------------------------------- #
# Arbitragem a prazo (covered interest arbitrage)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ArbitragemPrazo:
    """Oportunidade de arbitragem a prazo: forward de mercado ≠ equilíbrio.

    Se o forward de mercado está **acima** do equilíbrio, a base está
    sobrevalorizada a prazo → vende-se a base forward (cara) e compra-se
    sinteticamente via MMI. Se está **abaixo**, faz-se o inverso. O ganho
    realiza-se na moeda cotada.
    """

    base: str
    cotada: str
    dias: int
    sentido: str  # "vender base forward" / "comprar base forward"
    equilibrio_bid: Decimal
    equilibrio_ask: Decimal
    mercado_bid: Decimal
    mercado_ask: Decimal
    taxa_mercado: Decimal  # ponta do forward de mercado que se negoceia
    sintetico: Decimal  # custo/valor por 1 base, replicado via MMI (em cotada)
    ganho_por_base: Decimal  # ganho por 1 unidade da base (em cotada)

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"

    @property
    def ganho_pct(self) -> Decimal:
        return self.ganho_por_base / self.sintetico * CEM

    def lucro(self, montante_base) -> Decimal:
        """Lucro (em moeda cotada) ao arbitrar ``montante_base`` da base."""
        return Decimal(str(montante_base)) * self.ganho_por_base


def arbitragem_a_prazo(
    spot: Cotacao,
    juro_base: TaxaJuro,
    juro_cotada: TaxaJuro,
    dias: int,
    mercado_bid,
    mercado_ask,
    limiar: Decimal = Decimal("0"),
) -> ArbitragemPrazo | None:
    """Deteta arbitragem entre o forward de mercado e o de equilíbrio (PTJ).

    Devolve ``None`` se os intervalos se sobrepõem (preços consistentes) ou se o
    ganho por unidade de base não excede ``limiar``.
    """
    eq = forward(spot, juro_base, juro_cotada, dias)
    mb, ma = _para_decimal(mercado_bid), _para_decimal(mercado_ask)
    if mb > ma:
        raise CotacaoInvalida("O forward de mercado tem bid > ask.")

    fb_base_ask = juro_base.fator("ask", dias)
    if mb > eq.ask:
        # Mercado acima do equilíbrio → base sobrevalorizada → vender base forward.
        # Réplica: aplica base (i_ask), compra base no spot (ask), financia em
        # cotada (i_ask). Custo sintético por 1 base entregue ao vencimento:
        sintetico = spot.ask * juro_cotada.fator("ask", dias) / fb_base_ask
        ganho = mb - sintetico
        sentido = "vender base forward (base sobrevalorizada a prazo)"
        taxa = mb
    elif ma < eq.bid:
        # Mercado abaixo do equilíbrio → base subvalorizada → comprar base forward.
        # Réplica: pede base emprestada (i_ask), vende no spot (bid), aplica a
        # cotada (i_bid). Valor sintético por 1 base produzida ao vencimento:
        sintetico = spot.bid * juro_cotada.fator("bid", dias) / fb_base_ask
        ganho = sintetico - ma
        sentido = "comprar base forward (base subvalorizada a prazo)"
        taxa = ma
    else:
        return None

    if ganho <= limiar:
        return None
    return ArbitragemPrazo(
        spot.base,
        spot.cotada,
        dias,
        sentido,
        eq.bid,
        eq.ask,
        mb,
        ma,
        taxa,
        sintetico,
        ganho,
    )
