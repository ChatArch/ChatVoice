"""Public product retirement must not expose the parked Copilot beta."""
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_public_product_navigation_has_only_shipped_products():
    html = (ROOT / "src/chatvoice/web/static/index.html").read_text()
    nav = re.search(r'<nav class="product-tabs".*?</nav>', html, re.S)
    assert nav is not None
    assert "会中助手" not in nav.group()
    assert 'data-product="copilot"' not in nav.group()
    assert all(f'data-product="{name}"' in nav.group() for name in ("meeting", "studio", "conversation"))


def test_production_controller_refuses_beta_without_requesting_its_apis():
    node = shutil.which("node")
    assert node
    result = subprocess.run([node, str(Path(__file__).with_name("nonbrowser_copilot_retired.cjs"))], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines().count("PASS copilot-retired") == 1
