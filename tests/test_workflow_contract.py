from pathlib import Path

from chatstyle import render_click_tree

from chatvoice.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _text_blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        chunk.split("```", 1)[0].rstrip()
        for chunk in text.split("```text\n")[1:]
    ]


def test_runtime_dependency_and_shared_tree_contract():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    cli = (ROOT / "src" / "chatvoice" / "cli.py").read_text(encoding="utf-8")

    assert '"click>=8.0,<9.0"' in pyproject
    assert '"chatstyle>=0.2.0,<0.3.0"' in pyproject
    assert '"chatenv>=0.2.10,<0.3.0"' in pyproject
    assert '[project.entry-points."chatenv.configs"]' in pyproject
    assert 'chatvoice = "chatvoice.config"' in pyproject
    assert "add_tree_option" in cli
    assert 'name="chatvoice"' in cli
    assert "_render_cli_tree" not in cli


def test_ci_checks_installed_and_built_wheel_contracts():
    workflow = (
        ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert 'python-version: ["3.10", "3.11", "3.12"]' in workflow
    assert "chatvoice --version" in workflow
    assert "chatvoice --tree" in workflow
    assert "chatvoice --tree-brief" in workflow
    assert "python -m build" in workflow
    assert "python -m twine check dist/*" in workflow
    assert '"$RUNNER_TEMP/chatvoice-wheel/bin/python" -m pip install dist/*.whl' in workflow
    assert "mkdocs build --strict" in workflow


def test_publish_workflow_is_tag_only_oidc_and_main_guarded():
    workflow = (
        ROOT / ".github" / "workflows" / "publish.yml"
    ).read_text(encoding="utf-8")

    assert "tags:" in workflow
    assert "workflow_dispatch" not in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "git fetch --no-tags origin main:refs/remotes/origin/main" in workflow
    assert 'git merge-base --is-ancestor "${GITHUB_SHA}" refs/remotes/origin/main' in workflow


def test_bilingual_tree_docs_match_registered_full_and_brief_trees():
    expected = [
        render_click_tree(main, root_name="chatvoice"),
        render_click_tree(main, root_name="chatvoice", brief=True),
    ]

    for path in (
        ROOT / "docs" / "cli-tree.md",
        ROOT / "docs" / "cli-tree.en.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "chatstyle.add_tree_option()" in text
        assert _text_blocks(path)[:2] == expected
