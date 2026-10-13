"""Uji asap Fase 0: kerangka aplikasi hidup dan halaman inti bisa dirender."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="noc01",
        password="RahasiaKuat123",
        first_name="Budi",
        last_name="Santoso",
        position="NOC Engineer",
    )


# ATOMIC_REQUESTS=True membuka transaksi di tiap request, jadi semua tes view
# butuh fixture `db` walaupun view-nya sendiri tidak menyentuh tabel.
def test_halaman_login_tampil(client, db):
    resp = client.get(reverse("accounts:login"))
    assert resp.status_code == 200
    assert "Sign In" in resp.content.decode()


def test_dashboard_butuh_login(client, db):
    resp = client.get(reverse("core:dashboard"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp["Location"]


def test_login_berhasil_lalu_dashboard(client, user):
    resp = client.post(
        reverse("accounts:login"),
        {"username": "noc01", "password": "RahasiaKuat123"},
        follow=True,
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Dashboard" in body
    assert "Budi Santoso" in body


def test_login_gagal_menampilkan_pesan(client, user):
    resp = client.post(
        reverse("accounts:login"),
        {"username": "noc01", "password": "salah"},
    )
    assert resp.status_code == 200
    assert "Invalid username or password" in resp.content.decode()


def test_styleguide_tampil(client, user):
    client.force_login(user)
    resp = client.get(reverse("core:styleguide"))
    assert resp.status_code == 200
    assert "Color Palette" in resp.content.decode()


def test_healthz_ok(client, db):
    resp = client.get(reverse("core:healthz"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_logout_mengembalikan_ke_login(client, user):
    client.force_login(user)
    resp = client.post(reverse("accounts:logout"), follow=True)
    assert resp.status_code == 200
    assert "Sign In" in resp.content.decode()


@pytest.mark.django_db
def test_inisial_dan_nama_tampil_benar():
    u = User.objects.create_user(username="ahmad", password="x", first_name="Ahmad",
                                 last_name="Fauzi")
    assert u.display_name == "Ahmad Fauzi"
    assert u.initials == "AF"

    v = User.objects.create_user(username="operator", password="x")
    assert v.display_name == "operator"
    assert v.initials == "OP"
