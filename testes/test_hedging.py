"""Testes do hedging cambial (Forward Hedge vs Money Market Hedge).

Reproduzem a contas a mecânica das duas estratégias de cobertura de uma
exposição cambial futura (pagamento ou recebimento em moeda estrangeira),
validando:

1. que cada perna do Money Market Hedge (MMH) usa a ponta bid/ask correta do
   spot e das taxas de juro;
2. a igualdade teórica MMH ≈ Forward Hedge (em mercado sem fricção as duas
   estratégias replicam-se — é o próprio conteúdo económico da PTJ/CIP);
3. a regra de decisão (minimizar custo / maximizar receita na moeda base).

Enquadramento: Madura, *International Financial Management*, e Shapiro,
*Multinational Financial Management* (money market hedge).
"""

from decimal import Decimal, getcontext

import pytest

from cross_rates.nucleo import (
    AnaliseHedging,
    Cotacao,
    CotacaoInvalida,
    TaxaJuro,
    analisa_hedging,
    forward,
)

getcontext().prec = 28
REL = Decimal("0.0001")  # tolerância relativa (4 casas)


def proximo(obtido: Decimal, esperado: str) -> bool:
    alvo = Decimal(esperado)
    return abs(obtido - alvo) <= abs(alvo) * REL


@pytest.fixture
def eur_usd_90d():
    """Exposição clássica: EUR (base) / USD (cotada estrangeira), 90 dias."""
    spot = Cotacao("EUR", "USD", "1.0850", "1.0852")
    juro_base = TaxaJuro("EUR", "2.0", "2.1")  # EUR
    juro_me = TaxaJuro("USD", "4.2", "4.3")  # USD (a estrangeira/cotada)
    return spot, juro_base, juro_me


# --------------------------------------------------------------------------- #
# Hedging de PAGAMENTO em moeda estrangeira
# --------------------------------------------------------------------------- #


def test_pagamento_per_leg_bid_ask(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("pagamento", 1_000_000, spot, juro_base, juro_me, 90)

    # Forward hedge: compra a ME a prazo liquidando ao F_bid (vende base ao bid).
    f = forward(spot, juro_base, juro_me, 90)
    assert r.fwd_taxa == f.bid
    assert r.fwd_resultado_base == Decimal("1000000") / f.bid

    # MMH passo-a-passo (validação à mão, Madura):
    #  1. Aplica hoje o PV da ME a i_bid(USD): cresce até ao montante a pagar.
    pv_usd = Decimal("1000000") / juro_me.fator("bid", 90)
    assert r.mmh_me_presente == pv_usd
    #  2. Compra a ME à vista ao S_bid (vende base).
    assert r.mmh_spot_taxa == spot.bid
    assert r.mmh_base_presente == pv_usd / spot.bid
    #  3. Financia-se na base a i_ask(EUR) até ao vencimento.
    assert r.mmh_taxa_juro_base == juro_base.ask
    assert r.mmh_resultado_base == r.mmh_base_presente * juro_base.fator("ask", 90)


def test_pagamento_valor_manual(eur_usd_90d):
    # Empresa europeia deve USD 1.000.000 daqui a 90 dias.
    # PV_USD = 1e6 / (1 + 0,042·90/360) = 989.609,1044...
    # Base hoje = PV_USD / 1,0850 = 912.082,1239 EUR
    # Custo futuro = 912.082,1239 · (1 + 0,021·90/360) = 916.870,5550 EUR
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("pagamento", 1_000_000, spot, juro_base, juro_me, 90)
    assert proximo(r.mmh_resultado_base, "916870.5550")
    assert proximo(r.fwd_resultado_base, "916870.5550")  # ≈ MMH


def test_pagamento_minimiza_custo(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("pagamento", 1_000_000, spot, juro_base, juro_me, 90)
    # Para um pagamento escolhe-se a estratégia com MENOR custo na base.
    if r.fwd_resultado_base < r.mmh_resultado_base:
        esperado = "Forward Hedge"
    else:
        esperado = "Money Market Hedge"
    assert r.melhor_estrategia == esperado
    assert r.melhor_estrategia in ("Forward Hedge", "Money Market Hedge")


# --------------------------------------------------------------------------- #
# Hedging de RECEBIMENTO em moeda estrangeira
# --------------------------------------------------------------------------- #


def test_recebimento_per_leg_bid_ask(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("recebimento", 1_000_000, spot, juro_base, juro_me, 90)

    # Forward hedge: vende a ME a prazo liquidando ao F_ask (compra base ao ask).
    f = forward(spot, juro_base, juro_me, 90)
    assert r.fwd_taxa == f.ask
    assert r.fwd_resultado_base == Decimal("1000000") / f.ask

    # MMH passo-a-passo:
    #  1. Pede ME emprestada hoje a i_ask(USD) — o recebimento futuro amortiza-a.
    pv_usd = Decimal("1000000") / juro_me.fator("ask", 90)
    assert r.mmh_me_presente == pv_usd
    #  2. Vende a ME à vista ao S_ask (compra base).
    assert r.mmh_spot_taxa == spot.ask
    assert r.mmh_base_presente == pv_usd / spot.ask
    #  3. Aplica a base a i_bid(EUR) até ao vencimento.
    assert r.mmh_taxa_juro_base == juro_base.bid
    assert r.mmh_resultado_base == r.mmh_base_presente * juro_base.fator("bid", 90)


def test_recebimento_valor_manual(eur_usd_90d):
    # Empresa europeia vai receber USD 1.000.000 daqui a 90 dias.
    # PV_USD = 1e6 / (1 + 0,043·90/360) = 989.364,3334...
    # Base hoje = PV_USD / 1,0852 = 911.688,4753 EUR
    # Receita futura = 911.688,4753 · (1 + 0,020·90/360) = 916.246,9177 EUR
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("recebimento", 1_000_000, spot, juro_base, juro_me, 90)
    assert proximo(r.mmh_resultado_base, "916246.9177")
    assert proximo(r.fwd_resultado_base, "916246.9177")  # ≈ MMH


def test_recebimento_maximiza_receita(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("recebimento", 1_000_000, spot, juro_base, juro_me, 90)
    # Para um recebimento escolhe-se a estratégia com MAIOR receita na base.
    if r.mmh_resultado_base > r.fwd_resultado_base:
        assert r.melhor_estrategia == "Money Market Hedge"
    elif r.fwd_resultado_base > r.mmh_resultado_base:
        assert r.melhor_estrategia == "Forward Hedge"
    else:
        assert r.melhor_estrategia == "Indiferente"


# --------------------------------------------------------------------------- #
# Propriedade teórica central: MMH replica o Forward (CIP)
# --------------------------------------------------------------------------- #


def test_mmh_replica_forward_sem_spread():
    # Com spot e juros sem spread (bid=ask), MMH e Forward são matematicamente
    # idênticos — é o conteúdo económico da Paridade das Taxas de Juro coberta.
    spot = Cotacao("EUR", "USD", "1.1000", "1.1000")
    jb = TaxaJuro("EUR", "3.0", "3.0")
    ju = TaxaJuro("USD", "5.0", "5.0")

    for tipo in ("pagamento", "recebimento"):
        r = analisa_hedging(tipo, 1_000_000, spot, jb, ju, 180)
        assert r.fwd_resultado_base == r.mmh_resultado_base
        assert r.melhor_estrategia == "Indiferente"


def test_diferenca_mmh_forward_e_da_sempre_a_melhor(eur_usd_90d):
    # A regra de decisão garante que a "melhor estratégia" é sempre a que
    # domina, qualquer que seja a exposição.
    spot, juro_base, juro_me = eur_usd_90d
    for tipo in ("pagamento", "recebimento"):
        r: AnaliseHedging = analisa_hedging(tipo, 1_000_000, spot, juro_base, juro_me, 90)
        if r.melhor_estrategia == "Forward Hedge":
            if tipo == "pagamento":
                assert r.fwd_resultado_base <= r.mmh_resultado_base
            else:
                assert r.fwd_resultado_base >= r.mmh_resultado_base
        elif r.melhor_estrategia == "Money Market Hedge":
            if tipo == "pagamento":
                assert r.mmh_resultado_base <= r.fwd_resultado_base
            else:
                assert r.mmh_resultado_base >= r.fwd_resultado_base


# --------------------------------------------------------------------------- #
# Inferência de moedas e validação de entrada
# --------------------------------------------------------------------------- #


def test_moedas_inferidas_do_spot(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    r = analisa_hedging("pagamento", 500_000, spot, juro_base, juro_me, 30)
    # A moeda estrangeira (a cotada) é o USD; a base (nacional) é o EUR.
    assert r.moeda_estrangeira == "USD"
    assert r.moeda_base == "EUR"


def test_tipo_exposicao_invalido(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    with pytest.raises(CotacaoInvalida):
        analisa_hedging("investimento", 1_000_000, spot, juro_base, juro_me, 90)


def test_montante_nao_positivo(eur_usd_90d):
    spot, juro_base, juro_me = eur_usd_90d
    with pytest.raises(CotacaoInvalida):
        analisa_hedging("pagamento", 0, spot, juro_base, juro_me, 90)
    with pytest.raises(CotacaoInvalida):
        analisa_hedging("recebimento", -100, spot, juro_base, juro_me, 90)


def test_aceita_entrada_numerica(eur_usd_90d):
    # Montante como int e str devem convergir para o mesmo resultado.
    spot, juro_base, juro_me = eur_usd_90d
    r_int = analisa_hedging("pagamento", 1000000, spot, juro_base, juro_me, 90)
    r_str = analisa_hedging("pagamento", "1000000", spot, juro_base, juro_me, 90)
    assert r_int.fwd_resultado_base == r_str.fwd_resultado_base
