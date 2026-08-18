"""CLI entrypoint for chatvoice."""

from __future__ import annotations

import inspect
import json as jsonlib
import os

import click

from chatvoice import __version__
from chatvoice.accounts import AccountRuntimeError, create_account, list_accounts
from chatvoice.asr import get_asr_channels
from chatvoice.client import (
    ChatVoiceApiError,
    create_remote_token,
    get_remote_conversation,
    get_remote_meeting,
    list_remote_conversations,
    list_remote_meetings,
    list_remote_tokens,
    revoke_remote_token,
)
from chatvoice.doctor import run_doctor
from chatvoice.health import get_status
from chatvoice.paths import ensure_runtime_dirs, state_paths
from chatvoice.service import render_service_plan, serve_app


def _purpose(command: click.Command) -> str:
    text = command.short_help or inspect.getdoc(command.callback) or ""
    return " ".join(text.strip().split()).rstrip(".")


def _parameter_piece(parameter: click.Parameter) -> str | None:
    if getattr(parameter, "hidden", False) or parameter.name == "help":
        return None
    if isinstance(parameter, click.Argument):
        piece = parameter.name.upper().replace("_", "-")
        if not parameter.required:
            piece = f"[{piece}]"
        if parameter.nargs == -1:
            piece = f"{piece}..."
        return piece
    if not isinstance(parameter, click.Option):
        return None
    option_names = [name for name in (*parameter.opts, *parameter.secondary_opts) if name.startswith("--")]
    if not option_names:
        option_names = [name for name in (*parameter.opts, *parameter.secondary_opts) if name.startswith("-")]
    if not option_names:
        return None
    if parameter.is_flag or parameter.flag_value is not None:
        piece = "/".join(option_names)
    else:
        metavar = parameter.metavar or parameter.name.upper().replace("_", "-")
        piece = f"{'/'.join(option_names)} {metavar}"
    if not parameter.required:
        piece = f"[{piece}]"
    return piece


def _command_signature(name: str, command: click.Command) -> str:
    pieces = [piece for piece in (_parameter_piece(parameter) for parameter in command.params) if piece]
    return " ".join([name, *pieces])


def _render_command_tree(command: click.Command, name: str, prefix: str, is_last: bool, lines: list[str]) -> None:
    connector = "└── " if is_last else "├── "
    line = f"{prefix}{connector}{_command_signature(name, command)}"
    purpose = _purpose(command)
    if purpose:
        line = f"{line}  # {purpose}"
    lines.append(line)
    if not isinstance(command, click.Group):
        return
    children = [(child_name, child) for child_name, child in command.commands.items() if not child.hidden]
    child_prefix = prefix + ("    " if is_last else "│   ")
    for index, (child_name, child) in enumerate(children):
        _render_command_tree(child, child_name, child_prefix, index == len(children) - 1, lines)


def _render_cli_tree(root: click.Group) -> str:
    children = [(name, command) for name, command in root.commands.items() if not command.hidden]
    lines = [f"chatvoice  # {_purpose(root)}"]
    root_options = [
        ("--help", "Show help for the current command."),
        ("--version", "Show package version."),
        ("--tree", "Print the registered CLI tree."),
    ]
    for index, (option, purpose) in enumerate(root_options):
        is_last = not children and index == len(root_options) - 1
        lines.append(f"{'└──' if is_last else '├──'} {option}  # {purpose}")
    for index, (child_name, child) in enumerate(children):
        _render_command_tree(child, child_name, "", index == len(children) - 1, lines)
    return "\n".join(lines)


def _emit(payload: object, *, as_json: bool = False) -> None:
    if as_json:
        click.echo(jsonlib.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                click.echo(f"{key}:")
                for child_key, child_value in value.items():
                    click.echo(f"  {child_key}: {child_value}")
            else:
                click.echo(f"{key}: {value}")
    else:
        click.echo(str(payload))


def _env_value(env_name: str, *, label: str) -> str:
    value = os.getenv(env_name, "")
    if not value:
        raise click.ClickException(f"Missing {label}; set environment variable {env_name}")
    return value


def _api_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except ChatVoiceApiError as exc:
        prefix = f"HTTP {exc.status_code}: " if exc.status_code else ""
        raise click.ClickException(prefix + str(exc)) from exc


@click.group(invoke_without_command=True, no_args_is_help=True)
@click.version_option(__version__, prog_name="chatvoice")
@click.option("--tree", "show_tree", is_flag=True, is_eager=True, help="Print the registered CLI tree.")
@click.pass_context
def main(ctx: click.Context, show_tree: bool) -> None:
    """ChatVoice command line interface."""
    if show_tree:
        click.echo(_render_cli_tree(ctx.command))
        ctx.exit()


@main.command("paths")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def paths_command(as_json: bool) -> None:
    """Show resolved ChatVoice runtime paths."""

    _emit(state_paths().as_dict(), as_json=as_json)


@main.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def doctor_command(as_json: bool) -> None:
    """Check local ChatVoice service readiness without secrets."""

    _emit(run_doctor(), as_json=as_json)


@main.group()
def serve() -> None:
    """Start packaged ChatVoice services."""


@serve.command("app")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host interface for Uvicorn.")
@click.option("--port", default=18087, show_default=True, type=int, help="Port for Uvicorn.")
@click.option("--reload", is_flag=True, help="Enable Uvicorn reload for development.")
@click.option("--workers", default=1, show_default=True, type=int, help="Number of Uvicorn workers. Keep 1 with SQLite.")
@click.option("--dry-run", is_flag=True, help="Print the sanitized service plan without starting.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output for --dry-run.")
def serve_app_command(host: str, port: int, reload: bool, workers: int, dry_run: bool, as_json: bool) -> None:
    """Start the packaged Speakr web application."""

    if dry_run:
        _emit(render_service_plan(host=host, port=port, workers=workers), as_json=as_json)
        return
    if workers != 1:
        click.echo("Warning: SQLite WAL supports one service node; use workers=1 unless storage has been migrated.", err=True)
    serve_app(host=host, port=port, reload=reload, workers=workers)


@main.group()
def health() -> None:
    """Read health from a running ChatVoice service."""


@health.command("status")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--timeout", default=5.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def health_status_command(url: str, timeout: float, as_json: bool) -> None:
    """Read the /api/status endpoint."""

    result = get_status(url, timeout=timeout)
    _emit(result, as_json=as_json)
    if not result.get("ok"):
        raise click.ClickException(str(result.get("error") or result.get("error_type") or "health check failed"))


@main.group()
def asr() -> None:
    """Inspect ASR provider configuration."""


@asr.command("channels")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def asr_channels_command(as_json: bool) -> None:
    """List ASR channels and API-provider readiness."""

    _emit(get_asr_channels(), as_json=as_json)


@main.group("accounts")
def accounts_group() -> None:
    """Manage invited accounts in the local service database."""


@accounts_group.command("add")
@click.argument("account")
@click.option("--display-name", default=None, help="Optional display name shown in the web UI.")
@click.option("--password-env", default="CHATVOICE_ACCOUNT_LOGIN", show_default=True, help="Environment variable containing the new account password.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def account_add_command(account: str, display_name: str | None, password_env: str, as_json: bool) -> None:
    """Create one invited account from the packaged runtime."""

    password = _env_value(password_env, label="new account password")
    try:
        payload = create_account(account, password, display_name)
    except (AccountRuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(payload, as_json=as_json)


@accounts_group.command("list")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def account_list_command(as_json: bool) -> None:
    """List invited account metadata without password material."""

    try:
        payload = {"accounts": list_accounts()}
    except AccountRuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(payload, as_json=as_json)


@main.group("tokens")
def tokens_group() -> None:
    """Manage service API tokens for automation."""


@tokens_group.command("create")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--account", required=True, help="Managed account name or email.")
@click.option("--password-env", default="CHATVOICE_ACCOUNT_LOGIN", show_default=True, help="Environment variable containing the account password.")
@click.option("--name", default="cli", show_default=True, help="Human-readable token name.")
@click.option("--expires-days", type=int, default=None, help="Optional token expiry in days.")
@click.option("--scope", "scopes", multiple=True, help="Token scope. Repeat for multiple scopes.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def token_create_command(url: str, account: str, password_env: str, name: str, expires_days: int | None, scopes: tuple[str, ...], timeout: float, as_json: bool) -> None:
    """Create a one-time-visible API token after account login."""

    password = _env_value(password_env, label="account password")
    payload = _api_call(create_remote_token, url, account, password, name, expires_days, scopes, timeout=timeout)
    _emit(payload, as_json=as_json)


@tokens_group.command("list")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--account", required=True, help="Managed account name or email.")
@click.option("--password-env", default="CHATVOICE_ACCOUNT_LOGIN", show_default=True, help="Environment variable containing the account password.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def token_list_command(url: str, account: str, password_env: str, timeout: float, as_json: bool) -> None:
    """List API token metadata without revealing token values."""

    password = _env_value(password_env, label="account password")
    payload = _api_call(list_remote_tokens, url, account, password, timeout=timeout)
    _emit(payload, as_json=as_json)


@tokens_group.command("revoke")
@click.argument("token_id")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--account", required=True, help="Managed account name or email.")
@click.option("--password-env", default="CHATVOICE_ACCOUNT_LOGIN", show_default=True, help="Environment variable containing the account password.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def token_revoke_command(token_id: str, url: str, account: str, password_env: str, timeout: float, as_json: bool) -> None:
    """Revoke an API token by id."""

    password = _env_value(password_env, label="account password")
    payload = _api_call(revoke_remote_token, url, account, password, token_id, timeout=timeout)
    _emit(payload, as_json=as_json)


@main.group("data")
def data_group() -> None:
    """Read meeting and conversation data from a running service."""


def _resolved_api_token(token_env: str) -> str:
    return _env_value(token_env, label="API token")


@data_group.command("meetings")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_meetings_command(url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """List meetings including transcripts and summaries."""

    payload = _api_call(list_remote_meetings, url, _resolved_api_token(token_env), timeout=timeout)
    _emit(payload, as_json=as_json)


@data_group.command("meeting")
@click.argument("meeting_id")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_meeting_command(meeting_id: str, url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """Read one meeting with transcript and summary."""

    payload = _api_call(get_remote_meeting, url, _resolved_api_token(token_env), meeting_id, timeout=timeout)
    _emit(payload, as_json=as_json)


@data_group.command("conversations")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_conversations_command(url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """List realtime conversations including messages."""

    payload = _api_call(list_remote_conversations, url, _resolved_api_token(token_env), timeout=timeout)
    _emit(payload, as_json=as_json)


@data_group.command("conversation")
@click.argument("conversation_id")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_conversation_command(conversation_id: str, url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """Read one realtime conversation with messages."""

    payload = _api_call(get_remote_conversation, url, _resolved_api_token(token_env), conversation_id, timeout=timeout)
    _emit(payload, as_json=as_json)


@main.group()
def service() -> None:
    """Plan and inspect ChatVoice service deployment."""


@service.command("plan")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host interface for the generated plan.")
@click.option("--port", default=18087, show_default=True, type=int, help="Service port for the generated plan.")
@click.option("--workers", default=1, show_default=True, type=int, help="Worker count for the generated plan.")
@click.option("--ensure-dirs", is_flag=True, help="Create runtime directories before printing the plan.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def service_plan_command(host: str, port: int, workers: int, ensure_dirs: bool, as_json: bool) -> None:
    """Render a sanitized service deployment plan."""

    if ensure_dirs:
        ensure_runtime_dirs()
    _emit(render_service_plan(host=host, port=port, workers=workers), as_json=as_json)


if __name__ == "__main__":
    main()
