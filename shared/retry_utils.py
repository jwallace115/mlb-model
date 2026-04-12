"""
Shared HTTP retry utility with exponential backoff.
Handles 429 rate limits and transient errors across all pipelines.
"""

import logging
import time

logger = logging.getLogger("retry_utils")


def retry_request(func, max_retries=3, base_wait=30, label="HTTP request"):
    """Retry a callable up to max_retries times with exponential backoff.

    Args:
        func: callable that performs the HTTP request and returns the result.
              Must raise on failure (e.g., requests.Response.raise_for_status()).
        max_retries: maximum number of retry attempts after first failure.
        base_wait: initial wait in seconds before first retry.
        label: descriptive label for log messages.

    Returns:
        The return value of func() on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exc = e
            err_msg = str(e)
            is_429 = "429" in err_msg or "Too Many Requests" in err_msg
            is_transient = is_429 or any(
                code in err_msg
                for code in ("500", "502", "503", "504", "timeout", "Timeout", "ConnectionError")
            )

            if not is_transient or attempt >= max_retries:
                logger.error("%s: failed after %d attempt(s): %s", label, attempt + 1, e)
                raise

            wait = base_wait * (2 ** attempt)
            kind = "429 rate limit" if is_429 else "transient error"
            logger.warning(
                "%s: attempt %d/%d failed (%s). Retrying in %ds...",
                label, attempt + 1, max_retries + 1, kind, wait,
            )
            time.sleep(wait)

    raise last_exc
