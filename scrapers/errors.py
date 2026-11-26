"""Keep credentials and untrusted upstream details out of diagnostics."""

from requests.exceptions import Timeout


class ScrapeError(RuntimeError):
    """An error with a locally constructed, safe diagnostic message."""


def safe_error_message(exc: Exception) -> str:
    """Never echo external exception text, URLs, headers or response bodies."""
    if isinstance(exc, ScrapeError):
        return str(exc)
    if isinstance(exc, (Timeout, TimeoutError)):
        return "Request timed out"
    return f"Unexpected error ({type(exc).__name__})"
