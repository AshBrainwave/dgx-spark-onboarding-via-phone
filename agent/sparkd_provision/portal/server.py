from __future__ import annotations

from aiohttp import web

from sparkd_provision.api.handlers import Handlers


def create_app(handlers: Handlers) -> web.Application:
    app = web.Application()

    async def api(request: web.Request) -> web.Response:
        try:
            result = await handlers.handle(await request.json())
        except (ValueError, TypeError) as exc:
            result = {"v": 1, "id": "", "ok": False, "err": {"code": "BAD_REQUEST", "msg": str(exc), "detail": {}}}
        return web.json_response(result)

    async def probe(_: web.Request) -> web.Response:
        raise web.HTTPFound("/portal/")

    async def portal(_: web.Request) -> web.Response:
        return web.Response(text="DGX Spark portal running. Use the hosted simulator UI.", content_type="text/html")

    app.router.add_post("/api/v1", api)
    app.router.add_get("/portal/", portal)
    app.router.add_get("/hotspot-detect.html", probe)
    app.router.add_get("/generate_204", probe)
    app.router.add_get("/connecttest.txt", probe)
    return app
