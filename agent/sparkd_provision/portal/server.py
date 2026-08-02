from __future__ import annotations

from importlib.resources import files

from aiohttp import web
from cryptography.exceptions import InvalidTag

from sparkd_provision.api.handlers import Handlers


def _is_bound_host(request_host: str, bound_host: str | None, bound_port: int | None) -> bool:
    if not bound_host or not bound_port:
        return False
    expected = {f"{bound_host}:{bound_port}"}
    if bound_port == 80:
        expected.add(bound_host)
    return request_host.lower() in {host.lower() for host in expected}


def _portal_html() -> str:
    return files("sparkd_provision").joinpath("portal/static/index.html").read_text()


def create_app(handlers: Handlers) -> web.Application:
    app = web.Application()

    @web.middleware
    async def cors(request: web.Request, handler: web.RequestHandler) -> web.StreamResponse:
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    app.middlewares.append(cors)

    async def api(request: web.Request) -> web.Response:
        try:
            result = await handlers.handle(await request.json())
        except (InvalidTag, ValueError, TypeError) as exc:
            result = {"v": 1, "id": "", "ok": False, "err": {"code": "BAD_REQUEST", "msg": str(exc), "detail": {}}}
        return web.json_response(result)

    async def apple_probe(_: web.Request) -> web.Response:
        if await handlers.provisioning_online():
            return web.Response(
                text="<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>",
                content_type="text/html",
            )
        raise web.HTTPFound("/portal/")

    async def android_probe(_: web.Request) -> web.Response:
        if await handlers.provisioning_online():
            return web.Response(status=204)
        raise web.HTTPFound("/portal/")

    async def windows_probe(_: web.Request) -> web.Response:
        if await handlers.provisioning_online():
            return web.Response(text="Microsoft Connect Test")
        raise web.HTTPFound("/portal/")

    async def portal(_: web.Request) -> web.Response:
        return web.Response(text=_portal_html(), content_type="text/html")

    app.router.add_post("/api/v1", api)
    app.router.add_get("/portal/", portal)
    async def catch_all(request: web.Request) -> web.Response:
        sockname = request.transport.get_extra_info("sockname") if request.transport else None
        bound_host, bound_port = sockname[:2] if sockname else (None, None)
        if not _is_bound_host(request.host, bound_host, bound_port):
            raise web.HTTPFound("/portal/")
        raise web.HTTPNotFound()

    app.router.add_get("/hotspot-detect.html", apple_probe)
    app.router.add_get("/generate_204", android_probe)
    app.router.add_get("/connecttest.txt", windows_probe)
    app.router.add_get("/{tail:.*}", catch_all)
    return app
