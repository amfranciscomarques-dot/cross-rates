# syntax=docker/dockerfile:1
#
# Imagem do frontend web (FastAPI + HTMX). Multi-estágio: o "builder" instala o
# pacote — com o extra "web" — num virtualenv isolado; o "runtime" leva só esse
# venv numa base slim, sem toolchain de build. Sem ficheiros específicos de
# alojamento: host/porta/feed vêm do ambiente (ver cross_rates/web/app.py).

# --- Estágio 1: builder -------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# venv dedicado, copiado intacto para o runtime.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Metadados de build primeiro (melhor cache); pyproject referencia README/LICENSE.
COPY pyproject.toml README.md LICENSE ./
COPY cross_rates ./cross_rates

# Instala o pacote + extra web (fastapi/uvicorn/jinja2/python-multipart).
# Os templates Jinja e estáticos seguem via package-data (ver pyproject.toml).
RUN pip install ".[web]"

# --- Estágio 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Em contentor: ligar em todas as interfaces e abrir já com dados ao vivo.
    CROSS_RATES_HOST=0.0.0.0 \
    CROSS_RATES_PORT=8000 \
    CROSS_RATES_FEED=frankfurter

# Correr como utilizador não-root.
RUN useradd --create-home --uid 1000 app
COPY --from=builder /opt/venv /opt/venv
USER app

EXPOSE 8000

# Saúde: a página inicial responde 200 (usa o Python da imagem, sem curl).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/').read()"]

# Entry-point declarado no pyproject ([project.scripts]).
CMD ["cross-rates-web"]
