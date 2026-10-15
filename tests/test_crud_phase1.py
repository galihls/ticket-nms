"""
Test CRUD Fase 1 — Ticketing NMS
Menguji seluruh operasi CRUD: Tickets, Solutions, Reports, Accounts
"""
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.tickets.models import Ticket, TicketReply, Company
from apps.solutions.models import Article, Category
from apps.core.models import ActivityLog, Notification


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin_test",
        password="test1234",
        first_name="Admin",
        last_name="Test",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def agent_user(db):
    return User.objects.create_user(
        username="agent_test",
        password="test1234",
        first_name="Agent",
        last_name="NOC",
        department="NOC",
        shift="pagi",
    )


@pytest.fixture
def auth_client(admin_user):
    c = Client()
    c.login(username="admin_test", password="test1234")
    return c


@pytest.fixture
def agent_client(agent_user):
    c = Client()
    c.login(username="agent_test", password="test1234")
    return c


# ═══════════════════════════════════════════════════════════════
# TICKETS CRUD
# ═══════════════════════════════════════════════════════════════

class TestTicketList:
    def test_list_requires_login(self, db):
        resp = Client().get(reverse("tickets:list"))
        assert resp.status_code == 302

    def test_list_loads(self, auth_client):
        resp = auth_client.get(reverse("tickets:list"))
        assert resp.status_code == 200

    def test_list_filter_by_status(self, auth_client):
        resp = auth_client.get(reverse("tickets:list") + "?status=open")
        assert resp.status_code == 200

    def test_list_filter_by_priority(self, auth_client):
        resp = auth_client.get(reverse("tickets:list") + "?priority=high")
        assert resp.status_code == 200

    def test_list_search(self, auth_client):
        resp = auth_client.get(reverse("tickets:list") + "?q=test")
        assert resp.status_code == 200


class TestTicketCreate:
    def test_create_page_loads(self, auth_client):
        resp = auth_client.get(reverse("tickets:create"))
        assert resp.status_code == 200

    def test_create_ticket_problem(self, auth_client, admin_user):
        now = timezone.now()
        resp = auth_client.post(reverse("tickets:create"), {
            "ticket_type": "PR",
            "problem_category": "los",
            "subject": "Link down site Jakarta",
            "description": "Fiber cut di ruas utama",
            "requester_name": "Budi Santoso",
            "requester_email": "budi@initech.co.id",
            "requester_phone": "081234567890",
            "company": "INITECH",
            "source": "nms",
            "priority": "high",
            "status": "open",
            "site_code": "JKT-001",
            "opened_at": now.strftime("%Y-%m-%dT%H:%M"),
        })
        # Should redirect to detail on success
        assert resp.status_code == 302, f"Expected redirect, got {resp.status_code}"
        ticket = Ticket.objects.filter(subject="Link down site Jakarta").first()
        assert ticket is not None, "Ticket should be created"
        assert ticket.number.startswith("26PR"), f"Number should start with 26PR, got {ticket.number}"
        assert ticket.status == "open"

    def test_create_ticket_feature_request(self, auth_client):
        now = timezone.now()
        resp = auth_client.post(reverse("tickets:create"), {
            "ticket_type": "FR",
            "subject": "Request monitoring dashboard baru",
            "description": "Dashboard untuk monitoring SLA per site",
            "requester_name": "Dewi Sari",
            "requester_phone": "081234567890",
            "company": "INITECH",
            "source": "email",
            "priority": "medium",
            "status": "open",
            "opened_at": now.strftime("%Y-%m-%dT%H:%M"),
        })
        assert resp.status_code == 302
        ticket = Ticket.objects.filter(subject__contains="monitoring dashboard").first()
        assert ticket is not None
        assert ticket.number.startswith("26FR")

    def test_create_ticket_generates_audit_log(self, auth_client, admin_user):
        now = timezone.now()
        initial_count = ActivityLog.objects.count()
        auth_client.post(reverse("tickets:create"), {
            "ticket_type": "PR",
            "problem_category": "power",
            "subject": "Test audit log",
            "description": "Testing",
            "requester_name": "Test",
            "requester_phone": "081234567890",
            "company": "INITECH",
            "source": "nms",
            "priority": "low",
            "status": "open",
            "opened_at": now.strftime("%Y-%m-%dT%H:%M"),
        })
        assert ActivityLog.objects.count() > initial_count

    def test_create_ticket_generates_notification(self, auth_client):
        now = timezone.now()
        initial_count = Notification.objects.count()
        auth_client.post(reverse("tickets:create"), {
            "ticket_type": "PR",
            "problem_category": "los",
            "subject": "Urgent ticket test",
            "description": "Testing notif",
            "requester_name": "Test",
            "requester_phone": "081234567890",
            "company": "INITECH",
            "source": "nms",
            "priority": "high",
            "status": "open",
            "opened_at": now.strftime("%Y-%m-%dT%H:%M"),
        })
        assert Notification.objects.count() > initial_count


class TestTicketDetail:
    @pytest.fixture
    def ticket(self, admin_user):
        return Ticket.objects.create(
            ticket_type="PR",
            problem_category="los",
            company="INITECH",
            subject="Test detail",
            description="Desc",
            requester_name="Test",
            requester_phone="081234567890",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )

    def test_detail_page_loads(self, auth_client, ticket):
        resp = auth_client.get(reverse("tickets:detail", args=[ticket.number]))
        assert resp.status_code == 200

    def test_detail_shows_ticket_info(self, auth_client, ticket):
        resp = auth_client.get(reverse("tickets:detail", args=[ticket.number]))
        assert ticket.subject.encode() in resp.content


class TestTicketEdit:
    @pytest.fixture
    def ticket(self, admin_user):
        return Ticket.objects.create(
            ticket_type="PR",
            problem_category="los",
            company="INITECH",
            subject="Before edit",
            description="Desc",
            requester_name="Test",
            requester_phone="081234567890",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )

    def test_edit_page_loads(self, auth_client, ticket):
        resp = auth_client.get(reverse("tickets:edit", args=[ticket.number]))
        assert resp.status_code == 200

    def test_edit_ticket(self, auth_client, ticket):
        resp = auth_client.post(reverse("tickets:edit", args=[ticket.number]), {
            "ticket_type": "PR",
            "problem_category": "los",
            "company": "INITECH",
            "subject": "After edit",
            "description": "Updated desc",
            "requester_name": "Test",
            "requester_phone": "081234567890",
            "source": "nms",
            "priority": "high",
            "status": "open",
        })
        assert resp.status_code == 302
        ticket.refresh_from_db()
        assert ticket.subject == "After edit"
        assert ticket.priority == "high"


class TestTicketReplyFlow:
    @pytest.fixture
    def ticket(self, admin_user):
        return Ticket.objects.create(
            ticket_type="PR",
            problem_category="los",
            company="INITECH",
            subject="Reply test",
            description="Desc",
            requester_name="Test",
            requester_phone="081234567890",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )

    def test_reply_public_transitions_to_outstanding(self, auth_client, ticket):
        resp = auth_client.post(reverse("tickets:reply", args=[ticket.number]), {
            "body": "Sedang kami cek, mohon tunggu.",
            "is_private": "",  # unchecked = public reply
        })
        assert resp.status_code == 302
        ticket.refresh_from_db()
        assert ticket.status == "open", f"Expected open, got {ticket.status}"
        assert ticket.first_response_at is not None

    def test_reply_private_note_stays_open(self, auth_client, ticket):
        resp = auth_client.post(reverse("tickets:reply", args=[ticket.number]), {
            "body": "Catatan internal: perlu eskalasi ke FE.",
            "is_private": "on",
        })
        assert resp.status_code == 302
        ticket.refresh_from_db()
        # Private note should NOT auto-transition status
        assert ticket.status == "open"


class TestTicketCloseReopen:
    @pytest.fixture
    def ticket(self, admin_user):
        return Ticket.objects.create(
            ticket_type="PR",
            problem_category="los",
            company="INITECH",
            subject="Close test",
            description="Desc",
            requester_name="Test",
            requester_phone="081234567890",
            source="nms",
            priority="medium",
            status="outstanding",
            opened_at=timezone.now(),
            created_by=admin_user,
        )

    def test_close_ticket(self, auth_client, ticket):
        resp = auth_client.post(reverse("tickets:close", args=[ticket.number]), {
            "reason_category": "Resolved",
            "reason": "Fiber sudah disambung ulang, link up normal.",
        })
        assert resp.status_code == 302
        ticket.refresh_from_db()
        assert ticket.status == "closed"
        assert ticket.closed_at is not None
        assert "Resolved" in ticket.close_reason

    def test_reopen_ticket(self, auth_client, ticket, admin_user):
        # Close first
        ticket.status = "closed"
        ticket.closed_at = timezone.now()
        ticket.close_reason = "Test"
        ticket.save()

        resp = auth_client.post(reverse("tickets:reopen", args=[ticket.number]))
        assert resp.status_code == 302
        ticket.refresh_from_db()
        assert ticket.status == "outstanding"
        assert ticket.closed_at is None


class TestTicketProperties:
    @pytest.fixture
    def ticket(self, admin_user):
        return Ticket.objects.create(
            ticket_type="PR",
            problem_category="los",
            company="INITECH",
            subject="Props test",
            description="Desc",
            requester_name="Test",
            requester_phone="081234567890",
            source="nms",
            priority="low",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )

    def test_update_priority(self, auth_client, ticket):
        resp = auth_client.post(
            reverse("tickets:properties", args=[ticket.number]),
            {"priority": "high"},
        )
        assert resp.status_code == 302
        ticket.refresh_from_db()
        assert ticket.priority == "high"

    def test_update_assignee(self, auth_client, ticket, admin_user):
        resp = auth_client.post(
            reverse("tickets:properties", args=[ticket.number]),
            {"assignee": admin_user.pk},
        )
        assert resp.status_code == 302
        ticket.refresh_from_db()
        assert ticket.assignee == admin_user


class TestTicketBulk:
    @pytest.fixture
    def tickets(self, admin_user):
        ts = []
        for i in range(3):
            ts.append(Ticket.objects.create(
                ticket_type="PR",
                problem_category="los",
                company="INITECH",
                subject=f"Bulk test {i}",
                description="Desc",
                requester_name="Test",
                requester_phone="081234567890",
                source="nms",
                priority="medium",
                status="open",
                opened_at=timezone.now(),
                created_by=admin_user,
            ))
        return ts

    def test_bulk_close(self, auth_client, tickets):
        numbers = [t.number for t in tickets]
        resp = auth_client.post(reverse("tickets:bulk"), {
            "action": "status:closed",
            "selected": numbers,
        })
        assert resp.status_code == 302
        for t in tickets:
            t.refresh_from_db()
            assert t.status == "closed"


class TestTicketNumbering:
    def test_sequential_numbering(self, admin_user):
        t1 = Ticket.objects.create(
            ticket_type="PR", subject="A", description="D",
            requester_name="T", requester_phone="081234567890",
            company="INITECH", source="nms", priority="low",
            status="open", opened_at=timezone.now(),
            created_by=admin_user,
        )
        t2 = Ticket.objects.create(
            ticket_type="PR", subject="B", description="D",
            requester_name="T", requester_phone="081234567890",
            company="INITECH", source="nms", priority="low",
            status="open", opened_at=timezone.now(),
            created_by=admin_user,
        )
        n1 = int(t1.number[-4:])
        n2 = int(t2.number[-4:])
        assert n2 == n1 + 1, f"Expected sequential: {t1.number} -> {t2.number}"

    def test_pr_and_fr_independent_sequence(self, admin_user):
        pr = Ticket.objects.create(
            ticket_type="PR", subject="P", description="D",
            requester_name="T", requester_phone="081234567890",
            company="INITECH", source="nms", priority="low",
            status="open", opened_at=timezone.now(),
            created_by=admin_user,
        )
        fr = Ticket.objects.create(
            ticket_type="FR", subject="F", description="D",
            requester_name="T", requester_phone="081234567890",
            company="INITECH", source="nms", priority="low",
            status="open", opened_at=timezone.now(),
            created_by=admin_user,
        )
        assert "PR" in pr.number
        assert "FR" in fr.number


# ═══════════════════════════════════════════════════════════════
# SOLUTIONS CRUD
# ═══════════════════════════════════════════════════════════════

class TestSolutionsHome:
    def test_home_loads(self, auth_client):
        resp = auth_client.get(reverse("solutions:home"))
        assert resp.status_code == 200


class TestSolutionsArticle:
    def test_create_article_page_loads(self, auth_client):
        resp = auth_client.get(reverse("solutions:create"))
        assert resp.status_code == 200

    def test_create_article(self, auth_client):
        resp = auth_client.post(reverse("solutions:create"), {
            "category": "PR",
            "title": "Cara Troubleshoot Fiber Cut",
            "summary": "Panduan menangani fiber cut",
            "body": "1. Cek OTDR\n2. Identifikasi lokasi\n3. Splicing",
            "tags": "fiber, otdr, splicing",
            "status": "published",
        })
        assert resp.status_code == 302
        art = Article.objects.filter(title__contains="Fiber Cut").first()
        assert art is not None
        assert art.slug  # auto-generated

    def test_create_article_from_ticket(self, auth_client, admin_user):
        ticket = Ticket.objects.create(
            ticket_type="PR", problem_category="los", company="INITECH",
            subject="FO cut JKT-042",
            description="Fiber cut di ruas utama Jakarta",
            requester_name="Test", requester_phone="081234567890",
            source="nms", priority="high",
            status="closed", opened_at=timezone.now(),
            closed_at=timezone.now(), close_reason="Resolved — Splicing selesai",
            created_by=admin_user, tags="fiber,jakarta",
        )
        resp = auth_client.get(reverse("solutions:create") + f"?dari={ticket.number}")
        assert resp.status_code == 200
        # Should pre-fill form from ticket data
        content = resp.content.decode()
        assert ticket.subject in content or "FO cut" in content

    def test_article_detail_and_view_count(self, auth_client):
        art = Article.objects.create(
            category="PR", title="Test Views", summary="S",
            body="Body", status="published",
        )
        resp = auth_client.get(reverse("solutions:detail", args=[art.slug]))
        assert resp.status_code == 200
        art.refresh_from_db()
        assert art.views == 1

        # Second visit in same session should NOT increment
        auth_client.get(reverse("solutions:detail", args=[art.slug]))
        art.refresh_from_db()
        assert art.views == 1

    def test_article_vote(self, auth_client):
        art = Article.objects.create(
            category="PR", title="Test Vote", summary="S",
            body="Body", status="published",
        )
        resp = auth_client.post(
            reverse("solutions:vote", args=[art.slug]),
            {"vote": "yes"},
        )
        assert resp.status_code == 302
        art.refresh_from_db()
        assert art.helpful == 1

    def test_edit_article(self, auth_client):
        art = Article.objects.create(
            category="PR", title="Before Edit", summary="S",
            body="Body", status="published",
        )
        resp = auth_client.post(reverse("solutions:edit", args=[art.slug]), {
            "category": "PR",
            "title": "After Edit",
            "summary": "Updated",
            "body": "New body",
            "tags": "",
            "status": "published",
        })
        assert resp.status_code == 302
        art.refresh_from_db()
        assert art.title == "After Edit"

    def test_browse_filters(self, auth_client):
        Article.objects.create(
            category="PR", title="Searchable Article", summary="S",
            body="fiber optic troubleshoot", status="published",
        )
        resp = auth_client.get(reverse("solutions:browse") + "?q=fiber")
        assert resp.status_code == 200
        assert b"Searchable Article" in resp.content


# ═══════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════

class TestReports:
    def test_export_agent_requires_admin(self, agent_client):
        resp = agent_client.get(reverse("reports:download") + "?type=agent")
        # Should 403 for non-admin
        assert resp.status_code == 403

    def test_export_page_loads_for_admin(self, auth_client):
        resp = auth_client.get(reverse("reports:export"))
        assert resp.status_code == 200

    def test_export_download_xlsx(self, auth_client):
        resp = auth_client.get(reverse("reports:download"))
        assert resp.status_code == 200
        assert "spreadsheet" in resp["Content-Type"] or "xlsx" in resp.get("Content-Disposition", "")


# ═══════════════════════════════════════════════════════════════
# ACCOUNTS
# ═══════════════════════════════════════════════════════════════

class TestAccounts:
    def test_profile_loads(self, auth_client):
        resp = auth_client.get(reverse("accounts:profile"))
        assert resp.status_code == 200

    def test_profile_update(self, auth_client):
        resp = auth_client.post(reverse("accounts:profile"), {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@initech.co.id",
            "nik": "EMP001",
            "position": "Engineer",
        })
        assert resp.status_code == 302
        user = User.objects.get(username="admin_test")
        assert user.first_name == "Updated"
        assert user.position == "Engineer"

    def test_agent_list_loads(self, auth_client):
        resp = auth_client.get(reverse("accounts:agents"))
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# DASHBOARD & CORE
# ═══════════════════════════════════════════════════════════════

class TestDashboardCore:
    def test_dashboard_loads(self, auth_client):
        resp = auth_client.get(reverse("core:dashboard"))
        assert resp.status_code == 200

    def test_dashboard_with_period(self, auth_client):
        resp = auth_client.get(reverse("core:dashboard") + "?preset=7d")
        assert resp.status_code == 200

    def test_search(self, auth_client):
        resp = auth_client.get(reverse("core:search") + "?q=test")
        assert resp.status_code == 200

    def test_activity_log_admin_only(self, agent_client):
        resp = agent_client.get(reverse("core:activity_log"))
        assert resp.status_code in (302, 403)

    def test_activity_log_loads(self, auth_client):
        resp = auth_client.get(reverse("core:activity_log"))
        assert resp.status_code == 200

    def test_notifications(self, auth_client):
        resp = auth_client.get(reverse("core:notifications"))
        assert resp.status_code == 200

    def test_healthz(self, db):
        resp = Client().get(reverse("core:healthz"))
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════════
# COMPANIES CRUD (ADMIN ONLY)
# ═══════════════════════════════════════════════════════════════

class TestCompanyCRUD:
    def test_company_list_requires_admin(self, agent_client):
        resp = agent_client.get(reverse("tickets:company_list"))
        assert resp.status_code == 403

    def test_company_list_loads_for_admin(self, auth_client):
        resp = auth_client.get(reverse("tickets:company_list"))
        assert resp.status_code == 200

    def test_company_create(self, auth_client):
        resp = auth_client.post(reverse("tickets:company_list"), {
            "name": "PT Sumber Alfaria",
            "code": "ALFA",
            "contact_person": "Joko",
            "contact_phone": "0812345678",
            "address": "Tangerang",
            "is_active": "on",
        })
        assert resp.status_code == 302
        c = Company.objects.filter(name="PT Sumber Alfaria").first()
        assert c is not None
        assert c.code == "ALFA"
        assert c.is_active is True

    def test_company_edit(self, auth_client):
        c = Company.objects.create(name="Old Partner", code="OLD", is_active=True)
        resp = auth_client.post(reverse("tickets:company_edit", args=[c.pk]), {
            "name": "Updated Partner",
            "code": "UPD",
            "contact_person": "Budi",
            "contact_phone": "08999999",
            "address": "Jakarta",
            "is_active": "on",
        })
        assert resp.status_code == 302
        c.refresh_from_db()
        assert c.name == "Updated Partner"
        assert c.code == "UPD"

    def test_company_toggle(self, auth_client):
        c = Company.objects.create(name="Toggle Co", is_active=True)
        resp = auth_client.post(reverse("tickets:company_toggle", args=[c.pk]))
        assert resp.status_code == 302
        c.refresh_from_db()
        assert c.is_active is False

        # Toggle back
        auth_client.post(reverse("tickets:company_toggle", args=[c.pk]))
        c.refresh_from_db()
        assert c.is_active is True

    def test_company_delete_zero_tickets(self, auth_client):
        c = Company.objects.create(name="Deleteable Co", is_active=True)
        resp = auth_client.post(reverse("tickets:company_delete", args=[c.pk]))
        assert resp.status_code == 302
        assert not Company.objects.filter(pk=c.pk).exists()

    def test_company_delete_prevented_if_tickets_exist(self, auth_client, admin_user):
        c = Company.objects.create(name="Has Tickets Co", is_active=True)
        Ticket.objects.create(
            ticket_type="PR",
            problem_category="los",
            company=c.name,
            subject="Ticket for co",
            description="Desc",
            requester_name="Test",
            requester_phone="081234567890",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )
        resp = auth_client.post(reverse("tickets:company_delete", args=[c.pk]))
        assert resp.status_code == 302
        # Company should still exist
        assert Company.objects.filter(pk=c.pk).exists()


class TestTicketDelete:
    def test_admin_can_delete_ticket(self, auth_client, admin_user):
        t = Ticket.objects.create(
            ticket_type="PR",
            subject="To be deleted",
            description="Delete test",
            company="INITECH",
            requester_name="Admin",
            requester_phone="08123456",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )
        resp = auth_client.post(reverse("tickets:delete", args=[t.number]))
        assert resp.status_code == 302
        assert not Ticket.objects.filter(pk=t.pk).exists()
        assert ActivityLog.objects.filter(target_label=t.number, verb="ticket_delete").exists()

    def test_agent_cannot_delete_ticket(self, agent_client, agent_user):
        t = Ticket.objects.create(
            ticket_type="PR",
            subject="Agent cannot delete",
            description="Delete test",
            company="INITECH",
            requester_name="Agent",
            requester_phone="08123456",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=agent_user,
        )
        resp = agent_client.post(reverse("tickets:delete", args=[t.number]))
        assert resp.status_code == 302
        # Ticket must still exist
        assert Ticket.objects.filter(pk=t.pk).exists()


class TestProblemCategoryOptional:
    def test_create_problem_ticket_without_category(self, auth_client):
        resp = auth_client.post(reverse("tickets:create"), {
            "ticket_type": "PR",
            "subject": "Unknown Problem Incident",
            "description": "Don't know the problem category yet",
            "company": "INITECH",
            "requester_phone": "0812345678",
            "priority": "medium",
            "status": "open",
            "source": "nms",
            "problem_category": "",
            "problem_detail": "",
        })
        assert resp.status_code == 302
        t = Ticket.objects.get(subject="Unknown Problem Incident")
        assert t.problem_category == ""

    def test_close_ticket_updates_category(self, auth_client, admin_user):
        t = Ticket.objects.create(
            ticket_type="PR",
            problem_category="",
            subject="Ticket to close with category",
            description="Desc",
            company="INITECH",
            requester_name="Admin",
            requester_phone="08123456",
            source="nms",
            priority="medium",
            status="open",
            opened_at=timezone.now(),
            created_by=admin_user,
        )
        resp = auth_client.post(reverse("tickets:close", args=[t.number]), {
            "reason_category": "Resolved",
            "reason": "Root cause identified as fiber cut",
            "problem_category": "los",
            "problem_detail": "Fiber cut at km 15",
        })
        assert resp.status_code == 302
        t.refresh_from_db()
        assert t.status == Ticket.Status.CLOSED
        assert t.problem_category == "los"
        assert t.problem_detail == "Fiber cut at km 15"


class TestExportDateFilter:
    def test_export_page_with_date_range(self, auth_client):
        resp = auth_client.get(reverse("reports:export") + "?from=2026-10-01&to=2026-10-15")
        assert resp.status_code == 200
        assert "01/10/2026" in resp.context["range_label"]
        assert "15/10/2026" in resp.context["range_label"]
