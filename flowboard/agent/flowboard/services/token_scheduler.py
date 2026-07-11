"""Token freshness scheduler.

Google's ``ya29.*`` Bearer tokens (the ones the Flowboard extension captures
from the user's labs.google session) typically expire in ~1 hour. If the
humanless image-to-video pipeline runs a long batch (say 30 short clips =
~30 min of renders) we stay well under that limit, but Sonnet's review
pointed out the risk: a slightly larger batch + slow renders + a hiccup
could push us past expiry, and Google's first 401 would silently kill
every subsequent request in that batch.

This scheduler:

  1. Tracks the last token capture timestamp (``flow_client._token_captured_at``).
  2. Before each request, checks if the token is older than
     ``TOKEN_MAX_AGE_S`` (default 50 min — 10 min safety margin under
     Google's 1h expiry).
  3. If stale, sends a ``force_recapture`` WS message to the extension.
     The extension's existing ``captureTokenFromFlowTab`` runs a
     credentialed ``fetch('/fx/tools/flow')`` against the active Flow
     tab, which causes Google's SPA to re-issue an ``Authorization``
     header. The extension's network observer picks it up and pushes
     it to the agent via the existing ``token_captured`` WS event.
  4. Waits up to ``RECAPTURE_WAIT_S`` seconds for the new token to land.
     On timeout, raises ``TokenRefreshError`` so the caller can decide
     whether to abort the batch or skip the item.

This is intentionally a *thin* layer over ``flow_client`` — it doesn't
duplicate any Bearer logic. All it does is glue the time-based check to
the existing capture path.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .flow_client import FlowClient

logger = logging.getLogger(__name__)


# Refresh 10 minutes before Google's 1h expiry. Chosen because:
#   * Render time for one 8s Veo 3.1 Lite clip = 60-90s typically
#   * A 30-clip batch runs ~30 min, leaves 20 min slack under 50-min mark
#   * If refresh fails we still have 10 min before Google-side failure
TOKEN_MAX_AGE_S: int = 50 * 60

# How long to wait for the extension's `token_captured` callback after
# we sent `force_recapture`. 15 s = enough for the credentialed fetch
# to round-trip + extension's network observer to fire + WS to deliver.
RECAPTURE_WAIT_S: float = 15.0


class TokenRefreshError(RuntimeError):
    """The extension couldn't deliver a fresh token within the wait window."""


class TokenScheduler:
    """Wraps FlowClient with a pre-request freshness check.

    Use as an async context manager around each pipeline run, or call
    ``ensure_fresh()`` directly before each /api/automate/image-to-video
    invocation.

    Example::

        scheduler = TokenScheduler(flow_client)
        await scheduler.ensure_fresh()           # no-op if token is recent
        result = await flow_client.api_request(...)
    """

    def __init__(self, flow_client: "FlowClient") -> None:
        self._flow_client = flow_client

    @property
    def token_age_s(self) -> float | None:
        """Seconds since the last token capture. None if no token yet."""
        captured_at = self._flow_client._token_captured_at
        if captured_at is None:
            return None
        return max(0.0, time.time() - captured_at)

    def is_stale(self) -> bool:
        """True if the current token is older than ``TOKEN_MAX_AGE_S``
        or if no token has ever been captured.
        """
        age = self.token_age_s
        if age is None:
            # No token yet — let the caller decide what to do. We treat
            # this as "not stale" because the normal request path will
            # error out cleanly with a clear "extension not connected"
            # message. This scheduler shouldn't paper over that.
            return False
        return age > TOKEN_MAX_AGE_S

    async def ensure_fresh(self) -> None:
        """If the cached token is older than the threshold, ask the
        extension to capture a new one and wait for it to land.

        Raises ``TokenRefreshError`` if no extension is connected, the
        recapture fails, or the new token doesn't arrive within the
        wait window.
        """
        if not self.is_stale():
            age = self.token_age_s
            logger.debug(
                "TokenScheduler: token age %.1fs (limit %ds) — fresh, skip",
                age if age is not None else 0.0,
                TOKEN_MAX_AGE_S,
            )
            return

        if not self._flow_client.connected:
            raise TokenRefreshError(
                "cannot refresh token: Chrome extension is not connected. "
                "Open Flow in Profile 6 once to restore the WebSocket."
            )

        age = self.token_age_s or 0.0
        logger.info(
            "TokenScheduler: token age %.1fs exceeds %ds — forcing recapture",
            age,
            TOKEN_MAX_AGE_S,
        )

        # Snapshot the current capture timestamp so we can detect when a
        # NEW one arrives. If _token_captured_at doesn't change within
        # RECAPTURE_WAIT_S, the extension failed to deliver a fresh token.
        previous_capture_at = self._flow_client._token_captured_at

        # Send `force_recapture` over the existing WS. The extension's
        # background.js handler runs `captureTokenFromFlowTab()`, which
        # fires a credentialed fetch on the Flow tab. The page's
        # Authorization header gets re-issued, the extension's webRequest
        # observer catches it, and a new `token_captured` event flows
        # back through the same WS — updating _token_captured_at.
        await self._flow_client._send(
            "force_recapture",
            {"reason": "scheduler_age", "age_s": age},
            timeout=RECAPTURE_WAIT_S,
        )

        # The WS message itself completes when the extension ACKs. But
        # the actual token delivery is a *separate* `token_captured`
        # inbound event handled by `flow_client._on_ws_message`. We
        # poll for the timestamp change because that path is event-
        # driven and not awaited from here.
        deadline = time.monotonic() + RECAPTURE_WAIT_S
        while time.monotonic() < deadline:
            if self._flow_client._token_captured_at != previous_capture_at:
                new_age = self.token_age_s or 0.0
                logger.info(
                    "TokenScheduler: fresh token captured, age %.1fs",
                    new_age,
                )
                return
            await asyncio.sleep(0.5)

        raise TokenRefreshError(
            f"extension did not deliver a fresh token within "
            f"{RECAPTURE_WAIT_S:.0f}s. The Flow tab may be closed or the "
            f"extension's webRequest observer may have stopped firing."
        )


# Module-level singleton — bound to the existing ``flow_client`` global.
# Routes import this and use ``token_scheduler.ensure_fresh()`` directly.
from .flow_client import flow_client  # noqa: E402

token_scheduler = TokenScheduler(flow_client)


__all__ = [
    "TOKEN_MAX_AGE_S",
    "RECAPTURE_WAIT_S",
    "TokenRefreshError",
    "TokenScheduler",
    "token_scheduler",
]