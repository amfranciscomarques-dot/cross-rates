"""Testes do frontend web (FastAPI + HTMX) via ``TestClient``, sem rede.

Validam o contrato HTTP: a página inicial carrega, os fragmentos HTMX trazem o
que os parciais prometem, e — sobretudo — o **ciclo sem estado** funciona: as
cotações vão e voltam em ``<input hidden name="cotacoes">`` e cada operação
reconstrói o grafo a partir delas. Erros de input viram o parcial de erro.
"""

import re

import pytest
from starlette.testclient import TestClient

from cross_rates.web import app


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(app)


def _cotacoes(html: str) -> list[str]:
    """Extrai os valores dos inputs ocultos (o estado da sessão no cliente)."""
    return re.findall(r'name="cotacoes" value="([^"]+)"', html)


def test_index_carrega(cliente: TestClient) -> None:
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Cross-Rates" in r.text
    assert 'id="tabela"' in r.text


def test_index_semeado_pelo_feed(cliente: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com CROSS_RATES_FEED=simulado, a página abre já com cotações na tabela."""
    monkeypatch.setenv("CROSS_RATES_FEED", "simulado")
    r = cliente.get("/")
    assert r.status_code == 200
    assert "EUR/USD" in r.text
    assert _cotacoes(r.text)  # estado oculto pré-preenchido
    assert "carregadas do feed" in r.text


def test_index_feed_indisponivel_abre_vazio(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Se o feed falhar, a página degrada graciosamente: tabela vazia + nota."""
    import sys

    from cross_rates.feeds import FeedIndisponivel

    class _FeedAvariado:
        def cotacoes(self) -> list[object]:
            raise FeedIndisponivel("rede em baixo")

    # O módulo, via sys.modules: o nome `cross_rates.web.app` colide com a
    # instância FastAPI reexportada em cross_rates.web.__init__.
    web_app = sys.modules["cross_rates.web.app"]
    monkeypatch.setattr(web_app, "_feed_configurado", lambda: _FeedAvariado())
    r = cliente.get("/")
    assert r.status_code == 200
    assert _cotacoes(r.text) == []
    assert "indisponível" in r.text


def test_exemplos_devolvem_estado_oculto(cliente: TestClient) -> None:
    r = cliente.post("/exemplos/arbitragem", data={"cotacoes": []})
    assert r.status_code == 200
    cots = _cotacoes(r.text)
    assert cots == [
        "GBP JPY 212.646 212.689",
        "EUR JPY 183.618 183.646",
        "GBP EUR 1.1559 1.1561",
    ]


def test_conjunto_desconhecido_devolve_erro(cliente: TestClient) -> None:
    r = cliente.post("/exemplos/inexistente", data={"cotacoes": []})
    assert r.status_code == 200
    assert "desconhecido" in r.text


def test_adicionar_acumula_sobre_estado(cliente: TestClient) -> None:
    r = cliente.post(
        "/cotacoes",
        data={"cotacao": "EUR USD 1.0850 1.0852", "cotacoes": ["GBP USD 1.27 1.28"]},
    )
    cots = _cotacoes(r.text)
    assert len(cots) == 2
    assert "EUR/USD" in r.text and "Cotação adicionada" in r.text


def test_adicionar_invalido_preserva_estado(cliente: TestClient) -> None:
    r = cliente.post(
        "/cotacoes",
        data={"cotacao": "lixo", "cotacoes": ["GBP USD 1.27 1.28"]},
    )
    assert "Erro" in r.text
    assert _cotacoes(r.text) == ["GBP USD 1.27 1.28"]  # estado intacto


def test_limpar_esvazia_tabela(cliente: TestClient) -> None:
    r = cliente.post("/limpar", data={})
    assert _cotacoes(r.text) == []
    assert "Sem cotações" in r.text


def test_ciclo_triangular_eurgbpjpy(cliente: TestClient) -> None:
    """EUR→GBP→JPY→EUR: carregar exemplos, cross e arbitragem com lucro."""
    cots = _cotacoes(cliente.post("/exemplos/arbitragem", data={"cotacoes": []}).text)

    # cross GBP/EUR
    r = cliente.post("/cross", data={"calc": "GBP EUR", "cotacoes": cots})
    assert r.status_code == 200
    assert "GBP/EUR" in r.text and "spread" in r.text

    # arbitragem triangular com montante → fator > 1 e lucro
    r = cliente.post("/arbitragem", data={"montante": "1000000", "cotacoes": cots})
    assert "Arbitragem triangular" in r.text
    assert "fator" in r.text and "lucro" in r.text


def test_cross_sem_percurso_devolve_erro(cliente: TestClient) -> None:
    cots = ["EUR USD 1.08 1.09"]
    r = cliente.post("/cross", data={"calc": "GBP SEK", "cotacoes": cots})
    assert r.status_code == 200
    assert "erro" in r.text.lower()


def test_forward_com_arbitragem_a_prazo(cliente: TestClient) -> None:
    cots = _cotacoes(cliente.post("/exemplos/forward", data={"cotacoes": []}).text)
    r = cliente.post(
        "/forward",
        data={
            "forward": "CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079",
            "montante": "1000000",
            "cotacoes": cots,
        },
    )
    assert r.status_code == 200
    assert "Arbitragem a prazo" in r.text
    assert "prémio" in r.text or "desconto" in r.text


def test_swap_e_hedge(cliente: TestClient) -> None:
    cots = ["EUR USD 1.0850 1.0852"]
    r = cliente.post("/swap", data={"swap": "EUR USD 20 30", "cotacoes": cots})
    assert "outright" in r.text

    r = cliente.post(
        "/hedge",
        data={"hedge": "pagamento 500000 EUR USD 90 3.1 3.2 4.5 4.6", "cotacoes": cots},
    )
    assert "Melhor estratégia" in r.text


# --- ramos de erro de cada operação ---------------------------------------- #


def test_arbitragem_montante_invalido_devolve_erro(cliente: TestClient) -> None:
    r = cliente.post("/arbitragem", data={"montante": "abc", "cotacoes": []})
    assert r.status_code == 200
    assert "erro" in r.text.lower()


def test_forward_formato_invalido_devolve_erro(cliente: TestClient) -> None:
    r = cliente.post("/forward", data={"forward": "EUR USD", "cotacoes": []})
    assert r.status_code == 200
    assert "erro" in r.text.lower()


def test_swap_formato_invalido_devolve_erro(cliente: TestClient) -> None:
    r = cliente.post("/swap", data={"swap": "EUR USD 20", "cotacoes": []})
    assert r.status_code == 200
    assert "erro" in r.text.lower()


def test_hedge_formato_invalido_devolve_erro(cliente: TestClient) -> None:
    r = cliente.post("/hedge", data={"hedge": "pagamento 500000 EUR", "cotacoes": []})
    assert r.status_code == 200
    assert "erro" in r.text.lower()


# --- entry-points ----------------------------------------------------------- #


def test_serve_arranca_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    """``serve()`` apenas configura e delega no uvicorn — não abrimos socket."""
    import uvicorn

    from cross_rates.web import app as fastapi_app
    from cross_rates.web.app import serve

    chamado: dict[str, object] = {}

    def _fake_run(app_obj: object, **kwargs: object) -> None:
        chamado["app"] = app_obj
        chamado["kwargs"] = kwargs

    monkeypatch.setattr(uvicorn, "run", _fake_run)
    serve()
    assert chamado["app"] is fastapi_app
    assert chamado["kwargs"]["port"] == 8000


def test_modulo_main_invoca_a_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    """``python -m cross_rates`` chama ``cross_rates.tui.main`` sem abrir a TUI."""
    import runpy

    import cross_rates.tui as tui

    chamado: list[bool] = []
    monkeypatch.setattr(tui, "main", lambda: chamado.append(True))
    runpy.run_module("cross_rates", run_name="__main__")
    assert chamado == [True]
