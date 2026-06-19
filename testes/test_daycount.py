"""Testes das convenções de contagem de dias (Act/360, Act/365).

O forward de equilíbrio (PTJ) prorateia as taxas de juro anuais pelo prazo.
A base do ano é propriedade da moeda: USD/EUR/JPY/CHF usam Act/360 (Eurobasis);
GBP/AUD/NZD usam Act/365 (Sterling basis). A escolher errada introduz um erro
sistemático no forward — daí estes testes existirem.
"""

from decimal import Decimal

from cross_rates.nucleo import (
    ConvencaoDia,
    Cotacao,
    TaxaJuro,
    convencao_por_omissao_moeda,
    forward,
)

REL = Decimal("0.0001")


def proximo(obtido: Decimal, esperado: str) -> bool:
    alvo = Decimal(esperado)
    return abs(obtido - alvo) <= abs(alvo) * REL


# --------------------------------------------------------------------------- #
# ConvencaoDia: valores e mapeamento por moeda
# --------------------------------------------------------------------------- #


def test_dias_no_ano():
    assert ConvencaoDia.ACT_360.dias_no_ano() == Decimal(360)
    assert ConvencaoDia.ACT_365.dias_no_ano() == Decimal(365)


def test_convencao_por_omissao():
    # GBP, AUD, NZD → Act/365 (Sterling basis); as restantes → Act/360.
    assert convencao_por_omissao_moeda("GBP") is ConvencaoDia.ACT_365
    assert convencao_por_omissao_moeda("AUD") is ConvencaoDia.ACT_365
    assert convencao_por_omissao_moeda("NZD") is ConvencaoDia.ACT_365
    for moeda in ("USD", "EUR", "JPY", "CHF", "CAD", "SEK"):
        assert convencao_por_omissao_moeda(moeda) is ConvencaoDia.ACT_360


def test_convencao_por_omissao_case_insensitive():
    assert convencao_por_omissao_moeda("gbp") is ConvencaoDia.ACT_365
    assert convencao_por_omissao_moeda("usd") is ConvencaoDia.ACT_360


def test_de_texto_infere_convencao_da_moeda():
    # "GBP 4.2 4.3" deve inferir Act/365; "USD ..." Act/360.
    assert TaxaJuro.de_texto("GBP 4.2 4.3").convencao is ConvencaoDia.ACT_365
    assert TaxaJuro.de_texto("USD 4.2 4.3").convencao is ConvencaoDia.ACT_360


def test_de_texto_convencao_explicita_sobrescreve():
    # Override explícito ganha à inferência.
    t = TaxaJuro.de_texto("GBP 4.2 4.3", convencao=ConvencaoDia.ACT_360)
    assert t.convencao is ConvencaoDia.ACT_360


# --------------------------------------------------------------------------- #
# Fator de capitalização
# --------------------------------------------------------------------------- #


def test_fator_act_360():
    # 5% a.a., 90 dias, Act/360 → 1 + 0,05·90/360 = 1,0125.
    t = TaxaJuro("USD", "5", "5", convencao=ConvencaoDia.ACT_360)
    assert t.fator("bid", 90) == Decimal("1.0125")


def test_fator_act_365():
    # 5% a.a., 365 dias, Act/365 → 1,05 (exatamente um ano).
    t = TaxaJuro("GBP", "5", "5", convencao=ConvencaoDia.ACT_365)
    assert t.fator("bid", 365) == Decimal("1.05")


def test_fator_act_360_vs_act_365_diverge():
    # Mesmo prazo/taxa, convenções diferentes → fatores diferentes.
    # Act/360 capitaliza mais por dia (base menor).
    t360 = TaxaJuro("XXX", "5", "5", convencao=ConvencaoDia.ACT_360)
    t365 = TaxaJuro("XXX", "5", "5", convencao=ConvencaoDia.ACT_365)
    n = 90
    assert t360.fator("bid", n) > t365.fator("bid", n)
    # E o valor de Act/360 bate o cálculo explícito.
    assert t360.fator("bid", n) == Decimal(1) + Decimal("0.05") * Decimal(n) / Decimal(360)
    assert t365.fator("bid", n) == Decimal(1) + Decimal("0.05") * Decimal(n) / Decimal(365)


def test_default_e_act_360():
    # Default do dataclass = Act/360 (preserva cálculos históricos do caderno).
    t = TaxaJuro("USD", "4.2", "4.3")
    assert t.convencao is ConvencaoDia.ACT_360


# --------------------------------------------------------------------------- #
# Impacto no forward de equilíbrio
# --------------------------------------------------------------------------- #


def test_forward_muda_com_a_convencao_da_cotada():
    # Mesmo spot/mesmas taxas, mudar a convenção da cotada altera o forward.
    spot = Cotacao("EUR", "GBP", "0.8500", "0.8500")
    jb = TaxaJuro("EUR", "2", "2", convencao=ConvencaoDia.ACT_360)
    jc_365 = TaxaJuro("GBP", "5", "5", convencao=ConvencaoDia.ACT_365)  # correto p/ GBP
    jc_360 = TaxaJuro("GBP", "5", "5", convencao=ConvencaoDia.ACT_360)  # errado p/ GBP

    f_correto = forward(spot, jb, jc_365, 180)
    f_errado = forward(spot, jb, jc_360, 180)
    assert f_correto.bid != f_errado.bid
    # Como i_GBP > i_EUR, base EUR a prémio; ambas > spot.
    assert f_correto.bid > spot.bid and f_errado.bid > spot.bid


def test_forward_formula_exibe_base_correta():
    # A fórmula exibida deve refletir a convenção real de cada moeda.
    spot = Cotacao("EUR", "GBP", "0.8500", "0.8500")
    jb = TaxaJuro("EUR", "2", "2", convencao=ConvencaoDia.ACT_360)
    jc = TaxaJuro("GBP", "5", "5", convencao=ConvencaoDia.ACT_365)
    f = forward(spot, jb, jc, 180)
    assert "180/365" in f.bid_formula  # cotada GBP a Act/365
    assert "180/360" in f.bid_formula  # base EUR a Act/360


def test_forward_act365_valor_manual():
    # EUR/GBP, 180 dias, spot 0,8500, i_EUR 2%, i_GBP 5% (ambas mid).
    # F = 0,85 × (1 + 0,05·180/365) / (1 + 0,02·180/360)
    spot = Cotacao("EUR", "GBP", "0.8500", "0.8500")
    jb = TaxaJuro("EUR", "2", "2", convencao=ConvencaoDia.ACT_360)
    jc = TaxaJuro("GBP", "5", "5", convencao=ConvencaoDia.ACT_365)
    f = forward(spot, jb, jc, 180)
    esperado = (
        Decimal("0.8500")
        * (Decimal(1) + Decimal("0.05") * Decimal(180) / Decimal(365))
        / (Decimal(1) + Decimal("0.02") * Decimal(180) / Decimal(360))
    )
    assert proximo(f.bid, str(esperado))
