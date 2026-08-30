from fastapi import FastAPI

from app.api.routes.profiles import router as profiles_router


app = FastAPI(
    title="OpportunityOS API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "opportunityos-api",
        "version": "0.1.0",
    }


app.include_router(profiles_router)