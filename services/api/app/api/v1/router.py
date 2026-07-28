from fastapi import APIRouter

from .answers import router as answers_router
from .applications import router as applications_router
from .browser_runs import router as browser_runs_router
from .discovery import router as discovery_router
from .health import router as health_router
from .jobs import router as jobs_router
from .matches import router as matches_router
from .profiles import router as profiles_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router, tags=["health"])
router.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
router.include_router(matches_router, prefix="/matches", tags=["matches"])
router.include_router(applications_router, prefix="/applications", tags=["applications"])
router.include_router(browser_runs_router, prefix="/applications", tags=["browser-runs"])
router.include_router(answers_router, prefix="/answers", tags=["answers"])
router.include_router(discovery_router, prefix="/discovery/runs", tags=["discovery"])
