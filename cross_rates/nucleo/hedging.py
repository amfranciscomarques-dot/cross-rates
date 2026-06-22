"""Estratégias de Cobertura de Risco Cambial (Hedging).

Compara alternativas para cobrir uma exposição cambial futura (recebimento
ou pagamento em moeda estrangeira):
1. Cobertura a prazo (Forward Hedge)
2. Cobertura no mercado monetário (Money Market Hedge)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .cotacao import Cotacao, CotacaoInvalida, Numerico, para_decimal
from .forward import TaxaJuro, forward
from .opcoes import OpcaoVanilla, TipoOpcao, garman_kohlhagen

CEM = Decimal(100)


@dataclass(frozen=True)
class AnaliseHedging:
    """Comparação entre Forward Hedge e Money Market Hedge para uma exposição."""

    tipo_exposicao: str  # "recebimento" ou "pagamento"
    moeda_estrangeira: str
    moeda_base: str
    montante_me: Decimal
    dias: int

    # Forward Hedge
    fwd_taxa: Decimal
    fwd_resultado_base: Decimal

    # Money Market Hedge (MMH)
    mmh_me_presente: Decimal
    mmh_spot_taxa: Decimal
    mmh_base_presente: Decimal
    mmh_taxa_juro_base: Decimal
    mmh_resultado_base: Decimal

    # Cobertura com opção (terceira estratégia, opcional). É contingente — fixa
    # apenas o custo máximo / a receita mínima (mantendo o lado favorável), pelo
    # que não entra na escolha de `melhor_estrategia` (esta fica entre Forward e
    # MMH). Avaliada a mid (o preço GK é, ele próprio, um conceito de mid).
    opcao_tipo: str | None = None  # "call" (recebimento) / "put" (pagamento)
    opcao_strike: Decimal | None = None
    opcao_notional: Decimal | None = None  # em BASE (= montante_me / strike)
    opcao_premio_cotada: Decimal | None = None  # prémio hoje, em COTADA
    opcao_premio_base: Decimal | None = None  # prémio capitalizado até t, em BASE
    opcao_resultado_base: Decimal | None = None  # custo máx. / receita mín., em BASE

    @property
    def melhor_estrategia(self) -> str:
        if self.tipo_exposicao == "recebimento":
            # Queremos maximizar a receita na moeda base
            if self.fwd_resultado_base > self.mmh_resultado_base:
                return "Forward Hedge"
            elif self.mmh_resultado_base > self.fwd_resultado_base:
                return "Money Market Hedge"
            return "Indiferente"
        else:
            # Queremos minimizar o custo na moeda base
            if self.fwd_resultado_base < self.mmh_resultado_base:
                return "Forward Hedge"
            elif self.mmh_resultado_base < self.fwd_resultado_base:
                return "Money Market Hedge"
            return "Indiferente"


def analisa_hedging(
    tipo: str,  # "recebimento" ou "pagamento"
    montante_estrangeira: Numerico,
    spot: Cotacao,
    juro_base: TaxaJuro,
    juro_estrangeira: TaxaJuro,
    dias: int,
    opcao_strike: Numerico | None = None,
    vol: Numerico | None = None,
) -> AnaliseHedging:
    """Analisa a melhor estratégia de cobertura.

    A ``moeda_base`` (nacional) e a ``moeda_estrangeira`` são inferidas do ``spot``.
    Assume-se que a moeda estrangeira é a COTADA (ao incerto) e a base é a BASE (ao certo).
    Para Portugal (onde o EUR é quase sempre a base), se a dívida for em USD,
    o spot deve ser EUR/USD.

    Se ``opcao_strike`` e ``vol`` forem dados, acrescenta-se uma terceira
    estratégia — a **cobertura com opção** (Garman-Kohlhagen): um pagamento
    compra uma *put* sobre a base e um recebimento uma *call*, fixando o custo
    máximo / a receita mínima e mantendo o lado favorável. Por ser contingente,
    não entra na escolha de ``melhor_estrategia``.
    """
    if tipo not in ("recebimento", "pagamento"):
        raise CotacaoInvalida("Tipo de exposição deve ser 'recebimento' ou 'pagamento'.")

    montante_me = para_decimal(montante_estrangeira)
    if montante_me <= 0:
        raise CotacaoInvalida("O montante deve ser positivo.")

    # PTJ de equilíbrio para ver o forward outright
    fwd_eq = forward(spot, juro_base, juro_estrangeira, dias)

    if tipo == "recebimento":
        # Recebimento de ME (a moeda cotada) em t = dias.
        #
        # Forward hedge: o cliente vende a ME a prazo, i.e. compra a base a prazo.
        # O banco vende a base ao ask, logo o cliente liquida ao F_ask: a receita
        # na moeda base é montante_ME / F_ask.
        fwd_taxa = fwd_eq.ask
        fwd_resultado = montante_me / fwd_taxa

        # Money market hedge (replica o forward via MMI):
        #   1. Pede ME emprestada hoje à taxa i_ask(ME), de modo a que o
        #      recebimento futuro amortize exatamente o empréstimo:
        #      PV_ME = montante_ME / (1 + i_ask(ME)·t).
        mmh_me_presente = montante_me / juro_estrangeira.fator("ask", dias)
        #   2. Vende a ME à vista (compra base) ao S_ask.
        mmh_spot_taxa = spot.ask
        mmh_base_presente = mmh_me_presente / mmh_spot_taxa
        #   3. Aplica a base até t à taxa i_bid(base).
        mmh_taxa_juro_base = juro_base.bid
        mmh_resultado = mmh_base_presente * juro_base.fator("bid", dias)

    else:
        # Pagamento de ME (a moeda cotada) em t = dias.
        #
        # Forward hedge: o cliente compra a ME a prazo, i.e. vende a base a prazo.
        # O banco compra a base ao bid, logo o cliente liquida ao F_bid: o custo
        # na moeda base é montante_ME / F_bid.
        fwd_taxa = fwd_eq.bid
        fwd_resultado = montante_me / fwd_taxa

        # Money market hedge (replica o forward via MMI):
        #   1. Aplica hoje o valor presente da ME à taxa i_bid(ME), de modo a
        #      que cresça até ao montante a pagar:
        #      PV_ME = montante_ME / (1 + i_bid(ME)·t).
        mmh_me_presente = montante_me / juro_estrangeira.fator("bid", dias)
        #   2. Compra a ME à vista (vende base) ao S_bid.
        mmh_spot_taxa = spot.bid
        mmh_base_presente = mmh_me_presente / mmh_spot_taxa
        #   3. Financia-se na base até t à taxa i_ask(base).
        mmh_taxa_juro_base = juro_base.ask
        mmh_resultado = mmh_base_presente * juro_base.fator("ask", dias)

    op = _cobertura_opcao(
        tipo, montante_me, spot, juro_base, juro_estrangeira, dias, opcao_strike, vol
    )

    return AnaliseHedging(
        tipo_exposicao=tipo,
        moeda_estrangeira=spot.cotada,
        moeda_base=spot.base,
        montante_me=montante_me,
        dias=dias,
        fwd_taxa=fwd_taxa,
        fwd_resultado_base=fwd_resultado,
        mmh_me_presente=mmh_me_presente,
        mmh_spot_taxa=mmh_spot_taxa,
        mmh_base_presente=mmh_base_presente,
        mmh_taxa_juro_base=mmh_taxa_juro_base,
        mmh_resultado_base=mmh_resultado,
        opcao_tipo=op[0],
        opcao_strike=op[1],
        opcao_notional=op[2],
        opcao_premio_cotada=op[3],
        opcao_premio_base=op[4],
        opcao_resultado_base=op[5],
    )


_SemOpcao = tuple[None, None, None, None, None, None]
_ComOpcao = tuple[str, Decimal, Decimal, Decimal, Decimal, Decimal]


def _cobertura_opcao(
    tipo: str,
    montante_me: Decimal,
    spot: Cotacao,
    juro_base: TaxaJuro,
    juro_estrangeira: TaxaJuro,
    dias: int,
    opcao_strike: Numerico | None,
    vol: Numerico | None,
) -> _SemOpcao | _ComOpcao:
    """Cobertura com opção (GK): custo máximo (pagamento) / receita mínima (recebimento).

    Pagamento → *put* sobre a base; recebimento → *call* sobre a base. Dimensiona
    o notional em ``montante_me / strike`` BASE, de modo que o exercício converta
    exatamente ``montante_me`` da cotada. O prémio (em COTADA) é convertido a mid
    e capitalizado até ``t`` à taxa-base mid. Devolve tuplo de ``None`` se não há
    opção; senão ``(tipo, strike, notional, prémio_cotada, prémio_base, resultado)``.
    """
    if opcao_strike is None or vol is None:
        return None, None, None, None, None, None
    strike = para_decimal(opcao_strike)
    if strike <= 0:
        raise CotacaoInvalida("O strike da opção tem de ser positivo.")

    tipo_op = TipoOpcao.PUT if tipo == "pagamento" else TipoOpcao.CALL
    notional = montante_me / strike  # em BASE
    opcao = OpcaoVanilla(tipo_op, spot.base, spot.cotada, strike, dias, notional)
    gk = garman_kohlhagen(opcao, spot, vol, juro_base, juro_estrangeira)

    # Prémio: COTADA hoje → BASE a mid → capitalizado até t à taxa-base mid.
    premio_base_hoje = gk.preco_total / gk.spot
    ano = juro_base.convencao.dias_no_ano()
    fator_base_mid = Decimal(1) + (juro_base.media / CEM) * Decimal(dias) / ano
    premio_base_t = premio_base_hoje * fator_base_mid

    # Exercício: entrega/recebe `notional` BASE (= montante_me / strike).
    if tipo == "pagamento":
        resultado = notional + premio_base_t  # custo máximo coberto
    else:
        resultado = notional - premio_base_t  # receita mínima garantida
    return tipo_op.value, strike, notional, gk.preco_total, premio_base_t, resultado
