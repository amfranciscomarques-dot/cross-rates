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

from decimal import Decimal

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from cross_rates.nucleo import (
    Arbitragem,
    ArbitragemGeografica,
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    SemPercurso,
)
from cross_rates.servico import (
    EXEMPLO_FORWARD_INPUT,
    EXEMPLO_OPCAO_INPUT,
    EXEMPLOS_ARBITRAGEM,
    EXEMPLOS_CROSS,
    EXEMPLOS_FORWARD_SPOT,
    EXEMPLOS_GEOGRAFICA,
    EXEMPLOS_OPCAO_SPOT,
    analisar_arbitragem,
    calcular_cross,
    calcular_forward,
    calcular_hedge,
    calcular_opcao,
    calcular_swap,
    parse_montante,
)
from cross_rates.tui.formato import fmt as _fmt
from cross_rates.tui.pratica import PraticaScreen

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
Câmbio entre duas moedas sem cotação direta, via uma moeda-veículo C.
Em cada conversão aplica-se a ponta [b]desfavorável[/b] ao cliente — passar por
uma moeda intermédia nunca contorna a margem.

  [b]Ótica dos fluxos (compra/venda)[/b] — para achar X/Y, parte de [b]1 X[/b] e
  segue a cadeia de trocas [b]X → C → Y[/b]. Em cada perna, vê o que tens nesse
  par e o que queres obter:
     • tens a BASE e queres a COTADA  → [b]× taxa[/b]  (vendes a base, recebes cotada)
     • tens a COTADA e queres a BASE  → [b]÷ taxa[/b]  (gastas cotada p/ comprar base)
  O "direto/indireto" é apenas o efeito líquido destas duas pernas — depende de
  que lado a moeda comum C ocupa (ao certo/ao incerto) em cada par:

  [b]Cross direto (÷)[/b] — C do [b]mesmo lado[/b] nos dois pares (ex.: X/C e Y/C):
     X →[× X/C]→ C →[÷ Y/C]→ Y   ⇒   X/Y = (X/C) ÷ (Y/C)
     bid = bid(X/C) ÷ ask(Y/C)   ;   ask = ask(X/C) ÷ bid(Y/C)
  [b]Cross indireto (×)[/b] — C em [b]lados opostos[/b] (ex.: X/C e C/Y):
     X →[× X/C]→ C →[× C/Y]→ Y   ⇒   X/Y = (X/C) × (C/Y)
     bid = bid(X/C) × bid(C/Y)   ;   ask = ask(X/C) × ask(C/Y)

  [b]Porquê estas pontas no bid/ask[/b]: o [b]bid[/b] do cross é o percurso em que
  o cliente [b]vende X[/b] (acaba com Y); o [b]ask[/b] é o inverso, [b]compra X[/b].
  Em cada perna do fluxo usa-se sempre a ponta pior p/ o cliente — vende ao bid,
  compra ao ask — por isso o bid e o ask do cross misturam bids e asks dos pares.

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

[b]8. Opções cambiais (Garman-Kohlhagen)[/b]
Opção vanilla sobre BASE/COTADA: a BASE é o ativo (rende r_f), a COTADA o
numerário (rende r_d). Black-Scholes adaptado a divisas:
     call = S·e^(−r_f·T)·N(d1) − K·e^(−r_d·T)·N(d2)
     d1 = [ln(S/K) + (r_d − r_f + σ²/2)·T] / (σ·√T) ; d2 = d1 − σ·√T
Prémio em COTADA por 1 BASE. [b]Gregas:[/b] delta (spot), gamma (delta), vega
(vol), theta (tempo), rho (taxa doméstica). Paridade put-call:
     C − P = S·e^(−r_f·T) − K·e^(−r_d·T).
"""


class PedeFicheiroModal(ModalScreen[str]):
    """Modal para pedir o nome do ficheiro para salvar/abrir cenário."""
    
    def __init__(self, titulo: str) -> None:
        super().__init__()
        self.titulo = titulo

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_dialog"):
            yield Label(self.titulo, classes="rotulo")
            yield Input(placeholder="ex.: exame_2023.txt", id="ficheiro_input")
            yield Label("Pressione Enter para confirmar, Esc para cancelar", classes="dica")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss("")


class CrossRatesApp(App):
    """Calculadora de cross-rates e arbitragem triangular, com bid/ask."""

    TITLE = "Calculadora de Cross-Rates — bid/ask"
    CSS = """
    #corpo { height: 1fr; }
    #esquerda { width: 3fr; padding: 0 1; }
    #direita { width: 2fr; padding: 0 1; border-left: solid $accent; }
    #resultado, #arb, #forward_res, #swap_res, #hedge_res, #opcao_res {
        height: auto; padding: 1; border: round $accent; margin: 1 0;
    }
    #teoria { padding: 1; }
    #intro { padding: 1; color: $text-muted; }
    .rotulo { color: $accent; padding: 1 0 0 0; text-style: bold; }
    .dica { color: $text-muted; }
    Input { margin: 0 0 1 0; }
    DataTable { height: auto; }
    #modal_dialog {
        width: 60;
        height: auto;
        padding: 2;
        background: $surface;
        border: thick $primary;
        align: center middle;
    }
    """
    BINDINGS = [
        ("q", "quit", "Sair"),
        ("p", "pratica", "Prática"),
        ("a", "arbitragem", "Arbitragem"),
        ("e", "exemplos_cross", "Ex. cross"),
        ("x", "exemplos_arbitragem", "Ex. triangular"),
        ("g", "exemplos_geografica", "Ex. geográfica"),
        ("f", "exemplos_forward", "Ex. forward"),
        ("k", "exemplos_opcao", "Ex. opção"),
        ("l", "limpar", "Limpar"),
        ("s", "salvar_cenario", "Salvar Cenário"),
        ("o", "abrir_cenario", "Abrir Cenário"),
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

                yield Label("Swaps (Pontos Forward)", classes="rotulo")
                yield Static(
                    "BASE COTADA pontos_bid pontos_ask [casas_decimais]. "
                    "O spot tem de estar na tabela. Padrão: 4 casas decimais.",
                    classes="dica",
                )
                yield Input(placeholder="ex.: EUR USD 20 30", id="swap")
                yield Static("Sem cálculo de swap ainda.", id="swap_res")

                yield Label("Hedging (Cobertura de Risco)", classes="rotulo")
                yield Static(
                    "TIPO MONTANTE BASE COTADA dias i_base(b a) i_cotada(b a) "
                    "[strike vol]. TIPO = recebimento | pagamento. A Moeda "
                    "Estrangeira será sempre a COTADA. Com strike e vol (% anual) "
                    "acrescenta a cobertura com opção (GK).",
                    classes="dica",
                )
                yield Input(
                    placeholder="ex.: pagamento 500000 EUR USD 90 3.1 3.2 4.5 4.6",
                    id="hedge",
                )
                yield Static("Sem análise de hedging ainda.", id="hedge_res")

                yield Label("Opções cambiais (Garman-Kohlhagen)  [tecla k]", classes="rotulo")
                yield Static(
                    "TIPO BASE COTADA strike dias vol i_base(b a) i_cotada(b a) "
                    "[notional]. TIPO = call | put; vol em % anual; o spot vem da "
                    "tabela. Prémio em COTADA por 1 BASE, com delta/gamma/vega/"
                    "theta/rho.",
                    classes="dica",
                )
                yield Input(
                    placeholder="ex.: call EUR USD 1.1000 180 10 2.9 3.1 4.9 5.1 1000000",
                    id="opcao",
                )
                yield Static("Sem avaliação de opção ainda.", id="opcao_res")
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

    def action_exemplos_opcao(self) -> None:
        self._adicionar_cotacao(Cotacao(*EXEMPLOS_OPCAO_SPOT))
        self.query_one("#opcao", Input).value = EXEMPLO_OPCAO_INPUT
        self._info(
            "Exemplo de opção carregado: spot EUR/USD na tabela e o input "
            "preenchido (call ATM 180d, vol 10%). Prima Enter no campo de opção."
        )

    def action_pratica(self) -> None:
        self.push_screen(PraticaScreen())

    def action_teoria(self) -> None:
        painel = self.query_one("#direita", VerticalScroll)
        painel.display = not painel.display

    def action_arbitragem(self) -> None:
        montante = self._le_montante()
        if montante is False:  # entrada inválida
            return
        geograficas, triangulares = analisar_arbitragem(self.grafo)
        self._mostrar_arbitragem(geograficas, triangulares, montante)

    def action_salvar_cenario(self) -> None:
        def callback(ficheiro: str) -> None:
            if not ficheiro:
                return
            try:
                with open(ficheiro, "w", encoding="utf-8") as f:
                    for c in self.grafo.cotacoes:
                        fonte = c.fonte if c.fonte else ""
                        linha = f"{c.base} {c.cotada} {c.bid} {c.ask} {fonte}".strip()
                        f.write(linha + "\n")
                self._info(f"Cenário salvo em: {ficheiro}")
            except Exception as e:
                self._erro(f"Falha ao salvar cenário: {e}")

        self.push_screen(PedeFicheiroModal("Nome do ficheiro para salvar:"), callback)

    def action_abrir_cenario(self) -> None:
        def callback(ficheiro: str) -> None:
            if not ficheiro:
                return
            try:
                novas_cotacoes = []
                with open(ficheiro, encoding="utf-8") as f:
                    for linha in f:
                        linha = linha.strip()
                        if linha and not linha.startswith("#"):
                            novas_cotacoes.append(Cotacao.de_texto(linha))
                
                self.action_limpar()
                for c in novas_cotacoes:
                    self._adicionar_cotacao(c)
                self._info(f"Cenário aberto: {ficheiro}")
            except FileNotFoundError:
                self._erro(f"Ficheiro não encontrado: {ficheiro}")
            except Exception as e:
                self._erro(f"Falha ao abrir cenário: {e}")

        self.push_screen(PedeFicheiroModal("Nome do ficheiro para abrir:"), callback)

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
        elif evento.input.id == "swap" and texto:
            self._tratar_swap(texto)
        elif evento.input.id == "hedge" and texto:
            self._tratar_hedge(texto)
        elif evento.input.id == "opcao" and texto:
            self._tratar_opcao(texto)

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
        try:
            r = calcular_cross(self.grafo, texto)
        except (SemPercurso, CotacaoInvalida) as exc:
            self._erro(str(exc))
            return
        self._mostrar_resultado(r)

    def _tratar_forward(self, texto: str) -> None:
        try:
            r, arb = calcular_forward(self.grafo, texto)
        except (CotacaoInvalida, SemPercurso) as exc:
            self._erro_forward(str(exc))
            return
        self._mostrar_forward(r, arb)

    def _tratar_swap(self, texto: str) -> None:
        try:
            r = calcular_swap(self.grafo, texto)
        except (CotacaoInvalida, SemPercurso) as exc:
            self._erro_swap(str(exc))
            return
        self._mostrar_swap(r)

    def _tratar_hedge(self, texto: str) -> None:
        try:
            r = calcular_hedge(self.grafo, texto)
        except (CotacaoInvalida, SemPercurso) as exc:
            self._erro_hedge(str(exc))
            return
        self._mostrar_hedge(r)

    def _tratar_opcao(self, texto: str) -> None:
        try:
            r = calcular_opcao(self.grafo, texto)
        except (CotacaoInvalida, SemPercurso) as exc:
            self._erro_opcao(str(exc))
            return
        self._mostrar_opcao(r)

    def _le_montante(self) -> Decimal | None | bool:
        """Devolve o montante (Decimal), ``None`` se vazio, ``False`` se inválido."""
        try:
            return parse_montante(self.query_one("#montante", Input).value)
        except CotacaoInvalida:
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

    def _mostrar_swap(self, r) -> None:
        cd = r.casas_decimais_pontos
        linhas = [
            f"[b]{r.par}[/b] outright (via swap) = "
            f"[green]{_fmt(r.fwd_bid, cd)}[/green] – [red]{_fmt(r.fwd_ask, cd)}[/red]",
            f"[b]spot:[/b] {_fmt(r.spot_bid)} – {_fmt(r.spot_ask)}    "
            f"[b]pontos:[/b] {_fmt(r.pontos_bid)} / {_fmt(r.pontos_ask)}    "
            f"[b]base a {r.sinal}[/b]",
            f"  {r.forward_formula_bid}",
            f"  {r.forward_formula_ask}",
        ]
        self.query_one("#swap_res", Static).update("\n".join(linhas))

    def _mostrar_hedge(self, r) -> None:
        acao = "Custo" if r.tipo_exposicao == "pagamento" else "Receita"
        linhas = [
            f"[b]Hedging de {r.tipo_exposicao}:[/b] {_fmt(r.montante_me)} "
            f"{r.moeda_estrangeira} a {r.dias} dias",
            "",
            "[b u]Forward Hedge[/b u]",
            f"  Taxa forward aplicada: {_fmt(r.fwd_taxa, 6)}",
            f"  {acao} total: [green]{_fmt(r.fwd_resultado_base, 2)} {r.moeda_base}[/green]",
            "",
            "[b u]Money Market Hedge[/b u]",
            f"  1. Valor presente em {r.moeda_estrangeira}: "
            f"{_fmt(r.mmh_me_presente, 2)} (taxa juro: {_fmt(r.mmh_taxa_juro_base, 4)}%)",
            f"  2. Conversão spot ({_fmt(r.mmh_spot_taxa, 6)}): "
            f"{_fmt(r.mmh_base_presente, 2)} {r.moeda_base}",
            f"  3. Valor futuro: [green]{_fmt(r.mmh_resultado_base, 2)} {r.moeda_base}[/green]",
        ]
        if r.opcao_resultado_base is not None:
            rotulo = "Custo máximo" if r.tipo_exposicao == "pagamento" else "Receita mínima"
            linhas += [
                "",
                "[b u]Cobertura com opção (Garman-Kohlhagen)[/b u]",
                f"  Compra de [b]{(r.opcao_tipo or '').upper()}[/b] sobre {r.moeda_base} · "
                f"strike {_fmt(r.opcao_strike, 6)} · notional "
                f"{_fmt(r.opcao_notional, 2)} {r.moeda_base}",
                f"  Prémio (capitalizado): {_fmt(r.opcao_premio_base, 2)} {r.moeda_base}",
                f"  {rotulo} coberto: [green]{_fmt(r.opcao_resultado_base, 2)} "
                f"{r.moeda_base}[/green]  [dim](contingente — mantém o lado favorável)[/dim]",
            ]
        linhas += [
            "",
            f"[b]Melhor estratégia:[/b] [bold magenta]{r.melhor_estrategia}[/bold magenta] "
            "[dim](Forward vs Money Market)[/dim]",
        ]
        self.query_one("#hedge_res", Static).update("\n".join(linhas))

    def _mostrar_opcao(self, r) -> None:
        linhas = [
            f"[b]{r.par} {r.tipo.upper()}[/b]  strike {_fmt(r.strike)}  "
            f"{r.dias}d  vol {_fmt(r.vol)}%",
            f"  prémio = [green]{_fmt(r.preco, 6)} {r.cotada}[/green] por 1 {r.base}"
            f"    total: [green]{_fmt(r.preco_total, 2)} {r.cotada}[/green] "
            f"({_fmt(r.notional)} {r.base})",
            f"  spot(mid) {_fmt(r.spot, 4)}  ·  r_f({r.base})={_fmt(r.juro_base, 4)}%  "
            f"·  r_d({r.cotada})={_fmt(r.juro_cotada, 4)}%  ·  "
            f"d1={_fmt(r.d1, 4)}  d2={_fmt(r.d2, 4)}",
            "[b u]Gregas[/b u]",
            f"  delta {_fmt(r.delta, 4)}   gamma {_fmt(r.gamma, 4)}   "
            f"vega {_fmt(r.vega, 6)} (/+1 vol pt)",
            f"  theta {_fmt(r.theta, 6)} (/dia)   rho {_fmt(r.rho, 6)} (/+1 pt r_d)",
            f"[i]{r.nota}[/i]",
        ]
        self.query_one("#opcao_res", Static).update("\n".join(linhas))

    def _erro_opcao(self, msg: str) -> None:
        self.query_one("#opcao_res", Static).update(f"[b red]Erro:[/b red] {msg}")

    def _erro_forward(self, msg: str) -> None:
        self.query_one("#forward_res", Static).update(f"[b red]Erro:[/b red] {msg}")

    def _erro_swap(self, msg: str) -> None:
        self.query_one("#swap_res", Static).update(f"[b red]Erro:[/b red] {msg}")

    def _erro_hedge(self, msg: str) -> None:
        self.query_one("#hedge_res", Static).update(f"[b red]Erro:[/b red] {msg}")

    def _info(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(msg)

    def _erro(self, msg: str) -> None:
        self.query_one("#resultado", Static).update(f"[b red]Erro:[/b red] {msg}")


def main() -> None:
    CrossRatesApp().run()


if __name__ == "__main__":
    main()
