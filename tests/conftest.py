from pathlib import Path
import os
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_configure(config):
    config._offline_home = tempfile.TemporaryDirectory(prefix="chatvoice-pytest-")
    names = ("HOME", "CHATARCH_HOME", "CHATVOICE_HOME")
    config._original_homes = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ[name] = str(Path(config._offline_home.name) / name.lower())


def pytest_unconfigure(config):
    for name, value in getattr(config, "_original_homes", {}).items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    if hasattr(config, "_offline_home"):
        config._offline_home.cleanup()
