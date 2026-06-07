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

1. **Adicionar cotação** — escreva `BASE COTADA bid ask`, ex.: `EUR USD 1.0850 1.0852`.
2. **Calcular cross** — escreva `BASE COTADA`, ex.: `GBP SEK`.
3. Atalhos: `e` carrega cotações de exemplo, `l` limpa a tabela, `q` sai.

O resultado mostra `bid – ask`, o `spread`, o **tipo** (direta / cross direto ÷
/ cross indireto ×) e o **percurso** de moedas usado.

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
  nucleo/        # lógica cambial pura, sem interface (100% testável)
    cotacao.py   # Cotacao: par, bid, ask (+ validação)
    grafo.py     # GrafoCambial: moedas (nós) e conversões (arestas)
    cross.py     # cross(): deriva o cross-rate + percurso + tipo
  tui/
    app.py       # interface Textual
  __main__.py    # python -m cross_rates
testes/
  test_cross.py  # trancado às resoluções do Caderno de Exercícios nº 1
```

## Testes

```bash
pytest
```

Os testes do cross-rate reproduzem exercícios resolvidos (Ex. 10, 11, 12, 17),
validando em simultâneo a matemática e a convenção bid/ask.

## Roteiro (próximas fases)

Tudo assenta no mesmo `GrafoCambial`:

- **Arbitragem geográfica** — mesmo par cotado em praças diferentes (Ex. 15–16).
- **Arbitragem triangular** — cross implícito vs. cotado (Ex. 17–18).
- **Forwards / PTJ** — taxas a prazo com bid/ask (Ex. 21–29).
- **Swaps cambiais** — spot + forward de sinais opostos (Ex. 30).
- **Feeds em tempo real** — fonte de preços conectável (broker/exchange).
