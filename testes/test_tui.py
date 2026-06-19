"""Teste headless da TUI: adicionar cotações e calcular um cross."""

import pytest

from cross_rates.tui import CrossRatesApp


@pytest.mark.asyncio
async def test_fluxo_adicionar_e_calcular():
    app = CrossRatesApp()
    async with app.run_test() as pilot:
        app.action_exemplos_cross()  # carrega Ex. 12
        await pilot.pause()
        assert len(app.grafo.cotacoes) == 3

        calc = app.query_one("#calc")
        calc.focus()
        await pilot.pause()
        calc.value = "GBP CHF"
        await pilot.press("enter")
        await pilot.pause()

        from cross_rates.nucleo import cross
        from cross_rates.tui.app import _fmt

        r = cross(app.grafo, "GBP", "CHF")
        conteudo = str(app.query_one("#resultado").render())
        assert _fmt(r.bid) in conteudo
        assert "direto" in conteudo


@pytest.mark.asyncio
async def test_forward_na_tui():
    app = CrossRatesApp()
    async with app.run_test() as pilot:
        app.action_exemplos_forward()  # Ex. 27: spot CHF/USD + input preenchido
        await pilot.pause()
        assert len(app.grafo.cotacoes) == 1

        campo = app.query_one("#forward")
        campo.focus()
        await pilot.pause()
        await pilot.press("enter")  # input já vem preenchido pelo exemplo
        await pilot.pause()

        conteudo = str(app.query_one("#forward_res").render())
        assert "forward" in conteudo.lower()
        assert "prémio" in conteudo.lower()  # i_USD > i_CHF → CHF a prémio
        assert "arbitragem a prazo" in conteudo.lower()


@pytest.mark.asyncio
async def test_arbitragem_na_tui():
    app = CrossRatesApp()
    async with app.run_test() as pilot:
        app.action_exemplos_arbitragem()  # Ex. 17 (tem arbitragem)
        await pilot.pause()
        app.query_one("#montante").value = "2500000"
        app.action_arbitragem()
        await pilot.pause()
        conteudo = str(app.query_one("#arb").render())
        assert "arbitragem" in conteudo.lower()
        assert "lucro" in conteudo.lower()
