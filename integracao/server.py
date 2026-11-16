import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from aiohttp import web
from anycubic_cloud_api import AnycubicAuthMode, AnycubicMQTTAPI
from normalize import authenticated, normalize_printer

# Suppress third-party payload logging: it can include account information.
for name in ("anycubic_cloud_api", "aiohttp.client"):
    logger = logging.getLogger(name)
    logger.handlers = [logging.NullHandler()]
    logger.propagate = False

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ.get("PANEL_USER", "")
PASSWORD = os.environ.get("PANEL_PASSWORD", "")
TOKEN = os.environ.get("ANYCUBIC_TOKEN", "").strip()


class Bridge:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.last_attempt = 0.0
        self.last_success = None
        self.printers = []
        self.state = "not_configured" if not TOKEN else "not_tested"

    async def read(self):
        async with self.lock:
            if not TOKEN:
                return self.snapshot()
            if self.last_attempt and time.monotonic() - self.last_attempt < 60:
                return self.snapshot()
            self.last_attempt = time.monotonic()
            try:
                async with asyncio.timeout(35):
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                        api = AnycubicMQTTAPI(session=session)
                        api.set_authentication(auth_token=TOKEN, auth_mode=AnycubicAuthMode.SLICER)
                        if not await api.check_api_tokens():
                            self.state = "authentication_failed"
                            return self.snapshot()
                        printers = await api.list_my_printers()
                        rows = [normalize_printer(p) for p in printers]
                        if len({p["id"] for p in rows}) != len(rows):
                            raise ValueError("Duplicate printer id")
                        self.printers = rows
                        self.last_success = datetime.now(timezone.utc).isoformat()
                        self.state = "ok"
            except TimeoutError:
                self.state = "timeout"
            except Exception:
                # Never return exception text or raw API payload to the browser/logs.
                self.state = "cloud_error"
            return self.snapshot()

    def snapshot(self):
        return {"state": self.state, "configured": bool(TOKEN),
                "last_success": self.last_success, "printers": self.printers,
                "stale": self.state != "ok", "minimum_interval_seconds": 60,
                "expected_printers": 2, "read_only": True,
                "telemetry_note": "Consulta HTTP inicial: somente identificacao e estado. Progresso, trabalho, temperaturas e tempos ainda nao mapeados/validados."}


@web.middleware
async def security(request, handler):
    if request.path == "/healthz" and request.method in ("GET", "HEAD"):
        return web.json_response({"alive": True})
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
               "Referrer-Policy": "no-referrer", "X-Frame-Options": "SAMEORIGIN",
               "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"}
    if not USER or len(PASSWORD) < 16:
        return web.Response(status=503, text="Configure PANEL_USER e PANEL_PASSWORD (minimo 16 caracteres) na hospedagem.", headers=headers)
    if not authenticated(request.headers.get("Authorization", ""), USER, PASSWORD):
        headers["WWW-Authenticate"] = 'Basic realm="Fabrica 3D", charset="UTF-8"'
        return web.Response(status=401, text="Autenticacao do painel necessaria.", headers=headers)
    if request.method not in ("GET", "HEAD"):
        return web.Response(status=405, text="Somente leitura.", headers=headers)
    try:
        response = await handler(request)
    except web.HTTPException as response_error:
        response = response_error
    except Exception:
        response = web.Response(status=500, text="Falha interna; nenhum detalhe sensivel foi exposto.")
    response.headers.update(headers)
    return response


def make_app():
    app = web.Application(middlewares=[security])
    bridge = Bridge()

    async def home(request):
        raise web.HTTPFound("/fabrica/conexao.html")

    async def status(request):
        return web.json_response(bridge.snapshot())

    async def printers(request):
        return web.json_response(await bridge.read())

    app.router.add_get("/", home)
    app.router.add_get("/healthz", status)
    app.router.add_get("/api/connection", status)
    app.router.add_get("/api/printers", printers)
    app.router.add_static("/fabrica/", ROOT / "fabrica", show_index=False)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), access_log=None)
