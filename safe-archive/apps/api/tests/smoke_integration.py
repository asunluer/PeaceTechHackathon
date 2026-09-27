"""Manual Compose smoke check against a disposable SAFE_ARCHIVE_DB_NAME database."""

import asyncio
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cli.create_admin import create_administrator
from app.application.auth import AdministratorExists
from app.core.config import get_settings
from app.infrastructure.database import Database
from app.infrastructure.models import AIAnalysisRow, CaseRow, EvidenceRow
from app.main import app

PASSWORD = "IsolatedSmokePassphrase123!"


def token(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/token", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def submit() -> None:
    try:
        asyncio.run(create_administrator("admin@smoke.example.org", PASSWORD))
    except AdministratorExists:
        pass
    with TestClient(app) as client:
        admin = token(client, "admin@smoke.example.org")
        for email, role in (("victim@smoke.example.org", "victim"), ("investigator@smoke.example.org", "ngo_investigator")):
            response = client.post("/api/v1/users", headers=admin, json={"email": email, "password": PASSWORD, "role": role})
            assert response.status_code == 201, response.text
        victim = token(client, "victim@smoke.example.org")
        response = client.post("/api/v1/reports", headers=victim, json={"url": "https://example.com", "shared_text": "https://example.com", "victim_statement": "A public page"})
        assert response.status_code == 201, response.text
        receipt = response.json()
        assert receipt["capture_status"] == "queued"
        assert client.get(f"/api/v1/evidence/{receipt['evidence_id']}", headers=admin).status_code == 200
        investigator = token(client, "investigator@smoke.example.org")
        assert client.get(f"/api/v1/evidence/{receipt['evidence_id']}", headers=investigator).status_code == 404
        # User ordering is not a contract; explicitly look up the investigator.
        investigator_id = next(row["id"] for row in client.get("/api/v1/users", headers=admin).json() if row["email"] == "investigator@smoke.example.org")
        assigned = client.patch(f"/api/v1/cases/{receipt['case_id']}/assignment", headers=admin, json={"investigator_id": investigator_id})
        assert assigned.status_code == 200, assigned.text
        assert client.get(f"/api/v1/evidence/{receipt['evidence_id']}", headers=investigator).status_code == 200
        print("submission and access rules passed")


async def evidence_id_from_database():
    database = Database(get_settings())
    try:
        async with database.sessions() as session:
            return await session.scalar(select(EvidenceRow.id).join(CaseRow).where(CaseRow.title == "Report from Other"))
    finally:
        await database.dispose()


async def add_test_analysis(evidence_id):
    database = Database(get_settings())
    try:
        async with database.sessions() as session:
            existing = await session.scalar(select(AIAnalysisRow.id).where(AIAnalysisRow.evidence_id == evidence_id, AIAnalysisRow.model_name == "smoke-test"))
            if existing is not None:
                return
            session.add(AIAnalysisRow(
                evidence_id=evidence_id,
                model_name="smoke-test",
                summary="AI-only smoke marker",
                entities=[],
                detected_threats=[],
                detected_pii=[],
                tags=["ai-smoke"],
                timeline=[],
            ))
            await session.commit()
    finally:
        await database.dispose()


def verify() -> None:
    evidence_id = asyncio.run(evidence_id_from_database())
    assert evidence_id is not None
    asyncio.run(add_test_analysis(evidence_id))
    with TestClient(app) as client:
        admin = token(client, "admin@smoke.example.org")
        victim = token(client, "victim@smoke.example.org")
        investigator = token(client, "investigator@smoke.example.org")
        evidence = client.get(f"/api/v1/evidence/{evidence_id}", headers=investigator)
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["capture_status"] == "captured", evidence.text
        assert len(evidence.json()["hash_sha256"]) == 64
        case_id = evidence.json()["case_id"]
        assert client.get(f"/api/v1/evidence/{evidence_id}/analyses", headers=victim).status_code == 403
        assert client.get(f"/api/v1/evidence/{evidence_id}/analyses", headers=investigator).status_code == 200
        assert client.get("/api/v1/cases", params={"q": "AI-only smoke marker"}, headers=victim).json() == []
        assert len(client.get("/api/v1/cases", params={"q": "AI-only smoke marker"}, headers=admin).json()) == 1
        assert client.get("/api/v1/cases", params={"q": "%"}, headers=admin).json() == []
        assert client.get("/api/v1/cases/stats", headers=admin).json()["total"] >= 1
        files = client.get(f"/api/v1/evidence/{evidence_id}/files", headers=investigator)
        assert files.status_code == 200, files.text
        assert {row["file_type"] for row in files.json()} == {"html", "full_screenshot", "focused_screenshot", "manifest"}
        for row in files.json():
            download = client.get(f"/api/v1/evidence/{evidence_id}/files/{row['id']}", headers=investigator)
            assert download.status_code == 200, download.text
            assert len(download.content) == row["size"]
        assert client.get(f"/api/v1/cases/{case_id}/report.pdf", headers=victim).status_code == 403
        report = client.get(f"/api/v1/cases/{case_id}/report.pdf", headers=investigator)
        assert report.status_code == 200, report.text
        assert report.content.startswith(b"%PDF-")
        audit = client.get(f"/api/v1/cases/{case_id}/audit", headers=investigator)
        assert audit.status_code == 200
        assert any(item["action"] == "case.assigned" for item in audit.json())
        note = client.post(f"/api/v1/cases/{case_id}/notes", headers=investigator, json={"body": "Reviewed example"})
        assert note.status_code == 201, note.text
        assert client.get(f"/api/v1/cases/{case_id}/notes", headers=investigator).json()[0]["body"] == "Reviewed example"
        assert client.get(f"/api/v1/cases/{case_id}/timeline", headers=admin).status_code == 200
        print("capture, file integrity, authorization, notes, and PDF passed")


if __name__ == "__main__":
    if sys.argv[1] == "submit":
        submit()
    elif sys.argv[1] == "verify":
        verify()
