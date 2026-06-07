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
4. Atalhos: `e` exemplos de cross, `x` exemplos triangular, `g` exemplos
   geográfica, `t` painel de teoria, `l` limpa a tabela, `q` sai.

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
  tui/
    app.py          # interface Textual (cross, arbitragem, teoria)
  __main__.py       # python -m cross_rates
testes/
  test_cross.py     # trancado às resoluções do Caderno (Ex. 10/11/12/17)
  test_arbitragem.py# trancado a Ex. 17/18
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

## Roteiro (próximas fases)

Tudo assenta no mesmo `GrafoCambial`:

- ~~**Arbitragem triangular** — cross implícito vs. cotado (Ex. 17–18).~~ ✅ feito.
- ~~**Arbitragem geográfica** — mesmo par em praças diferentes (Ex. 15–16).~~ ✅ feito.
- **Forwards / PTJ** — taxas a prazo com bid/ask (Ex. 21–29).
- **Swaps cambiais** — spot + forward de sinais opostos (Ex. 30).
- **Feeds em tempo real** — fonte de preços conectável (broker/exchange).
