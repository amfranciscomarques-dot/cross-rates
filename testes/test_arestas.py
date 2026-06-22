"""Testes de ramos defensivos, validações e orientações alternativas.

Os testes "de exercício" (``test_cross``, ``test_forward``, ``test_servico``,
…) reproduzem os casos do caderno e cobrem o caminho feliz. Este módulo
completa-os: exercita as **guardas de validação**, os **ramos neutros/inversos**
e as **orientações alternativas** que os exemplos canónicos não tocam — para que
a cobertura reflita também o comportamento em erro, não só os números certos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cross_rates.nucleo import (
    AnaliseHedging,
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    SemPercurso,
    TaxaJuro,
    arbitragem_a_prazo,
    arbitragens_triangulares,
    cross,
    forward,
)
from cross_rates.nucleo.cotacao import para_decimal
from cross_rates.servico.operacoes import (
    adicionar_cotacao,
    calcular_forward,
    calcular_hedge,
    calcular_swap,
    spot_para,
)
from cross_rates.servico.serial import para_dict


def _grafo(*args_list: tuple[str, ...]) -> GrafoCambial:
    g = GrafoCambial()
    for args in args_list:
        g.adicionar(Cotacao(*args))
    return g


# --------------------------------------------------------------------------- #
# cotacao.py — conversão numérica tolerante
# --------------------------------------------------------------------------- #


def test_para_decimal_texto_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        para_decimal("não-é-número")


# --------------------------------------------------------------------------- #
# grafo.py — limpar, percursos triviais e arestas em falta
# --------------------------------------------------------------------------- #


def test_grafo_limpar_esvazia_cotacoes_e_moedas() -> None:
    g = _grafo(("EUR", "USD", "1.08", "1.09"))
    assert g.moedas()
    g.limpar()
    assert g.moedas() == set()
    assert g.cotacoes == []


def test_percurso_destino_desconhecido() -> None:
    g = _grafo(("EUR", "USD", "1.08", "1.09"))
    with pytest.raises(SemPercurso):
        g.percurso("EUR", "ZAR")  # origem conhecida, destino fora do grafo


def test_percurso_origem_igual_destino() -> None:
    g = _grafo(("EUR", "USD", "1.08", "1.09"))
    assert g.percurso("EUR", "EUR") == ["EUR"]


def test_taxa_percurso_sem_aresta() -> None:
    g = _grafo(("EUR", "USD", "1.08", "1.09"))
    # JPY não está ligado a EUR: a aresta pedida não existe.
    with pytest.raises(SemPercurso):
        g.taxa_percurso(["EUR", "JPY"])


# --------------------------------------------------------------------------- #
# cross.py — cross em cadeia (4 moedas, 3 saltos)
# --------------------------------------------------------------------------- #


def test_cross_em_cadeia_quatro_moedas() -> None:
    # EUR→USD→GBP→JPY: sem atalho, o percurso tem 3 saltos → tipo "cadeia".
    g = _grafo(
        ("EUR", "USD", "1.08", "1.09"),
        ("USD", "GBP", "0.78", "0.79"),
        ("GBP", "JPY", "190.0", "190.5"),
    )
    r = cross(g, "EUR", "JPY")
    assert r.percurso == ["EUR", "USD", "GBP", "JPY"]
    assert r.tipo == "cadeia (3 saltos)"
    assert "cadeia (3 saltos)" in r.nota
    assert r.bid > 0 and r.ask >= r.bid


# --------------------------------------------------------------------------- #
# arbitragem.py — triplo sem todos os pares (ciclo incompleto → None)
# --------------------------------------------------------------------------- #


def test_arbitragem_triangular_ignora_triplo_incompleto() -> None:
    # Triângulo completo EUR-USD-GBP + JPY ligado só ao EUR.
    # As triplas que incluem JPY não têm todos os pares → _ciclo devolve None.
    g = _grafo(
        ("EUR", "USD", "1.08", "1.09"),
        ("USD", "GBP", "0.78", "0.79"),
        ("EUR", "GBP", "0.84", "0.85"),
        ("EUR", "JPY", "160.0", "160.5"),
    )
    # Não deve rebentar: as triplas incompletas são silenciosamente saltadas.
    arbs = arbitragens_triangulares(g)
    assert isinstance(arbs, list)


# --------------------------------------------------------------------------- #
# forward.py — validações e o ramo neutro (sinal/nota)
# --------------------------------------------------------------------------- #


def test_taxajuro_convencao_invalida() -> None:
    with pytest.raises(CotacaoInvalida):
        TaxaJuro("USD", "4", "4", convencao="Act/360")  # type: ignore[arg-type]


def test_taxajuro_de_texto_formato_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        TaxaJuro.de_texto("USD 4.2")  # falta o i_ask


def test_forward_taxa_juro_cotada_nao_corresponde() -> None:
    spot = Cotacao("EUR", "USD", "1.08", "1.09")
    juro_base = TaxaJuro("EUR", "2", "2.1")
    juro_cotada = TaxaJuro("GBP", "4", "4.1")  # devia ser USD
    with pytest.raises(CotacaoInvalida):
        forward(spot, juro_base, juro_cotada, 180)


def test_forward_dias_nao_positivo() -> None:
    spot = Cotacao("EUR", "USD", "1.08", "1.09")
    juro_base = TaxaJuro("EUR", "2", "2.1")
    juro_cotada = TaxaJuro("USD", "4", "4.1")
    with pytest.raises(CotacaoInvalida):
        forward(spot, juro_base, juro_cotada, 0)


def test_forward_sinal_neutro_quando_juros_iguais() -> None:
    # i_base == i_cotada (mesma média) → nem prémio nem desconto.
    spot = Cotacao("EUR", "USD", "1.08", "1.09")
    juro_base = TaxaJuro("EUR", "3", "3")
    juro_cotada = TaxaJuro("USD", "3", "3")
    r = forward(spot, juro_base, juro_cotada, 180)
    assert r.sinal == "neutro"
    assert "sem prémio nem desconto" in r.nota


# --------------------------------------------------------------------------- #
# forward.py — arbitragem a prazo: mercado invertido e ganho abaixo do limiar
# --------------------------------------------------------------------------- #


def test_arbitragem_prazo_mercado_invertido() -> None:
    spot = Cotacao("CHF", "USD", "1.2745", "1.2748")
    juro_base = TaxaJuro("CHF", "0.1072", "0.1144")
    juro_cotada = TaxaJuro("USD", "4.9379", "4.9438")
    with pytest.raises(CotacaoInvalida):
        # bid > ask no forward de mercado
        arbitragem_a_prazo(spot, juro_base, juro_cotada, 180, "1.31", "1.30")


def test_arbitragem_prazo_ganho_abaixo_do_limiar() -> None:
    # Mesmo desalinhamento do caderno, mas com um limiar enorme: o ganho real
    # (pequeno) não o ultrapassa → não há oportunidade (None).
    spot = Cotacao("CHF", "USD", "1.2745", "1.2748")
    juro_base = TaxaJuro("CHF", "0.1072", "0.1144")
    juro_cotada = TaxaJuro("USD", "4.9379", "4.9438")
    arb = arbitragem_a_prazo(
        spot, juro_base, juro_cotada, 180, "1.3076", "1.3079", limiar=Decimal("1")
    )
    assert arb is None


# --------------------------------------------------------------------------- #
# hedging.py — regra de decisão em todos os ramos (forçada via dataclass)
# --------------------------------------------------------------------------- #


def _analise(tipo: str, fwd: str, mmh: str) -> AnaliseHedging:
    """Constrói uma AnaliseHedging com só os campos que a decisão usa."""
    um = Decimal("1")
    return AnaliseHedging(
        tipo_exposicao=tipo,
        moeda_estrangeira="USD",
        moeda_base="EUR",
        montante_me=um,
        dias=90,
        fwd_taxa=um,
        fwd_resultado_base=Decimal(fwd),
        mmh_me_presente=um,
        mmh_spot_taxa=um,
        mmh_base_presente=um,
        mmh_taxa_juro_base=um,
        mmh_resultado_base=Decimal(mmh),
    )


@pytest.mark.parametrize(
    ("tipo", "fwd", "mmh", "esperado"),
    [
        # recebimento → maximizar receita na base
        ("recebimento", "100", "90", "Forward Hedge"),
        ("recebimento", "90", "100", "Money Market Hedge"),
        ("recebimento", "100", "100", "Indiferente"),
        # pagamento → minimizar custo na base
        ("pagamento", "90", "100", "Forward Hedge"),
        ("pagamento", "100", "90", "Money Market Hedge"),
        ("pagamento", "100", "100", "Indiferente"),
    ],
)
def test_melhor_estrategia_todos_os_ramos(
    tipo: str, fwd: str, mmh: str, esperado: str
) -> None:
    assert _analise(tipo, fwd, mmh).melhor_estrategia == esperado


# --------------------------------------------------------------------------- #
# servico/operacoes.py — parsing, orientação inversa e formatos inválidos
# --------------------------------------------------------------------------- #


def test_spot_para_orientacao_inversa() -> None:
    g = _grafo(("EUR", "USD", "1.0850", "1.0852"))
    # Pede-se USD/EUR; a tabela só tem EUR/USD → devolve a cotação invertida.
    s = spot_para(g, "USD", "EUR")
    assert s is not None
    assert s.base == "USD" and s.cotada == "EUR"
    assert s.bid == Decimal(1) / Decimal("1.0852")
    assert s.ask == Decimal(1) / Decimal("1.0850")


def test_adicionar_cotacao_devolve_e_regista() -> None:
    g = GrafoCambial()
    c = adicionar_cotacao(g, "EUR USD 1.08 1.09")
    assert c.par == "EUR/USD"
    assert g.cotacoes and g.cotacoes[0].par == "EUR/USD"


def test_calcular_forward_dias_nao_inteiro() -> None:
    g = _grafo(("CHF", "USD", "1.2745", "1.2748"))
    with pytest.raises(CotacaoInvalida):
        calcular_forward(g, "CHF USD abc 0.1 0.2 4.9 5.0")


def test_calcular_forward_formato_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        calcular_forward(GrafoCambial(), "EUR USD")  # nem 7 nem 9 campos


def test_calcular_swap_formato_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        calcular_swap(GrafoCambial(), "EUR USD 20")  # falta o pontos_ask


def test_calcular_hedge_formato_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        calcular_hedge(GrafoCambial(), "pagamento 500000 EUR")  # campos a menos


# --------------------------------------------------------------------------- #
# servico/serial.py — despacho do view-model
# --------------------------------------------------------------------------- #


def test_para_dict_despacha_cotacao() -> None:
    d = para_dict(Cotacao("EUR", "USD", "1.08", "1.09"))
    assert d["par"] == "EUR/USD"
    assert isinstance(d["bid"], str)


def test_para_dict_tipo_sem_serializador() -> None:
    with pytest.raises(TypeError):
        para_dict("não é um resultado do núcleo")  # type: ignore[arg-type]
