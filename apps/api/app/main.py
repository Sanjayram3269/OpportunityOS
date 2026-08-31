from fastapi import FastAPI

from app.api.routes.companies import router as companies_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.leads import router as leads_router
from app.api.routes.matching import router as matching_router
from app.api.routes.opportunities import router as opportunities_router
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
app.include_router(companies_router)
app.include_router(leads_router)
app.include_router(opportunities_router)
app.include_router(discovery_router)
app.include_router(matching_router)