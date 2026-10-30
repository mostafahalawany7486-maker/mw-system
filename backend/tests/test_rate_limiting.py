"""
Rate limiting tests. The limiter is disabled by default for every other
test in this suite (see conftest.py's `client` fixture) since its
in-memory counter is a process-global singleton that would otherwise
accumulate across the hundreds of tests that log in via the shared
_auth_headers() helper pattern used throughout this test suite. This
file is the one place that explicitly re-enables it to verify the
limiter itself is correctly wired up, then restores the disabled state
so it doesn't affect any other test file (pytest doesn't guarantee
file/test ordering, so this must not leak state either direction).
"""
import pytest
from app.core.rate_limit import limiter, LOGIN_RATE_LIMIT


@pytest.fixture()
def rate_limited_client(client):
    """Re-enables the limiter for the duration of one test, then turns
    it back off — every other test file expects it off."""
    limiter.reset()  # clear any counts left over from a previous enabled run
    limiter.enabled = True
    yield client
    limiter.enabled = False


def _limit_count() -> int:
    # LOGIN_RATE_LIMIT is a string like "10/minute" — the test only needs
    # the numeric ceiling, not the window, to know how many requests it
    # takes to trip the limiter.
    return int(LOGIN_RATE_LIMIT.split("/")[0])


def test_login_rate_limit_blocks_excessive_attempts(rate_limited_client, seeded_admin):
    limit = _limit_count()
    responses = []
    for _ in range(limit + 3):
        resp = rate_limited_client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
        responses.append(resp.status_code)

    assert 429 in responses, f"Expected a 429 after {limit} attempts, got status codes: {responses}"
    # everything up to the limit should have been processed normally (401, not 429)
    assert responses[0] == 401


def test_login_rate_limit_response_has_retry_after_header(rate_limited_client, seeded_admin):
    limit = _limit_count()
    resp = None
    for _ in range(limit + 3):
        resp = rate_limited_client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
        if resp.status_code == 429:
            break
    assert resp is not None and resp.status_code == 429
    assert "retry-after" in {k.lower() for k in resp.headers.keys()}


def test_login_rate_limit_is_disabled_by_default_for_other_tests(client, seeded_admin):
    """Sanity check on the fixture itself — the ordinary `client` fixture
    (used by every other test file) must NOT be rate-limited, even after
    the tests above deliberately tripped the limiter."""
    limit = _limit_count()
    for _ in range(limit + 5):
        resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
        assert resp.status_code == 200, "The default test client must never be rate-limited"
