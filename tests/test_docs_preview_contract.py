"""Production docs must preserve the shared development preview."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def deployment_script() -> str:
    workflow = (WORKFLOWS / "deploy.yaml").read_text(encoding="utf-8")
    marker = "      - name: Build and publish docs\n        run: |\n"
    assert marker in workflow, "Production workflow is missing the preview-preserving build block"
    block = workflow.split(marker, 1)[1]
    return "\n".join(line[10:] if line.startswith("          ") else line
                     for line in block.splitlines())


def test_docs_jobs_share_non_cancelling_lock_and_git_identity():
    for name in ("deploy.yaml", "preview.yaml"):
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "  group: docs-pages\n  cancel-in-progress: false\n" in workflow
        assert "git config user.name github-actions[bot]" in workflow
        assert "git config user.email 41898282+github-actions[bot]@users.noreply.github.com" in workflow
    assert "mike deploy dev -p --allow-empty" in (WORKFLOWS / "preview.yaml").read_text()


def test_production_uses_fresh_build_and_keeps_only_preview_artifacts():
    script = deployment_script()
    assert "mkdocs build --strict" in script
    assert "git ls-remote --heads origin gh-pages" in script
    assert '"${published}/dev"' in script
    assert '"${published}/versions.json"' in script
    assert "git worktree remove" in script
    assert "ghp-import --no-jekyll --push --force" in script
    assert "mkdocs gh-deploy --force" not in script


@pytest.mark.skipif(sys.platform != "linux", reason="Disposable Bash deployment shell is exercised on Linux; static contracts run everywhere")
@pytest.mark.parametrize("preview", [True, False], ids=["existing-preview", "first-publication"])
def test_production_preserves_preview_without_old_pages_and_cleans_worktree(tmp_path, preview):
    git_executable = shutil.which("git")
    bash_executable = shutil.which("bash")
    if not git_executable or not bash_executable:
        pytest.skip("Local Git and Bash are needed for the disposable deployment shell")

    home = tmp_path / "home"
    home.mkdir()
    child_env = {
        "HOME": str(home), "CHATARCH_HOME": str(tmp_path / "chatarch"),
        "TMPDIR": str(tmp_path), "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"],
    }

    def git(*args, cwd=tmp_path):
        result = subprocess.run([git_executable, *args], cwd=cwd, env=child_env,
                                text=True, capture_output=True, check=True, timeout=15)
        return result.stdout.strip()

    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote))
    source = tmp_path / "source"
    source.mkdir()
    git("init", cwd=source)
    git("config", "user.name", "Docs Test", cwd=source)
    git("config", "user.email", "docs-test@example.invalid", cwd=source)
    git("remote", "add", "origin", str(remote), cwd=source)
    (source / "README.md").write_text("fresh source", encoding="utf-8")
    git("add", "README.md", cwd=source)
    git("commit", "-m", "source", cwd=source)
    if preview:
        old = tmp_path / "published"
        old.mkdir()
        git("init", cwd=old)
        git("config", "user.name", "Docs Test", cwd=old)
        git("config", "user.email", "docs-test@example.invalid", cwd=old)
        (old / "dev").mkdir()
        (old / "dev/index.html").write_text("preserved preview", encoding="utf-8")
        (old / "versions.json").write_text('[{"version":"dev"}]', encoding="utf-8")
        (old / "obsolete.html").write_text("must not return", encoding="utf-8")
        git("add", ".", cwd=old)
        git("commit", "-m", "old publication", cwd=old)
        git("push", str(remote), "HEAD:refs/heads/gh-pages", cwd=old)

    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    build = tool_bin / "mkdocs"
    build.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
                     "assert sys.argv[1:] == ['build', '--strict']\n"
                     "Path('site').mkdir()\nPath('site/index.html').write_text('fresh production')\n",
                     encoding="utf-8")
    build.chmod(0o700)
    publisher = tool_bin / "ghp-import"
    publisher.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
                         "assert sys.argv[1:5] == ['--no-jekyll', '--push', '--force', '--message']\n"
                         "assert Path('site/index.html').read_text() == 'fresh production'\n"
                         "assert not Path('site/obsolete.html').exists()\n"
                         f"assert Path('site/dev/index.html').exists() == {preview!r}\n"
                         f"assert Path('site/versions.json').exists() == {preview!r}\n"
                         f"if {preview!r}: assert Path('site/dev/index.html').read_text() == 'preserved preview'\n"
                         "Path('published-ok').write_text('ok')\n", encoding="utf-8")
    publisher.chmod(0o700)
    runner = tmp_path / "runner"
    runner.mkdir()
    child_env.update({"PATH": str(tool_bin) + os.pathsep + child_env["PATH"],
                      "RUNNER_TEMP": str(runner), "GITHUB_SHA": git("rev-parse", "HEAD", cwd=source)})
    subprocess.run([bash_executable, "-c", deployment_script()], cwd=source, env=child_env,
                   text=True, capture_output=True, check=True, timeout=30)
    assert (source / "published-ok").read_text() == "ok"
    assert not (runner / "docs-published").exists()
    assert git("worktree", "list", "--porcelain", cwd=source).count("worktree ") == 1
