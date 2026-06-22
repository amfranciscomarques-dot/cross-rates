# Deployment

The web UI ships as a portable container image. There is no provider lock-in:
the image binds `0.0.0.0` and reads its port from the environment, so it runs
on any container host (Fly.io, Render, Railway, Cloud Run, a plain VM, …).

## Build

```sh
docker build -t cross-rates-web .
```

Multi-stage build: a builder stage installs the package with the `web` extra
into an isolated virtualenv; the runtime stage is a slim, non-root image
carrying only that venv. No build toolchain ends up in the final image.

## Run

```sh
docker run --rm -p 8000:8000 cross-rates-web
```

Then open <http://127.0.0.1:8000/>. The page opens **pre-seeded with live ECB
reference rates** (the image defaults `CROSS_RATES_FEED=frankfurter`).

For a deterministic, offline demo (no network call), use the fixture feed:

```sh
docker run --rm -p 8000:8000 -e CROSS_RATES_FEED=simulado cross-rates-web
```

## Configuration

All configuration is via environment variables — no config files.

| Variable            | Default     | Purpose                                                        |
| ------------------- | ----------- | -------------------------------------------------------------- |
| `CROSS_RATES_HOST`  | `127.0.0.1` | Bind address. The image overrides this to `0.0.0.0`.           |
| `CROSS_RATES_PORT`  | `8000`      | Listen port. `PORT` is honoured as a fallback (many PaaS set it). |
| `CROSS_RATES_FEED`  | unset¹      | `frankfurter` (live ECB) · `simulado` (offline fixture) · `none`. |

¹ Unset means no feed: the page opens with an empty table. The container image
sets it to `frankfurter`.

If the live feed is unreachable, the page degrades gracefully — it opens with an
empty table and a note, never a 500.

## Hosting

Pick any host that runs a container and routes a port:

- **PaaS** (Fly.io / Render / Railway / Cloud Run): point it at this repo or the
  built image. Most inject `$PORT`, which `serve()` already honours; set
  `CROSS_RATES_FEED=frankfurter` if you want the live demo.
- **VM**: `docker run -d -p 80:8000 --restart unless-stopped cross-rates-web`.

CI builds and smoke-tests the image on every push, but does **not** deploy —
the deploy step is intentionally left to whichever host you choose.
