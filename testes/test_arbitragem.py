"""Testes da deteção de arbitragem triangular, trancados ao caderno (Ex. 17/18)."""

from decimal import Decimal

from cross_rates.nucleo import Cotacao, GrafoCambial, arbitragens_triangulares


def grafo_de(*cotacoes):
    g = GrafoCambial()
    for base, cotada, bid, ask in cotacoes:
        g.adicionar(Cotacao(base, cotada, bid, ask))
    return g


def test_ex17_arbitragem_triangular_existe():
    # GBP/JPY, EUR/JPY, GBP/EUR -> ciclo EUR->GBP->JPY->EUR, +3917 € em 2,5M.
    g = grafo_de(
        ("GBP", "JPY", "212.646", "212.689"),
        ("EUR", "JPY", "183.618", "183.646"),
        ("GBP", "EUR", "1.1559", "1.1561"),
    )
    ops = arbitragens_triangulares(g)
    assert len(ops) == 1
    arb = ops[0]
    assert set(arb.ciclo) == {"EUR", "GBP", "JPY"}
    assert arb.fator > 1
    lucro = arb.lucro(2_500_000)
    assert abs(lucro - Decimal("3917")) < Decimal("20")  # caderno: +3917 €


def test_ex17c_sem_arbitragem_quando_sobrepoe():
    # Alínea c): GBP/JPY mais baixo -> intervalos sobrepoem-se -> sem arbitragem.
    g = grafo_de(
        ("GBP", "JPY", "212.308", "212.3255"),
        ("EUR", "JPY", "183.618", "183.646"),
        ("GBP", "EUR", "1.1559", "1.1561"),
    )
    assert arbitragens_triangulares(g) == []


def test_ex18_arbitragem_via_cad():
    # CAD/CHF, GBP/CAD, GBP/CHF -> ciclo CAD->CHF->GBP->CAD, +20248 CAD em 6M.
    g = grafo_de(
        ("CAD", "CHF", "0.5675", "0.5677"),
        ("GBP", "CAD", "1.8722", "1.8728"),
        ("GBP", "CHF", "1.0586", "1.0589"),
    )
    ops = arbitragens_triangulares(g)
    assert len(ops) == 1
    arb = ops[0]
    lucro = arb.lucro(6_000_000)
    assert abs(lucro - Decimal("20248")) < Decimal("60")  # caderno: +20248 CAD


def test_limiar_filtra_ganhos_pequenos():
    g = grafo_de(
        ("GBP", "JPY", "212.646", "212.689"),
        ("EUR", "JPY", "183.618", "183.646"),
        ("GBP", "EUR", "1.1559", "1.1561"),
    )
    # ganho ~0,157%; um limiar de 1% deve filtrá-lo.
    assert arbitragens_triangulares(g, limiar=Decimal("0.01")) == []


def test_simulacao_perna_a_perna():
    g = grafo_de(
        ("GBP", "JPY", "212.646", "212.689"),
        ("EUR", "JPY", "183.618", "183.646"),
        ("GBP", "EUR", "1.1559", "1.1561"),
    )
    arb = arbitragens_triangulares(g)[0]
    sim = arb.simulacao(2_500_000)
    assert sim[0] == (arb.ciclo[0], Decimal("2500000"))
    assert sim[-1][0] == arb.ciclo[-1]  # fecha na moeda inicial
    assert sim[-1][1] > sim[0][1]  # termina com mais do que partiu
