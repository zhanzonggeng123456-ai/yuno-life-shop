"""Public native-API ingress. Existing HTML business routes remain local-only."""
from starlette.responses import JSONResponse

from app.main import app as marketplace


class NativeGateway:
    def __init__(self, backend):
        self.backend = backend

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.backend(scope, receive, send)
            return
        path = scope["path"]

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([(b"x-content-type-options", b"nosniff"),
                                (b"referrer-policy", b"no-referrer"),
                                (b"x-frame-options", b"DENY")])
                if not path.startswith("/uploads/"):
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        if path == "/" and scope["method"] in ("GET", "HEAD"):
            response = JSONResponse({"app": "YUNO LIFE SHOP", "api": "/api/v1",
                                     "payment": "simulated", "delivery": "simulated"})
            await response(scope, receive, secured_send)
        elif (path == "/healthz" or path.startswith("/api/v1/")
              or path.startswith("/uploads/")):
            await self.backend(scope, receive, secured_send)
        else:
            await JSONResponse({"detail": "not_found"}, status_code=404)(
                scope, receive, secured_send)


app = NativeGateway(marketplace)
