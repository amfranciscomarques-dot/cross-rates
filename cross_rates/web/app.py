"""Aplicação FastAPI (HTMX + Jinja) — frontend web da calculadora de cross-rates.

Sem estado: o browser guarda as cotações em ``<input hidden name="cotacoes">``
(um por linha da tabela) e reenvia-as a cada operação via ``hx-include``. Cada
rota reconstrói um :class:`GrafoCambial` a partir desse texto, delega na camada
de serviço partilhada e devolve um fragmento HTML para o HTMX trocar in-place.
Os erros de input (``CotacaoInvalida``/``SemPercurso``) viram o parcial ``_erro``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cross_rates.nucleo import Cotacao, CotacaoInvalida, GrafoCambial, SemPercurso
from cross_rates.servico import (
    EXEMPLO_FORWARD_INPUT,
    EXEMPLOS_ARBITRAGEM,
    EXEMPLOS_CROSS,
    EXEMPLOS_FORWARD_SPOT,
    EXEMPLOS_GEOGRAFICA,
    analisar_arbitragem,
    calcular_cross,
    calcular_forward,
    calcular_hedge,
    calcular_swap,
    parse_montante,
)
from cross_rates.servico.serial import (
    arbitragem_prazo_dict,
    cotacao_dict,
    forward_dict,
    geografica_dict,
    para_dict,
    triangular_dict,
)

_AQUI = Path(__file__).parent
templates = Jinja2Templates(directory=str(_AQUI / "templates"))

app = FastAPI(title="Cross-Rates", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(_AQUI / "static")), name="static")

# Conjuntos de exemplo (caderno) acessíveis por nome na rota /exemplos/{conjunto}.
_EXEMPLOS: dict[str, list[tuple[str, ...]]] = {
    "cross": EXEMPLOS_CROSS,
    "arbitragem": EXEMPLOS_ARBITRAGEM,
    "geografica": EXEMPLOS_GEOGRAFICA,
    "forward": [EXEMPLOS_FORWARD_SPOT],
}

# Form fields reutilizados: lista de cotações (estado) e montante opcional.
Cotacoes = Annotated[list[str], Form()]
Texto = Annotated[str, Form()]


def _raw(c: Cotacao) -> str:
    """Texto canónico re-parseável (precisão total) para o input oculto."""
    return f"{c.base} {c.cotada} {c.bid} {c.ask} {c.fonte}".strip()


def _grafo(cotacoes: list[str]) -> GrafoCambial:
    """Reconstrói o grafo a partir das linhas de texto enviadas pelo cliente."""
    grafo = GrafoCambial()
    for linha in cotacoes:
        linha = linha.strip()
        if linha:
            grafo.adicionar(Cotacao.de_texto(linha))
    return grafo


def _tabela(request: Request, grafo: GrafoCambial, msg: str = "") -> HTMLResponse:
    """Renderiza o parcial da tabela (linhas visíveis + estado oculto)."""
    linhas = [{"d": cotacao_dict(c), "raw": _raw(c)} for c in grafo.cotacoes]
    return templates.TemplateResponse(
        request,
        "partials/_tabela.html",
        {"linhas": linhas, "msg": msg},
    )


def _erro(request: Request, alvo: str, msg: str) -> HTMLResponse:
    """Parcial de erro destinado ao painel de resultado ``alvo``."""
    return templates.TemplateResponse(
        request, "partials/_erro.html", {"msg": msg, "alvo": alvo}
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"exemplo_forward": EXEMPLO_FORWARD_INPUT, "linhas": [], "msg": ""},
    )


@app.post("/cotacoes", response_class=HTMLResponse)
def adicionar(request: Request, cotacao: Texto, cotacoes: Cotacoes = []) -> HTMLResponse:
    try:
        grafo = _grafo(cotacoes)
        nova = Cotacao.de_texto(cotacao)
    except CotacaoInvalida as exc:
        return _tabela(request, _grafo(cotacoes), msg=f"Erro: {exc}")
    grafo.adicionar(nova)
    return _tabela(request, grafo, msg=f"Cotação adicionada: {nova}")


@app.post("/exemplos/{conjunto}", response_class=HTMLResponse)
def exemplos(request: Request, conjunto: str, cotacoes: Cotacoes = []) -> HTMLResponse:
    args_list = _EXEMPLOS.get(conjunto)
    if args_list is None:
        return _tabela(request, _grafo(cotacoes), msg=f"Erro: conjunto '{conjunto}' desconhecido.")
    grafo = _grafo(cotacoes)
    for args in args_list:
        grafo.adicionar(Cotacao(*args))
    return _tabela(request, grafo, msg="Exemplos carregados.")


@app.post("/limpar", response_class=HTMLResponse)
def limpar(request: Request) -> HTMLResponse:
    return _tabela(request, GrafoCambial(), msg="Tabela limpa.")


@app.post("/cross", response_class=HTMLResponse)
def cross(request: Request, calc: Texto, cotacoes: Cotacoes = []) -> HTMLResponse:
    try:
        r = calcular_cross(_grafo(cotacoes), calc)
    except (SemPercurso, CotacaoInvalida) as exc:
        return _erro(request, "resultado", str(exc))
    return templates.TemplateResponse(
        request, "partials/_cross.html", {"r": para_dict(r)}
    )


@app.post("/arbitragem", response_class=HTMLResponse)
def arbitragem(request: Request, montante: Texto = "", cotacoes: Cotacoes = []) -> HTMLResponse:
    try:
        m = parse_montante(montante)
        geos, tris = analisar_arbitragem(_grafo(cotacoes))
    except (SemPercurso, CotacaoInvalida) as exc:
        return _erro(request, "arb", str(exc))
    return templates.TemplateResponse(
        request,
        "partials/_arbitragem.html",
        {
            "geograficas": [geografica_dict(a, m) for a in geos],
            "triangulares": [triangular_dict(a, m) for a in tris],
        },
    )


@app.post("/forward", response_class=HTMLResponse)
def forward(
    request: Request, forward: Texto, montante: Texto = "", cotacoes: Cotacoes = []
) -> HTMLResponse:
    try:
        m = parse_montante(montante)
        r, arb = calcular_forward(_grafo(cotacoes), forward)
    except (SemPercurso, CotacaoInvalida) as exc:
        return _erro(request, "forward_res", str(exc))
    # Sem arbitragem mas com forward de mercado (9 campos): a TUI mostra nota.
    tem_mercado = len(forward.split()) == 9
    return templates.TemplateResponse(
        request,
        "partials/_forward.html",
        {
            "r": forward_dict(r),
            "arb": arbitragem_prazo_dict(arb, m) if arb is not None else None,
            "tem_mercado": tem_mercado,
        },
    )


@app.post("/swap", response_class=HTMLResponse)
def swap(request: Request, swap: Texto, cotacoes: Cotacoes = []) -> HTMLResponse:
    try:
        r = calcular_swap(_grafo(cotacoes), swap)
    except (SemPercurso, CotacaoInvalida) as exc:
        return _erro(request, "swap_res", str(exc))
    return templates.TemplateResponse(
        request, "partials/_swap.html", {"r": para_dict(r)}
    )


@app.post("/hedge", response_class=HTMLResponse)
def hedge(request: Request, hedge: Texto, cotacoes: Cotacoes = []) -> HTMLResponse:
    try:
        r = calcular_hedge(_grafo(cotacoes), hedge)
    except (SemPercurso, CotacaoInvalida) as exc:
        return _erro(request, "hedge_res", str(exc))
    return templates.TemplateResponse(
        request, "partials/_hedge.html", {"r": para_dict(r)}
    )


def serve() -> None:
    """Entry-point ``cross-rates-web``: arranca o uvicorn em 127.0.0.1:8000."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
