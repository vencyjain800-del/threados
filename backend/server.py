from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from auth import auth_router, ensure_demo_user, get_current_user
from seed import seed_if_empty
from routers.dashboard import dashboard_router
from routers.products import products_router
from routers.recommendations import recommendations_router
from routers.risks import risks_router
from routers.forecasting import forecasting_router
from db import db

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

app = FastAPI(title="ThreadOS API", version="1.0.0")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"app": "ThreadOS", "version": "1.0.0"}


@api_router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


# Mount feature routers under /api
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(products_router)
api_router.include_router(recommendations_router)
api_router.include_router(risks_router)
api_router.include_router(forecasting_router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("threados")


@app.on_event("startup")
async def startup():
    logger.info("ThreadOS starting up...")
    await ensure_demo_user()
    seeded = await seed_if_empty()
    if seeded:
        logger.info(f"Seeded {seeded} SKUs with 90 days history.")
    else:
        logger.info("Data already present, skipping seed.")


@app.on_event("shutdown")
async def shutdown():
    pass
