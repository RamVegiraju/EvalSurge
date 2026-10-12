"""Prepared LangGraph native agent App; real inference, no load generation."""

from native_agent import create_native_app, run_server

app = create_native_app("langgraph")

if __name__ == "__main__":
    run_server(app)
