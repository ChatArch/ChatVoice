"""Provider-neutral ASR selection and cached, non-billable status."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Mapping


PLAN_CHANNEL = "volcengine-plan"
PLAN_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async"
PLAN_RESOURCE = "volc.seedasr.sauc.duration"
CHANNELS = {"auto", PLAN_CHANNEL, "funasr-gpu", "funasr-cpu", "api-server", "stub-local"}
FAILURE_REASONS = {"configuration", "permission", "entitlement", "authentication", "quota", "network", "timeout", "protocol"}


@dataclass(frozen=True)
class PlanSettings:
    transport: str
    base: str
    key: str
    model: str
    resource_id: str
    user_audio_allowed: bool

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "PlanSettings":
        get = lambda name, default="": str(values.get(name, default) or "").strip()
        return cls(
            transport=get("CHATVOICE_ASR_PLAN_TRANSPORT", "volcengine-ws"),
            base=get("CHATVOICE_ASR_PLAN_BASE", PLAN_ENDPOINT),
            key=get("CHATVOICE_ASR_PLAN_API_KEY"),
            model=get("CHATVOICE_ASR_PLAN_MODEL", "bigmodel"),
            resource_id=get("CHATVOICE_ASR_PLAN_RESOURCE_ID", PLAN_RESOURCE),
            user_audio_allowed=get("CHATVOICE_ASR_PLAN_USER_AUDIO_ALLOWED").lower() in {"1", "true", "yes"},
        )

    @property
    def configured(self) -> bool:
        # Exact allowlist prevents a Plan key from reaching a paid endpoint or redirect target.
        return bool(self.key) and self.transport == "volcengine-ws" and self.base == PLAN_ENDPOINT and self.model == "bigmodel" and self.resource_id == PLAN_RESOURCE


@dataclass(frozen=True)
class Route:
    selected: str
    actual: str
    fallback_reason: str | None = None


class AsrRouter:
    def __init__(self, settings: PlanSettings, *, clock: Callable[[], float] = time.time) -> None:
        self.settings = settings
        self.clock = clock
        self.state = "unknown"
        self.reason: str | None = None
        self.checked_at: float | None = None
        self.expires_at: float | None = None
        self.speech_verified = False

    def _state(self) -> str:
        if self.expires_at is not None and self.clock() >= self.expires_at:
            return "stale"
        return self.state

    def mark_failure(self, reason: str) -> None:
        self.reason = reason if reason in FAILURE_REASONS else "protocol"
        self.state = "unavailable"
        self.checked_at = self.clock()
        self.expires_at = self.checked_at + (300 if self.reason in {"entitlement", "authentication", "quota"} else 60)
        self.speech_verified = False

    def mark_available(self, *, speech_verified: bool) -> None:
        self.state = "healthy"
        self.reason = None
        self.checked_at = self.clock()
        self.expires_at = self.checked_at + 300
        self.speech_verified = self.speech_verified or speech_verified

    def resolve(self, preference: str | None) -> Route:
        selected = preference or "auto"
        if selected not in CHANNELS:
            raise ValueError("unknown ASR channel")
        if selected != "auto" and selected != PLAN_CHANNEL:
            return Route(selected, selected)
        reason = None
        if not self.settings.configured:
            reason = "configuration"
        elif not self.settings.user_audio_allowed:
            reason = "permission"
        elif self._state() == "unavailable":
            reason = self.reason or "protocol"
        if selected == PLAN_CHANNEL:
            if reason:
                raise ValueError(f"Plan ASR unavailable: {reason}")
            return Route(selected, PLAN_CHANNEL)
        return Route("auto", "funasr-gpu", reason) if reason else Route("auto", PLAN_CHANNEL)

    def status(self, selected: str = "auto") -> dict[str, object]:
        try:
            route = self.resolve(selected)
            actual, fallback = route.actual, route.fallback_reason
        except ValueError:
            actual, fallback = selected, self.reason or ("configuration" if not self.settings.configured else "permission")
        return {
            "selected": selected,
            "default": "auto",
            "actual": actual,
            "fallback_reason": fallback,
            "plan": {
                "configured": self.settings.configured,
                "user_audio_allowed": self.settings.user_audio_allowed,
                "state": self._state(),
                "reason": self.reason,
                "checked_at": self.checked_at,
                "expires_at": self.expires_at,
                "ttl_seconds": max(0, round(self.expires_at - self.clock())) if self.expires_at is not None else 0,
                "functional": self._state() == "healthy",
                "speech_verified": self.speech_verified and self._state() == "healthy",
            },
        }
