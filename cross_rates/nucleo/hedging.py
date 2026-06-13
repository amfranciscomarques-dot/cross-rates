"""Estratégias de Cobertura de Risco Cambial (Hedging).

Compara alternativas para cobrir uma exposição cambial futura (recebimento
ou pagamento em moeda estrangeira):
1. Cobertura a prazo (Forward Hedge)
2. Cobertura no mercado monetário (Money Market Hedge)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .cotacao import Cotacao, CotacaoInvalida, _para_decimal
from .forward import TaxaJuro, forward, ResultadoForward


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
    montante_estrangeira,
    spot: Cotacao,
    juro_base: TaxaJuro,
    juro_estrangeira: TaxaJuro,
    dias: int,
) -> AnaliseHedging:
    """Analisa a melhor estratégia de cobertura.

    A ``moeda_base`` (nacional) e a ``moeda_estrangeira`` são inferidas do ``spot``.
    Assume-se que a moeda estrangeira é a COTADA (ao incerto) e a base é a BASE (ao certo).
    Para Portugal (onde o EUR é quase sempre a base), se a dívida for em USD,
    o spot deve ser EUR/USD.
    """
    if tipo not in ("recebimento", "pagamento"):
        raise CotacaoInvalida("Tipo de exposição deve ser 'recebimento' ou 'pagamento'.")
    
    montante_me = _para_decimal(montante_estrangeira)
    if montante_me <= 0:
        raise CotacaoInvalida("O montante deve ser positivo.")

    # PTJ de equilíbrio para ver o forward outright
    fwd_eq = forward(spot, juro_base, juro_estrangeira, dias)

    if tipo == "recebimento":
        # Recebimento em ME (Cotada).
        # Forward: cliente vende a ME a prazo. Para cotada, cliente vende ao F_bid (porque ele compra base).
        # A taxa aplicável para transformar Cotada em Base é 1 / F_ask.
        # Espera, o cliente RECEBE Cotada, logo ele tem de VENDER Cotada e COMPRAR Base.
        # Banco Vende Base ao ask, logo Cliente Compra Base ao ask.
        # Quantidade de Base = Montante_ME / F_ask
        fwd_taxa = fwd_eq.ask
        fwd_resultado = montante_me / fwd_taxa

        # MMH:
        # Pede emprestado ME hoje, vende no spot, aplica Base hoje.
        # 1. Pede emprestado ME: taxa i_ask_ME
        # Quanto pedir para que com juros dê igual ao Montante_ME a receber?
        mmh_me_presente = montante_me / juro_estrangeira.fator("ask", dias)
        
        # 2. Vende ME no spot (Compra Base): taxa S_ask
        mmh_spot_taxa = spot.ask
        mmh_base_presente = mmh_me_presente / mmh_spot_taxa

        # 3. Aplica Base: taxa i_bid_Base
        mmh_taxa_juro_base = juro_base.bid
        mmh_resultado = mmh_base_presente * juro_base.fator("bid", dias)

    else:
        # Pagamento em ME (Cotada).
        # Forward: cliente precisa de ME a prazo. Vai COMPRAR ME e VENDER Base.
        # Banco Compra Base ao bid, logo Cliente Vende Base ao bid.
        # Quantidade de Base = Montante_ME / F_bid
        fwd_taxa = fwd_eq.bid
        fwd_resultado = montante_me / fwd_taxa

        # MMH:
        # Toma emprestado Base hoje, compra ME no spot, aplica ME hoje.
        # 1. Aplica ME para que no futuro seja igual ao Montante_ME: taxa i_bid_ME
        mmh_me_presente = montante_me / juro_estrangeira.fator("bid", dias)
        
        # 2. Compra ME no spot (Vende Base): taxa S_bid
        mmh_spot_taxa = spot.bid
        mmh_base_presente = mmh_me_presente / mmh_spot_taxa

        # 3. Pede emprestado Base: taxa i_ask_Base
        mmh_taxa_juro_base = juro_base.ask
        mmh_resultado = mmh_base_presente * juro_base.fator("ask", dias)

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
    )
