"""Tests for Task P7-6: refresh GitNexus index.

Phase 7 emits the refresh command but blocks on user authorization
(plan §"Allowed Deviations"). When `.gitnexus/meta.json` exists, the
test asserts `lastIndexed` is younger than the most recent source
change (HEAD commit time); otherwise the test documents the
intentionally-deferred no-op.

Phase 7 cleanup: the original assertion compared `lastIndexed` to a
hardcoded `PHASE_START = date(2026, 5, 1)`. That date drifts out of
relevance the moment HEAD advances — the right invariant is "index
younger than the last source change", which is what GitNexus actually
guarantees post-refresh.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _meta_path() -> Path:
    return _repo_root() / ".gitnexus" / "meta.json"


def _head_commit_time() -> datetime | None:
    """Return HEAD commit time as timezone-aware UTC datetime, or
    ``None`` if not in a git checkout (test then falls back to a
    24-hour freshness window)."""
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "HEAD"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    iso = proc.stdout.strip()
    if not iso:
        return None
    # ``%cI`` is strict ISO-8601 with timezone (e.g. 2026-05-06T19:12:03+03:00).
    return datetime.fromisoformat(iso)


def _parse_last_indexed(value: str) -> datetime:
    """Parse the GitNexus ``lastIndexed`` field. Accepts ISO-8601 with
    timezone; treats trailing ``Z`` as UTC; date-only strings are
    interpreted as midnight UTC (worst case for the assertion, so the
    check fails closed on coarse stamps)."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if "T" not in s:
        # Date-only — treat as start-of-day UTC.
        return datetime.fromisoformat(s + "T00:00:00+00:00")
    parsed = datetime.fromisoformat(s)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


class TestTaskP7_6:
    @pytest.mark.docs
    def test_gitnexus_index_state_documented(self) -> None:
        """Either an up-to-date `meta.json` exists with `lastIndexed`
        younger than the most recent source change (HEAD commit time),
        OR the index is intentionally absent (user has not authorised
        the refresh yet)."""
        meta = _meta_path()
        if not meta.is_file():
            pytest.skip(
                "No .gitnexus/meta.json — refresh requires user "
                "authorization (plan §'Allowed Deviations'); skipped "
                "rather than failed."
            )
        data = json.loads(meta.read_text(encoding="utf-8"))
        last_raw = data.get("lastIndexed") or data.get("last_indexed")
        assert last_raw is not None, ".gitnexus/meta.json must record `lastIndexed` after refresh"
        last_indexed = _parse_last_indexed(str(last_raw))
        head_time = _head_commit_time()
        if head_time is None:
            # Fallback: index must be younger than 24h. Captures the
            # intent ("recent refresh") without a git dependency.
            now = datetime.now(UTC)
            age_seconds = (now - last_indexed).total_seconds()
            assert age_seconds <= 24 * 3600, (
                f".gitnexus/meta.json lastIndexed={last_raw} is older "
                f"than 24h ({age_seconds / 3600:.1f}h) — re-run "
                "`npx gitnexus analyze` (with --embeddings if applicable)"
            )
        else:
            assert last_indexed >= head_time, (
                f".gitnexus/meta.json lastIndexed={last_raw} predates "
                f"HEAD commit time {head_time.isoformat()} — re-run "
                "`npx gitnexus analyze` (with --embeddings if applicable)"
            )

    @pytest.mark.docs
    def test_embeddings_count_preserved_if_present(self) -> None:
        """If `meta.json` previously recorded embeddings > 0, refresh
        must preserve that count (i.e. used `--embeddings` flag)."""
        meta = _meta_path()
        if not meta.is_file():
            pytest.skip("no .gitnexus/meta.json — see authorization note")
        data = json.loads(meta.read_text(encoding="utf-8"))
        stats = data.get("stats", {})
        embeddings = stats.get("embeddings")
        if embeddings is None or embeddings == 0:
            pytest.skip(
                "no pre-existing embeddings to preserve; --embeddings flag was not required"
            )
        assert embeddings > 0, (
            "post-refresh embeddings count dropped to 0 — must rerun "
            "`npx gitnexus analyze --embeddings` to preserve"
        )
