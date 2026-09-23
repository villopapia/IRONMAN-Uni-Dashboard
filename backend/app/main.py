from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    academic,
    academic_tracking,
    calendar,
    competitors,
    compliance,
    garmin,
    load,
    nutrition,
    overview,
    performance,
    training,
)
from .services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Fitness Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(academic.router, prefix="/api/academic", tags=["academic"])
app.include_router(academic_tracking.router, prefix="/api/academic", tags=["academic"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["competitors"])
app.include_router(nutrition.router, prefix="/api/nutrition", tags=["nutrition"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(garmin.router, prefix="/api/garmin", tags=["garmin"])
app.include_router(performance.router, prefix="/api/performance", tags=["performance"])
app.include_router(compliance.router, prefix="/api/compliance", tags=["compliance"])
app.include_router(load.router, prefix="/api/load", tags=["load"])
app.include_router(overview.router, prefix="/api/overview", tags=["overview"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
