from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.config import settings

app = FastAPI(
    title="CareerPilot API",
    version="0.1.0",
    description=(
        "CareerPilot job discovery and assisted-application API. "
        "Initial release always stops before submission."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "mode": settings.initial_submission_mode}
