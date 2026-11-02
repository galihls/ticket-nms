from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.tickets.models import Company, CompanyService, Ticket
from apps.tickets.forms import TicketForm, CompanyForm, CompanyServiceForm
import json


class CompanyAndServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password123"
        )
        self.staff_user = User.objects.create_user(
            username="staff", email="staff@example.com", password="password123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="agent", email="agent@example.com", password="password123"
        )
        self.company = Company.objects.create(
            name="PT Solusi Maju Bersama",
            code="SMB",
            customer_id="CUST-SMB-001",
            partner="PT Partner Global",
            contact_person="Budi Santoso",
            contact_phone="081234567890",
        )
        self.service1 = CompanyService.objects.create(
            company=self.company,
            service_id="SRV-SMB-01",
            service_name="Dedicated Internet 100Mbps",
            device_solution="MikroTik CCR2004",
            brand="MikroTik",
        )
        self.service2 = CompanyService.objects.create(
            company=self.company,
            service_id="SRV-SMB-02",
            service_name="Managed Firewall",
            device_solution="FortiGate 60F",
            brand="Fortinet",
        )

    def test_company_str_and_properties(self):
        self.assertEqual(str(self.company), "PT Solusi Maju Bersama")
        self.assertEqual(self.company.service_count, 2)
        self.assertEqual(self.company.ticket_count, 0)

    def test_company_service_str(self):
        self.assertIn("SRV-SMB-01", str(self.service1))
        self.assertIn("Dedicated Internet 100Mbps", str(self.service1))
        self.assertIn("PT Solusi Maju Bersama", str(self.service1))

    def test_ticket_form_auto_fill_from_company_service(self):
        form_data = {
            "ticket_type": "PR",
            "subject": "Internet Down di Site Cabang",
            "description": "Koneksi terputus sejak pagi",
            "company": self.company.name,
            "priority": "medium",
            "status": "open",
            "source": "chat",
            "problem_category": "los",
            "requester_phone": "081234567890",
            "company_service": self.service1.id,
        }
        form = TicketForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        ticket = form.save(commit=False)
        ticket.created_by = self.regular_user
        ticket.requester_name = self.regular_user.display_name
        ticket.requester_email = self.regular_user.email
        ticket.save()

        self.assertEqual(ticket.customer_id, "CUST-SMB-001")
        self.assertEqual(ticket.partner, "PT Partner Global")
        self.assertEqual(ticket.service_id, "SRV-SMB-01")
        self.assertEqual(ticket.service_name, "Dedicated Internet 100Mbps")
        self.assertEqual(ticket.device_solution, "MikroTik CCR2004")
        self.assertEqual(ticket.brand, "MikroTik")
        self.assertEqual(ticket.company_service, self.service1)

    def test_ticket_form_fallback_to_company_when_no_service_selected(self):
        form_data = {
            "ticket_type": "PR",
            "subject": "Kendala Listrik Site",
            "description": "Genset mati",
            "company": self.company.name,
            "priority": "medium",
            "status": "open",
            "source": "chat",
            "problem_category": "power",
            "requester_phone": "081234567890",
            "company_service": "",
        }
        form = TicketForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        ticket = form.save(commit=False)
        ticket.created_by = self.regular_user
        ticket.save()

        self.assertEqual(ticket.customer_id, "CUST-SMB-001")
        self.assertEqual(ticket.partner, "PT Partner Global")
        self.assertIsNone(ticket.company_service)
        self.assertEqual(ticket.service_id, "")
        self.assertEqual(ticket.service_name, "")

    def test_ticket_form_manual_override(self):
        form_data = {
            "ticket_type": "PR",
            "subject": "Kendala Khusus Custom Device",
            "description": "Perangkat custom",
            "company": self.company.name,
            "priority": "medium",
            "status": "open",
            "source": "chat",
            "problem_category": "other",
            "problem_detail": "Custom cabling",
            "requester_phone": "081234567890",
            "company_service": "",
            "service_id": "CUSTOM-SID-99",
            "service_name": "Dark Fiber",
            "device_solution": "Cisco Catalyst",
            "brand": "Cisco",
        }
        form = TicketForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        ticket = form.save(commit=False)
        ticket.created_by = self.regular_user
        ticket.save()

        self.assertEqual(ticket.service_id, "CUSTOM-SID-99")
        self.assertEqual(ticket.service_name, "Dark Fiber")
        self.assertEqual(ticket.device_solution, "Cisco Catalyst")
        self.assertEqual(ticket.brand, "Cisco")

    def test_ticket_form_type_validation_rules(self):
        # PR with 'other' needs problem_detail
        form_pr_invalid = TicketForm(data={
            "ticket_type": "PR",
            "subject": "Test Problem Other",
            "description": "Desc",
            "company": self.company.name,
            "priority": "medium",
            "status": "open",
            "source": "chat",
            "problem_category": "other",
            "problem_detail": "",
            "requester_phone": "081234567890",
        })
        self.assertFalse(form_pr_invalid.is_valid())
        self.assertIn("problem_detail", form_pr_invalid.errors)

        # FR does not allow low priority
        form_fr_invalid = TicketForm(data={
            "ticket_type": "FR",
            "subject": "Test Feature Request",
            "description": "Desc",
            "company": self.company.name,
            "priority": "low",
            "status": "open",
            "source": "chat",
            "requester_phone": "081234567890",
        })
        self.assertFalse(form_fr_invalid.is_valid())
        self.assertIn("priority", form_fr_invalid.errors)

        # RC requires address and only allows medium priority
        form_rc_invalid = TicketForm(data={
            "ticket_type": "RC",
            "subject": "Test Relocation",
            "description": "Desc",
            "company": self.company.name,
            "priority": "high",
            "status": "open",
            "source": "chat",
            "address": "",
            "requester_phone": "081234567890",
        })
        self.assertFalse(form_rc_invalid.is_valid())
        self.assertIn("address", form_rc_invalid.errors)
        self.assertIn("priority", form_rc_invalid.errors)


class TicketViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password123"
        )
        self.agent = User.objects.create_user(
            username="agent", email="agent@example.com", password="password123"
        )
        self.company = Company.objects.create(
            name="PT Solusi Maju Bersama",
            customer_id="CUST-SMB-001",
            partner="PT Partner Global",
        )
        self.service = CompanyService.objects.create(
            company=self.company,
            service_id="SRV-001",
            service_name="Bandwidth 100M",
            device_solution="Router",
            brand="MikroTik",
        )
        self.ticket = Ticket.objects.create(
            ticket_type="PR",
            subject="Gangguan Koneksi",
            description="Koneksi drop",
            company=self.company.name,
            customer_id=self.company.customer_id,
            partner=self.company.partner,
            company_service=self.service,
            service_id=self.service.service_id,
            service_name=self.service.service_name,
            device_solution=self.service.device_solution,
            brand=self.service.brand,
            priority="medium",
            problem_category="los",
            requester_phone="081234567890",
            created_by=self.agent,
            requester_name=self.agent.display_name,
            requester_email=self.agent.email,
        )

    def test_company_list_view_permissions(self):
        # Regular user cannot access company list
        self.client.force_login(self.agent)
        response_agent = self.client.get(reverse("tickets:company_list"))
        self.assertEqual(response_agent.status_code, 403)

        # Admin user can access company list
        self.client.force_login(self.admin)
        response_admin = self.client.get(reverse("tickets:company_list"))
        self.assertEqual(response_admin.status_code, 200)
        self.assertContains(response_admin, "PT Solusi Maju Bersama")
        self.assertContains(response_admin, "CUST-SMB-001")

        # Test alias route /tiket/perusahaan/
        response_alias = self.client.get("/tiket/perusahaan/")
        self.assertEqual(response_alias.status_code, 200)

    def test_company_edit_view_permissions(self):
        # Regular user cannot edit company (staff/superuser only)
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:company_edit", kwargs={"pk": self.company.pk}))
        self.assertEqual(response.status_code, 403)

        # Admin can edit company
        self.client.force_login(self.admin)
        response = self.client.get(reverse("tickets:company_edit", kwargs={"pk": self.company.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PT Solusi Maju Bersama")
        self.assertContains(response, "Services / Products Catalog")

    def test_company_service_create_and_delete_view(self):
        self.client.force_login(self.admin)

        # Add service
        response = self.client.post(
            reverse("tickets:company_service_create", kwargs={"company_pk": self.company.pk}),
            {
                "service_id": "SRV-NEW-99",
                "service_name": "Cloud Backup Solution",
                "device_solution": "Storage",
                "brand": "Dell",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_srv = CompanyService.objects.filter(service_id="SRV-NEW-99").first()
        self.assertIsNotNone(new_srv)
        self.assertEqual(new_srv.service_name, "Cloud Backup Solution")

        # Delete service
        del_response = self.client.post(
            reverse("tickets:company_service_delete", kwargs={"pk": new_srv.pk})
        )
        self.assertEqual(del_response.status_code, 302)
        self.assertFalse(CompanyService.objects.filter(service_id="SRV-NEW-99").exists())

    def test_companies_data_api(self):
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:companies_data_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("PT Solusi Maju Bersama", data)
        comp_data = data["PT Solusi Maju Bersama"]
        self.assertEqual(comp_data["customer_id"], "CUST-SMB-001")
        self.assertEqual(comp_data["partner"], "PT Partner Global")
        self.assertEqual(len(comp_data["services"]), 1)
        self.assertEqual(comp_data["services"][0]["service_id"], "SRV-001")

    def test_ticket_create_view_get_and_post(self):
        self.client.force_login(self.agent)
        # GET form
        response = self.client.get(reverse("tickets:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer ID")
        self.assertContains(response, "Pilihan Layanan / Service")

        # POST create
        post_response = self.client.post(reverse("tickets:create"), {
            "ticket_type": "PR",
            "subject": "Web Portal lambat",
            "description": "Respon web lemot di client",
            "company": self.company.name,
            "priority": "medium",
            "status": "open",
            "source": "chat",
            "problem_category": "los",
            "requester_phone": "081234567890",
            "company_service": self.service.id,
        })
        self.assertEqual(post_response.status_code, 302)
        new_ticket = Ticket.objects.filter(subject="Web Portal lambat").first()
        self.assertIsNotNone(new_ticket)
        self.assertEqual(new_ticket.customer_id, "CUST-SMB-001")
        self.assertEqual(new_ticket.service_name, "Bandwidth 100M")

    def test_ticket_detail_view(self):
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:detail", kwargs={"number": self.ticket.number}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CUST-SMB-001")
        self.assertContains(response, "PT Partner Global")
        self.assertContains(response, "Bandwidth 100M")
        self.assertContains(response, "MikroTik")

    def test_company_delete_protection_when_tickets_exist(self):
        self.client.force_login(self.admin)
        # Attempting to delete company that has active ticket
        response = self.client.post(reverse("tickets:company_delete", kwargs={"pk": self.company.pk}))
        self.assertEqual(response.status_code, 302)
        # Company should still exist
        self.assertTrue(Company.objects.filter(pk=self.company.pk).exists())
