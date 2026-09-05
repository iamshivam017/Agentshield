from fastapi import FastAPI

app = FastAPI(
    title="AgentShield API",
    version="0.1.0",
    description="Defense-only AI risk and trust layer for agentic payments.",
)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/api/v1", tags=["system"])
def api_version() -> dict[str, str]:
    return {"service": "agentshield-api", "version": "v1"}
