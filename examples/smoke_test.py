"""Run API and mock agent on real localhost sockets, benchmark, and stop both."""

import asyncio
import json
from pathlib import Path

import httpx
import uvicorn


async def main() -> None:
    """Exercise API submission, real Locust traffic, and polling over local sockets.

    The mock target needs no paid credentials. Explicit scorers demonstrate missing
    reference evidence, and configured judge credentials can enable paid scoring.
    Both local servers are stopped even if submission or assertions fail.
    """
    servers = [
        uvicorn.Server(
            uvicorn.Config(
                "benchmark_agents.api:app", host="127.0.0.1", port=9000, log_level="warning"
            )
        ),
        uvicorn.Server(
            uvicorn.Config(
                "examples.mock_agent:app", host="127.0.0.1", port=9001, log_level="warning"
            )
        ),
    ]
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    try:
        for _ in range(100):
            if all(server.started for server in servers):
                break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("Local servers failed to start")
        async with httpx.AsyncClient(base_url="http://127.0.0.1:9000") as client:
            response = await client.post(
                "/v1/runs", json=json.loads(Path("examples/run.json").read_text())
            )
            response.raise_for_status()
            for _ in range(200):
                result = (await client.get(response.json()["url"])).json()
                if result["status"] in {"completed", "completed_with_gaps", "failed"}:
                    break
                await asyncio.sleep(0.05)
            assert result["load_status"] == "completed", result
            assert result["metrics"]["requests"] == 20
            assert result["metrics"]["error_rate"] == 0
            assert result["metrics"]["engine"] == "locust"
            assert result["metrics"]["observed_peak_in_flight"] == 3
            assert result["plan"]["recommendations"][1]["status"] == "needs_data"
            print(
                json.dumps(
                    {
                        "id": result["id"],
                        "metrics": result["metrics"],
                        "evaluation": result["evaluation"],
                    },
                    indent=2,
                )
            )
    finally:
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
