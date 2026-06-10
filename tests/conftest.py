import os

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests hermetic from the developer's local environment.

    Settings loads `.env` / `.env.local` and `EXPERT_NEXT_*` variables. A developer's
    local `.env.local` (e.g. EXPERT_NEXT_NGENT_CWD_BASE) would otherwise leak into every
    `Settings(...)` built in tests and override the values a test passes explicitly. Disable
    the env files and strip the prefix vars so each `Settings(...)` reflects only its kwargs
    and the in-code defaults.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in list(os.environ):
        if key.startswith("EXPERT_NEXT_"):
            monkeypatch.delenv(key, raising=False)
