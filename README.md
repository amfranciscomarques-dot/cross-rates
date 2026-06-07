# Calculadora de Cross-Rates (bid/ask)

Calculadora de **taxas cruzadas (cross-rates)** com **bid e ask**, em terminal.
Deriva o câmbio entre duas moedas que não se cotam diretamente, através de uma
ou mais moedas-veículo, aplicando em cada conversão a ponta da forquilha
desfavorável ao cliente — tal como no mercado real.

Pensada para crescer até uma ferramenta de **arbitragem** (geográfica,
triangular e a prazo) para empresas e bancos.

## Instalação

```bash
pip install -e ".[dev]"
```

## Utilizar

```bash
python -m cross_rates        # abre a interface de terminal (TUI)
```

Na TUI:

1. **Adicionar cotação** — escreva `BASE COTADA bid ask [fonte]`, ex.:
   `EUR USD 1.1574 1.1576 Paris`. A fonte (praça/banco) é opcional.
2. **Calcular cross** — escreva `BASE COTADA`, ex.: `GBP SEK`.
3. **Arbitragem** — tecla `a` (geográfica + triangular; opcionalmente com montante).
4. **Forward (PTJ)** — escreva `BASE COTADA dias i_base_bid i_base_ask
   i_cot_bid i_cot_ask [fwd_bid fwd_ask]`, ex.:
   `CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079`. O spot vem da
   tabela; os juros são em % anual (base 360). Com a cotação forward de mercado
   no fim, verifica também a **arbitragem a prazo**.
5. Atalhos: `e` exemplos de cross, `x` exemplos triangular, `g` exemplos
   geográfica, `f` exemplo de forward, `t` painel de teoria, `l` limpa a
   tabela, `q` sai.

O resultado do cross mostra `bid – ask`, `spread`, **tipo** (direta / inversa /
cross direto ÷ / cross indireto ×), o **percurso**, as **fórmulas** bid/ask com
as pontas certas e uma **nota metodológica**. Um **painel de teoria** (tecla `t`)
resume a convenção, a regra do bid/ask e as regras de cross e arbitragem.

A arbitragem lista os ciclos de 3 moedas com **fator > 1** (ganho certo),
detalhando cada perna e, se indicar um montante, o **lucro** e a **simulação**.

## Convenção

Na notação `BASE/COTADA`, a **BASE** está *ao certo* e a **COTADA** *ao
incerto*: o preço diz quantas unidades de COTADA valem 1 unidade de BASE, com
`bid <= ask`.

| Quem               | Compra a base | Vende a base |
| ------------------ | ------------- | ------------ |
| Banco/market maker | ao bid        | ao ask       |
| Cliente            | ao ask        | ao bid       |

## Como funciona o cálculo

Cada cotação `BASE/COTADA (bid b, ask a)` gera duas conversões dirigidas:

- `BASE -> COTADA` à taxa `b` (vender 1 BASE rende `b` COTADA);
- `COTADA -> BASE` à taxa `1/a` (1 COTADA compra `1/a` BASE).

O cross deriva-se de dois percursos no grafo:

- **bid** (vender a base) = taxa do percurso `BASE -> ... -> COTADA`;
- **ask** (comprar a base) = `1 / (taxa de COTADA -> ... -> BASE)`.

Este modelo reproduz automaticamente as regras do caderno (cross direto `÷` e
indireto `×`) e prepara o terreno para a deteção de arbitragem (um ciclo cujo
produto de taxas seja `> 1`).

## Arquitetura

```
cross_rates/
  nucleo/           # lógica cambial pura, sem interface (100% testável)
    cotacao.py      # Cotacao: par, bid, ask (+ validação)
    grafo.py        # GrafoCambial: moedas (nós) e conversões (arestas)
    cross.py        # cross(): cross-rate + percurso + tipo + fórmulas + nota
    arbitragem.py   # arbitragens_geograficas() e _triangulares()
    forward.py      # forward() PTJ + arbitragem_a_prazo() (TaxaJuro)
  tui/
    app.py          # interface Textual (cross, arbitragem, forward, teoria)
  __main__.py       # python -m cross_rates
testes/
  test_cross.py     # trancado às resoluções do Caderno (Ex. 10/11/12/17)
  test_arbitragem.py# trancado a Ex. 15/16/17/18
  test_forward.py   # trancado a Ex. 21b/22b/23/27/28
  test_tui.py       # fluxo headless da interface
```

## Testes

```bash
pytest
```

Os testes do cross-rate reproduzem exercícios resolvidos (Ex. 10, 11, 12, 17),
validando em simultâneo a matemática e a convenção bid/ask.

## Arbitragem

**Geográfica (espacial)** — mesmo par cotado em praças diferentes (campo `fonte`).
Há ganho certo se o `ask` mais baixo (compra da base) for inferior ao `bid` mais
alto (venda): `ask(A) < bid(B)` → compra em A, vende em B. Ver
`arbitragens_geograficas()`.

**Triangular** — um **ciclo de 3 moedas** `A→B→C→A` cujo produto das taxas (cada
uma já na ponta bid/ask correta) é **> 1**:

    fator > 1  ⇒  ganho certo = (fator − 1) × montante inicial

É a forma unificada da regra do caderno "cross implícito ≠ cotação direta".
Risco nulo, porque as pernas são simultâneas. Ver `arbitragens_triangulares()`.

## Forwards (taxas a prazo) — PTJ

A taxa **forward** de equilíbrio resulta da **Paridade das Taxas de Juro coberta
(PTJ/CIP)**: é a taxa que impede a arbitragem entre o forward direto e a réplica
no Mercado Monetário Internacional (não é uma previsão da cotação futura). Para
o par `BASE/COTADA`, a `dias` dias na base `n/360`:

    F = S × (1 + i_cotada·n/360) ÷ (1 + i_base·n/360)

- `i_cotada > i_base` → `F > S`: a base cotiza-se **a prémio**;
- `i_cotada < i_base` → `F < S`: a base **a desconto**.

Com bid/ask, cada ponta combina as pernas que desfavorecem o cliente:
`F_bid = S_bid·(1+i_bid_cot·t)/(1+i_ask_base·t)` e
`F_ask = S_ask·(1+i_ask_cot·t)/(1+i_bid_base·t)`. Ver `forward()` e `TaxaJuro`.

**Arbitragem a prazo (covered interest arbitrage)** — quando o forward cotado no
mercado sai do intervalo de equilíbrio, há lucro certo: vende-se a ponta cara e
replica-se via MMI a barata. Ver `arbitragem_a_prazo()`.

## Roteiro (próximas fases)

Tudo assenta no mesmo `GrafoCambial`:

- ~~**Arbitragem triangular** — cross implícito vs. cotado (Ex. 17–18).~~ ✅ feito.
- ~~**Arbitragem geográfica** — mesmo par em praças diferentes (Ex. 15–16).~~ ✅ feito.
- ~~**Forwards / PTJ** — taxas a prazo com bid/ask + arbitragem a prazo (Ex. 21–29).~~ ✅ feito.
- **Swaps cambiais** — spot + forward de sinais opostos (Ex. 30).
- **Feeds em tempo real** — fonte de preços conectável (broker/exchange).
