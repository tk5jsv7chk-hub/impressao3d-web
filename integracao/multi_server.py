import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web
from cryptography.fernet import Fernet
from anycubic_cloud_api import AnycubicAuthMode, AnycubicMQTTAPI
from normalize import authenticated, normalize_printer

for namespace in ("anycubic_cloud_api", "aiohttp.client"):
    log = logging.getLogger(namespace)
    log.handlers = [logging.NullHandler()]
    log.propagate = False

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = {
    "not_tested": "Ainda nao consultada apos iniciar o servidor.",
    "ok": "Consulta concluida; confira os estados com o Slicer.",
    "authentication_failed": "Sessao recusada. Renove a autorizacao.",
    "timeout": "Consulta excedeu o tempo limite; dados anteriores nao sao atuais.",
    "cloud_error": "Falha na nuvem ou incompatibilidade; dados anteriores nao sao atuais.",
}


class Problem(ValueError):
    pass


def clock():
    return datetime.now(timezone.utc).isoformat()


def token_value(value):
    if not isinstance(value, str):
        raise Problem("Informe uma sessao autorizada, nao a senha da Anycubic.")
    value = value.strip()
    if not 30 <= len(value) <= 16000 or any(c.isspace() for c in value) or value.startswith("{"):
        raise Problem("Sessao em formato invalido. Nao envie arquivos completos.")
    return value


class Vault:
    def __init__(self, url, secret):
        if not url or len(secret) < 32:
            raise Problem("Configure banco e chave de criptografia na hospedagem.")
        self.url = url
        self.cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))

    def seal(self, item):
        return self.cipher.encrypt(json.dumps(item).encode()).decode()

    def unseal(self, blob):
        item = json.loads(self.cipher.decrypt(blob.encode()))
        if not isinstance(item, dict):
            raise Problem("Registro invalido")
        return item

    def connect(self):
        import psycopg
        return psycopg.connect(self.url, connect_timeout=5, options="-c statement_timeout=5000")

    def execute(self, query, params=(), fetch=False):
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS anycubic_accounts (id TEXT PRIMARY KEY, sealed TEXT NOT NULL)")
            cursor = conn.execute(query, params)
            return cursor.fetchall() if fetch else None

    def all(self):
        return {key: self.unseal(blob) for key, blob in self.execute("SELECT id,sealed FROM anycubic_accounts ORDER BY id", fetch=True)}

    def save(self, key, item):
        self.execute("INSERT INTO anycubic_accounts(id,sealed) VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET sealed=EXCLUDED.sealed", (key, self.seal(item)))

    def delete(self, key):
        self.execute("DELETE FROM anycubic_accounts WHERE id=%s", (key,))

    def restore(self, entries):
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS anycubic_accounts (id TEXT PRIMARY KEY, sealed TEXT NOT NULL)")
            for key, blob in entries.items():
                conn.execute("INSERT INTO anycubic_accounts(id,sealed) VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET sealed=EXCLUDED.sealed", (key, blob))

    def backup(self):
        return dict(self.execute("SELECT id,sealed FROM anycubic_accounts ORDER BY id", fetch=True))


class Poller:
    def __init__(self, token):
        self.token = token
        self.last_attempt = 0.0
        self.last_success = None
        self.state = "not_tested"
        self.printers = []

    def snapshot(self):
        age = None if self.last_success is None else (datetime.now(timezone.utc) - datetime.fromisoformat(self.last_success)).total_seconds()
        return {"state": self.state, "message": MESSAGES[self.state], "last_success": self.last_success,
                "stale": self.state != "ok" or age is None or age > 120,
                "printers": self.printers, "minimum_interval_seconds": 60}

    async def read(self):
        if self.last_attempt and time.monotonic() - self.last_attempt < 60:
            return self.snapshot()
        self.last_attempt = time.monotonic()
        try:
            async with asyncio.timeout(35):
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    api = AnycubicMQTTAPI(session=session)
                    api.set_authentication(auth_token=self.token, auth_mode=AnycubicAuthMode.SLICER)
                    if not await api.check_api_tokens():
                        self.state = "authentication_failed"
                        return self.snapshot()
                    printers = await api.list_my_printers()
                    rows = [normalize_printer(p) for p in printers]
                    if len({p["id"] for p in rows}) != len(rows):
                        raise Problem("Duplicate id")
                    self.printers = rows
                    self.last_success = clock()
                    self.state = "ok"
        except TimeoutError:
            self.state = "timeout"
        except Exception:
            self.state = "cloud_error"
        return self.snapshot()


def make_app(store=None, poller_factory=Poller, user=None, password=None):
    user = os.environ.get("PANEL_USER", "") if user is None else user
    password = os.environ.get("PANEL_PASSWORD", "") if password is None else password
    if store is None:
        try:
            store = Vault(os.environ.get("DATABASE_URL", ""), os.environ.get("VAULT_KEY", ""))
        except ValueError:
            pass
    pollers, failures = {}, []
    lock = asyncio.Lock()
    failed_add_at = 0.0

    @web.middleware
    async def guard(request, handler):
        if request.path == "/healthz" and request.method in ("GET", "HEAD"):
            return web.json_response({"alive": True})
        headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                   "Referrer-Policy": "no-referrer", "X-Frame-Options": "SAMEORIGIN",
                   "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"}
        def error(status, message):
            return web.json_response({"error": message}, status=status, headers=headers)
        if not user or len(password) < 16:
            return error(503, "Acesso do painel nao configurado.")
        now = time.monotonic()
        failures[:] = [stamp for stamp in failures if now - stamp < 60]
        if not authenticated(request.headers.get("Authorization", ""), user, password):
            if len(failures) >= 30:
                return error(429, "Aguarde um minuto antes de tentar novamente.")
            failures.append(now)
            headers["WWW-Authenticate"] = 'Basic realm="Fabrica 3D", charset="UTF-8"'
            return error(401, "Entre com o usuario e senha do painel.")
        if request.method not in ("GET", "HEAD"):
            origin = urlsplit(request.headers.get("Origin", ""))
            if (request.method != "POST" or request.path != "/api/accounts" or
                request.headers.get("X-Panel-Action") != "1" or request.content_type != "application/json" or
                origin.netloc != request.host or origin.scheme not in ("https", "http") or
                (origin.scheme == "http" and request.host.split(":")[0] not in ("localhost", "127.0.0.1"))):
                return error(403, "Requisicao de escrita bloqueada.")
        try:
            response = await handler(request)
        except Problem as exc:
            # Only our own validation errors are raised outside the cloud adapter.
            response = error(400, str(exc)[:200])
        except web.HTTPException as exc:
            response = exc
        except Exception:
            response = error(503, "Banco ou servico indisponivel. Nenhuma credencial foi exibida; tente novamente.")
        response.headers.update(headers)
        return response

    app = web.Application(middlewares=[guard], client_max_size=524288)

    def require_store():
        if store is None:
            raise Problem("Persistencia nao configurada. Sincronize o Blueprint com banco e VAULT_KEY.")

    def get_poller(key, item):
        if key not in pollers:
            pollers[key] = poller_factory(item["token"])
        return pollers[key]

    async def accounts(request):
        nonlocal failed_add_at
        require_store()
        async with lock:
            items = await asyncio.to_thread(store.all)
            if request.method == "GET":
                result = []
                for key, item in items.items():
                    snap = get_poller(key, item).snapshot()
                    selected = item.get("selected")
                    result.append({"id": key, "name": item["name"], "selected": selected,
                                   "updated": item["updated"], **snap})
                return web.json_response({"accounts": result, "read_only_printers": True,
                    "note": "Persistencia externa. Banco Free do Render expira em 30 dias; exporte backup e planeje migracao. Sessao inicial ainda exige autorizacao sua."})
            body = await request.json()
            if not isinstance(body, dict):
                raise Problem("Pedido invalido")
            action, key = body.get("action"), body.get("id")
            if action == "restore":
                archive = body.get("archive")
                if not isinstance(archive, dict) or archive.get("format") != "anycubic-vault-v1":
                    raise Problem("Backup incompativel")
                entries = archive.get("sealed_accounts")
                if not isinstance(entries, dict) or len(entries) > 20 or len(set(items) | set(entries)) > 20:
                    raise Problem("Backup fora do limite de 20 contas")
                for identity, blob in entries.items():
                    try:
                        uuid.UUID(identity)
                        if not isinstance(blob, str) or len(blob) > 50000:
                            raise Problem("Registro invalido")
                        restored = store.unseal(blob)
                        token_value(restored.get("token"))
                        label = restored.get("name")
                        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80:
                            raise Problem("Nome invalido")
                        selection = restored.get("selected")
                        if selection is not None and (not isinstance(selection, list) or len(selection) > 200 or any(not isinstance(x, str) for x in selection)):
                            raise Problem("Selecao invalida")
                        if not isinstance(restored.get("updated"), str):
                            raise Problem("Registro invalido")
                    except Exception:
                        raise Problem("Backup invalido ou criado com outra VAULT_KEY. Nenhuma conta foi alterada.") from None
                await asyncio.to_thread(store.restore, entries)
                pollers.clear()
                return web.json_response({"restored": len(entries)})
            if action in ("add", "renew"):
                if time.monotonic() - failed_add_at < 60:
                    return web.json_response({"error": "Aguarde um minuto antes de outra tentativa de autorizacao."}, status=429)
                if action == "renew" and key not in items:
                    raise Problem("Conta nao encontrada")
                if action == "add" and len(items) >= 20:
                    raise Problem("Limite inicial de 20 contas.")
                name = body.get("name", "")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                    raise Problem("Informe um nome de ate 80 caracteres.")
                token = token_value(body.get("token"))
                candidate = poller_factory(token)
                failed_add_at = time.monotonic()
                snap = await candidate.read()
                if snap["state"] != "ok":
                    return web.json_response({"error": snap["message"] + " A credencial nova nao foi salva."}, status=422)
                key = key if action == "renew" else str(uuid.uuid4())
                item = {"name": name.strip(), "token": token, "selected": items.get(key, {}).get("selected"), "updated": clock()}
                await asyncio.to_thread(store.save, key, item)
                pollers[key] = candidate
                return web.json_response({"saved": True, "id": key})
            if key not in items:
                raise Problem("Conta nao encontrada")
            item = items[key]
            if action == "test":
                return web.json_response(await get_poller(key, item).read())
            if action == "select":
                selected = body.get("selected")
                valid = {p["id"] for p in get_poller(key, item).snapshot()["printers"]}
                if not isinstance(selected, list) or len(selected) > 200 or any(not isinstance(p, str) or p not in valid for p in selected):
                    raise Problem("Selecao invalida; consulte as impressoras primeiro.")
                item["selected"] = list(dict.fromkeys(selected))
                item["updated"] = clock()
                await asyncio.to_thread(store.save, key, item)
                return web.json_response({"saved": True})
            if action == "remove":
                await asyncio.to_thread(store.delete, key)
                pollers.pop(key, None)
                return web.json_response({"removed": True})
            raise Problem("Operacao nao permitida")

    async def backup(request):
        require_store()
        async with lock:
            sealed = await asyncio.to_thread(store.backup)
        return web.json_response({"format": "anycubic-vault-v1", "created": clock(), "sealed_accounts": sealed},
            headers={"Content-Disposition": 'attachment; filename="contas-anycubic-criptografadas.json"'})

    async def home(request):
        raise web.HTTPFound("/fabrica/contas.html")

    app.router.add_get("/", home)
    app.router.add_get("/healthz", home)
    app.router.add_get("/api/accounts/backup", backup)
    app.router.add_get("/api/accounts", accounts)
    app.router.add_post("/api/accounts", accounts)
    app.router.add_static("/fabrica/", ROOT / "fabrica", show_index=False)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), access_log=None)
