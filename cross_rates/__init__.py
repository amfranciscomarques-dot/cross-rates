"""Calculadora de cross-rates (taxas cruzadas) com bid/ask.

Pacote organizado em duas camadas:

* ``cross_rates.nucleo`` — lógica cambial pura, testável, sem interface.
* ``cross_rates.tui``    — interface de terminal (Textual) sobre o núcleo.
"""

__version__ = "0.1.0"
