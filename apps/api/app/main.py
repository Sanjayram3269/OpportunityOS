from fastapi import FastAPI

from app.api.routes.ai_insight import router as ai_insight_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.companies import router as companies_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.exports import router as exports_router
from app.api.routes.leads import router as leads_router
from app.api.routes.matching import router as matching_router
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.followups import router as followups_router
from app.api.routes.outreach import router as outreach_router
from app.api.routes.planning import router as planning_router
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
app.include_router(planning_router)  # Before opportunities to avoid /opportunities/planning vs /{id} conflict
app.include_router(opportunities_router)
app.include_router(discovery_router)
app.include_router(matching_router)
app.include_router(ai_insight_router)
app.include_router(outreach_router)
app.include_router(followups_router)
app.include_router(campaigns_router)
app.include_router(exports_router)