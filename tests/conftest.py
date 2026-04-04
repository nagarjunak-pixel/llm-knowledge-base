"""Shared pytest fixtures that give every test an isolated knowledge base."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import Settings, get_settings
from app.db import Database
from app.llm import LLMClient


@pytest.fixture
def kb(tmp_path: Path, monkeypatch):
    # Isolate the app from the real repo by pointing it at a tmp dir.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings(root_dir=tmp_path, db_path_name="test.db")
    settings.ensure_dirs()
    get_settings.cache_clear()
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    db = Database(settings.db_path)
    llm = LLMClient(api_key=None, model="offline-stub")
    return settings, db, llm


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """TestClient with an isolated settings singleton."""
    from fastapi.testclient import TestClient

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings(root_dir=tmp_path, db_path_name="test.db")
    settings.ensure_dirs()

    from app import main as main_module

    app = main_module.app

    def _override() -> Settings:
        return settings

    # Clear any stale overrides from prior tests, then install ours.
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = _override
    try:
        with TestClient(app) as c:
            yield c, settings
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
