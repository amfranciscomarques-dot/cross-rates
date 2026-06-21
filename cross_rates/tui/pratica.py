"""Ecrã de prática: exercícios guiados sobre cross-rates, arbitragem e forwards."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from cross_rates.nucleo import (
    Cotacao,
    GrafoCambial,
    TaxaJuro,
    arbitragem_a_prazo,
    arbitragens_geograficas,
    arbitragens_triangulares,
    cross,
    forward,
)
from cross_rates.tui.formato import fmt as _fmt


@dataclass
class Exercicio:
    id: str
    titulo: str
    categoria: str
    enunciado: str
    pergunta: str
    dica: str
    cotacoes: list[tuple]
    acao: str
    tolerancia: Decimal = field(default_factory=lambda: Decimal("0.0001"))


EXERCICIOS: list[Exercicio] = [
    Exercicio(
        id="ex12a",
        titulo="Ex. 12a — Cross direto (÷)",
        categoria="Cross",
        enunciado=(
            "Cotações (mesma praça):\n"
            "  GBP/CAD  bid 1.8091  ask 1.8096\n"
            "  CHF/CAD  bid 1.7029  ask 1.7035"
        ),
        pergunta="Calcule o cross-rate GBP/CHF.  Formato: bid ask",
        dica=(
            "Fluxo GBP → CAD → CHF: parte de 1 GBP.\n"
            "  1) GBP/CAD: tens a base GBP, vendes → × (recebes CAD).\n"
            "  2) CHF/CAD: tens CAD (cotada), compras CHF → ÷.\n"
            "CAD é a cotada em ambos os pares (mesmo lado) → cross direto (÷).\n"
            "  bid (vendes GBP) = bid(GBP/CAD) ÷ ask(CHF/CAD)\n"
            "  ask (compras GBP) = ask(GBP/CAD) ÷ bid(CHF/CAD)"
        ),
        cotacoes=[
            ("GBP", "CAD", "1.8091", "1.8096"),
            ("CHF", "CAD", "1.7029", "1.7035"),
        ],
        acao="cross GBP CHF",
    ),
    Exercicio(
        id="ex12b",
        titulo="Ex. 12b — Cross indireto (×)",
        categoria="Cross",
        enunciado=(
            "Cotações (mesma praça):\n"
            "  CHF/CAD  bid 1.7029  ask 1.7035\n"
            "  CAD/SEK  bid 6.5499  ask 6.5533"
        ),
        pergunta="Calcule o cross-rate CHF/SEK.  Formato: bid ask",
        dica=(
            "Fluxo CHF → CAD → SEK: parte de 1 CHF.\n"
            "  1) CHF/CAD: tens a base CHF, vendes → × (recebes CAD).\n"
            "  2) CAD/SEK: tens a base CAD, vendes → × (recebes SEK).\n"
            "CAD é cotada em CHF/CAD mas base em CAD/SEK (lados opostos) → cross indireto (×).\n"
            "  bid (vendes CHF) = bid(CHF/CAD) × bid(CAD/SEK)\n"
            "  ask (compras CHF) = ask(CHF/CAD) × ask(CAD/SEK)"
        ),
        cotacoes=[
            ("CHF", "CAD", "1.7029", "1.7035"),
            ("CAD", "SEK", "6.5499", "6.5533"),
        ],
        acao="cross CHF SEK",
    ),
    Exercicio(
        id="ex12c",
        titulo="Ex. 12c — Cross indireto (×)",
        categoria="Cross",
        enunciado=(
            "Cotações (mesma praça):\n"
            "  GBP/CAD  bid 1.8091  ask 1.8096\n"
            "  CAD/SEK  bid 6.5499  ask 6.5533"
        ),
        pergunta="Calcule o cross-rate GBP/SEK.  Formato: bid ask",
        dica=(
            "Fluxo GBP → CAD → SEK: parte de 1 GBP.\n"
            "  1) GBP/CAD: tens a base GBP, vendes → × (recebes CAD).\n"
            "  2) CAD/SEK: tens a base CAD, vendes → × (recebes SEK).\n"
            "CAD é cotada em GBP/CAD mas base em CAD/SEK (lados opostos) → cross indireto (×).\n"
            "  bid (vendes GBP) = bid(GBP/CAD) × bid(CAD/SEK)\n"
            "  ask (compras GBP) = ask(GBP/CAD) × ask(CAD/SEK)"
        ),
        cotacoes=[
            ("GBP", "CAD", "1.8091", "1.8096"),
            ("CAD", "SEK", "6.5499", "6.5533"),
        ],
        acao="cross GBP SEK",
    ),
    Exercicio(
        id="ex15",
        titulo="Ex. 15 — Arbitragem geográfica",
        categoria="Geográfica",
        enunciado=(
            "EUR/USD cotado em duas praças:\n"
            "  Paris    bid 1.1574  ask 1.1576\n"
            "  Londres  bid 1.1583  ask 1.1585"
        ),
        pergunta="Existe arbitragem geográfica?  Formato: sim  ou  não",
        dica=(
            "Compare ask_mínimo com bid_máximo:\n"
            "  ask(Paris) = 1.1576   bid(Londres) = 1.1583\n"
            "  Se ask < bid → comprar na praça mais barata, vender na mais cara."
        ),
        cotacoes=[
            ("EUR", "USD", "1.1574", "1.1576", "Paris"),
            ("EUR", "USD", "1.1583", "1.1585", "Londres"),
        ],
        acao="geografica",
    ),
    Exercicio(
        id="ex17",
        titulo="Ex. 17 — Arbitragem triangular",
        categoria="Triangular",
        enunciado=(
            "Cotações (mesma praça):\n"
            "  GBP/JPY  bid 212.646  ask 212.689\n"
            "  EUR/JPY  bid 183.618  ask 183.646\n"
            "  GBP/EUR  bid 1.1559   ask 1.1561"
        ),
        pergunta="Existe arbitragem triangular?  Formato: sim  ou  não",
        dica=(
            "Experimente o ciclo EUR→GBP→JPY→EUR:\n"
            "  EUR→GBP : 1 ÷ ask(GBP/EUR) = 1 ÷ 1.1561\n"
            "  GBP→JPY : bid(GBP/JPY) = 212.646\n"
            "  JPY→EUR : 1 ÷ ask(EUR/JPY) = 1 ÷ 183.646\n"
            "  fator = produto das três taxas; fator > 1 → arbitragem."
        ),
        cotacoes=[
            ("GBP", "JPY", "212.646", "212.689"),
            ("EUR", "JPY", "183.618", "183.646"),
            ("GBP", "EUR", "1.1559", "1.1561"),
        ],
        acao="triangular",
    ),
    Exercicio(
        id="ex27a",
        titulo="Ex. 27a — Forward PTJ 180 dias",
        categoria="Forward",
        enunciado=(
            "Spot CHF/USD:  bid 1.2745  ask 1.2748\n"
            "i_CHF (% a.a., base 360):  bid 0.1072  ask 0.1144\n"
            "i_USD (% a.a., base 360):  bid 4.9379  ask 4.9438\n"
            "Prazo: 180 dias"
        ),
        pergunta="Calcule o forward CHF/USD a 180 dias.  Formato: bid ask  (4 casas)",
        dica=(
            "F_bid = S_bid × (1 + i_bid_USD · 180/360) ÷ (1 + i_ask_CHF · 180/360)\n"
            "F_ask = S_ask × (1 + i_ask_USD · 180/360) ÷ (1 + i_bid_CHF · 180/360)\n"
            "i_USD > i_CHF → USD sobe a prazo → base CHF a prémio (F > S)."
        ),
        cotacoes=[("CHF", "USD", "1.2745", "1.2748")],
        acao="forward CHF USD 180 0.1072 0.1144 4.9379 4.9438",
    ),
    Exercicio(
        id="ex27b",
        titulo="Ex. 27b — Arbitragem a prazo",
        categoria="Forward",
        enunciado=(
            "Spot CHF/USD:  bid 1.2745  ask 1.2748\n"
            "i_CHF (% a.a., base 360):  bid 0.1072  ask 0.1144\n"
            "i_USD (% a.a., base 360):  bid 4.9379  ask 4.9438\n"
            "Prazo: 180 dias\n"
            "Forward de mercado:  bid 1.3076  ask 1.3079"
        ),
        pergunta="Existe arbitragem a prazo?  Formato: sim  ou  não",
        dica=(
            "Compare o forward de mercado com o intervalo de equilíbrio PTJ.\n"
            "  mercado_bid > equil_ask → base sobrevalorizada → vender base forward.\n"
            "  mercado_ask < equil_bid → base subvalorizada  → comprar base forward."
        ),
        cotacoes=[("CHF", "USD", "1.2745", "1.2748")],
        acao="forward CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079",
    ),
]


class PraticaScreen(Screen):
    """Ecrã de prática com exercícios guiados sobre cross-rates e arbitragem."""

    CSS = """
    PraticaScreen { layout: horizontal; }
    #lista-painel {
        width: 32;
        border-right: solid $accent;
        padding: 0 1;
    }
    #ex-painel { width: 1fr; padding: 1 2; }
    #titulo-ex {
        color: $accent;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #enunciado {
        height: auto;
        padding: 1;
        border: round $surface-darken-3;
        margin: 0 0 1 0;
    }
    #pergunta { padding: 0 0 1 0; }
    #dica-bloco {
        height: auto;
        padding: 1;
        border: round $warning;
        color: $warning;
        margin: 0 0 1 0;
    }
    #feedback {
        height: auto;
        padding: 1;
        border: round $surface-darken-3;
        margin: 0 0 1 0;
    }
    #nav-info { color: $text-muted; }
    Input { margin: 0 0 1 0; }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Fechar"),
        ("h", "dica", "Dica"),
        ("n", "proximo", "Seguinte"),
        ("b", "anterior", "Anterior"),
        ("r", "reset", "Limpar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._idx = 0
        self._dica_visivel = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="lista-painel"):
                yield Label("Exercicios", classes="rotulo")
                yield ListView(
                    *[
                        ListItem(
                            Label(f"[{ex.categoria}]\n{ex.titulo.split('—')[0].strip()}"),
                            id=f"item-{ex.id}",
                        )
                        for ex in EXERCICIOS
                    ],
                    id="lista",
                )
            with VerticalScroll(id="ex-painel"):
                yield Label("", id="titulo-ex")
                yield Static("", id="enunciado")
                yield Label("", id="pergunta")
                yield Input(placeholder="a sua resposta...", id="resposta")
                yield Static("", id="dica-bloco")
                yield Static("", id="feedback")
                yield Label("", id="nav-info")
        yield Footer()

    def on_mount(self) -> None:
        self._mostrar(0)

    def _mostrar(self, idx: int) -> None:
        self._idx = idx
        ex = EXERCICIOS[idx]
        self._dica_visivel = False
        self.query_one("#titulo-ex", Label).update(
            f"[{idx + 1}/{len(EXERCICIOS)}]  {ex.titulo}"
        )
        self.query_one("#enunciado", Static).update(ex.enunciado)
        self.query_one("#pergunta", Label).update(f"[b]{ex.pergunta}[/b]")
        self.query_one("#dica-bloco", Static).update("")
        self.query_one("#dica-bloco", Static).display = False
        self.query_one("#feedback", Static).update("")
        entrada = self.query_one("#resposta", Input)
        entrada.value = ""
        entrada.focus()
        partes_nav = ["n: seguinte"] if idx < len(EXERCICIOS) - 1 else []
        if idx > 0:
            partes_nav.append("b: anterior")
        partes_nav += ["h: dica", "r: limpar", "Esc: fechar"]
        self.query_one("#nav-info", Label).update(f"[dim]{'  |  '.join(partes_nav)}[/dim]")
        self.query_one("#lista", ListView).index = idx

    def action_dica(self) -> None:
        bloco = self.query_one("#dica-bloco", Static)
        if self._dica_visivel:
            bloco.display = False
            self._dica_visivel = False
        else:
            bloco.update(f"[b]Dica:[/b]\n{EXERCICIOS[self._idx].dica}")
            bloco.display = True
            self._dica_visivel = True

    def action_proximo(self) -> None:
        if self._idx < len(EXERCICIOS) - 1:
            self._mostrar(self._idx + 1)

    def action_anterior(self) -> None:
        if self._idx > 0:
            self._mostrar(self._idx - 1)

    def action_reset(self) -> None:
        self.query_one("#resposta", Input).value = ""
        self.query_one("#feedback", Static).update("")
        self.query_one("#resposta", Input).focus()

    def on_list_view_selected(self, evento: ListView.Selected) -> None:
        item_id = evento.item.id or ""
        ex_id = item_id.removeprefix("item-")
        for i, ex in enumerate(EXERCICIOS):
            if ex.id == ex_id:
                self._mostrar(i)
                break

    def on_input_submitted(self, evento: Input.Submitted) -> None:
        if evento.input.id == "resposta":
            self._verificar(evento.value.strip())

    def _verificar(self, resposta: str) -> None:
        if not resposta:
            return
        ex = EXERCICIOS[self._idx]
        grafo = GrafoCambial()
        for args in ex.cotacoes:
            grafo.adicionar(Cotacao(*args))
        try:
            resultado = _calcular(grafo, ex)
        except Exception as exc:
            self.query_one("#feedback", Static).update(f"[red]Erro interno: {exc}[/red]")
            return
        correto, detalhe = _avaliar(ex, resposta, resultado)
        cor = "green" if correto else "red"
        cabecalho = "Correto!" if correto else "Errado."
        self.query_one("#feedback", Static).update(
            f"[b {cor}]{cabecalho}[/b {cor}]\n{detalhe}"
        )


# --------------------------------------------------------------------------- #
# Lógica pura (fora da classe para facilitar testes)
# --------------------------------------------------------------------------- #


def _calcular(grafo: GrafoCambial, ex: Exercicio):
    p = ex.acao.split()
    if p[0] == "cross":
        return cross(grafo, p[1], p[2])
    if p[0] == "triangular":
        return arbitragens_triangulares(grafo)
    if p[0] == "geografica":
        return arbitragens_geograficas(grafo)
    if p[0] == "forward":
        base, cotada, dias = p[1], p[2], int(p[3])
        jb = TaxaJuro.de_moeda(base, p[4], p[5])
        jc = TaxaJuro.de_moeda(cotada, p[6], p[7])
        spot = grafo.cotacao_do_par(base, cotada)
        fwd = forward(spot, jb, jc, dias)
        if len(p) == 10:
            arb = arbitragem_a_prazo(spot, jb, jc, dias, p[8], p[9])
            return fwd, arb
        return fwd
    raise ValueError(f"Ação desconhecida: {p[0]!r}")


def _avaliar(ex: Exercicio, resposta: str, resultado) -> tuple[bool, str]:
    tipo = ex.acao.split()[0]

    if tipo == "cross":
        partes = resposta.replace(",", ".").split()
        if len(partes) != 2:
            return False, "Formato esperado: bid ask  (ex.: 1.0620 1.0626)."
        try:
            r_bid, r_ask = Decimal(partes[0]), Decimal(partes[1])
        except Exception:
            return False, "Valores numéricos inválidos."
        tol = ex.tolerancia
        ok = abs(r_bid - resultado.bid) <= tol and abs(r_ask - resultado.ask) <= tol
        return ok, (
            f"bid = {_fmt(resultado.bid, 4)}   ask = {_fmt(resultado.ask, 4)}\n"
            f"Tipo: {resultado.tipo}\n"
            f"Percurso: {resultado.percurso_texto}\n"
            f"{resultado.bid_formula}\n{resultado.ask_formula}\n"
            f"[i]{resultado.nota}[/i]"
        )

    if tipo in ("triangular", "geografica"):
        tem = len(resultado) > 0
        norm = resposta.lower().strip().rstrip(".")
        if norm not in ("sim", "não", "nao"):
            return False, "Resposta esperada: sim  ou  não."
        ok = (norm == "sim") == tem
        if tem and tipo == "triangular":
            arb = resultado[0]
            detalhe = (
                f"Ciclo: {arb.ciclo_texto}\n"
                f"Fator: {_fmt(arb.fator, 6)}  (+{_fmt(arb.ganho_pct, 4)}%)\n"
                + "\n".join(f"  {p.descricao}" for p in arb.passos)
            )
        elif tem:
            arb = resultado[0]
            detalhe = (
                f"Comprar {arb.par} em {arb.fonte_compra} @ ask {_fmt(arb.ask_compra)}\n"
                f"Vender  {arb.par} em {arb.fonte_venda} @ bid {_fmt(arb.bid_venda)}\n"
                f"Ganho: {_fmt(arb.ganho_pct, 4)}%"
            )
        else:
            detalhe = "Sem arbitragem: os preços são mutuamente consistentes."
        return ok, detalhe

    if tipo == "forward":
        tem_mercado = len(ex.acao.split()) == 10
        if tem_mercado:
            fwd, arb = resultado
            tem = arb is not None
            norm = resposta.lower().strip().rstrip(".")
            if norm not in ("sim", "não", "nao"):
                return False, "Resposta esperada: sim  ou  não."
            ok = (norm == "sim") == tem
            detalhe = (
                f"Forward equilíbrio: {_fmt(fwd.bid, 4)} – {_fmt(fwd.ask, 4)}\n"
                + (
                    f"Forward mercado:    {_fmt(arb.mercado_bid, 4)} – {_fmt(arb.mercado_ask, 4)}\n"
                    f"→ {arb.sentido}"
                    if tem
                    else "Mercado dentro do intervalo de equilíbrio (sem arbitragem)."
                )
            )
            return ok, detalhe
        else:
            fwd = resultado
            partes = resposta.replace(",", ".").split()
            if len(partes) != 2:
                return False, "Formato esperado: bid ask  (ex.: 1.3053 1.3057)."
            try:
                r_bid, r_ask = Decimal(partes[0]), Decimal(partes[1])
            except Exception:
                return False, "Valores numéricos inválidos."
            tol = ex.tolerancia
            ok = abs(r_bid - fwd.bid) <= tol and abs(r_ask - fwd.ask) <= tol
            return ok, (
                f"bid = {_fmt(fwd.bid, 4)}   ask = {_fmt(fwd.ask, 4)}\n"
                f"{fwd.bid_formula}\n{fwd.ask_formula}\n"
                f"Base a [b]{fwd.sinal}[/b]\n[i]{fwd.nota}[/i]"
            )

    return False, "Tipo de exercício desconhecido."
