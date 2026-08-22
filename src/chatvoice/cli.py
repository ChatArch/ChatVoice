"""CLI entrypoint for chatvoice."""

from __future__ import annotations

import json as jsonlib
import os

import click
try:
    from chatstyle import add_tree_option
except Exception:  # pragma: no cover - supports older public ChatStyle wheels.
    def add_tree_option(renderer_options=None):  # type: ignore[no-redef]
        def decorator(target):
            root = (renderer_options or {}).get("root_name", "chatvoice")

            def _print_tree(ctx, _param, value):
                if not value or ctx.resilient_parsing:
                    return None
                click.echo(
                    f"{root}\n"
                    "├── --help  # Show this message and exit.\n"
                    "├── --version  # Show the version and exit.\n"
                    "├── --tree  # Print the registered CLI tree and exit.\n"
                    "├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.\n"
                    "├── accounts\n"
                    "│   ├── add  # Create one invited account.\n"
                    "│   └── list  # List invited account metadata.\n"
                    "├── asr-channels  # List ASR channel readiness.\n"
                    "├── data\n"
                    "│   ├── conversation  # Read one realtime conversation.\n"
                    "│   ├── conversations  # Read realtime conversation metadata.\n"
                    "│   ├── meeting  # Read one meeting detail.\n"
                    "│   └── meetings  # Read meeting metadata.\n"
                    "├── doctor  # Check local service readiness.\n"
                    "├── health\n"
                    "│   └── status  # Read /api/status.\n"
                    "├── paths  # Show resolved runtime paths.\n"
                    "├── service\n"
                    "│   └── plan  # Show a service start plan.\n"
                    "├── serve\n"
                    "│   └── app  # Start the Speakr web app.\n"
                    "└── tokens\n"
                    "    ├── create  # Create a remote token.\n"
                    "    ├── list  # List remote token metadata.\n"
                    "    └── revoke  # Revoke a remote token."
                )
                ctx.exit()

            target = click.option("--tree-brief", is_flag=True, expose_value=False, callback=_print_tree, is_eager=True)(target)
            target = click.option("--tree", is_flag=True, expose_value=False, callback=_print_tree, is_eager=True)(target)
            return target
        return decorator

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


@click.group(
    name="chatvoice",
    invoke_without_command=True,
    no_args_is_help=True,
)
@click.version_option(__version__, prog_name="chatvoice")
@add_tree_option(renderer_options={"root_name": "chatvoice"})
def main() -> None:
    """ChatVoice command line interface."""


@main.command("paths")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def paths_command(as_json: bool) -> None:
    """Show resolved runtime paths; read-only text or JSON output."""

    _emit(state_paths().as_dict(), as_json=as_json)


@main.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def doctor_command(as_json: bool) -> None:
    """Check local service readiness; read-only and secret-safe."""

    _emit(run_doctor(), as_json=as_json)


@main.group()
def serve() -> None:
    """Start packaged ChatVoice services; long-running side effects."""


@serve.command("app")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host interface for Uvicorn.")
@click.option("--port", default=18087, show_default=True, type=int, help="Port for Uvicorn.")
@click.option("--reload", is_flag=True, help="Enable Uvicorn reload for development.")
@click.option("--workers", default=1, show_default=True, type=int, help="Number of Uvicorn workers. Keep 1 with SQLite.")
@click.option("--dry-run", is_flag=True, help="Print the sanitized service plan without starting.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output for --dry-run.")
def serve_app_command(host: str, port: int, reload: bool, workers: int, dry_run: bool, as_json: bool) -> None:
    """Start the Speakr web app; --dry-run only prints a safe plan."""

    if dry_run:
        _emit(render_service_plan(host=host, port=port, workers=workers), as_json=as_json)
        return
    if workers != 1:
        click.echo("Warning: SQLite WAL supports one service node; use workers=1 unless storage has been migrated.", err=True)
    serve_app(host=host, port=port, reload=reload, workers=workers)


@main.group()
def health() -> None:
    """Read health from a running ChatVoice service; no writes."""


@health.command("status")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--timeout", default=5.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def health_status_command(url: str, timeout: float, as_json: bool) -> None:
    """Read /api/status; returns redacted text or JSON."""

    result = get_status(url, timeout=timeout)
    _emit(result, as_json=as_json)
    if not result.get("ok"):
        raise click.ClickException(str(result.get("error") or result.get("error_type") or "health check failed"))


@main.group()
def asr() -> None:
    """Inspect ASR provider configuration; no secret values."""


@asr.command("channels")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def asr_channels_command(as_json: bool) -> None:
    """List ASR channel readiness; read-only and secret-safe."""

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
    """Create one invited account; writes the local service database."""

    password = _env_value(password_env, label="new account password")
    try:
        payload = create_account(account, password, display_name)
    except (AccountRuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(payload, as_json=as_json)


@accounts_group.command("list")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def account_list_command(as_json: bool) -> None:
    """List invited account metadata; read-only, without passwords."""

    try:
        payload = {"accounts": list_accounts()}
    except AccountRuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(payload, as_json=as_json)


@main.group("tokens")
def tokens_group() -> None:
    """Manage service API tokens; remote credential side effects."""


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
    """Create a remote token; prints its secret value exactly once."""

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
    """List remote token metadata; read-only, without token values."""

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
    """Revoke a remote API token by id; destructive credential write."""

    password = _env_value(password_env, label="account password")
    payload = _api_call(revoke_remote_token, url, account, password, token_id, timeout=timeout)
    _emit(payload, as_json=as_json)


@main.group("data")
def data_group() -> None:
    """Read meeting and conversation records from a running service."""


def _resolved_api_token(token_env: str) -> str:
    return _env_value(token_env, label="API token")


@data_group.command("meetings")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_meetings_command(url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """List meeting metadata; read-only text or JSON output."""

    payload = _api_call(list_remote_meetings, url, _resolved_api_token(token_env), timeout=timeout)
    _emit(payload, as_json=as_json)


@data_group.command("meeting")
@click.argument("meeting_id")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_meeting_command(meeting_id: str, url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """Read one meeting; outputs its transcript and summary."""

    payload = _api_call(get_remote_meeting, url, _resolved_api_token(token_env), meeting_id, timeout=timeout)
    _emit(payload, as_json=as_json)


@data_group.command("conversations")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_conversations_command(url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """List realtime conversation metadata; read-only output."""

    payload = _api_call(list_remote_conversations, url, _resolved_api_token(token_env), timeout=timeout)
    _emit(payload, as_json=as_json)


@data_group.command("conversation")
@click.argument("conversation_id")
@click.option("--url", default="http://127.0.0.1:18087", show_default=True, help="Base service URL.")
@click.option("--token-env", default="CHATVOICE_DATA_READ", show_default=True, help="Environment variable containing the API token.")
@click.option("--timeout", default=10.0, show_default=True, type=float, help="HTTP timeout in seconds.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON output.")
def data_conversation_command(conversation_id: str, url: str, token_env: str, timeout: float, as_json: bool) -> None:
    """Read one realtime conversation; outputs stored messages."""

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
    """Render a safe plan; --ensure-dirs creates runtime directories."""

    if ensure_dirs:
        ensure_runtime_dirs()
    _emit(render_service_plan(host=host, port=port, workers=workers), as_json=as_json)


if __name__ == "__main__":
    main()
