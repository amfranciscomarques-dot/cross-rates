"""Interface de terminal (TUI) da calculadora de cross-rates.

Construída sobre o núcleo puro (``cross_rates.nucleo``). Componentes:

* **Tabela de cotações** — todas as cotações introduzidas (par, bid, ask, spread).
* **Adicionar cotação** — escrever ``EUR USD 1.0850 1.0852``.
* **Calcular cross** — escrever ``EUR GBP`` e ver bid/ask/spread, o tipo
  (direta / cross direto ÷ / indireto ×) e o percurso usado.
"""

from __future__ import annotations

from decimal import Decimal

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from cross_rates.nucleo import Cotacao, CotacaoInvalida, GrafoCambial, SemPercurso, cross

# Cotações de exemplo (Ex. 12 do caderno) para arranque rápido / demonstração.
EXEMPLOS = [
    ("GBP", "CAD", "1.8091", "1.8096"),
    ("CHF", "CAD", "1.7029", "1.7035"),
    ("CAD", "SEK", "6.5499", "6.5533"),
]


def _fmt(valor: Decimal) -> str:
    """Formata um Decimal sem zeros/expoentes supérfluos."""
    return f"{valor.normalize():f}"


class CrossRatesApp(App):
    """Calculadora de cross-rates com bid/ask."""

    TITLE = "Calculadora de Cross-Rates — bid/ask"
    CSS = """
    #painel { height: auto; padding: 0 1; }
    #resultado { height: auto; padding: 1; border: round $accent; margin: 1 0; }
    .rotulo { color: $text-muted; padding: 1 1 0 1; }
    Input { margin: 0 1 1 1; }
    DataTable { height: auto; margin: 0 1; }
    """
    BINDINGS = [
        ("q", "quit", "Sair"),
        ("l", "limpar", "Limpar tabela"),
        ("e", "exemplos", "Carregar exemplos"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.grafo = GrafoCambial()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="painel"):
            yield Label("Cotações", classes="rotulo")
            yield DataTable(id="tabela", zebra_stripes=True)
            yield Label("Adicionar cotação  (BASE COTADA bid ask)", classes="rotulo")
            yield Input(placeholder="ex.: EUR USD 1.0850 1.0852", id="add")
            yield Label("Calcular cross  (BASE COTADA)", classes="rotulo")
            yield Input(placeholder="ex.: GBP SEK", id="calc")
            yield Static("Introduza cotações e calcule um cross.", id="resultado")
        yield Footer()

    def on_mount(self) -> None:
        tabela = self.query_one("#tabela", DataTable)
        tabela.add_columns("Par", "bid", "ask", "spread")
        tabela.cursor_type = "row"

    # --- ações de teclado --------------------------------------------------- #

    def action_limpar(self) -> None:
        self.grafo.limpar()
        self.query_one("#tabela", DataTable).clear()
        self._info("Tabela limpa.")

    def action_exemplos(self) -> None:
        for args in EXEMPLOS:
            self._adicionar_cotacao(Cotacao(*args))
        self._info("Exemplos carregados (Ex. 12). Experimente: GBP CHF ou CHF SEK.")

    # --- entradas ----------------------------------------------------------- #

    def on_input_submitted(self, evento: Input.Submitted) -> None:
        texto = evento.value.strip()
        if not texto:
            return
        if evento.input.id == "add":
            self._tratar_adicao(texto, evento.input)
        elif evento.input.id == "calc":
            self._tratar_calculo(texto)

    def _tratar_adicao(self, texto: str, campo: Input) -> None:
        try:
            cotacao = Cotacao.de_texto(texto)
        except CotacaoInvalida as exc:
            self._erro(str(exc))
            return
        self._adicionar_cotacao(cotacao)
        campo.value = ""
        self._info(f"Cotação adicionada: {cotacao}")

    def _tratar_calculo(self, texto: str) -> None:
        partes = texto.upper().split()
        if len(partes) != 2:
            self._erro("Formato esperado: BASE COTADA (ex.: GBP SEK).")
            return
        base, cotada = partes
        try:
            r = cross(self.grafo, base, cotada)
        except (SemPercurso, CotacaoInvalida) as exc:
            self._erro(str(exc))
            return
        self._mostrar_resultado(r)

    # --- apresentação ------------------------------------------------------- #

    def _adicionar_cotacao(self, cotacao: Cotacao) -> None:
        self.grafo.adicionar(cotacao)
        self.query_one("#tabela", DataTable).add_row(
            cotacao.par, _fmt(cotacao.bid), _fmt(cotacao.ask), _fmt(cotacao.spread)
        )

    def _mostrar_resultado(self, r) -> None:
        texto = (
            f"[b]{r.par}[/b]  =  [green]{_fmt(r.bid)}[/green] – "
            f"[red]{_fmt(r.ask)}[/red]\n"
            f"spread: {_fmt(r.spread)}\n"
            f"tipo:   {r.tipo}\n"
            f"percurso: {r.percurso_texto}"
        )
        self.query_one("#resultado", Static).update(texto)

    def _info(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(msg)

    def _erro(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(f"[b red]Erro:[/b red] {msg}")


def main() -> None:
    CrossRatesApp().run()


if __name__ == "__main__":
    main()
