"""Legacy development import shim.

The maintained ChatVoice web runtime lives in ``chatvoice.web.legacy_app`` and
is served through ``chatvoice serve app`` / ``chatvoice.web.server:create_app``.
This module remains only so older local scripts that import ``app.main`` keep
working while using the packaged runtime implementation.
"""

from chatvoice.web.legacy_app import *  # noqa: F401,F403
