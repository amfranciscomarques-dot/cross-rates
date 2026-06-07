"""Interface de terminal (TUI) da calculadora de cross-rates e arbitragem.

Construída sobre o núcleo puro (``cross_rates.nucleo``). Componentes:

* **Tabela de cotações** — todas as cotações introduzidas (par, bid, ask, spread).
* **Adicionar cotação** — escrever ``EUR USD 1.0850 1.0852``.
* **Calcular cross** — escrever ``EUR GBP``: bid/ask/spread, tipo, percurso,
  fórmulas e nota metodológica.
* **Arbitragem triangular** — procura ciclos de 3 moedas com ganho certo.
* **Painel de teoria** — enquadramento e regras (alternável com a tecla ``t``).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from cross_rates.nucleo import (
    Arbitragem,
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    SemPercurso,
    arbitragens_triangulares,
    cross,
)

# Exemplos do caderno para arranque rápido.
EXEMPLOS_CROSS = [  # Ex. 12 — sem arbitragem, ilustra cross direto/indireto
    ("GBP", "CAD", "1.8091", "1.8096"),
    ("CHF", "CAD", "1.7029", "1.7035"),
    ("CAD", "SEK", "6.5499", "6.5533"),
]
EXEMPLOS_ARBITRAGEM = [  # Ex. 17 — triângulo GBP/JPY/EUR com arbitragem
    ("GBP", "JPY", "212.646", "212.689"),
    ("EUR", "JPY", "183.618", "183.646"),
    ("GBP", "EUR", "1.1559", "1.1561"),
]

INTRO = (
    "[b]Cross-rates & arbitragem[/b] — bid/ask. Notação [b]BASE/COTADA[/b]: a "
    "BASE está [i]ao certo[/i], a COTADA [i]ao incerto[/i] (quantas unidades de "
    "COTADA valem 1 BASE), com bid ≤ ask. Tecla [b]t[/b]: teoria."
)

TEORIA = """[b u]Enquadramento teórico[/b u]

[b]1. Convenção A/B[/b]
A = base (ao certo, 1 unidade); B = cotada (ao incerto, valor variável).
O preço diz quantas unidades de B valem 1 A. Mostra-se [b]bid – ask[/b], bid ≤ ask.

[b]2. Regra de ouro do bid/ask[/b]
  • Banco/market maker: compra a base ao [b]bid[/b], vende ao [b]ask[/b].
  • Cliente/empresa: compra a base ao [b]ask[/b], vende ao [b]bid[/b].
  • Empresa: recebe ME → vai [b]vender[/b]; paga ME → vai [b]comprar[/b].
Spread = ask − bid (a margem do banco).

[b]3. Cross-rate (taxa cruzada)[/b]
Câmbio entre duas moedas sem cotação direta, via uma moeda-veículo.
Em cada conversão aplica-se a ponta [b]desfavorável[/b] ao cliente — passar por
uma moeda intermédia nunca contorna a margem.

  [b]Cross direto (÷)[/b] — moeda comum do mesmo lado nos dois pares:
     bid = bid(X/C) ÷ ask(Y/C)   ;   ask = ask(X/C) ÷ bid(Y/C)
  [b]Cross indireto (×)[/b] — moeda comum em lados opostos:
     bid = bid(C/X) × bid(C/Y)   ;   ask = ask(C/X) × ask(C/Y)

Identificar onde está a moeda comum (ao certo/ao incerto) é o passo decisivo.

[b]4. Arbitragem triangular[/b]
Inconsistência entre três pares na mesma praça. No grafo: um ciclo de 3 moedas
A→B→C→A cujo [b]produto das taxas[/b] (já com bid/ask) seja [b]> 1[/b].
     fator > 1  ⇒  ganho certo = (fator − 1) × montante inicial
Equivale a "cross implícito ≠ cotação direta". Risco nulo: pernas simultâneas.

[b]5. Como esta ferramenta calcula[/b]
Cada cotação BASE/COTADA gera duas conversões dirigidas:
  BASE→COTADA à taxa bid   ;   COTADA→BASE à taxa 1/ask.
bid do cross = taxa do percurso BASE→…→COTADA; ask = 1/(taxa COTADA→…→BASE).
"""


def _fmt(valor: Decimal, casas: int | None = None) -> str:
    """Formata um Decimal; com ``casas`` arredonda, senão remove zeros supérfluos."""
    if casas is not None:
        cota = Decimal(1).scaleb(-casas)
        return f"{valor.quantize(cota)}"
    return f"{valor.normalize():f}"


class CrossRatesApp(App):
    """Calculadora de cross-rates e arbitragem triangular, com bid/ask."""

    TITLE = "Calculadora de Cross-Rates — bid/ask"
    CSS = """
    #corpo { height: 1fr; }
    #esquerda { width: 3fr; padding: 0 1; }
    #direita { width: 2fr; padding: 0 1; border-left: solid $accent; }
    #resultado, #arb {
        height: auto; padding: 1; border: round $accent; margin: 1 0;
    }
    #teoria { padding: 1; }
    #intro { padding: 1; color: $text-muted; }
    .rotulo { color: $accent; padding: 1 0 0 0; text-style: bold; }
    .dica { color: $text-muted; }
    Input { margin: 0 0 1 0; }
    DataTable { height: auto; }
    """
    BINDINGS = [
        ("q", "quit", "Sair"),
        ("a", "arbitragem", "Arbitragem"),
        ("e", "exemplos_cross", "Ex. cross"),
        ("x", "exemplos_arbitragem", "Ex. arbitragem"),
        ("l", "limpar", "Limpar"),
        ("t", "teoria", "Teoria"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.grafo = GrafoCambial()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="corpo"):
            with VerticalScroll(id="esquerda"):
                yield Static(INTRO, id="intro")

                yield Label("Cotações", classes="rotulo")
                yield DataTable(id="tabela", zebra_stripes=True)

                yield Label("Adicionar cotação", classes="rotulo")
                yield Static(
                    "Formato BASE COTADA bid ask. A base está ao certo; bid ≤ ask.",
                    classes="dica",
                )
                yield Input(placeholder="ex.: EUR USD 1.0850 1.0852", id="add")

                yield Label("Calcular cross-rate", classes="rotulo")
                yield Static(
                    "BASE COTADA. bid = vender a base; ask = comprar a base "
                    "(ponta do cliente).",
                    classes="dica",
                )
                yield Input(placeholder="ex.: GBP SEK", id="calc")
                yield Static("Introduza cotações e calcule um cross.", id="resultado")

                yield Label("Arbitragem triangular  [tecla a]", classes="rotulo")
                yield Static(
                    "Procura ciclos de 3 moedas com fator > 1 (ganho certo). "
                    "Indique um montante para ver o lucro e a simulação.",
                    classes="dica",
                )
                yield Input(
                    placeholder="montante da moeda inicial (opcional, ex.: 1000000)",
                    id="montante",
                )
                yield Static("Sem análise de arbitragem ainda.", id="arb")
            with VerticalScroll(id="direita"):
                yield Static(TEORIA, id="teoria")
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
        self.query_one("#arb", Static).update("Sem análise de arbitragem ainda.")

    def action_exemplos_cross(self) -> None:
        for args in EXEMPLOS_CROSS:
            self._adicionar_cotacao(Cotacao(*args))
        self._info("Exemplos de cross carregados (Ex. 12). Tente: GBP CHF ou CHF SEK.")

    def action_exemplos_arbitragem(self) -> None:
        for args in EXEMPLOS_ARBITRAGEM:
            self._adicionar_cotacao(Cotacao(*args))
        self._info("Exemplos de arbitragem carregados (Ex. 17). Prima [a].")

    def action_teoria(self) -> None:
        painel = self.query_one("#direita", VerticalScroll)
        painel.display = not painel.display

    def action_arbitragem(self) -> None:
        montante = self._le_montante()
        if montante is False:  # entrada inválida
            return
        oportunidades = arbitragens_triangulares(self.grafo)
        self._mostrar_arbitragem(oportunidades, montante)

    # --- entradas ----------------------------------------------------------- #

    def on_input_submitted(self, evento: Input.Submitted) -> None:
        texto = evento.value.strip()
        if evento.input.id == "add" and texto:
            self._tratar_adicao(texto, evento.input)
        elif evento.input.id == "calc" and texto:
            self._tratar_calculo(texto)
        elif evento.input.id == "montante":
            self.action_arbitragem()

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
        try:
            r = cross(self.grafo, partes[0], partes[1])
        except (SemPercurso, CotacaoInvalida) as exc:
            self._erro(str(exc))
            return
        self._mostrar_resultado(r)

    def _le_montante(self) -> Decimal | None | bool:
        """Devolve o montante (Decimal), ``None`` se vazio, ``False`` se inválido."""
        texto = self.query_one("#montante", Input).value.strip().replace(",", ".")
        if not texto:
            return None
        try:
            valor = Decimal(texto)
            if valor <= 0:
                raise InvalidOperation
            return valor
        except InvalidOperation:
            self.query_one("#arb", Static).update(
                "[b red]Erro:[/b red] montante inválido (ex.: 1000000)."
            )
            return False

    # --- apresentação ------------------------------------------------------- #

    def _adicionar_cotacao(self, cotacao: Cotacao) -> None:
        self.grafo.adicionar(cotacao)
        self.query_one("#tabela", DataTable).add_row(
            cotacao.par, _fmt(cotacao.bid), _fmt(cotacao.ask), _fmt(cotacao.spread)
        )

    def _mostrar_resultado(self, r) -> None:
        texto = (
            f"[b]{r.par}[/b]  =  [green]{_fmt(r.bid)}[/green] – "
            f"[red]{_fmt(r.ask)}[/red]    (spread {_fmt(r.spread)})\n"
            f"[b]tipo:[/b] {r.tipo}    [b]percurso:[/b] {r.percurso_texto}\n"
            f"  {r.bid_formula}\n"
            f"  {r.ask_formula}\n"
            f"[i]{r.nota}[/i]"
        )
        self.query_one("#resultado", Static).update(texto)

    def _mostrar_arbitragem(
        self, oportunidades: list[Arbitragem], montante
    ) -> None:
        alvo = self.query_one("#arb", Static)
        if not oportunidades:
            alvo.update(
                "[b]Sem arbitragem triangular.[/b] Nenhum ciclo de 3 moedas tem "
                "fator > 1: os preços são mutuamente consistentes (intervalos "
                "implícito e direto sobrepõem-se)."
            )
            return

        linhas = [f"[b]{len(oportunidades)} oportunidade(s) de arbitragem:[/b]\n"]
        for i, arb in enumerate(oportunidades, 1):
            linhas.append(
                f"[b]{i}. {arb.ciclo_texto}[/b]  — fator {_fmt(arb.fator, 6)}  "
                f"([green]+{_fmt(arb.ganho_pct, 4)}%[/green])"
            )
            for passo in arb.passos:
                linhas.append(
                    f"    {passo.descricao} @ {_fmt(passo.taxa, 6)}"
                )
            if montante:
                sim = arb.simulacao(montante)
                cadeia = "  ".join(f"{_fmt(v, 2)} {m}" for m, v in sim)
                lucro = arb.lucro(montante)
                linhas.append(f"    {cadeia}")
                linhas.append(
                    f"    [b green]lucro ≈ +{_fmt(lucro, 2)} "
                    f"{arb.ciclo[0]}[/b green]"
                )
            linhas.append("")
        alvo.update("\n".join(linhas).rstrip())

    def _info(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(msg)

    def _erro(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(f"[b red]Erro:[/b red] {msg}")


def main() -> None:
    CrossRatesApp().run()


if __name__ == "__main__":
    main()
