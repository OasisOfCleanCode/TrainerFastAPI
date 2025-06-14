# app/api/v1/endpoints/site.py
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.templates import templates

web_router = APIRouter()

# ГЛАВНАЯ
@web_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Главная | Main",
            "static_version": datetime.now().strftime("%Y%m%d%H%M"),
        },
    )

@web_router.get("/private_policy", response_class=HTMLResponse)
async def profile(request: Request):
    return templates.TemplateResponse(
        "private_police.html",
        {
            "request": request,
            "title": "Политика конфиденциальности | Privacy Policy",
            "static_version": datetime.now().strftime("%Y%m%d%H%M"),
        },
    )


# Личный кабинет
@web_router.get("/login", response_class=HTMLResponse)
async def profile(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Авторизация | Authorization",
            "static_version": datetime.now().strftime("%Y%m%d%H%M"),
        },
    )


@web_router.get("/register", response_class=HTMLResponse)
async def profile(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "title": "Регистрация | Registration",
            "static_version": datetime.now().strftime("%Y%m%d%H%M"),
        },
    )


# Личный кабинет
@web_router.get("/account", response_class=HTMLResponse)
async def profile(request: Request):
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "title": "Личный кабинет | Personal office",
            "static_version": datetime.now().strftime("%Y%m%d%H%M"),
        },
    )
