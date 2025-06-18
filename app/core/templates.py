# app/core/templates.py
from fastapi.templating import Jinja2Templates
from app.core.config import BASE_PATH

templates_dir = BASE_PATH / "templates"
templates = Jinja2Templates(directory=templates_dir)
