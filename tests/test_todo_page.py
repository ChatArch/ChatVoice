"""User-facing Markdown Todo workflow uses actual frontend controllers."""
from pathlib import Path
import shutil
import subprocess

import pytest

CASES = ["empty", "convert", "noAuto", "revise", "failure", "invalid", "late", "edited", "cancel", "existing", "persist", "noSummary", "duplicate", "legacy"]

@pytest.mark.parametrize("case", CASES)
def test_markdown_todo_page(case):
    node = shutil.which("node")
    assert node, "Node.js 22+ required"
    result = subprocess.run([node, str(Path(__file__).with_name("nonbrowser_todo_page.cjs")), case], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines().count("PASS todo-page " + case) == 1, result.stdout + result.stderr


def test_todo_reuses_prompt_styling_and_hides_idle_recorder():
    source = (Path(__file__).resolve().parents[1] / "src/chatvoice/web/static/index.html").read_text()
    assert source.count('class="summary-prompt" type="button" data-todo-prompt=') == 3
    assert '.todo-active .recording-console.idle' in source
    assert '.todo-active .recording-console.ended' in source
