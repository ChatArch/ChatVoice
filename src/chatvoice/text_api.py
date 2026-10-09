"""Independent OpenAI-compatible text requests, without web/DB/model imports.

Callers supply resolved ChatVoice values; this module never consults other
profiles or voice/global credentials. Errors contain no upstream response text.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
import json
import math
import time
from typing import Any
from urllib.parse import urlsplit
import urllib.request


class TextConfigurationError(ValueError):
    """Independent text configuration is incomplete or unsafe (HTTP 503)."""


class TextRequestError(RuntimeError):
    """Upstream text request failed; message is safe for public responses."""


@dataclass(frozen=True)
class TextSettings:
    base: str
    key: str = field(repr=False)
    model: str


def _values(values: Mapping[str, Any], purpose: str) -> tuple[str, str, str]:
    if purpose not in {'notes', 'title'}:
        raise ValueError('Text purpose must be notes or title')
    prefix = f'CHATVOICE_MEETING_{purpose.upper()}'
    return tuple(str(values.get(f'{prefix}_{suffix}') or '').strip()
                 for suffix in ('API_BASE', 'API_KEY', 'MODEL'))


def _safe_host(base: str) -> str | None:
    try:
        parsed = urlsplit(base)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or any(char.isspace() for char in base)):
            return None
        parsed.port  # validate malformed ports without disclosing the URL
        return parsed.hostname
    except ValueError:
        return None


def resolve_text_settings(values: Mapping[str, Any], purpose: str, *, req_model: str | None = None) -> TextSettings | None:
    """None means legacy routing; partial independent configuration fails closed.

    A request model override cannot repair a missing configured purpose model.
    """
    base, key, model = _values(values, purpose)
    if not base and not key:
        return None
    prefix = f'CHATVOICE_MEETING_{purpose.upper()}'
    if not all((base, key, model)):
        raise TextConfigurationError(f'{prefix}_API_BASE, {prefix}_API_KEY and {prefix}_MODEL must all be configured')
    if not _safe_host(base):
        raise TextConfigurationError(f'{prefix}_API_BASE must be an HTTP(S) URL without credentials, query or fragment')
    return TextSettings(base.rstrip('/'), key, (req_model or '').strip() or model)


def text_status(values: Mapping[str, Any], purpose: str) -> dict[str, Any] | None:
    """Safe independent status, including partial configurations; None is legacy."""
    base, key, model = _values(values, purpose)
    if not base and not key:
        return None
    return {'provider': 'chat-completions', 'base_host': _safe_host(base),
            'model': model or None, 'key_configured': bool(key),
            'configured': bool(base and key and model and _safe_host(base))}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a text key to a redirect destination.
        return None


def _open_request(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)


def _request(settings: TextSettings, messages: list[dict[str, str]], *, stream: bool = False,
             max_tokens: int | None = None, thinking_mode: str = 'provider-default') -> urllib.request.Request:
    if thinking_mode not in {'provider-default', 'ark-disabled'}:
        raise TextConfigurationError('Invalid text thinking mode')
    payload: dict[str, Any] = {'model': settings.model, 'messages': messages}
    if thinking_mode == 'ark-disabled':
        payload['thinking'] = {'type': 'disabled'}
    if stream:
        payload['stream'] = True
    if max_tokens is not None:
        payload['max_tokens'] = max_tokens
    return urllib.request.Request(
        settings.base + '/chat/completions',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': f'Bearer {settings.key}', 'Content-Type': 'application/json',
                 'Accept': 'text/event-stream' if stream else 'application/json',
                 'User-Agent': 'chatvoice-text/0.1'}, method='POST')


def _checked_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict) or 'error' in body:
        raise TextRequestError('Text service returned an invalid or error response')
    return body


def complete_text(settings: TextSettings, messages: list[dict[str, str]], *, timeout: float = 80,
                  max_tokens: int | None = None) -> dict[str, Any]:
    """Return nonempty final content; never substitute JSON/errors/reasoning."""
    try:
        request = _request(settings, messages, max_tokens=max_tokens)
        with _open_request(request, timeout=timeout) as response:
            body = _checked_body(json.loads(response.read().decode('utf-8')))
        choice = body['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise TextRequestError('Text service did not complete the text output')
        content = choice['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise TextRequestError('Text service returned empty or invalid content')
        return {'model': settings.model, 'content': content.strip(), 'raw_usage': body.get('usage')}
    except TextRequestError:
        raise
    except Exception:
        raise TextRequestError('Text service request failed or returned an invalid response') from None


def _positive_limit(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f'{name} must be a positive integer')
    return value


def _stream_may_continue(deadline: float | None, should_continue: Callable[[], bool] | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise TextRequestError('Text service stream exceeded configured deadline')
    if should_continue is not None and not should_continue():
        raise TextRequestError('Text service stream was cancelled')


def _readline_with_deadline(
    response: Any,
    *,
    limit: int,
    deadline: float | None,
    should_continue: Callable[[], bool] | None,
) -> bytes:
    """Read a bounded SSE line while checking cancellation between bytes.

    ``HTTPResponse.readline`` can remain inside one buffered call while a peer
    trickles a never-ending line. Copilot's small aggregate/line caps make a
    byte-at-a-time read acceptable and let its elapsed deadline take effect at
    a deterministic cooperative boundary without a watchdog thread.
    """
    line = bytearray()
    while True:
        _stream_may_continue(deadline, should_continue)
        chunk = response.read(1)
        # Cancellation/deadline can change during the read of the terminating
        # newline too; no final frame may bypass the post-read check.
        _stream_may_continue(deadline, should_continue)
        if not chunk:
            return bytes(line)
        if not isinstance(chunk, bytes):
            raise TextRequestError('Text service returned an invalid stream')
        line.extend(chunk)
        if len(line) > limit:
            raise TextRequestError('Text service stream exceeded configured limit')
        if chunk == b'\n':
            return bytes(line)


def stream_text(
    settings: TextSettings,
    messages: list[dict[str, str]],
    *,
    timeout: float = 120,
    thinking_mode: str = 'provider-default',
    max_tokens: int | None = None,
    max_line_bytes: int | None = None,
    max_event_bytes: int | None = None,
    max_stream_bytes: int | None = None,
    max_events: int | None = None,
    max_output_chars: int | None = None,
    max_output_bytes: int | None = None,
    deadline: float | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """Yield content deltas; errors, empty output and truncated streams raise.

    A normal finish marker or [DONE] is required; partial output is never done.
    Vendor-specific thinking is opt-in per request; default callers are unchanged.
    """
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be a finite positive number')
    if deadline is not None and (not isinstance(deadline, (int, float)) or not math.isfinite(deadline)):
        raise ValueError('deadline must be a finite monotonic timestamp')
    max_tokens = _positive_limit(max_tokens, 'max_tokens')
    max_line_bytes = _positive_limit(max_line_bytes, 'max_line_bytes')
    max_event_bytes = _positive_limit(max_event_bytes, 'max_event_bytes')
    max_stream_bytes = _positive_limit(max_stream_bytes, 'max_stream_bytes')
    max_events = _positive_limit(max_events, 'max_events')
    max_output_chars = _positive_limit(max_output_chars, 'max_output_chars')
    max_output_bytes = _positive_limit(max_output_bytes, 'max_output_bytes')
    response = None
    try:
        received_content = False
        finished = False
        stream_bytes = 0
        event_count = 0
        output_chars = 0
        output_bytes = 0
        _stream_may_continue(deadline, should_continue)
        request = _request(settings, messages, stream=True, max_tokens=max_tokens, thinking_mode=thinking_mode)
        response = _open_request(request, timeout=float(timeout))
        while True:
            _stream_may_continue(deadline, should_continue)
            if max_line_bytes is not None or deadline is not None or should_continue is not None:
                raw_line = _readline_with_deadline(
                    response,
                    limit=max_line_bytes or 64 * 1024,
                    deadline=deadline,
                    should_continue=should_continue,
                )
            else:
                raw_line = response.readline()
            if not raw_line:
                break
            stream_bytes += len(raw_line)
            if max_stream_bytes is not None and stream_bytes > max_stream_bytes:
                raise TextRequestError('Text service stream exceeded configured limit')
            line = raw_line.decode('utf-8').strip()
            if not line or line.startswith((':', 'event:', 'id:', 'retry:')):
                continue
            if not line.startswith('data:'):
                raise TextRequestError('Text service returned an invalid stream')
            data = line[5:].strip()
            event_count += 1
            if max_events is not None and event_count > max_events:
                raise TextRequestError('Text service stream exceeded configured limit')
            if max_event_bytes is not None and len(data.encode('utf-8')) > max_event_bytes:
                raise TextRequestError('Text service stream exceeded configured limit')
            if data == '[DONE]':
                finished = True
                break
            body = _checked_body(json.loads(data))
            choices = body.get('choices')
            if not isinstance(choices, list):
                raise TextRequestError('Text service returned an invalid stream')
            if not choices and body.get('usage'):
                continue
            if not choices:
                raise TextRequestError('Text service returned an invalid stream')
            choice = choices[0]
            delta = choice.get('delta', {}).get('content')
            if delta is not None and not isinstance(delta, str):
                raise TextRequestError('Text service returned invalid content')
            if delta:
                output_chars += len(delta)
                output_bytes += len(delta.encode('utf-8'))
                if ((max_output_chars is not None and output_chars > max_output_chars)
                        or (max_output_bytes is not None and output_bytes > max_output_bytes)):
                    raise TextRequestError('Text service stream exceeded configured limit')
                received_content = received_content or bool(delta.strip())
                yield delta
            reason = choice.get('finish_reason')
            if reason:
                if reason != 'stop':
                    raise TextRequestError('Text service did not complete the text output')
                finished = True
        if not received_content or not finished:
            raise TextRequestError('Text service returned empty or incomplete content')
    except TextRequestError:
        raise
    except Exception:
        raise TextRequestError('Text service stream failed or returned an invalid response') from None
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


def probe_text_configuration(values: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Minimal synthetic notes/title connectivity checks, only when explicit.

    Validate both boundaries before making any request. Output contains safe
    configuration metadata and success booleans, never content or credentials.
    max_tokens is an output parameter, not a hard reasoning/cost budget.
    """
    settings = {purpose: resolve_text_settings(values, purpose) for purpose in ('notes', 'title')}
    results = {}
    for purpose, config in settings.items():
        if config is None:
            continue
        prompt = ('Summarize this synthetic meeting in one sentence: the team agreed to write tests.'
                  if purpose == 'notes' else 'Give a short title for this synthetic meeting: the team agreed to write tests.')
        complete_text(config, [{'role': 'user', 'content': prompt}], timeout=30, max_tokens=64)
        results[purpose] = {**text_status(values, purpose), 'ok': True}
    return results
