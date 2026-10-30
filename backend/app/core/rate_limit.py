"""
Rate limiting for the authentication endpoints — found missing during
the production audit. Account lockout (see auth_service.py,
MAX_FAILED_ATTEMPTS/LOCKOUT_MINUTES) already throttles repeated
attempts against one *specific* account, but does nothing against
distributed credential-stuffing across many different email addresses,
or plain endpoint-hammering. This adds IP-based rate limiting on top.

Uses slowapi's in-memory backend, which is correct for a single-worker
deployment but does NOT share state across multiple worker processes —
if this API is ever run with multiple uvicorn/gunicorn workers, this
should be pointed at a shared backend (slowapi supports Redis natively:
`Limiter(key_func=get_remote_address, storage_uri="redis://...")`).
Documented here rather than silently assumed correct at any scale.

IMPORTANT: this import is wrapped defensively. `slowapi` was added
without the ability to actually pip-install and run it in the sandbox
this was built in — if it (or a transitive dependency) fails to import
for any reason in a real environment, that failure must not be able to
take down the entire application. main.py imports `limiter` from here
at module level, so an unguarded ImportError here would mean *every*
endpoint in the API fails, not just login — a single missing/broken
"nice to have" dependency should never be a single point of failure for
a system this size. If slowapi is unavailable, rate limiting silently
degrades to a no-op (the @limiter.limit(...) decorator becomes a
pass-through) rather than blocking startup; a loud log line says so.
"""
import logging

logger = logging.getLogger("pms")

LOGIN_RATE_LIMIT = "10/minute"
PASSWORD_RESET_RATE_LIMIT = "5/minute"

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMITING_AVAILABLE = True
except Exception as exc:  # noqa: BLE001 - deliberately broad: any import-time failure here must degrade, not propagate
    logger.warning(
        "Rate limiting disabled: slowapi could not be imported (%s). "
        "Login/password-reset endpoints will run without rate limiting; "
        "account lockout (see auth_service.py) still applies.", exc,
    )
    RATE_LIMITING_AVAILABLE = False

    class _NoOpLimiter:
        """Drop-in stand-in for slowapi.Limiter when the real thing isn't
        available — .limit(...) just returns the original function
        unchanged, so every call site (main.py, routers/auth.py) works
        exactly as if no rate limit were configured, with zero special
        casing needed at those call sites."""
        def limit(self, *_args, **_kwargs):
            def decorator(func):
                return func
            return decorator

    limiter = _NoOpLimiter()
