"""Teste headless da TUI: adicionar cotações e calcular um cross."""

import pytest

from cross_rates.tui import CrossRatesApp


@pytest.mark.asyncio
async def test_fluxo_adicionar_e_calcular():
    app = CrossRatesApp()
    async with app.run_test() as pilot:
        app.action_exemplos()  # carrega Ex. 12
        await pilot.pause()
        assert len(app.grafo.cotacoes) == 3

        calc = app.query_one("#calc")
        calc.focus()
        await pilot.pause()
        calc.value = "GBP CHF"
        await pilot.press("enter")
        await pilot.pause()

        from cross_rates.tui.app import _fmt
        from cross_rates.nucleo import cross

        r = cross(app.grafo, "GBP", "CHF")
        conteudo = str(app.query_one("#resultado").render())
        assert _fmt(r.bid) in conteudo
        assert "direto" in conteudo
