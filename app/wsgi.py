"""WSGI entry point used by gunicorn: ``gunicorn app.wsgi:app``."""

from app.main import create_app

app = create_app()
