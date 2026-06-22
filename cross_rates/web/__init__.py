"""Frontend web (FastAPI + HTMX/Jinja) da calculadora de cross-rates.

Reaproveita a camada de serviço agnóstica (``cross_rates.servico``): o parsing e
a orquestração são partilhados com a TUI, e os templates renderizam os dicts
JSON-safe do view-model. A app é **sem estado** — as cotações vivem no browser
(inputs ocultos) e são reenviadas a cada operação, que reconstrói o grafo.
"""

from .app import app, serve

__all__ = ["app", "serve"]
