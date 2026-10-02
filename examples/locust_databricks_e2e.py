"""Real REST API -> Locust -> Databricks streaming -> post-run FM judging."""

import asyncio
import json
import os
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv

from benchmark_agents.providers import DEFAULT_FM_ENDPOINT, workspace_client


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{Path('artifacts').resolve()}/locust-e2e.db"
    workspace = await asyncio.to_thread(workspace_client)
    os.environ["BENCHMARK_CONNECTIONS"] = json.dumps(
        {
            "workspace": {
                "url": workspace.config.host.rstrip("/") + "/serving-endpoints/chat/completions",
                "auth": "databricks",
            }
        }
    )
    endpoint = os.getenv("BENCHMARK_PLANNER_MODEL", DEFAULT_FM_ENDPOINT)
    body = {
        "target": {
            "url": workspace.config.host.rstrip("/") + "/serving-endpoints/chat/completions",
            "adapter": "openai-chat",
            "model": endpoint,
            "connection_id": "workspace",
        },
        "evaluation": {
            "description": "A refund policy assistant. Answers must address the question and correctly reflect the supplied reference policy.",
            "max_scored_requests": 4,
            "samples": [
                {
                    "inputs": {
                        "messages": [
                            {
                                "role": "system",
                                "content": "Policy: Opened items cannot be refunded. Unopened items can be refunded within 30 days. Answer in one short sentence.",
                            },
                            {"role": "user", "content": question},
                        ]
                    },
                    "expectations": {"expected_response": expected},
                }
                for question, expected in [
                    ("Can I refund an opened item?", "Opened items cannot be refunded."),
                    (
                        "Can I refund an unopened item purchased 10 days ago?",
                        "Yes, unopened items can be refunded within 30 days.",
                    ),
                ]
            ],
        },
        "load": {
            "concurrency": 2,
            "duration_seconds": 60,
            "max_requests": 4,
            "timeout_seconds": 60,
        },
    }
    server = uvicorn.Server(
        uvicorn.Config("benchmark_agents.api:app", host="127.0.0.1", port=9002, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        async with httpx.AsyncClient(base_url="http://127.0.0.1:9002", timeout=120) as client:
            submitted = await client.post("/v1/runs", json=body)
            submitted.raise_for_status()
            for _ in range(2400):
                response = await client.get(submitted.json()["url"])
                response.raise_for_status()
                result = response.json()
                if result["status"] in {
                    "completed",
                    "completed_with_gaps",
                    "failed",
                    "interrupted",
                }:
                    break
                await asyncio.sleep(0.1)
            assert result["status"] == "completed", result
            assert result["metrics"]["engine"] == "locust"
            assert result["metrics"]["requests"] == 4, result
            assert result["metrics"]["error_rate"] == 0, result
            assert result["metrics"]["observed_peak_in_flight"] == 2, result
            assert result["metrics"]["timing_successful_only"]["ttft_ms"]["count"] == 4
            assert result["plan"]["source"] == "llm"
            assert result["evaluation"]["status"] == "completed", result
            assert {r["scorer"] for r in result["evaluation"]["results"]} >= {
                "relevance",
                "correctness",
            }
            for score in result["evaluation"]["results"]:
                assert score["metrics"], score
            Path("artifacts/locust-databricks-e2e.json").write_text(json.dumps(result, indent=2))
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
        server.should_exit = True
        await task


if __name__ == "__main__":
    asyncio.run(main())
