from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_app_starts_in_local_mode() -> None:
    app = AppTest.from_file(str(ROOT_DIR / "app.py"))

    app.run()

    assert len(app.exception) == 0
