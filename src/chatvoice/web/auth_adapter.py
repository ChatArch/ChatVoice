"""Compatibility import for the shared ChatLogin ChatVoice-schema backend.

The host owns connection/lock/clock callbacks, HTTP mapping and business ACLs.
Authentication and session storage implementation live in ChatLogin.
"""
from chatlogin.backends import ChatVoiceAuth as AuthAdapter
from chatlogin.backends import ChatVoiceManagedStore as ManagedDirectoryStore
from chatlogin.backends import ChatVoiceSessionStore as HostSessionStore
from chatlogin.backends import initialize_chatvoice_managed_schema

__all__ = ["AuthAdapter", "HostSessionStore", "ManagedDirectoryStore", "initialize_chatvoice_managed_schema"]
