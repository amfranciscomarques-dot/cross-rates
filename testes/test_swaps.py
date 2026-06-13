import pytest
from decimal import Decimal

from cross_rates.nucleo.cotacao import Cotacao, CotacaoInvalida
from cross_rates.nucleo.swaps import outright_de_pontos


def test_outright_premio():
    # Spot: 1.1500 - 1.1510
    # Pontos: 20 - 30 (prémio, soma-se)
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "20", "30")
    
    assert sw.sinal == "prémio"
    assert sw.fwd_bid == Decimal("1.1520")
    assert sw.fwd_ask == Decimal("1.1540")


def test_outright_desconto():
    # Spot: 1.1500 - 1.1510
    # Pontos: 30 - 20 (desconto, subtrai-se)
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    sw = outright_de_pontos(spot, "30", "20")
    
    assert sw.sinal == "desconto"
    assert sw.fwd_bid == Decimal("1.1470")
    assert sw.fwd_ask == Decimal("1.1490")


def test_outright_casas_diferentes():
    # Spot: 140.50 - 140.60 (2 casas decimais)
    # Pontos: 15 - 20
    spot = Cotacao("USD", "JPY", "140.50", "140.60")
    sw = outright_de_pontos(spot, "15", "20", casas_decimais_pontos=2)
    
    assert sw.sinal == "prémio"
    assert sw.fwd_bid == Decimal("140.65")
    assert sw.fwd_ask == Decimal("140.80")

def test_pontos_invalidos():
    spot = Cotacao("EUR", "USD", "1.1500", "1.1510")
    with pytest.raises(CotacaoInvalida):
        outright_de_pontos(spot, "-20", "30")
