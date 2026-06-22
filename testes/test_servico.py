"""Testes da camada de serviço (parsing + orquestração + view-model).

Garantem a **paridade** entre o que o utilizador escreve em texto livre e o que
o núcleo calcula, e que o view-model (``para_dict``) produz dicts JSON-safe
(só ``str``/``list``/``dict``, nunca ``Decimal``) com os mesmos números da TUI.
Reproduzem exercícios do caderno, tal como os testes do núcleo.
"""

from decimal import Decimal

import pytest

from cross_rates.nucleo import (
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    SemPercurso,
)
from cross_rates.servico import (
    EXEMPLOS_ARBITRAGEM,
    EXEMPLOS_GEOGRAFICA,
    analisar_arbitragem,
    calcular_cross,
    calcular_forward,
    calcular_hedge,
    calcular_swap,
    para_dict,
    parse_montante,
)


def _grafo(*args_list: tuple[str, ...]) -> GrafoCambial:
    g = GrafoCambial()
    for args in args_list:
        g.adicionar(Cotacao(*args))
    return g


# --- parse de montante ---------------------------------------------------- #


def test_parse_montante_vazio_e_valido() -> None:
    assert parse_montante("") is None
    assert parse_montante("  ") is None
    assert parse_montante("1.000.000".replace(".", "")) == Decimal("1000000")
    assert parse_montante("1000,5") == Decimal("1000.5")


@pytest.mark.parametrize("texto", ["0", "-5", "abc"])
def test_parse_montante_invalido(texto: str) -> None:
    with pytest.raises(CotacaoInvalida):
        parse_montante(texto)


# --- cross ----------------------------------------------------------------- #


def test_calcular_cross_formato_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        calcular_cross(GrafoCambial(), "GBP")


def test_calcular_cross_sem_percurso() -> None:
    with pytest.raises(SemPercurso):
        calcular_cross(_grafo(("EUR", "USD", "1.08", "1.09")), "GBP SEK")


def test_calcular_cross_paridade_com_nucleo() -> None:
    g = _grafo(*EXEMPLOS_ARBITRAGEM)
    r = calcular_cross(g, "gbp eur")  # o serviço normaliza para maiúsculas
    assert r.par == "GBP/EUR"
    # view-model: tudo string, números preservados
    d = para_dict(r)
    assert isinstance(d["bid"], str) and isinstance(d["ask"], str)
    assert d["par"] == "GBP/EUR"


# --- arbitragem ------------------------------------------------------------ #


def test_arbitragem_triangular_com_lucro() -> None:
    geos, tris = analisar_arbitragem(_grafo(*EXEMPLOS_ARBITRAGEM))
    assert not geos
    assert len(tris) >= 1
    montante = Decimal("1000000")
    d = para_dict(tris[0], montante)
    assert Decimal(d["fator"]) > 1
    assert "simulacao" in d and Decimal(d["lucro"]) > 0
    assert d["moeda_lucro"] == tris[0].ciclo[0]


def test_arbitragem_geografica_view_model() -> None:
    geos, tris = analisar_arbitragem(_grafo(*EXEMPLOS_GEOGRAFICA))
    assert len(geos) == 1
    d = para_dict(geos[0], Decimal("1000000"))
    assert d["fonte_compra"] and d["fonte_venda"]
    assert isinstance(d["simulacao"], list)


# --- forward + arbitragem a prazo ------------------------------------------ #


def test_forward_e_arbitragem_a_prazo() -> None:
    g = _grafo(("CHF", "USD", "1.2745", "1.2748"))
    r, arb = calcular_forward(g, "CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079")
    assert r.dias == 180
    assert arb is not None  # forward de mercado fora do equilíbrio
    d = para_dict(arb, Decimal("1000000"))
    assert Decimal(d["ganho_pct"]) > 0
    assert "lucro" in d


def test_forward_sem_spot_levanta_erro() -> None:
    with pytest.raises(CotacaoInvalida):
        calcular_forward(GrafoCambial(), "CHF USD 180 0.1 0.2 4.9 5.0")


def test_forward_sete_campos_sem_arbitragem() -> None:
    g = _grafo(("CHF", "USD", "1.2745", "1.2748"))
    r, arb = calcular_forward(g, "CHF USD 180 0.1072 0.1144 4.9379 4.9438")
    assert arb is None
    assert para_dict(r)["dias"] == "180"


# --- swap ------------------------------------------------------------------ #


def test_swap_outright_via_pontos() -> None:
    g = _grafo(("EUR", "USD", "1.0850", "1.0852"))
    r = calcular_swap(g, "EUR USD 20 30")
    d = para_dict(r)
    assert d["par"] == "EUR/USD"
    assert Decimal(d["fwd_ask"]) > Decimal(d["spot_ask"])  # pontos positivos → prémio


# --- hedge ----------------------------------------------------------------- #


def test_hedge_escolhe_melhor_estrategia() -> None:
    g = _grafo(("EUR", "USD", "1.08", "1.09"))
    r = calcular_hedge(g, "pagamento 500000 EUR USD 90 3.1 3.2 4.5 4.6")
    d = para_dict(r)
    assert d["melhor_estrategia"]
    assert d["acao"] == "Custo"  # pagamento


def test_hedge_tipo_invalido() -> None:
    g = _grafo(("EUR", "USD", "1.08", "1.09"))
    with pytest.raises(CotacaoInvalida):
        calcular_hedge(g, "compra 500000 EUR USD 90 3.1 3.2 4.5 4.6")
