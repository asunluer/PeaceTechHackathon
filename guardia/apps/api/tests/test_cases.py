"""Case ownership, assignment, and submitted-link HTTP rules."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_case_service, get_current_user, get_session
from app.api.routes.cases import router as cases_router
from app.application.cases import CaseService
from app.domain.cases import Case, SubmittedLink
from app.domain.users import Role, User


def user(role: Role) -> User:
    return User(uuid4(), f"{uuid4()}@example.org", "hash", role, True, 0, datetime.now(timezone.utc))


class MemoryCases:
    def __init__(self) -> None:
        self.cases: dict[UUID, Case] = {}
        self.links: list[SubmittedLink] = []

    async def create_case(self, owner_id: UUID, title: str) -> Case:
        case = Case(uuid4(), owner_id, None, title, datetime.now(timezone.utc))
        self.cases[case.id] = case
        return case

    async def get_case(self, case_id: UUID) -> Case | None:
        return self.cases.get(case_id)

    def _visible_to(self, actor: User) -> list[Case]:
        cases = list(self.cases.values())
        if actor.role == Role.VICTIM:
            cases = [case for case in cases if case.owner_id == actor.id]
        elif actor.role == Role.NGO_INVESTIGATOR:
            cases = [case for case in cases if case.assigned_investigator_id == actor.id]
        return cases

    async def list_cases(self, actor: User, limit: int, offset: int) -> list[Case]:
        return self._visible_to(actor)[offset : offset + limit]

    async def search_cases(self, actor: User, query: str, limit: int, offset: int) -> list[Case]:
        needle = query.lower()
        matches = [case for case in self._visible_to(actor) if needle in case.title.lower()]
        return matches[offset : offset + limit]

    async def assign_investigator(self, case_id: UUID, investigator_id: UUID | None) -> Case:
        case = self.cases[case_id]
        assigned = Case(case.id, case.owner_id, investigator_id, case.title, case.created_at)
        self.cases[case_id] = assigned
        return assigned

    async def add_link(self, case_id: UUID, submitted_by: UUID, url: str) -> SubmittedLink:
        link = SubmittedLink(uuid4(), case_id, submitted_by, url, datetime.now(timezone.utc))
        self.links.append(link)
        return link

    async def list_links(self, case_id: UUID, limit: int, offset: int) -> list[SubmittedLink]:
        return [link for link in self.links if link.case_id == case_id][offset : offset + limit]


class MemoryUsers:
    def __init__(self, users: list[User]) -> None:
        self.users = {account.id: account for account in users}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)


class AuditSession:
    def add(self, row: object) -> None:
        pass

    async def commit(self) -> None:
        pass


def test_case_visibility_assignment_and_link_submission() -> None:
    owner = user(Role.VICTIM)
    other_victim = user(Role.VICTIM)
    investigator = user(Role.NGO_INVESTIGATOR)
    administrator = user(Role.ADMINISTRATOR)
    actor = [owner]

    service = CaseService(MemoryCases(), MemoryUsers([owner, other_victim, investigator, administrator]))
    app = FastAPI()
    app.include_router(cases_router, prefix="/api/v1")
    app.dependency_overrides[get_case_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: actor[0]
    app.dependency_overrides[get_session] = lambda: AuditSession()

    with TestClient(app) as client:
        response = client.post("/api/v1/cases", json={"title": "  Public posts  "})
        assert response.status_code == 201
        assert response.json()["title"] == "Public posts"
        case_id = response.json()["id"]

        assert client.post(f"/api/v1/cases/{case_id}/links", json={"url": "file:///private/data"}).status_code == 422
        assert client.post(f"/api/v1/cases/{case_id}/links", json={"url": "https://user:pass@example.org"}).status_code == 422
        link = client.post(f"/api/v1/cases/{case_id}/links", json={"url": "https://example.org/post?id=2"})
        assert link.status_code == 201
        assert link.json()["url"] == "https://example.org/post?id=2"

        actor[0] = other_victim
        assert client.get("/api/v1/cases").json() == []
        assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
        assert client.get(f"/api/v1/cases/{case_id}/links").status_code == 404

        actor[0] = investigator
        assert client.get(f"/api/v1/cases/{case_id}").status_code == 404

        actor[0] = administrator
        assert client.post("/api/v1/cases", json={"title": "Admin case"}).status_code == 403
        assert client.patch(f"/api/v1/cases/{case_id}/assignment", json={"investigator_id": str(owner.id)}).status_code == 422
        response = client.patch(
            f"/api/v1/cases/{case_id}/assignment",
            json={"investigator_id": str(investigator.id)},
        )
        assert response.status_code == 200

        actor[0] = investigator
        assert client.get(f"/api/v1/cases/{case_id}").status_code == 200
        assert len(client.get("/api/v1/cases").json()) == 1
        assert client.post(f"/api/v1/cases/{case_id}/links", json={"url": "https://example.org/another"}).status_code == 201

        actor[0] = administrator
        assert client.patch(f"/api/v1/cases/{case_id}/assignment", json={"investigator_id": None}).status_code == 200
        actor[0] = investigator
        assert client.get(f"/api/v1/cases/{case_id}").status_code == 404


def test_case_search_is_scoped_to_actor_visibility() -> None:
    owner = user(Role.VICTIM)
    other_victim = user(Role.VICTIM)
    actor = [owner]

    service = CaseService(MemoryCases(), MemoryUsers([owner, other_victim]))
    app = FastAPI()
    app.include_router(cases_router, prefix="/api/v1")
    app.dependency_overrides[get_case_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: actor[0]
    app.dependency_overrides[get_session] = lambda: AuditSession()

    with TestClient(app) as client:
        assert client.post("/api/v1/cases", json={"title": "Harassment on X"}).status_code == 201
        assert client.post("/api/v1/cases", json={"title": "Unrelated case"}).status_code == 201

        results = client.get("/api/v1/cases", params={"q": "harassment"}).json()
        assert len(results) == 1
        assert results[0]["title"] == "Harassment on X"

        assert client.get("/api/v1/cases", params={"q": "nothing matches"}).json() == []

        actor[0] = other_victim
        assert client.get("/api/v1/cases", params={"q": "harassment"}).json() == []
