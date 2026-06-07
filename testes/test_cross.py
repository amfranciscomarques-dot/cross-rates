"""Testes do núcleo, trancados às resoluções do Caderno de Exercícios nº 1.

Cada caso de cross-rate reproduz um exercício resolvido (Ex. 10, 11, 12, 17),
o que valida simultaneamente a matemática e a convenção bid/ask.
"""

from decimal import Decimal

import pytest

from cross_rates.nucleo import (
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    SemPercurso,
    cross,
)

# tolerância relativa: os valores do caderno estão arredondados a 4–5 casas.
REL = Decimal("0.0001")


def proximo(obtido: Decimal, esperado: str) -> bool:
    alvo = Decimal(esperado)
    return abs(obtido - alvo) <= abs(alvo) * REL


def grafo_de(*cotacoes: tuple[str, str, str, str]) -> GrafoCambial:
    g = GrafoCambial()
    for base, cotada, bid, ask in cotacoes:
        g.adicionar(Cotacao(base, cotada, bid, ask))
    return g


# --------------------------------------------------------------------------- #
# Validação de cotações
# --------------------------------------------------------------------------- #


def test_cotacao_normaliza_e_propriedades():
    c = Cotacao("eur", "usd", "1.0850", "1.0852")
    assert c.par == "EUR/USD"
    assert c.spread == Decimal("0.0002")


def test_cotacao_de_texto_aceita_virgula():
    c = Cotacao.de_texto("EUR USD 1,0850 1,0852")
    assert c.bid == Decimal("1.0850")


@pytest.mark.parametrize(
    "args",
    [
        ("EUR", "EUR", "1", "1.1"),   # mesma moeda
        ("EUR", "USD", "1.10", "1.09"),  # bid > ask
        ("EUR", "USD", "-1", "1"),     # não positivo
        ("EU", "USD", "1", "1.1"),     # código inválido
    ],
)
def test_cotacao_invalida(args):
    with pytest.raises(CotacaoInvalida):
        Cotacao(*args)


# --------------------------------------------------------------------------- #
# Cross-rates vs. caderno
# --------------------------------------------------------------------------- #


def test_ex10_mxn_dkk_via_usd_base_comum():
    # USD/MXN e USD/DKK -> MXN/DKK = 0,37255 – 0,37340 (base comum, direto)
    g = grafo_de(
        ("USD", "MXN", "17.3151", "17.3235"),
        ("USD", "DKK", "6.4540", "6.4656"),
    )
    r = cross(g, "MXN", "DKK")
    assert proximo(r.bid, "0.37255")
    assert proximo(r.ask, "0.37340")
    assert r.percurso == ["MXN", "USD", "DKK"]
    assert "direto" in r.tipo


def test_ex11_gbp_brl_via_usd_indireto():
    # USD/BRL e GBP/USD -> GBP/BRL = 6,9971 – 7,0037 (indireto ×)
    g = grafo_de(
        ("USD", "BRL", "5.2381", "5.2419"),
        ("GBP", "USD", "1.3358", "1.3361"),
    )
    r = cross(g, "GBP", "BRL")
    assert proximo(r.bid, "6.9971")
    assert proximo(r.ask, "7.0037")
    assert "indireto" in r.tipo


def test_ex12_gbp_chf_via_cad_direto():
    # GBP/CAD e CHF/CAD -> GBP/CHF = 1,0620 – 1,0627 (direto ÷, CAD ao incerto)
    g = grafo_de(
        ("GBP", "CAD", "1.8091", "1.8096"),
        ("CHF", "CAD", "1.7029", "1.7035"),
    )
    r = cross(g, "GBP", "CHF")
    assert proximo(r.bid, "1.0620")
    assert proximo(r.ask, "1.0627")
    assert "direto" in r.tipo


def test_ex12_chf_sek_via_cad_indireto():
    # CHF/CAD e CAD/SEK -> CHF/SEK = 11,1538 – 11,1636 (indireto ×)
    g = grafo_de(
        ("CHF", "CAD", "1.7029", "1.7035"),
        ("CAD", "SEK", "6.5499", "6.5533"),
    )
    r = cross(g, "CHF", "SEK")
    assert proximo(r.bid, "11.1538")
    assert proximo(r.ask, "11.1636")
    assert "indireto" in r.tipo


def test_ex17_gbp_eur_implicito_via_jpy():
    # GBP/JPY e EUR/JPY -> GBP/EUR implícito = 1,1579 – 1,1583 (direto ÷)
    g = grafo_de(
        ("GBP", "JPY", "212.646", "212.689"),
        ("EUR", "JPY", "183.618", "183.646"),
    )
    r = cross(g, "GBP", "EUR")
    assert proximo(r.bid, "1.1579")
    assert proximo(r.ask, "1.1583")


def test_formulas_batem_com_o_caderno():
    # Ex. 12 direto (÷) e Ex. 11 indireto (×): fórmulas explícitas com pontas.
    g = grafo_de(
        ("GBP", "CAD", "1.8091", "1.8096"),
        ("CHF", "CAD", "1.7029", "1.7035"),
    )
    r = cross(g, "GBP", "CHF")
    assert r.bid_formula == "bid = bid(GBP/CAD) ÷ ask(CHF/CAD)"
    assert r.ask_formula == "ask = ask(GBP/CAD) ÷ bid(CHF/CAD)"

    g2 = grafo_de(
        ("USD", "BRL", "5.2381", "5.2419"),
        ("GBP", "USD", "1.3358", "1.3361"),
    )
    r2 = cross(g2, "GBP", "BRL")
    assert r2.bid_formula == "bid = bid(GBP/USD) × bid(USD/BRL)"
    assert r2.ask_formula == "ask = ask(GBP/USD) × ask(USD/BRL)"


def test_classifica_inversa():
    g = grafo_de(("EUR", "USD", "1.0850", "1.0852"))
    assert cross(g, "USD", "EUR").tipo == "inversa"


def test_cotacao_direta_passa_intacta():
    g = grafo_de(("EUR", "USD", "1.0850", "1.0852"))
    r = cross(g, "EUR", "USD")
    assert r.bid == Decimal("1.0850")
    assert r.ask == Decimal("1.0852")
    assert r.tipo == "direta"


def test_inverso_da_direta():
    # USD/EUR derivado de EUR/USD: bid = 1/ask, ask = 1/bid
    g = grafo_de(("EUR", "USD", "1.0850", "1.0852"))
    r = cross(g, "USD", "EUR")
    assert proximo(r.bid, str(1 / Decimal("1.0852")))
    assert proximo(r.ask, str(1 / Decimal("1.0850")))


def test_sem_percurso_entre_moedas_desligadas():
    g = grafo_de(
        ("EUR", "USD", "1.08", "1.09"),
        ("GBP", "JPY", "190", "191"),
    )
    with pytest.raises(SemPercurso):
        cross(g, "EUR", "JPY")
