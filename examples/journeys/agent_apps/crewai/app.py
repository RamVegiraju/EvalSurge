"""Prepared CrewAI native entrypoint; deployment unresolved, no load generation."""

from native_agent import create_native_app, run_server

app = create_native_app("crewai")

if __name__ == "__main__":
    run_server(app)
