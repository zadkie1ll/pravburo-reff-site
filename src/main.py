"""Compatibility entrypoint. New deployments run ``src.site.main:app`` directly."""

from src.site.main import app

__all__ = ["app"]
