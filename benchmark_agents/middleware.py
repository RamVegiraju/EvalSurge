"""Transport limits enforced before unbounded request bodies reach API handlers."""

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .limits import MAX_REQUEST_BYTES


class BodyLimitMiddleware:
    """Bound decoded HTTP body bytes, including chunked requests without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        """Wrap an application with an eight-megabyte default submission limit."""
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Count incoming body chunks and raise a safe 413 before accepting excess bytes."""
        size = 0

        async def bounded_receive() -> Message:
            """Delegate one ASGI event while enforcing the cumulative HTTP body limit."""
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > self.max_bytes:
                    raise HTTPException(413, "Request body exceeds the eight-megabyte limit")
            return message

        await self.app(scope, bounded_receive if scope["type"] == "http" else receive, send)
