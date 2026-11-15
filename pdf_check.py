"""Checks that attached PDF links can be opened by anyone (no Google sign-in).

Used by generate_page.py to warn about flyers that visitors won't be able to
open. Requests are made anonymously (no cookies or credentials), the same way
a visitor's browser would see the link if they weren't signed in.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import urlparse

SIGN_IN_HOSTS = {"accounts.google.com"}
TIMEOUT_SECONDS = 10


def check_public(url: str) -> str | None:
    """Return None if `url` opens without signing in, otherwise a reason string."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (d38calendar link check)"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return "requires sign-in or permission"
        if exc.code == 404:
            return "file not found (deleted, or not shared publicly)"
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return f"could not check ({getattr(exc, 'reason', exc)})"

    if urlparse(final_url).hostname in SIGN_IN_HOSTS:
        return "requires sign-in (not shared as 'Anyone with the link')"
    return None
