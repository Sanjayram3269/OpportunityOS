from fastapi import FastAPI

app = FastAPI(
    title="OpportunityOS API",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "opportunityos-api",
        "version": "0.1.0",
    }