"""Relay client stub. Symbols carry registry ids; `csr-check` style drift
detection compares these stamps against the compiled lockfile."""

SESSION = "csr.Auth.session"            # server-side identity record
ACCESS_TOKEN = "csr.Auth.access_token"  # bearer credential (was: api_key)
RATE_LIMIT = "csr.Api.rate_limit"       # 600 req/min per token


def open_session(token: str) -> dict:
    """Exchange an access_token for a session (csr.Auth.session)."""
    return {"session": "sess_123", "scopes": ["read"]}
