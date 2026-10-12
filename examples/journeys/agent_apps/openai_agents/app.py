"""Prepared OpenAI Agents native agent App; real inference, no load generation."""

from native_agent import create_native_app, run_server

app = create_native_app("openai-agents")

if __name__ == "__main__":
    run_server(app)
