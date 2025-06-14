# app/app.py

import os
from pathlib import Path

import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.config import BASE_PATH
from version import get_app_version
from app.core.templates import templates
from app.fast_api.v1.endpoints import site as web_routes
from app.fast_api.v1.endpoints import info as info_routers

from app.utils.logger import logger
from app.core.error_handlers import setup_exception_handlers
from app.core.middlewares import (
    LogRouteMiddleware,
    DynamicCORSMiddleware,
    StaticVersionMiddleware,
)
from app.db.dao.user import UsersDAO


def load_md_description(filename: str) -> str:
    """Загружает содержимое .md файла из той же директории, где находится текущий модуль"""
    file_path = BASE_PATH / 'descriptions' / filename
    return file_path.read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Lifespan для управления жизненным циклом приложения"""
    logger.info("Инициализация приложения...")
    setup_exception_handlers(app)
    await configure_routers()
    await UsersDAO.check_roles_in_db()
    logger.info("Приложение готово к работе")
    yield
    logger.info("Завершение работы приложения")


# Основное приложение (объединяем фронт и бэк)
app_main = FastAPI(
    lifespan=lifespan,
    title="Trainer API Application — part of the Oasis of Clean Code project",
    description=load_md_description("TrainerAPI.md"),
    swagger_ui_parameters={"persistAuthorization": True},
    swagger_ui_init_oauth={
        "clientId": "swagger-client",
        "appName": "Swagger UI TrainerAPI",
        "scopes": "USER",  # Используем явно заданные роли
        "usePkceWithAuthorizationCodeGrant": True,
    },
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app_info = FastAPI(
    lifespan=lifespan,
    title="🔐 Информация о проекте BeaHea",
    description=load_md_description("description_info_api.md"),
    root_path="/api/info",  # Корневой путь приложения, добавляемый ко всем URL (например, при развертывании за прокси).
    swagger_ui_parameters={"persistAuthorization": True},
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app = FastAPI(
    lifespan=lifespan,
    redirect_slashes=False,
    version=get_app_version(),
    contact=dict(name="", email="", telegram="@d_m_elec"),
)

# ====== Конфигурация ======
# app.add_middleware(FingerPrintMiddleware)
app.add_middleware(LogRouteMiddleware)
app.add_middleware(DynamicCORSMiddleware)
app.add_middleware(StaticVersionMiddleware, templates=templates)


app_info.add_middleware(LogRouteMiddleware)
app_info.add_middleware(DynamicCORSMiddleware)
app_info.add_middleware(StaticVersionMiddleware, templates=templates)



# Редиректы на Swagger и ReDoc
@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    return RedirectResponse(url="/api/docs")


@app.get("/redoc", include_in_schema=False)
async def redirect_redoc():
    return RedirectResponse(url="/api/redoc")


@app.get("/api", include_in_schema=False)
async def redirect_api():
    return RedirectResponse(url="/api/docs")



app.mount("/api/info", app_info)

static_dir = Path(__file__).parent / "app" / "static"
app.mount(
    "/static",
    StaticFiles(directory=static_dir),
    name="static"
)

# Для логов (если нужно)
logs_dir = Path(__file__).parent / "logs"
app.mount(
    "/logs",
    StaticFiles(directory=logs_dir),
    name="logs"
)

app.mount("/", app_main)




# ====== Защита API ======
# protected_swagger = ProtectedSwagger()
#
#
# @app.middleware("http")
# async def swagger_auth_middleware(request: Request, call_next):
#     if request.url.path.startswith('/api'):
#         return await protected_swagger.process_request(request, call_next)
#     return await call_next(request)





# ====== Инициализация роутеров ======


async def configure_routers():
    """Инициализация всех API роутеров"""
    logger.info("Инициализация API роутеров...")

    # API роутеры
    auth_api = AuthAPI()
    security_api = SecurityAPI()
    profile_api = ProfileAPI()
    user_api = UserAPI()
    admin_api = AdminAPI()
    background_api = BackgroundAPI()

    await auth_api.initialize_routes()
    await security_api.initialize_routes()
    await profile_api.initialize_routes()
    await user_api.initialize_routes()
    await admin_api.initialize_routes()
    await background_api.initialize_routes()

    # Подключаем API с префиксом /api
    app_main.include_router(auth_api.router, prefix="/api")
    app_main.include_router(security_api.router, prefix="/api")
    app_main.include_router(profile_api.router, prefix="/api")
    app_main.include_router(user_api.router, prefix="/api")
    app_main.include_router(admin_api.router, prefix="/api")
    app_main.include_router(background_api.router, prefix="/api")

    # Подключаем системные API с префиксом /api
    app_info.include_router(info_routers.info_router, tags=["Information"])

    # Подключаем веб-роутеры
    app_main.include_router(web_routes.web_router, tags=["Web"])

    logger.info("Все роутеры успешно инициализированы")


if __name__ == "__main__":
    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=8666,
        reload=True,
        proxy_headers=True,
        factory=False,  # Если не используешь функцию, возвращающую app
    )
