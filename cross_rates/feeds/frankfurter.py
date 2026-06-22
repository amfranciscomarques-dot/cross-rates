"""Feed ao vivo a partir do Frankfurter (taxas de referência do BCE).

O Frankfurter (https://frankfurter.app) expõe as taxas de referência diárias
do Banco Central Europeu — gratuito e **sem chave de API**. Publica apenas
*mid rates* (o BCE não cota spreads), por isso este feed aplica um spread
sintético configurável (``spread_bps``, em pontos-base do mid) para produzir
bid/ask coerentes com a microestrutura do núcleo.

Todas as cotações partilham a moeda ``base`` (por omissão EUR), na forma
``EUR/USD``, ``EUR/GBP``, … — ~30 pares. O acesso HTTP é injetável (parâmetro
``leitor``) para que os testes corram offline e de forma determinística.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from cross_rates.nucleo import Cotacao, CotacaoInvalida, normaliza_moeda, para_decimal

from .base import FeedIndisponivel

# Endpoint público das últimas taxas (sem chave).
URL_BASE = "https://api.frankfurter.dev/v1/latest"

# Tempo-limite (s) do pedido HTTP — uma página não deve bloquear num feed lento.
_TEMPO_LIMITE = 10

# O Frankfurter (atrás da Cloudflare) devolve 403 ao User-Agent por omissão do
# urllib; identificamo-nos explicitamente.
_USER_AGENT = "cross-rates/0.1 (+https://github.com/amfranciscomarques-dot/cross-rates)"

# "Leitor" HTTP: recebe o URL e devolve o corpo (bytes). Injetável nos testes.
LeitorHttp = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    """Leitor por omissão: GET simples via ``urllib`` (stdlib, sem dependências)."""
    pedido = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(pedido, timeout=_TEMPO_LIMITE) as resposta:
        corpo: bytes = resposta.read()
    return corpo


class FrankfurterFeed:
    """Cotações ao vivo do Frankfurter com spread sintético sobre o mid do BCE."""

    def __init__(
        self,
        *,
        base: str = "EUR",
        simbolos: Sequence[str] | None = None,
        spread_bps: Decimal | int | float | str = 2,
        leitor: LeitorHttp = _http_get,
    ) -> None:
        self.base = normaliza_moeda(base)
        self.simbolos = [normaliza_moeda(s) for s in simbolos] if simbolos else None
        # Fração do mid em cada lado: spread total (bps) / 10000 / 2.
        self._meia_fracao = para_decimal(spread_bps) / Decimal(20000)
        self._leitor = leitor

    def cotacoes(self) -> list[Cotacao]:
        return self._para_cotacoes(self._obter_payload())

    def _url(self) -> str:
        params = {"base": self.base}
        if self.simbolos:
            params["symbols"] = ",".join(self.simbolos)
        return f"{URL_BASE}?{urllib.parse.urlencode(params)}"

    def _obter_payload(self) -> Mapping[str, Any]:
        try:
            corpo = self._leitor(self._url())
            dados = json.loads(corpo)
        except (OSError, ValueError) as exc:
            raise FeedIndisponivel(f"Falha ao obter cotações do Frankfurter: {exc}") from exc
        if not isinstance(dados, dict) or "rates" not in dados:
            raise FeedIndisponivel("Resposta do Frankfurter sem o campo 'rates'.")
        return dados

    def _para_cotacoes(self, dados: Mapping[str, Any]) -> list[Cotacao]:
        fonte = f"Frankfurter {dados.get('date', '')}".strip()
        cotacoes: list[Cotacao] = []
        for cotada, mid in dados["rates"].items():
            try:
                bid, ask = self._bid_ask(para_decimal(mid))
                cotacoes.append(Cotacao(self.base, cotada, bid, ask, fonte))
            except CotacaoInvalida as exc:
                raise FeedIndisponivel(f"Cotação inválida para {cotada}: {exc}") from exc
        return cotacoes

    def _bid_ask(self, mid: Decimal) -> tuple[Decimal, Decimal]:
        """Aplica o spread sintético: bid = mid·(1−f), ask = mid·(1+f)."""
        margem = mid * self._meia_fracao
        return mid - margem, mid + margem
