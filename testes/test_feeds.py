"""Testes dos feeds de cotações (sem rede).

O ``FrankfurterFeed`` é exercitado com um leitor HTTP injetado que devolve
respostas canónicas, cobrindo a transformação mid→bid/ask e os ramos de falha
(rede, JSON inválido, payload sem ``rates``, cotação inválida). O leitor real
(``_http_get``) é coberto isolando o ``urlopen``. O ``FeedSimulado`` valida-se
como fixture determinística.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal

import pytest

from cross_rates.feeds import (
    FeedError,
    FeedIndisponivel,
    FeedSimulado,
    FrankfurterFeed,
    feed_por_nome,
)
from cross_rates.feeds import frankfurter as fr
from cross_rates.nucleo import GrafoCambial


def _leitor(payload: dict[str, object]) -> fr.LeitorHttp:
    """Devolve um leitor HTTP que responde sempre com ``payload`` (JSON)."""
    corpo = json.dumps(payload).encode()
    return lambda url: corpo


_RESPOSTA = {
    "base": "EUR",
    "date": "2024-05-01",
    "rates": {"USD": 1.0853, "GBP": 0.8412, "JPY": 170.5},
}


# --- FrankfurterFeed: caminho feliz ---------------------------------------- #


def test_frankfurter_constroi_cotacoes_com_bid_ask() -> None:
    feed = FrankfurterFeed(leitor=_leitor(_RESPOSTA))
    cotacoes = {c.par: c for c in feed.cotacoes()}

    assert set(cotacoes) == {"EUR/USD", "EUR/GBP", "EUR/JPY"}
    eurusd = cotacoes["EUR/USD"]
    # bid < mid < ask, e o spread relativo é o configurado (2 bps por omissão).
    assert eurusd.bid < Decimal("1.0853") < eurusd.ask
    spread_rel = (eurusd.ask - eurusd.bid) / Decimal("1.0853")
    assert spread_rel == pytest.approx(Decimal("2") / Decimal("10000"))
    assert eurusd.fonte == "Frankfurter 2024-05-01"


def test_frankfurter_semeia_grafo_e_calcula_cross() -> None:
    grafo = GrafoCambial()
    for c in FrankfurterFeed(leitor=_leitor(_RESPOSTA)).cotacoes():
        grafo.adicionar(c)
    # GBP/USD via EUR existe assim que o grafo é semeado.
    assert {"EUR", "USD", "GBP", "JPY"} <= grafo.moedas()
    assert grafo.taxa_percurso(grafo.percurso("GBP", "USD")) > 0


def test_frankfurter_spread_configuravel() -> None:
    feed = FrankfurterFeed(spread_bps=10, leitor=_leitor(_RESPOSTA))
    eurusd = next(c for c in feed.cotacoes() if c.par == "EUR/USD")
    spread_rel = (eurusd.ask - eurusd.bid) / Decimal("1.0853")
    assert spread_rel == pytest.approx(Decimal("10") / Decimal("10000"))


def test_frankfurter_url_inclui_base_e_simbolos() -> None:
    capturado: dict[str, str] = {}

    def leitor(url: str) -> bytes:
        capturado["url"] = url
        return json.dumps({"base": "USD", "date": "2024-05-01", "rates": {"EUR": 0.92}}).encode()

    FrankfurterFeed(base="usd", simbolos=["eur", "gbp"], leitor=leitor).cotacoes()
    assert "base=USD" in capturado["url"]
    assert "symbols=EUR%2CGBP" in capturado["url"]


# --- FrankfurterFeed: ramos de falha --------------------------------------- #


def test_frankfurter_falha_de_rede() -> None:
    def leitor(url: str) -> bytes:
        raise urllib.error.URLError("sem rede")

    with pytest.raises(FeedIndisponivel):
        FrankfurterFeed(leitor=leitor).cotacoes()


def test_frankfurter_json_invalido() -> None:
    with pytest.raises(FeedIndisponivel):
        FrankfurterFeed(leitor=lambda url: b"isto nao e json").cotacoes()


def test_frankfurter_payload_sem_rates() -> None:
    with pytest.raises(FeedIndisponivel):
        FrankfurterFeed(leitor=_leitor({"base": "EUR", "date": "2024-05-01"})).cotacoes()


def test_frankfurter_cotacao_invalida_e_envolvida() -> None:
    mau = {"base": "EUR", "date": "2024-05-01", "rates": {"USD": "lixo"}}
    with pytest.raises(FeedIndisponivel):
        FrankfurterFeed(leitor=_leitor(mau)).cotacoes()


# --- leitor HTTP real (isolando o urlopen) --------------------------------- #


def test_http_get_le_o_corpo(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResp:
        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b"corpo"

    def _fake_urlopen(pedido: urllib.request.Request, timeout: int) -> _FakeResp:
        # _http_get envia um Request com User-Agent próprio (evita o 403 da Cloudflare).
        assert "frankfurter" in pedido.full_url
        assert pedido.get_header("User-agent") == fr._USER_AGENT
        return _FakeResp()

    monkeypatch.setattr(fr.urllib.request, "urlopen", _fake_urlopen)
    assert fr._http_get(f"{fr.URL_BASE}?base=EUR") == b"corpo"


# --- FeedSimulado ----------------------------------------------------------- #


def test_simulado_deterministico_e_valido() -> None:
    feed = FeedSimulado()
    a = feed.cotacoes()
    b = feed.cotacoes()
    assert [str(c) for c in a] == [str(c) for c in b]
    assert all(c.base == "EUR" and c.bid < c.ask and c.fonte == "Simulado" for c in a)
    assert {c.cotada for c in a} >= {"USD", "GBP", "JPY"}


# --- fábrica feed_por_nome -------------------------------------------------- #


@pytest.mark.parametrize("nome", ["", "  ", "none", "NENHUM", None])
def test_feed_por_nome_desligado(nome: str | None) -> None:
    assert feed_por_nome(nome) is None


def test_feed_por_nome_resolve_concretos() -> None:
    assert isinstance(feed_por_nome("frankfurter"), FrankfurterFeed)
    assert isinstance(feed_por_nome("Simulado"), FeedSimulado)


def test_feed_por_nome_desconhecido() -> None:
    with pytest.raises(FeedError):
        feed_por_nome("bloomberg")
