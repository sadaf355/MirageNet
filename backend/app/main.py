from contextlib import asynccontextmanager
from time import perf_counter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.seed import seed_nodes
from app.routers import alerts, decoys, incidents, network, scenarios, system, sensors, evaluation, play, adaption

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_nodes(db)
        from app.models import Decoy
        if db.query(Decoy).count() == 0:
            from app.services.forge import forge_decoys
            forge_decoys(db, 60, company_profile="Northwind Logistics demo")
            staged = db.query(Decoy).filter(Decoy.status == "staged").all()
            for decoy in staged:
                decoy.status = "deployed"
            db.commit()
    yield

app = FastAPI(title=settings.app_name, version="0.1.0",
              description="Synthetic, sandbox-only cyber deception and incident-story simulator.",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(system.router)
app.include_router(network.router)
app.include_router(alerts.router)
app.include_router(sensors.router)
app.include_router(decoys.router)
app.include_router(incidents.router)
app.include_router(scenarios.router)
app.include_router(evaluation.router)
app.include_router(play.router)
app.include_router(adaption.router)

@app.get("/")
def root():
    return {"name": "MirageNet", "api_docs": "/docs", "status": "ready",
            "safety_mode": "synthetic-sandbox-only"}


@app.middleware("http")
async def measure_sensor_endpoint_latency(request, call_next):
    """Measure actual HTTP request/response latency for sensor endpoints."""
    started = perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api/sensor/"):
        response.headers["X-Sensor-Latency-Seconds"] = f"{perf_counter() - started:.6f}"
    return response
