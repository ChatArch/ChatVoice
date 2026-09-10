"""Run the shipped controllers and registered handlers without a browser."""
from pathlib import Path
import shutil
import subprocess

import pytest


CASES = (
    [("title", mode) for mode in ("success", "empty", "failure", "late", "manual")]
    + [("clone", mode) for mode in ("success", "guest", "noReference", "noConsent", "failed", "stale", "staleCreate", "staleAudio", "poll")]
    + [("realtime", mode) for mode in ("success", "connectFailure", "micFailure")]
    + [("meeting",), ("token",), ("navigation",), ("lateRevision",), ("mutations",), ("asrFinish",), ("access", "success"), ("access", "failure")]
    + [("recording", state, action) for state in ("connecting", "recording", "paused", "finishing") for action in ("reset", "new", "delete")]
    + [("revision", "success", str(preset)) for preset in range(4)]
    + [("revision", mode) for mode in ("error", "truncated")]
    + [("summary", mode) for mode in ("success", "failure", "late", "empty")]
    + [("tts", mode, format_name) for mode in ("success", "long", "empty", "error", "timeout", "emptyAudio") for format_name in ("mp3", "wav")]
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: "-".join(case))
def test_nonbrowser_controller_flow(case):
    node = shutil.which("node")
    assert node, "Node.js 22+ is required for offline controller regression"
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5, check=True)
    assert int(version.stdout.lstrip("v").split(".")[0]) >= 22, "Use Node.js 22+"
    result = subprocess.run(
        [node, str(Path(__file__).with_name("nonbrowser_flows.cjs")), *case],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected = "PASS " + " ".join(case)
    assert result.stdout.splitlines().count(expected) == 1, (
        f"Controller case did not complete exactly once: {expected}\n" + result.stdout + result.stderr
    )
