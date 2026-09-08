"""Regression tests for the regression runner's own fail-closed contract."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

import test_nonbrowser_flows as flows


@pytest.mark.parametrize("stdout", ["", "PASS tts success wav\n", "PASS tts success mp3 extra\n", "PASS tts success mp3\nPASS tts success mp3\n"])
def test_python_wrapper_rejects_missing_wrong_or_duplicate_completion(monkeypatch, stdout):
    monkeypatch.setattr(flows.shutil, "which", lambda _: "node")
    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "v22.18.0\n" if argv[-1] == "--version" else stdout, "")
    monkeypatch.setattr(flows.subprocess, "run", run)
    with pytest.raises(AssertionError):
        flows.test_nonbrowser_controller_flow(("tts", "success", "mp3"))


def test_python_wrapper_accepts_exact_completed_case(monkeypatch):
    monkeypatch.setattr(flows.shutil, "which", lambda _: "node")
    def run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "v22.18.0\n" if argv[-1] == "--version" else "PASS tts success mp3\n", "")
    monkeypatch.setattr(flows.subprocess, "run", run)
    flows.test_nonbrowser_controller_flow(("tts", "success", "mp3"))


@pytest.mark.parametrize("stdout", ["", "PASS wrong case\n", "PASS provider error survives close and resources are released extra\n"])
def test_realtime_python_wrapper_requires_completion(monkeypatch, stdout):
    import test_realtime_provider_errors as realtime
    monkeypatch.setattr(shutil, "which", lambda _: "node")
    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout, ""))
    with pytest.raises(AssertionError):
        realtime.test_realtime_controller_preserves_provider_error_after_close()


def test_realtime_unfinished_socket_boundary_cannot_exit_successfully():
    node = shutil.which("node")
    assert node, "Node.js 22+ is required"
    root = Path(__file__).resolve().parent
    script = f"""
      const h = require({json.dumps(str(root / 'nonbrowser_harness.cjs'))});
      const original = h.harness;
      h.harness = () => {{
        const app = original();
        const push = app.sockets.push;
        app.sockets.push = function (...sockets) {{
          for (const socket of sockets) socket.open = () => new Promise(() => {{}});
          return push.apply(this, sockets);
        }};
        return app;
      }};
      require({json.dumps(str(root / 'nonbrowser_realtime_error.cjs'))});
    """
    result = subprocess.run([node, "-e", script], text=True, capture_output=True, timeout=10)
    assert result.returncode != 0, "Unfinished realtime case incorrectly exited 0"
    assert "did not complete" in result.stderr, result.stderr
    assert "PASS provider error" not in result.stdout


def test_pending_production_handler_cannot_exit_successfully():
    node = shutil.which("node")
    assert node, "Node.js 22+ is required"
    root = Path(__file__).resolve().parent
    # Use the existing in-memory mutation facility: no production file writes.
    script = f"""
      const h = require({json.dumps(str(root / 'nonbrowser_harness.cjs'))});
      const original = h.harness;
      h.harness = () => original([
        'const audio = await response.blob();',
        'const audio = await new Promise(() => {{}});'
      ]);
      process.argv = [process.execPath, {json.dumps(str(root / 'nonbrowser_flows.cjs'))}, 'tts', 'success', 'mp3'];
      require({json.dumps(str(root / 'nonbrowser_flows.cjs'))});
    """
    result = subprocess.run([node, "-e", script], text=True, capture_output=True, timeout=10)
    assert result.returncode != 0, "Unfinished production promise incorrectly exited 0"
    assert "did not complete" in result.stderr, result.stderr
    assert "PASS tts success mp3" not in result.stdout
