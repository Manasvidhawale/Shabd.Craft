"""Regression coverage for runtime settings and retained-resource behavior."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from types import SimpleNamespace

import openai

import src.config as config
from src.config import Settings, settings, use_settings
from src.providers import openai_provider
from src.schemas import Experiment
from src import ui_helpers


def test_database_uses_current_runtime_path(monkeypatch, test_db_path):
    first_path = test_db_path
    second_path = test_db_path.with_name("second-workspace.db")

    monkeypatch.setattr(settings, "db_path", str(first_path))
    first_db = ui_helpers.get_database()
    first_db.create_experiment(Experiment(name="first"))

    monkeypatch.setattr(settings, "db_path", str(second_path))
    second_db = ui_helpers.get_database()

    assert first_db.db_path == str(first_path)
    assert second_db.db_path == str(second_path)
    assert second_db.list_experiments() == []


def test_runtime_settings_reset_to_environment_before_session_overrides(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    monkeypatch.setenv("SHABDCRAFT_DEFAULT_MODEL", "gpt-4")
    monkeypatch.setattr(
        ui_helpers,
        "st",
        SimpleNamespace(session_state={
            "user_default_model": "gpt-4o",
            "user_openai_api_key": "",
        }),
    )

    ui_helpers.apply_user_settings_to_runtime()

    assert settings.openai_api_key == "environment-key"
    assert settings.default_model == "gpt-4o"

    ui_helpers.st.session_state = {}
    ui_helpers.apply_user_settings_to_runtime()

    assert settings.openai_api_key == "environment-key"
    assert settings.default_model == "gpt-4"


def test_provider_client_uses_latest_timeout_without_reusing_old_client(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created.append(self)

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setattr(openai_provider.settings, "timeout", 7)
    first = openai_provider._get_openai_client("first-key", None)

    monkeypatch.setattr(openai_provider.settings, "timeout", 13)
    second = openai_provider._get_openai_client("second-key", "https://example.test")

    assert first is not second
    assert first.kwargs["timeout"] == 7
    assert first.kwargs["api_key"] == "first-key"
    assert second.kwargs["timeout"] == 13
    assert second.kwargs["api_key"] == "second-key"
    assert second.kwargs["base_url"] == "https://example.test"


def test_settings_contexts_remain_isolated_in_worker_threads():
    first_settings = Settings()
    first_settings.openai_api_key = "session-one-key"
    second_settings = Settings()
    second_settings.openai_api_key = "session-two-key"

    def read_active_key():
        return settings.openai_api_key

    with ThreadPoolExecutor(max_workers=2) as executor:
        with use_settings(first_settings):
            first_context = copy_context()
        with use_settings(second_settings):
            second_context = copy_context()
        first = executor.submit(first_context.run, read_active_key)
        second = executor.submit(second_context.run, read_active_key)

    assert first.result() == "session-one-key"
    assert second.result() == "session-two-key"


def test_reload_reads_updated_dotenv_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SHABDCRAFT_DEFAULT_MODEL=gpt-4\n", encoding="utf-8")
    monkeypatch.setattr(config, "_ENV_FILE", env_file)
    monkeypatch.delenv("SHABDCRAFT_DEFAULT_MODEL", raising=False)

    runtime_settings = Settings()
    assert runtime_settings.default_model == "gpt-4"

    env_file.write_text("SHABDCRAFT_DEFAULT_MODEL=gpt-4o\n", encoding="utf-8")
    runtime_settings._reload()
    assert runtime_settings.default_model == "gpt-4o"
