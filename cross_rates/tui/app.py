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
    ArbitragemGeografica,
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    SemPercurso,
    TaxaJuro,
    arbitragem_a_prazo,
    arbitragens_geograficas,
    arbitragens_triangulares,
    cross,
    forward,
    normaliza_moeda,
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
EXEMPLOS_GEOGRAFICA = [  # Ex. 15 — EUR/USD em duas praças
    ("EUR", "USD", "1.1574", "1.1576", "Paris"),
    ("EUR", "USD", "1.1583", "1.1585", "Londres"),
]
EXEMPLOS_FORWARD_SPOT = ("CHF", "USD", "1.2745", "1.2748")  # Ex. 27 (spot)
# Forward CHF/USD a 180d + forward de mercado 1,3076–1,3079 (tem arbitragem):
EXEMPLO_FORWARD_INPUT = "CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079"

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

[b]4. Arbitragem geográfica (espacial)[/b]
Mesmo par cotado em praças diferentes. Há ganho certo se o [b]ask mais baixo[/b]
(onde se compra a base) for inferior ao [b]bid mais alto[/b] (onde se vende):
     ask(praça A) < bid(praça B)  ⇒  compra em A, vende em B
Indique a praça/banco na cotação (5.º campo). Ganho na moeda cotada.

[b]5. Arbitragem triangular[/b]
Inconsistência entre três pares na mesma praça. No grafo: um ciclo de 3 moedas
A→B→C→A cujo [b]produto das taxas[/b] (já com bid/ask) seja [b]> 1[/b].
     fator > 1  ⇒  ganho certo = (fator − 1) × montante inicial
Equivale a "cross implícito ≠ cotação direta". Risco nulo: pernas simultâneas.

[b]6. Forward (taxa a prazo) — Paridade das Taxas de Juro (PTJ)[/b]
Câmbio fixado hoje para troca numa data futura. A taxa de equilíbrio é a que
impede a arbitragem com a réplica no mercado monetário (não é uma previsão):
     F = S × (1 + i_cotada·n/360) ÷ (1 + i_base·n/360)
  • i_cotada > i_base → F > S: base a [b]prémio[/b].
  • i_cotada < i_base → F < S: base a [b]desconto[/b].
Com bid/ask: F_bid usa i_bid(cotada) e i_ask(base); F_ask troca as pontas.
[b]Arbitragem a prazo:[/b] se o forward de mercado sai do intervalo de
equilíbrio, vende-se o que está caro e replica-se via MMI o que está barato.

[b]7. Como esta ferramenta calcula[/b]
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
    #resultado, #arb, #forward_res {
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
        ("x", "exemplos_arbitragem", "Ex. triangular"),
        ("g", "exemplos_geografica", "Ex. geográfica"),
        ("f", "exemplos_forward", "Ex. forward"),
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
                    "Formato BASE COTADA bid ask [fonte]. A base está ao certo; "
                    "bid ≤ ask. A fonte (praça/banco) é opcional, p/ arbitragem "
                    "geográfica.",
                    classes="dica",
                )
                yield Input(placeholder="ex.: EUR USD 1.1574 1.1576 Paris", id="add")

                yield Label("Calcular cross-rate", classes="rotulo")
                yield Static(
                    "BASE COTADA. bid = vender a base; ask = comprar a base "
                    "(ponta do cliente).",
                    classes="dica",
                )
                yield Input(placeholder="ex.: GBP SEK", id="calc")
                yield Static("Introduza cotações e calcule um cross.", id="resultado")

                yield Label("Arbitragem (geográfica + triangular)  [tecla a]", classes="rotulo")
                yield Static(
                    "Procura ganhos certos: mesmo par em praças diferentes e "
                    "ciclos de 3 moedas (fator > 1). Indique um montante para "
                    "ver o lucro e a simulação.",
                    classes="dica",
                )
                yield Input(
                    placeholder="montante da moeda inicial (opcional, ex.: 1000000)",
                    id="montante",
                )
                yield Static("Sem análise de arbitragem ainda.", id="arb")

                yield Label("Forward (taxa a prazo, PTJ)  [tecla f]", classes="rotulo")
                yield Static(
                    "BASE COTADA dias  i_base(bid ask)  i_cotada(bid ask)  "
                    "[fwd_bid fwd_ask]. O spot vem da tabela; juros em % anual "
                    "(base 360). Com o forward de mercado no fim, verifica também "
                    "a arbitragem a prazo (usa o montante acima, na base).",
                    classes="dica",
                )
                yield Input(
                    placeholder="ex.: CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079",
                    id="forward",
                )
                yield Static("Sem cálculo de forward ainda.", id="forward_res")
            with VerticalScroll(id="direita"):
                yield Static(TEORIA, id="teoria")
        yield Footer()

    def on_mount(self) -> None:
        tabela = self.query_one("#tabela", DataTable)
        tabela.add_columns("Par", "bid", "ask", "spread", "fonte")
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
        self._info("Exemplos de arbitragem triangular carregados (Ex. 17). Prima [a].")

    def action_exemplos_geografica(self) -> None:
        for args in EXEMPLOS_GEOGRAFICA:
            self._adicionar_cotacao(Cotacao(*args))
        self._info("Exemplos de arbitragem geográfica carregados (Ex. 15). Prima [a].")

    def action_exemplos_forward(self) -> None:
        self._adicionar_cotacao(Cotacao(*EXEMPLOS_FORWARD_SPOT))
        self.query_one("#forward", Input).value = EXEMPLO_FORWARD_INPUT
        self._info(
            "Exemplo de forward carregado (Ex. 27): spot CHF/USD na tabela e o "
            "input preenchido com juros e forward de mercado. Prima Enter no "
            "campo de forward (tem arbitragem a prazo)."
        )

    def action_teoria(self) -> None:
        painel = self.query_one("#direita", VerticalScroll)
        painel.display = not painel.display

    def action_arbitragem(self) -> None:
        montante = self._le_montante()
        if montante is False:  # entrada inválida
            return
        geograficas = arbitragens_geograficas(self.grafo)
        triangulares = arbitragens_triangulares(self.grafo)
        self._mostrar_arbitragem(geograficas, triangulares, montante)

    # --- entradas ----------------------------------------------------------- #

    def on_input_submitted(self, evento: Input.Submitted) -> None:
        texto = evento.value.strip()
        if evento.input.id == "add" and texto:
            self._tratar_adicao(texto, evento.input)
        elif evento.input.id == "calc" and texto:
            self._tratar_calculo(texto)
        elif evento.input.id == "montante":
            self.action_arbitragem()
        elif evento.input.id == "forward" and texto:
            self._tratar_forward(texto)

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

    def _tratar_forward(self, texto: str) -> None:
        partes = texto.replace(",", ".").split()
        if len(partes) not in (7, 9):
            self._erro_forward(
                "Formato: BASE COTADA dias i_base_bid i_base_ask i_cot_bid "
                "i_cot_ask [fwd_bid fwd_ask]."
            )
            return
        base, cotada, dias = partes[0], partes[1], partes[2]
        spot = self._spot_para(base, cotada)
        if spot is None:
            self._erro_forward(
                f"Sem spot {base.upper()}/{cotada.upper()} na tabela — adicione a "
                "cotação à vista primeiro."
            )
            return
        try:
            n = int(dias)
            juro_base = TaxaJuro(base, partes[3], partes[4])
            juro_cotada = TaxaJuro(cotada, partes[5], partes[6])
            r = forward(spot, juro_base, juro_cotada, n)
            arb = None
            if len(partes) == 9:
                arb = arbitragem_a_prazo(
                    spot, juro_base, juro_cotada, n, partes[7], partes[8]
                )
        except (CotacaoInvalida, ValueError) as exc:
            self._erro_forward(str(exc))
            return
        self._mostrar_forward(r, arb)

    def _spot_para(self, base: str, cotada: str) -> Cotacao | None:
        """Spot ``base/cotada`` a partir da tabela (invertendo se necessário)."""
        c = self.grafo.cotacao_do_par(base, cotada)
        if c is None:
            return None
        base, cotada = normaliza_moeda(base), normaliza_moeda(cotada)
        if c.base == base and c.cotada == cotada:
            return c
        # cotação na orientação inversa: bid' = 1/ask, ask' = 1/bid
        return Cotacao(base, cotada, Decimal(1) / c.ask, Decimal(1) / c.bid)

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
            cotacao.par,
            _fmt(cotacao.bid),
            _fmt(cotacao.ask),
            _fmt(cotacao.spread),
            cotacao.fonte or "—",
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
        self,
        geograficas: list[ArbitragemGeografica],
        triangulares: list[Arbitragem],
        montante,
    ) -> None:
        alvo = self.query_one("#arb", Static)
        if not geograficas and not triangulares:
            alvo.update(
                "[b]Sem arbitragem.[/b] Nenhum par em praças diferentes tem "
                "ask < bid cruzado, e nenhum ciclo de 3 moedas tem fator > 1: "
                "os preços são mutuamente consistentes."
            )
            return

        linhas: list[str] = []
        if geograficas:
            linhas.append("[b u]Arbitragem geográfica[/b u]")
            for i, arb in enumerate(geograficas, 1):
                linhas.append(
                    f"[b]{i}. {arb.par}[/b]  comprar em {arb.fonte_compra} @ ask "
                    f"{_fmt(arb.ask_compra)} → vender em {arb.fonte_venda} @ bid "
                    f"{_fmt(arb.bid_venda)}  ([green]+{_fmt(arb.ganho_pct, 4)}%[/green])"
                )
                if montante:
                    for passo in arb.simulacao(montante):
                        linhas.append(f"    {passo}")
            linhas.append("")

        if triangulares:
            linhas.append("[b u]Arbitragem triangular[/b u]")
            for i, arb in enumerate(triangulares, 1):
                linhas.append(
                    f"[b]{i}. {arb.ciclo_texto}[/b]  — fator {_fmt(arb.fator, 6)}  "
                    f"([green]+{_fmt(arb.ganho_pct, 4)}%[/green])"
                )
                for passo in arb.passos:
                    linhas.append(f"    {passo.descricao} @ {_fmt(passo.taxa, 6)}")
                if montante:
                    sim = arb.simulacao(montante)
                    cadeia = "  ".join(f"{_fmt(v, 2)} {m}" for m, v in sim)
                    linhas.append(f"    {cadeia}")
                    linhas.append(
                        f"    [b green]lucro ≈ +{_fmt(arb.lucro(montante), 2)} "
                        f"{arb.ciclo[0]}[/b green]"
                    )
            linhas.append("")
        alvo.update("\n".join(linhas).rstrip())

    def _mostrar_forward(self, r, arb) -> None:
        linhas = [
            f"[b]{r.par}[/b] forward {r.dias}d  =  [green]{_fmt(r.bid, 4)}[/green] – "
            f"[red]{_fmt(r.ask, 4)}[/red]    (spread {_fmt(r.spread, 4)})",
            f"[b]spot:[/b] {_fmt(r.spot_bid)} – {_fmt(r.spot_ask)}    "
            f"[b]pontos:[/b] {_fmt(r.pontos_bid, 4)} / {_fmt(r.pontos_ask, 4)}    "
            f"[b]base a {r.sinal}[/b]",
            f"  {r.bid_formula}",
            f"  {r.ask_formula}",
            f"[i]{r.nota}[/i]",
        ]
        if arb is not None:
            montante = self._le_montante()
            linhas.append("")
            linhas.append("[b u]Arbitragem a prazo[/b u]")
            linhas.append(
                f"  mercado {_fmt(arb.mercado_bid, 4)}–{_fmt(arb.mercado_ask, 4)} "
                f"vs equilíbrio {_fmt(arb.equilibrio_bid, 4)}–"
                f"{_fmt(arb.equilibrio_ask, 4)}"
            )
            linhas.append(
                f"  → [b]{arb.sentido}[/b] @ {_fmt(arb.taxa_mercado, 4)}; "
                f"sintético {_fmt(arb.sintetico, 6)}  "
                f"([green]+{_fmt(arb.ganho_pct, 4)}%[/green])"
            )
            if isinstance(montante, Decimal):
                linhas.append(
                    f"  lucro ≈ [b green]+{_fmt(arb.lucro(montante), 2)} "
                    f"{arb.cotada}[/b green]  (por {_fmt(montante)} {arb.base})"
                )
        elif len(self.query_one("#forward", Input).value.split()) == 9:
            linhas.append("")
            linhas.append(
                "[b]Sem arbitragem a prazo:[/b] o forward de mercado está dentro "
                "do intervalo de equilíbrio (preços consistentes com a PTJ)."
            )
        self.query_one("#forward_res", Static).update("\n".join(linhas))

    def _erro_forward(self, msg: str) -> None:
        self.query_one("#forward_res", Static).update(f"[b red]Erro:[/b red] {msg}")

    def _info(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(msg)

    def _erro(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(f"[b red]Erro:[/b red] {msg}")


def main() -> None:
    CrossRatesApp().run()


if __name__ == "__main__":
    main()
