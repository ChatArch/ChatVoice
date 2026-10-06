from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('case', ['account','guest','guest-long','retained','failure','cancel','new','oversize','empty','open-error'])
def test_audio_import_controller(case):
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, str(Path(__file__).with_name('nonbrowser_audio_import.cjs')), case], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines().count('PASS audio-import ' + case) == 1


def test_audio_import_ui_has_file_input_progress_cancel_and_default_privacy():
    source = (Path(__file__).resolve().parents[1] / 'src/chatvoice/web/static/index.html').read_text()
    for name in ['import-meeting-audio','meeting-import-file','meeting-import-status','cancel-meeting-import']:
        assert f'id="{name}"' in source
    assert "meeting-import-file').addEventListener('change'" in source
    assert "cancel-meeting-import').addEventListener('click'" in source
    assert '128 MiB' in source
