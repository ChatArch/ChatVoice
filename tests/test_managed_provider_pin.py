"""Unreleased managed web integration must pin reviewed provider code."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = "ChatLogin @ git+https://github.com/ChatArch/ChatLogin.git@62541684499f6e32e4a6af8ca5c59ba28e82f765"


def test_web_extra_pins_the_merged_managed_provider_until_public_release():
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^web\s*=\s*\[(.*)\]$', text, re.MULTILINE)
    assert match is not None
    web = match.group(1)
    assert PROVIDER in web
    assert "ChatLogin>=0.1.6,<0.2.0" in text
    assert "ChatLogin.git@main" not in text
