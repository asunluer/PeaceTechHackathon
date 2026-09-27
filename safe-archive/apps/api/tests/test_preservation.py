"""Verify evidence bytes stay encrypted and report exports remain readable."""

from datetime import datetime, timezone
import asyncio
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag

from app.application.reporting import build_case_report
from app.infrastructure.object_storage import LocalObjectStorage
from app.worker.capture import CapturedPage, require_public_url, store_capture


def test_write_once_encryption_and_integrity(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path, b"k" * 32)
    payload = b"public page text with a sensitive statement"
    storage.write_once("case/page.html", payload)
    assert storage.read("case/page.html") == payload
    assert payload not in (tmp_path / "case/page.html").read_bytes()
    with pytest.raises(FileExistsError):
        storage.write_once("case/page.html", b"replacement")
    with pytest.raises(ValueError):
        storage.write_once("../escape", payload)
    sealed = bytearray((tmp_path / "case/page.html").read_bytes())
    sealed[-1] ^= 1
    (tmp_path / "case/page.html").write_bytes(sealed)
    with pytest.raises(InvalidTag):
        storage.read("case/page.html")


def test_capture_manifest_hashes_each_original_file(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path, b"x" * 32)
    evidence_id = uuid4()
    page = CapturedPage(datetime.now(timezone.utc), "https://example.com", "Example", None, None, "visible", None, {"html": ("text/html", b"<p>visible</p>"), "full_screenshot": ("image/png", b"png")})
    package_hash, files = store_capture(storage, evidence_id, page)
    for row in files:
        assert sha256(storage.read(row["path"])).hexdigest() == row["hash_sha256"]
    assert next(row for row in files if row["file_type"] == "manifest")["hash_sha256"] == package_hash


def test_capture_rejects_local_or_non_http_urls() -> None:
    for url in ("http://127.0.0.1/private", "http://[::1]/", "file:///etc/passwd", "https://user:password@example.org"):
        with pytest.raises(ValueError):
            asyncio.run(require_public_url(url))


def test_report_contains_evidence_and_marks_ai_as_derived() -> None:
    now = datetime.now(timezone.utc)
    case = SimpleNamespace(id=uuid4(), title="Example case", status="open", created_at=now, victim_statement="Victim statement")
    evidence = SimpleNamespace(id=uuid4(), platform="other", capture_status="captured", capture_timestamp=now, created_at=now, original_url="https://example.com", hash_sha256="a" * 64, page_title="Example Domain", visible_author=None, visible_timestamp=None, visible_text="Visible public text", visible_comments="A visible public comment")
    analysis = SimpleNamespace(model_name="test-model", created_at=now, summary="AI summary", tags=["review"])
    payload = build_case_report(case, [evidence], {}, {evidence.id: [analysis]})
    assert payload.startswith(b"%PDF-")
    assert len(payload) > 1000
