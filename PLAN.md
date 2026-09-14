# Ticketing NMS — Rencana Pembangunan

Sistem **Ticketing + SLA Reporting** untuk PT Ideologi Nusa Integrasi (INITECH).
Mencatat gangguan per site, menarik SLA dari **Zabbix**, dan menghasilkan
laporan **Excel** per 4 jam / harian / bulanan.

Konteks: **solo developer**, arsitektur **monolit**, **Python + Django**.

> Revisi 2026-09-08 — menyesuaikan keputusan: master data dihapus (site diambil
> dari Zabbix), laporan diekspor manual tanpa email, dan tipe tiket menjadi
> pilihan Problem / CKG / Relokasi.

---

## 1. Ringkasan Keputusan

| Topik | Keputusan |
|---|---|
| Sumber data site | **Zabbix** — tidak ada modul master data terpisah, supaya tidak ada dua sumber kebenaran |
| Isi tiket | Kode site (mis. `CKGK0`), problem, waktu open, waktu close |
| Tipe tiket | **Problem** (harian) / **CKG** / **Relokasi** — dipilih saat membuat tiket; CKG & Relokasi jarang dipakai |
| Pelaporan rutin | Rekap **per 4 jam** (per shift) |
| SLA | Ditarik dari Zabbix untuk rentang **satu bulan**, ditampilkan bersama daftar problem site terkait |
| Excel | **Export manual** dari UI. Tidak ada pengiriman email otomatis |
| Periode export | Pilihan: **per 4 jam**, **harian**, **bulanan** |
| Login | Ya — akun lokal, dikelola administrator |

---

## 2. Stack

| Lapisan | Pilihan | Alasan |
|---|---|---|
| Framework | **Django 5.2 LTS** | Monolit lengkap: auth, session, ORM, migrasi, admin, permission sudah tersedia. Untuk solo dev ini menghemat berminggu-minggu. |
| Frontend | Django Template + **HTMX** + CSS custom | Tanpa SPA, tanpa build step Node. Satu codebase. CSS ditulis sendiri (bukan Bootstrap) agar tampilan khas INITECH. |
| Database | **PostgreSQL 16** (produksi) / SQLite (dev) | Dipilih lewat `DATABASE_URL`, tanpa ubah kode |
| Zabbix client | `requests` + wrapper sendiri | JSON-RPC sederhana; wrapper sendiri lebih tahan perbedaan versi 6.0/6.4/7.0 |
| Excel | **openpyxl** | Multi-sheet, styling, conditional format, chart |
| Penjadwalan | Management command + **cron** | Sinkron Zabbix berkala. Celery belum diperlukan |
| Serving | gunicorn + nginx + Docker Compose | Reproducible, mudah dipindah server |
| Testing | pytest + pytest-django | Fokus: perhitungan durasi/SLA, workflow tiket, generator Excel |

---

## 3. Struktur Proyek

```
ticketing-nms/
├── config/settings/{base,dev,prod}.py   # setelan per lingkungan
├── apps/
│   ├── core/          # BaseModel, layout, dashboard, healthz      ✅ Fase 0
│   ├── accounts/      # User custom, login/logout                  ✅ Fase 0
│   ├── zabbix/        # client API, sinkron site/host, snapshot SLA   Fase 2
│   ├── tickets/       # Ticket, tipe, status, komentar, riwayat       Fase 3
│   └── reports/       # builder Excel + halaman export                Fase 4
├── templates/         # base.html, partials, per-app
├── static/            # css/app.css (design system), js, img/logo.jpg
├── deploy/nginx.conf
├── tests/
├── docker-compose.yml · Dockerfile · requirements.txt · .env.example
```

---

## 4. Model Data

### accounts ✅ sudah ada
- `User(AbstractUser)` — `nik`, `phone`, `department`, `position`, `shift`
- Peran memakai Django **Group**: `Administrator`, `Supervisor`, `NOC`, `Teknisi`, `Viewer`

### zabbix (Fase 2) — cache, bukan master data
- `ZabbixSite` — `hostid`, `code` (mis. `CKGK0`), `name`, `groups`, `status`,
  `last_synced_at`. Diisi otomatis oleh perintah sinkronisasi; tidak diketik manual.
- `ZabbixProblem` — `eventid`, site, nama problem, severity, `started_at`,
  `resolved_at`, `acknowledged`, relasi opsional ke tiket
- `SlaSnapshot` — site, `period_start`, `period_end`, `slo`, `sli`, `uptime`,
  `downtime`, `error_budget`, `fetched_at`
- `SyncLog` — jenis, mulai/selesai, status, jumlah record, pesan error

### tickets (Fase 3)
- `Ticket`
  - `ticket_number` — auto, format `TKT-YYYYMM-NNNN`
  - `type` — `problem` / `ckg` / `relokasi`
  - `site` → `ZabbixSite`
  - `problem` (judul singkat), `description`, `root_cause`, `action_taken`
  - `severity`, `status`
  - `opened_at`, `closed_at`, `duration_minutes` (dihitung)
  - `assignee`, `created_by`, `shift`
  - relasi opsional ke `ZabbixProblem`
- Status: `Open → In Progress → Pending → Resolved → Closed` (+ `Reopened`, `Cancelled`)
- `TicketComment`, `TicketAttachment`, `TicketHistory` (jejak audit perubahan)

### reports (Fase 4)
- `ReportExport` — jenis periode (4 jam/harian/bulanan), rentang, filter site,
  file hasil, pembuat, waktu. Berguna sebagai jejak "laporan mana yang sudah dikirim ke siapa".

---

## 5. Integrasi Zabbix — catatan teknis

- **Endpoint:** `POST /api_jsonrpc.php`, JSON-RPC 2.0
- **Autentikasi:** **API token** via header `Authorization: Bearer <token>`
  (cara yang benar untuk Zabbix 6.4/7.0 — di 7.0 parameter `auth` di body sudah
  dihapus). Untuk Zabbix 6.0 disediakan jalur `user.login`. Mode dipilih lewat `.env`.
- **Method yang dipakai:**
  - `host.get` — daftar site/host → mengisi `ZabbixSite`
  - `problem.get` / `event.get` — daftar problem untuk kolom pendamping SLA
  - `sla.get` + `sla.getsli` — SLI per periode (Zabbix ≥ 6.0 dengan modul Services)
  - `service.get` — pohon service bila SLA dipetakan per service
- **Prinsip:** angka SLA **tidak dihitung ulang** — diambil dari Zabbix lalu
  di-snapshot ke DB, supaya laporan yang sudah terbit tidak berubah kalau data
  di Zabbix berubah atau kena housekeeping.
- **Jika modul Services/SLA di Zabbix belum dikonfigurasi:** jalur cadangan adalah
  menghitung availability dari `trend`/`history` item ICMP ping. Perlu dicek di
  awal Fase 2 — ini penentu besar arah pekerjaan.

---

## 6. Laporan Excel

Satu builder, tiga periode. Nama file mengikuti periode, mis.
`Laporan_4Jam_2026-09-08_0800-1200.xlsx`, `Laporan_Harian_2026-09-08.xlsx`,
`Laporan_Bulanan_2026-09.xlsx`.

**Laporan 4 jam & harian** — fokus operasional:

| Sheet | Isi |
|---|---|
| `Rekap` | Periode, jumlah tiket per tipe, jumlah open/closed, total downtime |
| `Detail Tiket` | No tiket, kode site, tipe, problem, open, close, durasi, status, PIC |
| `Problem Zabbix` | Problem aktif/selesai pada rentang tsb, severity, durasi, tiket terkait |

**Laporan bulanan** — fokus SLA:

| Sheet | Isi |
|---|---|
| `Ringkasan` | Periode, jumlah site, rata-rata SLA, jumlah site memenuhi/tidak memenuhi SLO |
| `SLA per Site` | Kode site, SLO, SLI aktual, uptime, downtime, error budget, status ✅/❌ — **di sebelahnya daftar problem site tsb** (sesuai permintaan) |
| `Detail Tiket` | Seluruh tiket bulan tersebut |
| `Detail Problem` | Seluruh problem Zabbix bulan tersebut |

Semua diunduh langsung dari halaman Export. Tidak ada penjadwalan email.

---

## 7. Roadmap

### ✅ Fase 0 — Fondasi & Login *(SELESAI)*
Struktur project, settings dev/prod, Docker, design system CSS dari warna logo,
layout sidebar+topbar, halaman login, dashboard kerangka, panduan komponen,
model `User` custom, healthz, 8 uji asap.

### Fase 1 — Manajemen Pengguna (2–3 hari)
- CRUD pengguna di UI (bukan hanya Django admin), aktif/nonaktif, reset password
- Group/peran + pembatasan menu per peran
- Ganti password sendiri, halaman profil
- Catatan percobaan login (audit) + kunci otomatis setelah gagal berulang
- **Selesai kalau:** admin bisa membuat akun NOC dan menu tampil sesuai peran

### Fase 2 — Integrasi Zabbix (4–5 hari)
- `ZabbixClient` (Bearer token / user.login, retry, timeout, logging)
- Halaman Pengaturan Zabbix + tombol **Test Connection**
- `sync_zabbix_sites` — isi daftar site dari `host.get`
- `sync_zabbix_problems` — tarik problem berkala
- Halaman daftar site + status sinkronisasi terakhir
- Cron sinkronisasi
- **Selesai kalau:** daftar site sungguhan (mis. `CKGK0`) muncul di aplikasi

### Fase 3 — Ticketing Inti (6–8 hari) ← modul terbesar
- Model tiket + penomoran otomatis + workflow status
- Form buat tiket: pilih **Problem / CKG / Relokasi**, pilih site dari Zabbix,
  isi problem, waktu open & close
- Daftar tiket: filter (tipe/status/site/rentang tanggal/PIC), pencarian, sortir,
  paginasi
- Detail tiket: komentar, lampiran, timeline perubahan
- Hitung durasi otomatis, tandai tiket yang masih terbuka
- **Selesai kalau:** satu tiket bisa berjalan Open → Closed lengkap dengan jejaknya

### Fase 4 — Export Excel & SLA (5–6 hari)
- `fetch_sla_snapshot` — tarik SLA sebulan dari Zabbix ke `SlaSnapshot`
- Halaman SLA Bulanan: tabel SLA per site + problem pendamping
- Halaman Export: pilih periode (4 jam / harian / bulanan) + filter site → unduh
- Builder Excel dengan styling dan conditional formatting
- **Selesai kalau:** ketiga jenis laporan bisa diunduh dan angkanya cocok dengan Zabbix

### Fase 5 — Dashboard (3–4 hari)
- Kotak angka: tiket terbuka, tiket 4 jam terakhir, SLA bulan berjalan, site bermasalah
- Grafik tren tiket & SLA, daftar tiket terbaru, site paling sering bermasalah

### Fase 6 — Hardening & Deploy (3–4 hari)
- Perluas cakupan tes, `DEBUG=False`, HTTPS, rate limit
- Deploy Docker Compose ke server, backup DB terjadwal + uji restore
- Dokumentasi instalasi, operasi, dan panduan pengguna

**Sisa perkiraan: 23–30 hari kerja (±5–6 minggu solo).**

---

## 8. Risiko

| Risiko | Mitigasi |
|---|---|
| Modul Services/SLA di Zabbix belum dikonfigurasi | Diperiksa di awal Fase 2; siapkan jalur cadangan hitung availability dari item ICMP |
| Versi Zabbix berbeda (6.0 vs 7.0) | Client mendukung dua mode auth; simpan contoh payload di `docs/` |
| Kode site di Zabbix tidak konsisten dengan yang dipakai tim | Sediakan kolom alias/nama tampilan pada `ZabbixSite` |
| Angka SLA berubah setelah laporan terbit | Snapshot ke DB; laporan selalu dari snapshot |
| Zabbix tidak bisa diakses saat membuat tiket | `ZabbixSite` adalah cache lokal — tiket tetap bisa dibuat walau Zabbix sedang down |
| Scope melebar | Perubahan dicatat di dokumen ini dulu sebelum dikerjakan |

---

## 9. Yang Masih Perlu Dikonfirmasi

1. **Versi Zabbix** yang dipakai, dan apakah modul **Services + SLA** sudah dikonfigurasi
   atau SLA masih dihitung manual. → penentu arah Fase 2 & 4.
2. **URL Zabbix + API token** (read-only sudah cukup) untuk mulai Fase 2.
3. **CKG** kepanjangannya apa, dan field tambahan apa yang perlu dicatat khusus
   untuk tiket CKG dan Relokasi (berbeda dari tiket Problem biasa)?
4. Rekap 4 jam mengikuti jam shift yang mana? Asumsi sementara:
   00–04, 04–08, 08–12, 12–16, 16–20, 20–24.
5. Ada **contoh file Excel** laporan yang selama ini dipakai? Kalau ada, formatnya diikuti.

Belum dijawab pun Fase 1 tetap bisa jalan; yang benar-benar terblokir hanya Fase 2.

---

## 10. Status Saat Ini

**Fase 0 selesai.** Aplikasi sudah bisa dijalankan, login berfungsi, tampilan
sudah memakai identitas INITECH. Langkah berikutnya: **Fase 1 — Manajemen Pengguna**,
atau langsung **Fase 2** kalau kredensial Zabbix sudah tersedia.
