"""Run the actual Settings controller regression in the normal Python suite."""
from pathlib import Path
import shutil
import subprocess


def test_asr_settings_controller_completes_under_normal_suite():
    node = shutil.which('node')
    assert node, 'Node.js 22+ is required for frontend controller tests'
    version = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=5, check=True)
    assert int(version.stdout.lstrip('v').split('.')[0]) >= 22
    result = subprocess.run(
        [node, str(Path(__file__).with_name('nonbrowser_asr_settings.cjs'))],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # node:test rejects event-loop-completed pending promises; require its full
    # terminal summary as well as exit zero, not a partial controller assertion.
    lines = result.stdout.splitlines()
    for marker in ('# tests 8', '# pass 8', '# fail 0', '# cancelled 0'):
        assert lines.count(marker) == 1, result.stdout + result.stderr
