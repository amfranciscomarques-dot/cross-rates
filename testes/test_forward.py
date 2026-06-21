"""Testes dos forwards (PTJ) e da arbitragem a prazo, trancados ao caderno.

Reproduzem exercícios resolvidos (Ex. 21b, 22b, 23, 27, 28), validando em
simultâneo a fórmula PTJ, a convenção bid/ask e a deteção de arbitragem a prazo.
"""

from decimal import Decimal

import pytest

from cross_rates.nucleo import (
    Cotacao,
    CotacaoInvalida,
    TaxaJuro,
    arbitragem_a_prazo,
    forward,
)

REL = Decimal("0.0001")  # caderno arredonda a 4 casas


def proximo(obtido: Decimal, esperado: str) -> bool:
    alvo = Decimal(esperado)
    return abs(obtido - alvo) <= abs(alvo) * REL


# --------------------------------------------------------------------------- #
# Forward de equilíbrio (PTJ)
# --------------------------------------------------------------------------- #


def test_ex21_22_forward_gbp_eur_120d():
    # Spot GBP/EUR 1,1488–1,1491; i_GBP 4,2006–4,2012; i_EUR 2,4592–2,4634; 120d.
    spot = Cotacao("GBP", "EUR", "1.1488", "1.1491")
    r = forward(spot, TaxaJuro("GBP", "4.2006", "4.2012"),
                TaxaJuro("EUR", "2.4592", "2.4634"), 120)
    assert proximo(r.bid, "1.1422")  # Ex. 21b: F_bid de equilíbrio
    assert proximo(r.ask, "1.1425")  # Ex. 22b: F_ask de equilíbrio
    assert r.sinal == "desconto"     # i_GBP > i_EUR → base GBP a desconto


def test_ex23a_eur_usd_6m_fbid():
    # EUR/USD 6m; i_USD 4,2379–4,2438; i_EUR 2,3652–2,3705; F_bid = 1,1853.
    spot = Cotacao("EUR", "USD", "1.1745", "1.1745")
    r = forward(spot, TaxaJuro("EUR", "2.3652", "2.3705"),
                TaxaJuro("USD", "4.2379", "4.2438"), 180)
    assert proximo(r.bid, "1.1853")


def test_ex23d_usd_nzd_3m_fbid():
    # USD/NZD 3m; i_NZD 3,4975–3,5117; i_USD 4,1282–4,1344; F_bid = 1,6778.
    spot = Cotacao("USD", "NZD", "1.6804", "1.6804")
    r = forward(spot, TaxaJuro("USD", "4.1282", "4.1344"),
                TaxaJuro("NZD", "3.4975", "3.5117"), 90)
    assert proximo(r.bid, "1.6778")


def test_ex27a_chf_usd_equilibrio():
    # CHF/USD 180d; equilíbrio 1,3052–1,3056.
    spot = Cotacao("CHF", "USD", "1.2745", "1.2748")
    r = forward(spot, TaxaJuro("CHF", "0.1072", "0.1144"),
                TaxaJuro("USD", "4.9379", "4.9438"), 180)
    assert proximo(r.bid, "1.3052")
    assert proximo(r.ask, "1.3056")
    assert r.sinal == "prémio"  # i_USD > i_CHF → base CHF a prémio


def test_ex28a_eur_usd_equilibrio():
    # EUR/USD 120d; equilíbrio 1,1753–1,1756.
    spot = Cotacao("EUR", "USD", "1.1656", "1.1658")
    r = forward(spot, TaxaJuro("EUR", "2.2845", "2.2895"),
                TaxaJuro("USD", "4.8082", "4.8245"), 120)
    assert proximo(r.bid, "1.1753")
    # A própria fórmula do caderno dá 1,1756; o documento imprime 1,1754 (lapso
    # de arredondamento — o spread dos juros não comporta forquilha tão estreita).
    assert proximo(r.ask, "1.1756")


def test_pontos_forward_sinal():
    # GBP a desconto → pontos forward negativos (F < S).
    spot = Cotacao("GBP", "EUR", "1.1488", "1.1491")
    r = forward(spot, TaxaJuro("GBP", "4.2006", "4.2012"),
                TaxaJuro("EUR", "2.4592", "2.4634"), 120)
    assert r.pontos_bid < 0
    assert r.pontos_ask < 0


# --------------------------------------------------------------------------- #
# Validação
# --------------------------------------------------------------------------- #


def test_taxa_juro_invalida():
    with pytest.raises(CotacaoInvalida):
        TaxaJuro("EUR", "5", "4")  # i_bid > i_ask
    with pytest.raises(CotacaoInvalida):
        TaxaJuro("EUR", "-1", "1")  # negativa


def test_forward_moeda_incoerente():
    spot = Cotacao("GBP", "EUR", "1.1488", "1.1491")
    with pytest.raises(CotacaoInvalida):
        forward(spot, TaxaJuro("USD", "4", "4.1"),
                TaxaJuro("EUR", "2", "2.1"), 120)


def test_taxa_juro_de_texto():
    t = TaxaJuro.de_texto("GBP 4,2006 4,2012")
    assert t.moeda == "GBP" and t.bid == Decimal("4.2006")


# --------------------------------------------------------------------------- #
# Arbitragem a prazo (covered interest arbitrage)
# --------------------------------------------------------------------------- #


def test_ex27c_arbitragem_vender_chf_forward():
    # Mercado CHF/USD 1,3076–1,3079 > equilíbrio 1,3052–1,3056 → vender base.
    spot = Cotacao("CHF", "USD", "1.2745", "1.2748")
    arb = arbitragem_a_prazo(spot, TaxaJuro("CHF", "0.1072", "0.1144"),
                             TaxaJuro("USD", "4.9379", "4.9438"), 180,
                             "1.3076", "1.3079")
    assert arb is not None
    assert arb.sentido.startswith("vender")
    # Lucro = (mercado_bid − F_ask de equilíbrio) × montante. O sintético de
    # cobertura é o próprio F_ask de equilíbrio (≈1,3056), pelo que o ganho por
    # CHF é ≈ 0,001988 → ≈ +1988 USD por 1M CHF, dentro do arredondamento do
    # caderno (1991).
    assert abs(arb.lucro(1_000_000) - Decimal("1988")) < Decimal("3")


def test_ex28b_arbitragem_comprar_eur_forward():
    # Mercado EUR/USD 1,1736–1,1739 < equilíbrio 1,1753–1,1754 → comprar base.
    spot = Cotacao("EUR", "USD", "1.1656", "1.1658")
    arb = arbitragem_a_prazo(spot, TaxaJuro("EUR", "2.2845", "2.2895"),
                             TaxaJuro("USD", "4.8082", "4.8245"), 120,
                             "1.1736", "1.1739")
    assert arb is not None
    assert arb.sentido.startswith("comprar")
    base = Decimal("3000000") / arb.mercado_ask  # 3M USD investidos
    assert abs(arb.lucro(base) - Decimal("3605")) < Decimal("10")  # caderno: +3605


def test_sem_arbitragem_quando_mercado_no_equilibrio():
    spot = Cotacao("CHF", "USD", "1.2745", "1.2748")
    juro_chf = TaxaJuro("CHF", "0.1072", "0.1144")
    juro_usd = TaxaJuro("USD", "4.9379", "4.9438")
    eq = forward(spot, juro_chf, juro_usd, 180)
    # Forward de mercado = equilíbrio → sem oportunidade.
    assert arbitragem_a_prazo(spot, juro_chf, juro_usd, 180, eq.bid, eq.ask) is None
