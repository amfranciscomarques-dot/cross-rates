"""Testes da lógica pura do ecrã de prática (``_calcular`` / ``_avaliar``).

As funções estão deliberadamente fora da classe ``PraticaScreen`` para poderem
ser testadas sem montar a TUI. Estes testes exercitam cada tipo de exercício
(cross, geográfica, triangular, forward e arbitragem a prazo).
"""

from decimal import Decimal

import pytest

from cross_rates.nucleo import Cotacao, GrafoCambial
from cross_rates.tui.pratica import EXERCICIOS, Exercicio, _avaliar, _calcular


def _exercicio(ex_id: str) -> Exercicio:
    return next(ex for ex in EXERCICIOS if ex.id == ex_id)


def _grafo(ex: Exercicio) -> GrafoCambial:
    grafo = GrafoCambial()
    for args in ex.cotacoes:
        grafo.adicionar(Cotacao(*args))
    return grafo


def test_todos_os_exercicios_calculam_sem_erro():
    # Garante que cada `acao` é válida e produz um resultado utilizável.
    for ex in EXERCICIOS:
        assert _calcular(_grafo(ex), ex) is not None


def test_cross_resposta_correta_e_incorreta():
    ex = _exercicio("ex12a")
    resultado = _calcular(_grafo(ex), ex)
    certo = f"{resultado.bid} {resultado.ask}"
    ok, _ = _avaliar(ex, certo, resultado)
    assert ok
    errado, _ = _avaliar(ex, "1.0000 1.0000", resultado)
    assert not errado


def test_cross_formato_invalido():
    ex = _exercicio("ex12a")
    resultado = _calcular(_grafo(ex), ex)
    ok, msg = _avaliar(ex, "1.0620", resultado)  # falta o ask
    assert not ok
    assert "bid ask" in msg


def test_geografica_sim_quando_existe_arbitragem():
    ex = _exercicio("ex15")
    resultado = _calcular(_grafo(ex), ex)
    assert len(resultado) > 0  # Ex. 15 tem arbitragem geográfica
    assert _avaliar(ex, "sim", resultado)[0]
    assert not _avaliar(ex, "não", resultado)[0]


def test_triangular_sim_quando_existe_arbitragem():
    ex = _exercicio("ex17")
    resultado = _calcular(_grafo(ex), ex)
    assert len(resultado) > 0  # Ex. 17 tem arbitragem triangular
    assert _avaliar(ex, "sim", resultado)[0]
    assert not _avaliar(ex, "nao", resultado)[0]


def test_forward_resposta_correta():
    ex = _exercicio("ex27a")
    resultado = _calcular(_grafo(ex), ex)
    # Responder com bid/ask arredondados a 4 casas (tolerância do exercício).
    certo = f"{resultado.bid:.4f} {resultado.ask:.4f}"
    assert _avaliar(ex, certo, resultado)[0]
    assert not _avaliar(ex, "1.0000 1.0000", resultado)[0]


def test_forward_arbitragem_a_prazo_sim():
    ex = _exercicio("ex27b")
    fwd, arb = _calcular(_grafo(ex), ex)
    assert arb is not None  # Ex. 27b tem arbitragem a prazo
    assert _avaliar(ex, "sim", (fwd, arb))[0]
    assert not _avaliar(ex, "não", (fwd, arb))[0]


def test_acao_desconhecida_levanta():
    ex = Exercicio(
        id="x", titulo="x", categoria="x", enunciado="x", pergunta="x",
        dica="x", cotacoes=[], acao="bananas EUR USD",
        tolerancia=Decimal("0.0001"),
    )
    with pytest.raises(ValueError):
        _calcular(GrafoCambial(), ex)
