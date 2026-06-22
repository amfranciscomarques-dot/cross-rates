"""Testes das opções cambiais vanilla (Garman-Kohlhagen).

O modelo (Hull, opções sobre divisas; Madura cap. 5) é determinístico, pelo que
os valores de referência foram fixados a partir da forma fechada e
cruzados, de forma independente, com ``statistics.NormalDist`` (Black-Scholes em
vírgula flutuante) — concordam a ~10 algarismos significativos. Validam-se:

1. ``d1``/``d2``, prémio e Gregas (delta, gamma, vega, theta, rho) de uma call e
   de uma put, fixados ao valor da forma fechada;
2. a **paridade put-call** (``C − P = S·e^(−r_f·T) − K·e^(−r_d·T)``), relação
   exata e independente do modelo;
3. a distribuição normal padrão em ``Decimal`` (``N(0)=½``, ``N(1.96)≈0.975``,
   simetria) e a validação de entrada.
"""

from decimal import Decimal

import pytest

from cross_rates.nucleo import (
    Cotacao,
    CotacaoInvalida,
    OpcaoVanilla,
    TaxaJuro,
    TipoOpcao,
    garman_kohlhagen,
)
from cross_rates.nucleo.opcoes import _erf, _norm_cdf

REL = Decimal("1e-6")  # forma fechada (não arredondamento de tabela)


def proximo(obtido: Decimal, esperado: str, rel: Decimal = REL) -> bool:
    alvo = Decimal(esperado)
    return abs(obtido - alvo) <= abs(alvo) * rel


@pytest.fixture
def mercado() -> tuple[Cotacao, TaxaJuro, TaxaJuro]:
    """EUR/USD: base EUR (r_f, mid 3%), cotada USD (r_d, mid 5%), spot mid 1.10."""
    spot = Cotacao("EUR", "USD", "1.0990", "1.1010")  # mid 1.1000
    juro_base = TaxaJuro("EUR", "2.9", "3.1")  # r_f = 3,0%
    juro_cotada = TaxaJuro("USD", "4.9", "5.1")  # r_d = 5,0%
    return spot, juro_base, juro_cotada


def _call(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro], notional: str = "1") -> object:
    spot, jb, jc = mercado
    o = OpcaoVanilla(TipoOpcao.CALL, "EUR", "USD", "1.1000", 180, notional)
    return garman_kohlhagen(o, spot, 10, jb, jc)


def _put(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> object:
    spot, jb, jc = mercado
    o = OpcaoVanilla(TipoOpcao.PUT, "EUR", "USD", "1.1000", 180)
    return garman_kohlhagen(o, spot, 10, jb, jc)


# --------------------------------------------------------------------------- #
# Prémio e d1/d2 (fixados à forma fechada)
# --------------------------------------------------------------------------- #


def test_call_preco_e_d1_d2(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    r = _call(mercado)
    assert r.par == "EUR/USD" and r.tipo == "call"
    assert proximo(r.d1, "0.1755617208")
    assert proximo(r.d2, "0.1053370325")
    assert proximo(r.preco, "0.0358254354")  # USD por 1 EUR


def test_put_preco(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    r = _put(mercado)
    assert r.tipo == "put"
    assert proximo(r.preco, "0.0251879941")


def test_preco_total_escala_com_notional(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    r = _call(mercado, notional="1000000")
    assert r.notional == Decimal("1000000")
    assert proximo(r.preco_total, "35825.4354")  # ≈ preco · 1e6 USD
    assert proximo(r.preco_total, str(r.preco * r.notional), Decimal("1e-12"))


# --------------------------------------------------------------------------- #
# Gregas (fixadas à forma fechada; escalas de mesa)
# --------------------------------------------------------------------------- #


def test_gregas_call(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    r = _call(mercado)
    assert proximo(r.delta, "0.5613147449")
    assert proximo(r.gamma, "5.0108279047")
    assert proximo(r.vega, "0.0029900228")  # por +1 ponto de vol
    assert proximo(r.theta, "-0.0001119813")  # por dia
    assert proximo(r.rho, "0.0028682669")  # por +1 ponto de r_d


def test_gregas_put(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    r = _put(mercado)
    assert proximo(r.delta, "-0.4239996357")
    assert proximo(r.gamma, "5.0108279047")  # idêntica à da call
    assert proximo(r.vega, "0.0029900228")  # idêntica à da call
    assert proximo(r.theta, "-0.0000540496")
    assert proximo(r.rho, "-0.0024242676")


# --------------------------------------------------------------------------- #
# Relações teóricas (independentes dos valores fixados)
# --------------------------------------------------------------------------- #


def test_paridade_put_call(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    # C − P = S·e^(−r_f·T) − K·e^(−r_d·T). Relação exata, sem hipóteses do modelo.
    c, p = _call(mercado), _put(mercado)
    s = Decimal("1.10")
    t = Decimal(180) / Decimal(365)
    esperado = s * (-(Decimal("0.03")) * t).exp() - Decimal("1.10") * (
        -(Decimal("0.05")) * t
    ).exp()
    assert abs((c.preco - p.preco) - esperado) < Decimal("1e-12")


def test_relacoes_entre_gregas(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    c, p = _call(mercado), _put(mercado)
    # delta_call − delta_put = e^(−r_f·T) (≈ 0,985314).
    t = Decimal(180) / Decimal(365)
    assert abs((c.delta - p.delta) - (-(Decimal("0.03")) * t).exp()) < Decimal("1e-12")
    # gamma e vega são iguais para call e put; ambos positivos.
    assert c.gamma == p.gamma and c.gamma > 0
    assert c.vega == p.vega and c.vega > 0
    # call delta ∈ (0, 1); put delta ∈ (−1, 0).
    assert 0 < c.delta < 1 and -1 < p.delta < 0


def test_spot_usa_o_mid(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    # Spread diferente mas o mesmo mid (1.10) → mesmo prémio (o modelo usa o mid).
    _, jb, jc = mercado
    o = OpcaoVanilla(TipoOpcao.CALL, "EUR", "USD", "1.1000", 180)
    largo = Cotacao("EUR", "USD", "1.0900", "1.1100")  # mid 1.1000
    assert garman_kohlhagen(o, largo, 10, jb, jc).preco == _call(mercado).preco


# --------------------------------------------------------------------------- #
# Distribuição normal padrão (Decimal)
# --------------------------------------------------------------------------- #


def test_norm_cdf_valores_conhecidos() -> None:
    assert _norm_cdf(Decimal(0)) == Decimal("0.5")
    assert proximo(_norm_cdf(Decimal("1.959963985")), "0.975")  # quantil 97,5%
    assert proximo(_norm_cdf(Decimal("-1.959963985")), "0.025")
    # Simetria: N(x) + N(−x) = 1.
    x = Decimal("0.7")
    assert abs(_norm_cdf(x) + _norm_cdf(-x) - 1) < Decimal("1e-20")


def test_erf_zero_e_impar() -> None:
    assert _erf(Decimal(0)) == 0
    assert abs(_erf(Decimal("0.8")) + _erf(Decimal("-0.8"))) < Decimal("1e-20")


# --------------------------------------------------------------------------- #
# Validação de entrada
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kwargs",
    [
        {"strike": "0"},  # strike não positivo
        {"dias": 0},  # prazo não positivo
        {"notional": "0"},  # notional não positivo
        {"base": "EUR", "cotada": "EUR"},  # base == cotada
    ],
)
def test_opcao_vanilla_invalida(kwargs: dict[str, object]) -> None:
    base = {"tipo": TipoOpcao.CALL, "base": "EUR", "cotada": "USD", "strike": "1.1", "dias": 180}
    base.update(kwargs)
    with pytest.raises(CotacaoInvalida):
        OpcaoVanilla(**base)  # type: ignore[arg-type]


def test_opcao_vanilla_tipo_invalido() -> None:
    with pytest.raises(CotacaoInvalida):
        OpcaoVanilla("call", "EUR", "USD", "1.1", 180)  # type: ignore[arg-type]


def test_gk_spot_nao_corresponde(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    _, jb, jc = mercado
    o = OpcaoVanilla(TipoOpcao.CALL, "EUR", "USD", "1.1", 180)
    with pytest.raises(CotacaoInvalida):
        garman_kohlhagen(o, Cotacao("GBP", "USD", "1.27", "1.28"), 10, jb, jc)


def test_gk_juros_incoerentes(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    spot, jb, jc = mercado
    o = OpcaoVanilla(TipoOpcao.CALL, "EUR", "USD", "1.1", 180)
    with pytest.raises(CotacaoInvalida):
        garman_kohlhagen(o, spot, 10, TaxaJuro("GBP", "3", "3.1"), jc)  # base errada
    with pytest.raises(CotacaoInvalida):
        garman_kohlhagen(o, spot, 10, jb, TaxaJuro("JPY", "5", "5.1"))  # cotada errada


def test_gk_vol_nao_positiva(mercado: tuple[Cotacao, TaxaJuro, TaxaJuro]) -> None:
    spot, jb, jc = mercado
    o = OpcaoVanilla(TipoOpcao.CALL, "EUR", "USD", "1.1", 180)
    with pytest.raises(CotacaoInvalida):
        garman_kohlhagen(o, spot, 0, jb, jc)
