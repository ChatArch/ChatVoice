"""Regressions for native upstream error envelopes (no network)."""
import json
import struct

import pytest

from chatvoice.volc_plan_asr import parse_response


@pytest.mark.parametrize('error,expected', [
    ('Agent Plan deduction is not enabled for this account or seat.', 'entitlement'),
    ({'message': 'Enable the Agent Plan deduction setting before use.'}, 'entitlement'),
    ('Agent Plan subscription has expired.', 'entitlement'),
    ('The account quota is exhausted.', 'quota'),
    ('The supplied API key failed authentication.', 'authentication'),
])
def test_native_error_field_preserves_safe_failure_category(error, expected):
    body = json.dumps({'error': error}).encode()
    # Native error message: no sequence, JSON, uncompressed; numeric error
    # status precedes the exact payload length. No credential is included.
    frame = bytes((0x11, 0xF0, 0x10, 0)) + struct.pack('>II', 45000030, len(body)) + body
    response = parse_response(frame)
    assert response.code == 45000030
    assert response.error_reason == expected
    assert not response.valid_terminal
    assert response.text == ''


def test_unknown_error_is_not_invented_as_expired_subscription():
    body = json.dumps({'error': 'Unrecognized provider condition.'}).encode()
    frame = bytes((0x11, 0xF0, 0x10, 0)) + struct.pack('>II', 45000030, len(body)) + body
    assert parse_response(frame).error_reason == 'protocol'
