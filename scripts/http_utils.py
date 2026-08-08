#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
http_utils.py — shared HTTP helper for ct-literature (exponential-backoff retry).

Used by all three fetchers (OpenAlex / Europe PMC / Semantic Scholar) to centralize:
  - HTTP 429: read the `Retry-After` header and wait that many seconds before retry (compliant backoff)
  - 5xx / connection errors / timeouts: exponential backoff (backoff ** (attempt-1))
  - 4xx parameter errors: treated as non-retryable and raised immediately
  - retries exhausted: raise HttpError; the caller decides degradation or abort

Background: OpenAlex has required an API key since 2026-02-13 — without a key only
100 credits/day (officially "not suitable for production"); a free key lifts the cap
to 100k/day. A key enters the keyed pool via the `Authorization: Bearer <key>` header;
even with a key, keep the polite-pool `mailto` identity. This module provides
build_openalex_headers() to construct those headers uniformly.

Zero confidential data or information input; reads only public literature.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "ct-literature/0.3.3"

# ── Lightweight .env key obfuscation (XOR+base64) ──────────────────────────────
# If the .env (holding the user's PRIVATE OpenAlex/S2 key) is ever accidentally
# packaged by a platform that ignores .gitignore/.clawhubignore (e.g. SkillHub),
# the shipped value is NOT the plaintext key — it fails naive grep/scan matching.
# NOT cryptography (the XOR key below is public); the real safeguard is that .env
# stays git/clawhub-ignored AND is stripped before any publish. _deobfuscate() is
# backward-compatible with a plaintext .env (returns the value unchanged on failure).
_OBF_XOR_KEY = b"ct-lit-obf-2026"


def _deobfuscate(val):
    """Reverse XOR+base64; return `val` unchanged if it isn't an obfuscated blob."""
    if not val:
        return val
    try:
        raw = base64.b64decode(val, validate=True)
        return bytes(c ^ _OBF_XOR_KEY[i % len(_OBF_XOR_KEY)]
                      for i, c in enumerate(raw)).decode("utf-8")
    except Exception:
        return val


class HttpError(Exception):
    """Unrecoverable HTTP / request error (retries exhausted or non-retryable 4xx)."""

    def __init__(self, message, status=None, retryable=False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable

    def __str__(self):
        if self.status is not None:
            return "[HTTP %s] %s" % (self.status, super().__str__())
        return super().__str__()


def get_json(url, headers=None, timeout=45, max_retries=4, backoff=2.0):
    """GET `url` and parse JSON, with built-in exponential-backoff retries.

    Returns: parsed dict / list.
    Raises: HttpError (retries exhausted or unrecoverable 4xx). Caller must
    catch and degrade as needed.

    Retry policy:
      - 429 / 5xx: retryable; wait = Retry-After (if present) or backoff**(attempt-1) seconds
      - URLError / timeout / connection error: retryable; wait = backoff**(attempt-1) seconds
      - 4xx (other than 429): non-retryable; raise immediately
    """
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            r = urllib.request.urlopen(req, timeout=timeout)
            raw = r.read()
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                wait = _retry_after(e) or (backoff ** (attempt - 1))
                print("[WARN] HTTP %s on %s (attempt %d/%d) -> retry in %.1fs"
                      % (e.code, _short(url), attempt, max_retries, wait))
                if attempt < max_retries:
                    time.sleep(wait)
                    continue
                raise HttpError("HTTP %s after %d retries" % (e.code, max_retries),
                                status=e.code, retryable=True)
            # 4xx parameter error: non-retryable
            raise HttpError("HTTP %s (non-retryable)" % e.code,
                            status=e.code, retryable=False)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            wait = backoff ** (attempt - 1)
            print("[WARN] request error on %s (attempt %d/%d): %s -> retry in %.1fs"
                  % (_short(url), attempt, max_retries, e, wait))
            if attempt < max_retries:
                time.sleep(wait)
                continue
            raise HttpError("request failed after %d retries: %s" % (max_retries, e),
                            retryable=True)
        except Exception as e:  # noqa: BLE001 - catch-all fallback, keep context
            wait = backoff ** (attempt - 1)
            print("[WARN] unexpected error on %s (attempt %d/%d): %s -> retry in %.1fs"
                  % (_short(url), attempt, max_retries, e, wait))
            if attempt < max_retries:
                time.sleep(wait)
                continue
            raise HttpError("unexpected failure after %d retries: %s" % (max_retries, e),
                            retryable=True)
    raise HttpError("unreachable retry loop", retryable=True)


def build_openalex_headers(api_key=None, mailto="dev@example.com"):
    """Build OpenAlex request headers: polite-pool mailto (in UA) + optional Bearer key.

    OpenAlex recommends the polite-pool via a `mailto` query param or a mailto in the
    UA. With a key, additionally inject `Authorization: Bearer <key>` to enter the
    keyed pool.
    """
    hdrs = {"User-Agent": UA}
    if mailto:
        hdrs["User-Agent"] = "%s (mailto:%s)" % (UA, mailto)
    if api_key:
        hdrs["Authorization"] = "Bearer %s" % api_key
    return hdrs


def load_openalex_key(env_var="OPENALEX_API_KEY"):
    """Load the OpenAlex key, zero-dependency and ready out of the box:

    1. Prefer the env var `OPENALEX_API_KEY` (shell export / container injection);
    2. Otherwise try `.env` at the skill root or in scripts/ (hand-parsed, no python-dotenv);
       on a hit, write back to `os.environ` so later calls reuse it.

    Returns the key string or None. The key itself is NEVER printed to logs / stdout.
    """
    val = os.environ.get(env_var)
    if val:
        return val
    here = os.path.dirname(os.path.abspath(__file__))
    skill_root = os.path.dirname(here)
    for cand in (os.path.join(skill_root, ".env"), os.path.join(here, ".env")):
        if not os.path.exists(cand):
            continue
        try:
            with open(cand, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line or _line.startswith("#"):
                        continue
                    if _line.startswith(env_var + "="):
                        _, _, _v = _line.partition("=")
                        _v = _v.strip().strip('"').strip("'")
                        _v = _deobfuscate(_v)
                        if _v:
                            os.environ[env_var] = _v
                            return _v
        except Exception:
            pass
    return None


def get_openalex_key(env_var="OPENALEX_API_KEY"):
    """Backward-compatible alias of load_openalex_key."""
    return load_openalex_key(env_var)


def build_s2_headers(api_key=None):
    """Build Semantic Scholar request headers: optional `x-api-key` for the keyed pool
    (much looser rate limit).

    Unauthenticated S2 Graph API is extremely strict (~1 req/s; shared-IP bursts get
    blocklisted for minutes); with a key it enters the keyed pool and throughput jumps.
    Runs without a key too, but easily hits 429 and degrades.
    """
    hdrs = {"User-Agent": UA}
    if api_key:
        hdrs["x-api-key"] = api_key
    return hdrs


def load_s2_key(env_var="SEMANTIC_SCHOLAR_API_KEY"):
    """Load the Semantic Scholar API key; same logic as load_openalex_key
    (env first, then .env fallback).

    Returns the key string or None. The key itself is NEVER printed to logs / stdout.
    """
    val = os.environ.get(env_var)
    if val:
        return val
    here = os.path.dirname(os.path.abspath(__file__))
    skill_root = os.path.dirname(here)
    for cand in (os.path.join(skill_root, ".env"), os.path.join(here, ".env")):
        if not os.path.exists(cand):
            continue
        try:
            with open(cand, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line or _line.startswith("#"):
                        continue
                    if _line.startswith(env_var + "="):
                        _, _, _v = _line.partition("=")
                        _v = _v.strip().strip('"').strip("'")
                        _v = _deobfuscate(_v)
                        if _v:
                            os.environ[env_var] = _v
                            return _v
        except Exception:
            pass
    return None


# Module-level guard so the "no key" notice prints at most once per process.
_S2_KEY_NOTICE_SHOWN = False


def notify_s2_key_if_missing(api_key=None, env_var="SEMANTIC_SCHOLAR_API_KEY"):
    """Print a one-time, locale-aware notice when no Semantic Scholar API key is configured.

    Informational only — never blocks execution. S2's key requires a manual form
    review (not auto-issued), so a key is usually absent short-term; when absent the
    source is skipped entirely (no doomed 429 request) rather than degraded. Routing
    through i18n keeps the notice locale-correct.
    """
    global _S2_KEY_NOTICE_SHOWN
    if _S2_KEY_NOTICE_SHOWN:
        return
    _S2_KEY_NOTICE_SHOWN = True
    if api_key:
        return
    resolved = load_s2_key(env_var)
    if resolved:
        return
    from i18n import t
    print(t("semantic_scholar.key_notice"))


# Module-level guard so the "no key" notice prints at most once per process.
_KEY_NOTICE_SHOWN = False


def notify_openalex_key_if_missing(api_key=None, env_var="OPENALEX_API_KEY"):
    """Print a one-time, locale-aware notice when no OpenAlex API key is configured.

    Intended for the runtime entry points (ct_literature.run / fetch_openalex.fetch):
    when the key is absent the skill still works in keyless mode (100 credits/day since
    2026-02-13), but the user should be told how to apply for a FREE key so production-scale
    searches are not throttled. The notice is **informational only** — it never blocks execution.

    Args:
        api_key: the key already resolved for this run (may be None).
        env_var: env var name used to look up the key if api_key is None.
    """
    global _KEY_NOTICE_SHOWN
    if _KEY_NOTICE_SHOWN:
        return
    if api_key:
        _KEY_NOTICE_SHOWN = True
        return
    # Re-resolve from env / .env; load_openalex_key() sets os.environ on a hit and
    # never prints the key value.
    resolved = load_openalex_key(env_var)
    if resolved:
        _KEY_NOTICE_SHOWN = True
        return
    from i18n import t
    print(t("openalex.key_notice"))
    _KEY_NOTICE_SHOWN = True


def _retry_after(e):
    """Read the real backoff seconds from an HTTP 429 response, by priority:
      1. the `Retry-After` response header (HTTP standard);
      2. the `duration` / `retryAfter` field in the response body JSON (some APIs like
         Semantic Scholar put the wait seconds in the 429 body instead of the header).
    Returns None if missing or invalid.
    """
    try:
        ra = e.headers.get("Retry-After")
        if ra:
            return float(ra)
    except Exception:
        pass
    # Many APIs (e.g. Semantic Scholar) place the wait seconds in the 429 body JSON's duration field
    try:
        if getattr(e, "code", None) == 429:
            body = e.read()
            d = json.loads(body.decode("utf-8", "replace"))
            if isinstance(d, dict):
                for k in ("duration", "retryAfter", "retry_after"):
                    v = d.get(k)
                    if v:
                        return float(v)
    except Exception:
        pass
    return None


def _short(url, n=72):
    return url if len(url) <= n else url[:n] + "..."
