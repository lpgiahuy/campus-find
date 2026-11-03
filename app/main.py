from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Vòng đời ứng dụng: khởi tạo logging khi startup."""
    setup_logging()
    logger.info(f"Khởi động ứng dụng {settings.APP_NAME} [Môi trường: {settings.APP_ENV}]")
    yield
    logger.info(f"Tắt ứng dụng {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="CampusFind — University Lost-and-Found Management REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


app.include_router(health_router)
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
