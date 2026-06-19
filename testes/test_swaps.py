"""Testes dos swaps cambiais (pontos forward → outright).

Cobrem a regra prémio/desconto, a escala dos pontos, JPY (2 casas), a
conservação do spread bid/ask e a coerência entre a cotação outright via swap
e a paridade das taxas de juro coberta (PTJ/CIP). Os valores provêm de
exemplos clássicos de manuais de Finanças Internacionais.
"""

from decimal import Decimal

import pytest

from cross_rates.nucleo import (
    Cotacao,
    CotacaoInvalida,
    TaxaJuro,
    forward,
    outright_de_pontos,
)

REL = Decimal("0.0001")  # tolerância relativa (4 casas)


def proximo(obtido: Decimal, esperado: str) -> bool:
    alvo = Decimal(esperado)
    return abs(obtido - alvo) <= abs(alvo) * REL


# --------------------------------------------------------------------------- #
# Regra prémio / desconto (soma/subtrai os pontos ao spot)
# --------------------------------------------------------------------------- #


def test_outright_premio():
    # Spot 1,1500–1,1510; pontos 20–30 (bid<ask → base a prémio, soma-se).
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "20", "30")

    assert sw.sinal == "prémio"
    assert sw.fwd_bid == Decimal("1.1520")
    assert sw.fwd_ask == Decimal("1.1540")


def test_outright_desconto():
    # Spot 1,1500–1,1510; pontos 30–20 (bid>ask → base a desconto, subtrai-se).
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "30", "20")

    assert sw.sinal == "desconto"
    assert sw.fwd_bid == Decimal("1.1470")
    assert sw.fwd_ask == Decimal("1.1490")


def test_outright_neutro_quando_pontos_iguais():
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "25", "25")
    assert sw.sinal == "neutro"
    assert sw.fwd_bid == Decimal("1.1500")
    assert sw.fwd_ask == Decimal("1.1510")


# --------------------------------------------------------------------------- #
# Escala dos pontos / convenção por moeda (JPY a 2 casas)
# --------------------------------------------------------------------------- #


def test_outright_casas_diferentes():
    # USD/JPY (2 casas); pontos 15–20 sobre escala 100 → 0,15–0,20.
    spot = Cotacao("USD", "JPY", "140.50", "140.60")
    sw = outright_de_pontos(spot, "15", "20", casas_decimais_pontos=2)

    assert sw.sinal == "prémio"
    assert sw.fwd_bid == Decimal("140.65")
    assert sw.fwd_ask == Decimal("140.80")


def test_pontos_escala_padrao_e_4_casas():
    # 4 casas (escala 10⁴): "20"/"30" valem 0,0020/0,0030 — igual ao padrão.
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "20", "30", casas_decimais_pontos=4)
    assert sw.fwd_bid == Decimal("1.1520")
    assert sw.fwd_ask == Decimal("1.1540")


def test_pontos_jpy_escala_centena():
    # USD/JPY: mercado costuma cotar pontos sobre 100 (2 casas).
    # 145,00 spot; pontos 50/70 → 0,50/0,70 → 145,50/145,70.
    spot = Cotacao("USD", "JPY", "145.00", "145.05")
    sw = outright_de_pontos(spot, "50", "70", casas_decimais_pontos=2)
    assert sw.fwd_bid == Decimal("145.50")
    assert sw.fwd_ask == Decimal("145.75")


# --------------------------------------------------------------------------- #
# Propriedades do spread e consistência bid/ask
# --------------------------------------------------------------------------- #


def test_spread_outright_igual_spot_mais_spread_pontos():
    # Num outright a prémio, o spread forward = spread spot + spread pontos.
    # Spot 1,1500/1,1510 (spread 0,0010); pontos 0,0020/0,0030 (spread 0,0010)
    # → outright 1,1520/1,1540 (spread 0,0020).
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "20", "30")
    escala = Decimal(10) ** sw.casas_decimais_pontos
    spread_pontos = (sw.pontos_ask - sw.pontos_bid) / escala
    assert sw.fwd_ask - sw.fwd_bid == Decimal("0.0020")
    assert sw.fwd_ask - sw.fwd_bid == spot.spread + spread_pontos


def test_sinal_preserva_sempre_bid_le_ask():
    # Propriedade: a regra de deteção prémio/desconto (derivada da própria
    # ordenação dos pontos) garante, por construção, que o outright nunca
    # inverte bid/ask, quaisquer que sejam os pontos positivos fornecidos.
    spot = Cotacao("USD", "JPY", "140.50", "140.55")
    for pb, pa in [("10", "5"), ("5", "10"), ("100", "1"), ("1", "100"), ("50", "70")]:
        sw = outright_de_pontos(spot, pb, pa, casas_decimais_pontos=2)
        assert sw.fwd_bid <= sw.fwd_ask, f"{pb}/{pa} inverteu bid/ask"


# --------------------------------------------------------------------------- #
# Validação de entrada
# --------------------------------------------------------------------------- #


def test_pontos_invalidos():
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    with pytest.raises(CotacaoInvalida):
        outright_de_pontos(spot, "-20", "30")


def test_pontos_aceitam_numericos():
    # A entrada tolera int, float, str (alias Numerico).
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, 20, 30)
    assert sw.fwd_bid == Decimal("1.1520")
    assert sw.pontos_bid == Decimal("20")


# --------------------------------------------------------------------------- #
# Coerência com PTJ: pontos de swap do forward de equilíbrio
# --------------------------------------------------------------------------- #


def test_pontos_de_swap_coerem_com_forward_equilibrio():
    # Os pontos do outright (via swap) têm de reproduzir o forward de PTJ.
    # EUR/USD 180d; i_EUR 2,3652–2,3705; i_USD 4,2379–4,2438.
    spot = Cotacao("EUR", "USD", "1.1745", "1.1745")
    r = forward(
        spot,
        TaxaJuro("EUR", "2.3652", "2.3705"),
        TaxaJuro("USD", "4.2379", "4.2438"),
        180,
    )
    # F_bid de equilíbrio ≈ 1,1853 (cf. test_forward.py).
    assert proximo(r.bid, "1.1853")

    # Reconstruir o outright a partir dos pontos implícitos (F − S).
    p_bid = r.bid - spot.bid  # pontos na escala da cotação
    p_ask = r.ask - spot.ask
    escala = Decimal(10) ** 4
    sw = outright_de_pontos(
        spot,
        p_bid * escala,
        p_ask * escala,
        casas_decimais_pontos=4,
    )
    assert proximo(sw.fwd_bid, str(r.bid))
    assert proximo(sw.fwd_ask, str(r.ask))


def test_sinal_swap_igual_sinal_ptj():
    # i_USD > i_EUR → EUR (base) a prémio tanto no outright como no PTJ.
    spot = Cotacao("EUR", "USD", "1.1745", "1.1745")
    r = forward(
        spot,
        TaxaJuro("EUR", "2.3652", "2.3705"),
        TaxaJuro("USD", "4.2379", "4.2438"),
        180,
    )
    p_bid = (r.bid - spot.bid) * Decimal(10) ** 4
    p_ask = (r.ask - spot.ask) * Decimal(10) ** 4
    sw = outright_de_pontos(spot, p_bid, p_ask, casas_decimais_pontos=4)
    assert sw.sinal == r.sinal == "prémio"
