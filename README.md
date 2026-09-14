# Ticketing NMS — INITECH

Sistem ticketing operasional jaringan dengan integrasi SLA Zabbix dan export
laporan Excel. Dibangun dengan Django 5.2 (monolit).

**Status: Fase 0 selesai** — fondasi, login, dan design system sudah jalan.
Rencana lengkap ada di [PLAN.md](PLAN.md).

---

## Menjalankan di lokal

```bash
# 1. Virtualenv + dependensi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Konfigurasi
cp .env.example .env
# buka .env, isi DJANGO_SECRET_KEY dengan string acak

# 3. Database (default SQLite, tanpa setup tambahan)
python manage.py migrate

# 4. Akun administrator pertama
python manage.py createsuperuser

# 5. Jalankan
python manage.py runserver
```

Buka http://127.0.0.1:8000 — akan diarahkan ke halaman login.

| Halaman | URL |
|---|---|
| Login | `/akun/masuk/` |
| Dashboard | `/` |
| Panduan komponen UI | `/panduan-komponen/` |
| Django admin | `/django-admin/` |
| Health check | `/healthz/` |

## Perintah harian

```bash
python manage.py check          # cek konfigurasi
python -m pytest tests/         # jalankan tes
ruff check .                    # lint
ruff check --fix .              # perbaiki otomatis
python manage.py makemigrations # setelah ubah model
```

## Menjalankan dengan Docker (mendekati produksi)

```bash
cp .env.example .env            # isi DJANGO_SECRET_KEY dan POSTGRES_PASSWORD
docker compose up --build
```

Aplikasi tersedia di http://localhost:8080 (nginx → gunicorn → postgres).
Migrasi dan `collectstatic` dijalankan otomatis saat container `web` start.

---

## Struktur

```
config/settings/     base.py (bersama) · dev.py · prod.py
apps/core/           BaseModel, layout, dashboard, healthz
apps/accounts/       User custom, login/logout
templates/           base.html + partials + per-app
static/css/app.css   design system (token warna, komponen)
deploy/nginx.conf    konfigurasi reverse proxy
tests/               uji asap
```

Modul menyusul: `apps/zabbix` (Fase 2), `apps/tickets` (Fase 3),
`apps/reports` (Fase 4).

## Konfigurasi lingkungan

Semua setelan lewat environment variable — lihat [.env.example](.env.example).
Yang penting:

| Variabel | Keterangan |
|---|---|
| `DJANGO_SECRET_KEY` | Wajib. Di produksi harus panjang dan acak |
| `DJANGO_DEBUG` | `True` hanya untuk lokal |
| `DATABASE_URL` | Kosong = SQLite. Postgres: `postgres://user:pass@host:5432/db` |
| `ZABBIX_URL` | Endpoint `api_jsonrpc.php` (dipakai mulai Fase 2) |
| `ZABBIX_API_TOKEN` | API token Zabbix, cara autentikasi yang disarankan |

## Design system

Palet diturunkan dari logo INITECH: navy perisai, biru badan, teal sirkuit.
Semua token warna ada di `static/css/app.css` bagian `:root` — mengubah warna
cukup di satu tempat. Contoh seluruh komponen bisa dilihat langsung di
`/panduan-komponen/`.

| Token | Nilai | Pemakaian |
|---|---|---|
| `--navy-800` | `#16294F` | Sidebar, judul |
| `--navy-600` | `#24457C` | Tombol utama |
| `--teal-600` | `#0F7F79` | Aksi sekunder, teks aksen |
| `--teal-400` | `#35C4BC` | Indikator aktif (bukan untuk teks) |
