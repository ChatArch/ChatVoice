#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"

python_bin="${PYTHON:-python3}"
venv="${ASR_GPU_VENV:-.venv-asr-gpu}"

if [[ ! -x "$venv/bin/python" ]]; then
  "$python_bin" -m venv "$venv"
fi

"$venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$venv/bin/python" -m pip install \
  --index-url https://pypi.org/simple \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  'torch==2.5.1+cu121' \
  'torchvision==0.20.1+cu121' \
  'torchaudio==2.5.1+cu121'
"$venv/bin/python" -m pip install \
  funasr modelscope soundfile scipy librosa pydub ffmpeg-python

"$venv/bin/python" - <<'PY'
import json, sys
mods = {}
for name in ['torch', 'torchaudio', 'funasr', 'modelscope', 'soundfile', 'numpy']:
    try:
        mod = __import__(name)
        mods[name] = getattr(mod, '__version__', 'installed')
    except Exception as exc:
        mods[name] = type(exc).__name__ + ': ' + str(exc)
try:
    import torch
    cuda = {'available': torch.cuda.is_available(), 'version': torch.version.cuda, 'device_count': torch.cuda.device_count()}
    if torch.cuda.is_available():
        cuda['device0'] = torch.cuda.get_device_name(0)
except Exception as exc:
    cuda = {'error': repr(exc)}
print(json.dumps({'python': sys.version, 'mods': mods, 'cuda': cuda}, ensure_ascii=False, indent=2))
PY
