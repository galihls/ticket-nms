# Update Requirement - INITECH Ticketing NMS

Dokumen ini berisi spesifikasi kebutuhan pengguna (user requirements) terbaru yang harus diimplementasikan pada sistem.

## 1. Login & Autentikasi

- **Single Sign-On (SSO):** Login wajib mengeksplorasi dan menggunakan akun Office 365 milik INITECH.
- **Protokol:** Menggunakan teknologi SAML 2.0 atau OIDC (OpenID Connect).
- **Session Management:** Tampilan _dashboard_ harus menunjukkan akun/email _agent_ yang sedang digunakan dan menyediakan opsi "Logout" untuk keluar dari sesi.

## 2. Dashboard

Semua data yang ditampilkan di _dashboard_ harus menyesuaikan dengan **Filter Kalender** (tanggal yang dipilih).

- **Visualisasi Data (Pie Chart):** Menampilkan persentase tiket dengan status **Open**, **Outstanding**, dan **Close**.
- **Total Angka (Data Count):** Menampilkan total kumulatif tiket dengan status **Open**, **Outstanding**, dan **Close**.
- **Agent Performance:** Fitur _sort by agent_ agar pengguna dapat melihat progres tiket per _agent_ (dari _open_ hingga _close_).
- **Quick Action:** _Agent_ dapat langsung membuat tiket gangguan (Create New Ticket) lewat _dashboard_.
- **Log Event / Audit Trail (Akses Admin):** Menampilkan log histori aktivitas yang dilakukan oleh _agent_.
  - _Contoh 1:_ Agent 01, Create ticket (Subject, Status, Person In Charge).
  - _Contoh 2:_ Agent 02, Close ticket (Subject, Status, Reason Close, Person In Charge).

## 3. Ticketing System

- **Pembuatan Tiket:** _Agent_ membuat tiket melalui panel navigasi.
- **Format Penomoran Otomatis:** Menggunakan format `[Tahun][Kode][NomorUrut]`.
  - Contoh: `26PR0000` atau `26FR0000`.
  - `26` = Tahun berjalan.
  - `PR` = Problem | `FR` = Feature Request.
  - `0000` = Nomor urut (mulai dari 1 hingga >1.000.000).
- **Notifikasi Global:** Admin dapat melihat notifikasi seluruh tiket dari semua _agent_.

## 4. Solutions (Knowledge Base)

- **Pusat Panduan:** Fitur di mana _agent_ dapat melihat panduan _troubleshooting_ atau solusi baru atas isu yang sudah ditangani oleh _agent_ lain.
- **Kategori Artikel Solusi:** Dibagi ke dalam dua jenis: **Problem** dan **Feature Request**.
- **Create Article:** _Agent_ dapat membuat artikel solusi baru berdasarkan isu yang sudah berhasil ditangani.

## 5. Analytics & Export

- **Hak Akses:** Hanya Admin yang dapat mengakses menu _Analytics Export_.
- **Laporan Excel:** Kemampuan menarik/mencetak data laporan harian dan bulanan ke dalam format `.xlsx`.
- **Referensi Output:** Hasil format _export_ harus mengacu pada dokumen `Report Monitoring INITECH 2026.xlsx`.
