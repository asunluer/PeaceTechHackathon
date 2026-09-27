"""Capture publicly reachable pages into a hashed, immutable evidence package."""

import asyncio
import ipaddress
import json
import logging
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import or_, select, update

from app.core.config import get_settings
from app.infrastructure.database import Database
from app.infrastructure.models import AuditLogRow, EvidenceFileRow, EvidenceRow
from app.infrastructure.object_storage import LocalObjectStorage, storage_from_settings

LOGGER = logging.getLogger("safe_archive.capture")
MAX_FILE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class CaptureJob:
    evidence_id: UUID
    url: str


@dataclass(frozen=True)
class CapturedPage:
    captured_at: datetime
    final_url: str
    page_title: str
    visible_author: str | None
    visible_timestamp: str | None
    visible_text: str
    visible_comments: str | None
    files: dict[str, tuple[str, bytes]]


async def require_public_url(value: str) -> None:
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Capture accepts only public HTTP(S) URLs without credentials")
    host = parts.hostname.rstrip(".")
    if not host:
        raise ValueError("URL hostname is empty")
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("URL hostname could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(info[4][0]).is_global for info in addresses):
        raise ValueError("URL resolves to a non-public address")


async def _first_attribute(page, selectors: list[tuple[str, str | None]]) -> str | None:
    for selector, attribute in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count():
                value = await locator.get_attribute(attribute) if attribute else await locator.inner_text(timeout=1000)
                if value and value.strip():
                    return value.strip()[:500]
        except Exception:
            continue
    return None


async def capture_page(url: str) -> CapturedPage:
    from playwright.async_api import async_playwright

    await require_public_url(url)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            context = await browser.new_context(
                accept_downloads=False,
                service_workers="block",
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )

            async def route_request(route) -> None:
                try:
                    await require_public_url(route.request.url)
                except ValueError:
                    await route.abort("blockedbyclient")
                else:
                    await route.continue_()

            await context.route("**/*", route_request)
            page = await context.new_page()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            if response is None or response.status >= 400:
                raise ValueError(f"Public page returned HTTP {response.status if response else 'no response'}")
            await require_public_url(page.url)
            await page.wait_for_timeout(1000)
            captured_at = datetime.now(timezone.utc)
            page_title = (await page.title())[:1000]
            visible_text = (await page.locator("body").inner_text(timeout=5000))[:200_000]
            visible_author = await _first_attribute(page, [
                ('meta[property="article:author"]', "content"),
                ('meta[name="author"]', "content"),
                ('[rel="author"]', None),
            ])
            visible_timestamp = await _first_attribute(page, [
                ('meta[property="article:published_time"]', "content"),
                ("time[datetime]", "datetime"),
                ("time", None),
            ])
            comments = await _first_attribute(page, [
                ('[aria-label="Comments"]', None),
                ('[data-testid*="comment"]', None),
            ])
            html = (await page.content()).encode("utf-8")
            full = await page.screenshot(full_page=True, animations="disabled")
            focus = await page.screenshot(full_page=False, animations="disabled")
            files = {
                "html": ("text/html; charset=utf-8", html),
                "full_screenshot": ("image/png", full),
                "focused_screenshot": ("image/png", focus),
            }
            if any(len(payload) > MAX_FILE_BYTES for _, payload in files.values()):
                raise ValueError("Capture artifact exceeds 25 MiB")
            await context.close()
            return CapturedPage(captured_at, page.url, page_title, visible_author, visible_timestamp, visible_text, comments, files)
        finally:
            await browser.close()


async def claim_job(database: Database) -> CaptureJob | None:
    now = datetime.now(timezone.utc)
    async with database.sessions() as session:
        await session.execute(
            update(EvidenceRow)
            .where(EvidenceRow.capture_status == "capturing", EvidenceRow.capture_started_at < now - timedelta(minutes=10), EvidenceRow.capture_attempts >= 3)
            .values(capture_status="failed", capture_error="Capture worker timed out")
        )
        row = await session.scalar(
            select(EvidenceRow)
            .where(
                or_(
                    EvidenceRow.capture_status == "queued",
                    (EvidenceRow.capture_status == "capturing") & (EvidenceRow.capture_started_at < now - timedelta(minutes=10)) & (EvidenceRow.capture_attempts < 3),
                )
            )
            .order_by(EvidenceRow.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            await session.commit()
            return None
        row.capture_status = "capturing"
        row.capture_started_at = now
        row.capture_attempts += 1
        row.capture_error = None
        await session.commit()
        return CaptureJob(row.id, row.original_url)


def store_capture(storage: LocalObjectStorage, evidence_id: UUID, page: CapturedPage) -> tuple[str, list[dict]]:
    file_records: list[dict] = []
    for kind, (mime_type, payload) in page.files.items():
        digest = sha256(payload).hexdigest()
        extension = "html" if kind == "html" else "png"
        key = f"{evidence_id}/{kind}-{digest}.{extension}"
        try:
            storage.write_once(key, payload)
        except FileExistsError:
            if storage.read(key) != payload:
                raise ValueError("Existing artifact does not match capture bytes")
        file_records.append({"file_type": kind, "path": key, "mime_type": mime_type, "size": len(payload), "hash_sha256": digest})
    manifest = {
        "evidence_id": str(evidence_id),
        "captured_at": page.captured_at.isoformat(),
        "final_url": page.final_url,
        "page_title": page.page_title,
        "visible_author": page.visible_author,
        "visible_timestamp": page.visible_timestamp,
        "files": [{key: item[key] for key in ("file_type", "hash_sha256", "size")} for item in file_records],
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    package_hash = sha256(manifest_bytes).hexdigest()
    manifest_key = f"{evidence_id}/manifest-{package_hash}.json"
    try:
        storage.write_once(manifest_key, manifest_bytes)
    except FileExistsError:
        if storage.read(manifest_key) != manifest_bytes:
            raise ValueError("Existing manifest does not match capture bytes")
    file_records.append({"file_type": "manifest", "path": manifest_key, "mime_type": "application/json", "size": len(manifest_bytes), "hash_sha256": package_hash})
    return package_hash, file_records


async def complete_job(database: Database, job: CaptureJob, page: CapturedPage, package_hash: str, records: list[dict]) -> None:
    async with database.sessions() as session:
        row = await session.get(EvidenceRow, job.evidence_id, with_for_update=True)
        if row is None or row.capture_status != "capturing":
            raise ValueError("Capture job is no longer active")
        row.capture_status = "captured"
        row.capture_timestamp = page.captured_at
        row.hash_sha256 = package_hash
        row.page_title = page.page_title
        row.visible_author = page.visible_author
        row.visible_timestamp = page.visible_timestamp
        row.visible_text = page.visible_text
        row.visible_comments = page.visible_comments
        for record in records:
            session.add(EvidenceFileRow(evidence_id=row.id, **record))
        session.add(AuditLogRow(user_id=None, action="evidence.captured", target_type="evidence", target_id=row.id, details={"sha256": package_hash}))
        await session.commit()


async def fail_job(database: Database, job: CaptureJob, error: Exception) -> None:
    async with database.sessions() as session:
        row = await session.get(EvidenceRow, job.evidence_id, with_for_update=True)
        if row is None or row.capture_status != "capturing":
            return
        row.capture_status = "failed"
        row.capture_error = str(error)[:1000]
        session.add(AuditLogRow(user_id=None, action="evidence.capture_failed", target_type="evidence", target_id=row.id, details={"error": type(error).__name__}))
        await session.commit()


async def run_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    storage = storage_from_settings(settings)
    database = Database(settings)
    try:
        while True:
            job = await claim_job(database)
            if job is None:
                await asyncio.sleep(5)
                continue
            try:
                page = await capture_page(job.url)
                package_hash, records = store_capture(storage, job.evidence_id, page)
                await complete_job(database, job, page, package_hash, records)
                LOGGER.info("Captured evidence %s", job.evidence_id)
            except Exception as exc:
                LOGGER.exception("Capture failed for evidence %s", job.evidence_id)
                await fail_job(database, job, exc)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(run_worker())
