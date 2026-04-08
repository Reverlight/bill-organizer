import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import settings
from app.db import async_sessionmaker, engine
from app.routers.workflow_router import router as workflow_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router)
