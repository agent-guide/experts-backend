import os

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests hermetic from the developer's local environment.

    Settings loads `.env` and `EXPERT_*` variables. A developer's project `.env`
    would otherwise leak into every `Settings(...)` built in tests and override the values
    a test passes explicitly. Disable the env file and strip the prefix vars so each
    `Settings(...)` reflects only its kwargs and the in-code defaults.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in list(os.environ):
        if key.startswith("EXPERT_"):
            monkeypatch.delenv(key, raising=False)
