"""Document common response headers and representative API examples."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

EVALUATION_EXAMPLE = {
    "description": "Answer refund questions accurately",
    "scorers": ["relevance", "correctness"],
    "samples": [
        {
            "inputs": {"query": "Can I refund an opened item?"},
            "expectations": {"expected_response": "Opened items cannot be refunded."},
        }
    ],
}
RUN_EXAMPLE = {
    "target": {"url": "http://127.0.0.1:9001/chat"},
    "evaluation": EVALUATION_EXAMPLE,
    "load": {"concurrency": 3, "max_requests": 20},
}


def install_schema(app: FastAPI) -> None:
    """Install the cached OpenAPI renderer with shared response-header examples.

    Args:
        app: Application whose routes and response models define the public schema.

    The renderer documents intended header conventions; behavioral tests must also
    verify them on success, handled errors, and unexpected failures.
    """

    def schema() -> dict[str, Any]:
        """Generate and cache the route schema, annotated with examples and headers."""
        if app.openapi_schema:
            return app.openapi_schema
        result = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            servers=app.servers,
            contact=app.contact,
        )
        for path, methods in result["paths"].items():
            for method, operation in methods.items():
                if method not in {"get", "post"}:
                    continue
                for name, response in operation["responses"].items():
                    response["headers"] = {
                        "Cache-Control": {
                            "description": "Private run data must not be cached.",
                            "schema": {"type": "string", "const": "no-store"},
                        },
                        "X-Request-ID": {
                            "description": "Server-generated correlation UUID.",
                            "schema": {"type": "string"},
                        },
                        "X-Content-Type-Options": {
                            "description": "Disable content sniffing.",
                            "schema": {"type": "string", "const": "nosniff"},
                        },
                    }
                    if name in {"201", "202"}:
                        response["headers"]["Location"] = {
                            "description": "Relative URL of the created resource.",
                            "schema": {"type": "string"},
                        }
                    if name in {"202", "429"}:
                        response["headers"]["Retry-After"] = {
                            "description": "Suggested polling/retry delay in seconds.",
                            "schema": {"type": "string"},
                        }
                    if int(name) >= 400:
                        response["content"]["application/json"]["example"] = {
                            "error": {
                                "code": "http_" + name,
                                "message": response["description"],
                                "request_id": "f8b348aa-05f1-4a0c-a706-11708aaf85e1",
                            }
                        }
                        if path.startswith("/v2/"):
                            response["content"]["application/json"]["example"]["error"].update(
                                code="invalid_request" if name == "422" else "request_failed",
                                phase="admission",
                                retryable=name in {"429", "502"},
                                guidance="Check request and operator configuration before submitting again.",
                            )
                for parameter in operation.get("parameters", []):
                    if parameter["in"] == "path":
                        parameter["description"] = "UUID returned when this resource was created."
                    elif parameter["name"] == "idempotency-key":
                        parameter["description"] = (
                            "Optional retry key; reuse with identical input only."
                        )
                if method == "post" and path in {"/v1/runs", "/v1/evaluation-plans"}:
                    operation["requestBody"]["content"]["application/json"]["example"] = (
                        RUN_EXAMPLE if path == "/v1/runs" else EVALUATION_EXAMPLE
                    )
                if method == "post" and path == "/v2/runs":
                    operation["requestBody"]["content"]["application/json"]["example"] = {
                        "target": {"connection_id": "refund-agent"},
                        "cases": [{"input": {"query": "Can I refund?"}}],
                        "load": {"concurrency": 3, "duration_seconds": 10, "max_requests": 20},
                        "evaluation": {"mode": "off"},
                    }
        app.openapi_schema = result
        return result

    app.openapi = schema
