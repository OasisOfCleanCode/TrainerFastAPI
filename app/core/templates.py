# app/core/templates.py
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=templates_dir)