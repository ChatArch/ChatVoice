"""Published managed web integration must use bounded provider releases."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_project_depends_on_published_bounded_managed_provider():
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^web\s*=\s*\[(.*)\]$', text, re.MULTILINE)
    assert match is not None
    web = match.group(1)
    assert '"ChatLogin>=0.2.0,<0.3.0"' in text
    assert "ChatLogin" not in web
    assert "git+" not in text
    assert "ChatLogin.git@main" not in text
