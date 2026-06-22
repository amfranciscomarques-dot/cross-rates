"""Operações de aplicação: parse de texto livre + orquestração do núcleo.

Funções agnósticas à interface (sem Textual nem FastAPI), partilhadas pela TUI
e pela web. Recebem um ``GrafoCambial`` com as cotações já carregadas e o texto
do utilizador, e devolvem objetos do núcleo. Em caso de erro de input levantam
``CotacaoInvalida``; uma moeda/percurso inexistente propaga ``SemPercurso``.
Cada frontend decide como apresentar o erro.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from cross_rates.nucleo import (
    AnaliseHedging,
    Arbitragem,
    ArbitragemGeografica,
    ArbitragemPrazo,
    Cotacao,
    CotacaoInvalida,
    GrafoCambial,
    ResultadoCross,
    ResultadoForward,
    SwapOutright,
    TaxaJuro,
    analisa_hedging,
    arbitragem_a_prazo,
    arbitragens_geograficas,
    arbitragens_triangulares,
    cross,
    forward,
    normaliza_moeda,
    outright_de_pontos,
)


def _inteiro(texto: str, campo: str) -> int:
    """Converte para ``int`` ou levanta ``CotacaoInvalida`` com uma mensagem clara."""
    try:
        return int(texto)
    except ValueError as exc:
        raise CotacaoInvalida(f"{campo} tem de ser um número inteiro (ex.: 180).") from exc


def parse_montante(texto: str) -> Decimal | None:
    """Lê um montante opcional: ``None`` se vazio; ``CotacaoInvalida`` se inválido."""
    texto = texto.strip().replace(",", ".")
    if not texto:
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation as exc:
        raise CotacaoInvalida("Montante inválido (ex.: 1000000).") from exc
    if valor <= 0:
        raise CotacaoInvalida("Montante inválido (ex.: 1000000).")
    return valor


def spot_para(grafo: GrafoCambial, base: str, cotada: str) -> Cotacao | None:
    """Spot ``base/cotada`` a partir da tabela (invertendo a orientação se preciso)."""
    c = grafo.cotacao_do_par(base, cotada)
    if c is None:
        return None
    base, cotada = normaliza_moeda(base), normaliza_moeda(cotada)
    if c.base == base and c.cotada == cotada:
        return c
    # cotação na orientação inversa: bid' = 1/ask, ask' = 1/bid
    return Cotacao(base, cotada, Decimal(1) / c.ask, Decimal(1) / c.bid)


def _spot_obrigatorio(grafo: GrafoCambial, base: str, cotada: str) -> Cotacao:
    spot = spot_para(grafo, base, cotada)
    if spot is None:
        raise CotacaoInvalida(
            f"Sem spot {normaliza_moeda(base)}/{normaliza_moeda(cotada)} na tabela — "
            "adicione a cotação à vista primeiro."
        )
    return spot


def adicionar_cotacao(grafo: GrafoCambial, texto: str) -> Cotacao:
    """Cria a cotação a partir do texto e adiciona-a ao grafo."""
    cotacao = Cotacao.de_texto(texto)
    grafo.adicionar(cotacao)
    return cotacao


def calcular_cross(grafo: GrafoCambial, texto: str) -> ResultadoCross:
    """Calcula o cross-rate ``BASE COTADA`` a partir das cotações do grafo."""
    partes = texto.upper().split()
    if len(partes) != 2:
        raise CotacaoInvalida("Formato esperado: BASE COTADA (ex.: GBP SEK).")
    return cross(grafo, partes[0], partes[1])


def analisar_arbitragem(
    grafo: GrafoCambial,
) -> tuple[list[ArbitragemGeografica], list[Arbitragem]]:
    """Procura arbitragens geográficas e triangulares no grafo atual."""
    return arbitragens_geograficas(grafo), arbitragens_triangulares(grafo)


def calcular_forward(
    grafo: GrafoCambial, texto: str
) -> tuple[ResultadoForward, ArbitragemPrazo | None]:
    """Calcula o forward (PTJ) e, com 9 campos, também a arbitragem a prazo.

    Formato: ``BASE COTADA dias i_base_bid i_base_ask i_cot_bid i_cot_ask
    [fwd_bid fwd_ask]``. O spot vem da tabela.
    """
    partes = texto.replace(",", ".").split()
    if len(partes) not in (7, 9):
        raise CotacaoInvalida(
            "Formato: BASE COTADA dias i_base_bid i_base_ask i_cot_bid "
            "i_cot_ask [fwd_bid fwd_ask]."
        )
    base, cotada = partes[0], partes[1]
    spot = _spot_obrigatorio(grafo, base, cotada)
    n = _inteiro(partes[2], "O prazo (dias)")
    juro_base = TaxaJuro.de_moeda(base, partes[3], partes[4])
    juro_cotada = TaxaJuro.de_moeda(cotada, partes[5], partes[6])
    r = forward(spot, juro_base, juro_cotada, n)
    arb = None
    if len(partes) == 9:
        arb = arbitragem_a_prazo(spot, juro_base, juro_cotada, n, partes[7], partes[8])
    return r, arb


def calcular_swap(grafo: GrafoCambial, texto: str) -> SwapOutright:
    """Calcula a taxa outright a partir dos pontos de swap.

    Formato: ``BASE COTADA pontos_bid pontos_ask [casas_decimais]``. Spot da tabela.
    """
    partes = texto.replace(",", ".").split()
    if len(partes) not in (4, 5):
        raise CotacaoInvalida("Formato: BASE COTADA pontos_bid pontos_ask [casas_decimais].")
    base, cotada = partes[0], partes[1]
    spot = _spot_obrigatorio(grafo, base, cotada)
    casas = _inteiro(partes[4], "As casas decimais") if len(partes) == 5 else 4
    return outright_de_pontos(spot, partes[2], partes[3], casas_decimais_pontos=casas)


def calcular_hedge(grafo: GrafoCambial, texto: str) -> AnaliseHedging:
    """Analisa a cobertura (Forward Hedge vs Money Market Hedge).

    Formato: ``TIPO MONTANTE BASE COTADA dias i_base_bid i_base_ask i_cot_bid i_cot_ask``,
    com ``TIPO`` = ``recebimento`` | ``pagamento``. Spot da tabela.
    """
    partes = texto.replace(",", ".").split()
    if len(partes) != 9:
        raise CotacaoInvalida(
            "Formato: TIPO MONTANTE BASE COTADA dias i_base(b a) i_cotada(b a)."
        )
    tipo = partes[0].lower()
    if tipo not in ("recebimento", "pagamento"):
        raise CotacaoInvalida("TIPO deve ser 'recebimento' ou 'pagamento'.")
    montante, base, cotada = partes[1], partes[2], partes[3]
    spot = _spot_obrigatorio(grafo, base, cotada)
    n = _inteiro(partes[4], "O prazo (dias)")
    juro_base = TaxaJuro.de_moeda(base, partes[5], partes[6])
    juro_cotada = TaxaJuro.de_moeda(cotada, partes[7], partes[8])
    return analisa_hedging(tipo, montante, spot, juro_base, juro_cotada, n)
