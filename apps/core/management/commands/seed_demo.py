"""Isi database dengan data peragaan yang realistis.

Dipakai untuk demo internal dan untuk melihat tampilan dalam keadaan penuh.
Sengaja memakai seed acak tetap supaya angka di layar sama setiap kali
dijalankan — presentasi tidak berubah-ubah antar percobaan.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import ActivityLog, Notification
from apps.solutions.models import Article, Category, Folder
from apps.tickets.models import Ticket, TicketReply

SEED = 20260912

AGENTS = [
    # username, nama, jabatan, shift, departemen, admin?
    ("rizky.pratama", "Rizky", "Pratama", "NOC Engineer", "pagi", "Network Operation", True),
    ("dewi.anggraini", "Dewi", "Anggraini", "NOC Engineer", "siang", "Network Operation", False),
    ("bagus.setiawan", "Bagus", "Setiawan", "Field Engineer", "pagi", "Field Support", False),
    ("nadia.puspita", "Nadia", "Puspita", "Helpdesk", "malam", "Customer Support", False),
    ("arif.hidayat", "Arif", "Hidayat", "Network Engineer", "non_shift", "Network Operation", False),
    ("sari.wulandari", "Sari", "Wulandari", "Supervisor NOC", "non_shift", "Network Operation", True),
]

SITE_CODES = ["CKGK0", "CKGK1", "BDGS2", "SBYT4", "MDNP1", "SMGJ3",
              "DPSB5", "MKSR2", "PLBG1", "BTMK7"]

COMPANIES = ["Kantor Pusat Jakarta", "Cabang Bandung", "Cabang Surabaya",
             "Cabang Medan", "Cabang Semarang", "Data Center Cikarang"]

REQUESTERS = ["Andi Nugroho", "Siti Rahayu", "Budi Santoso", "Maya Kartika",
              "Fajar Ramadhan", "Lestari Dewi", "Gunawan Wibowo", "Rina Marlina"]

PROBLEM_SUBJECTS = [
    ("Link down site {site} sejak pagi", "urgent",
     "Perangkat di site {site} tidak merespons ping sejak pukul 06.40. "
     "Alarm ICMP unavailable muncul di NMS dan belum recover otomatis."),
    ("Packet loss tinggi pada uplink {site}", "high",
     "Terpantau packet loss 12–18% pada interface uplink {site}. "
     "Latensi rata-rata naik dari 8 ms ke 140 ms."),
    ("Perangkat OLT {site} restart berulang", "urgent",
     "OLT di {site} melakukan restart tiga kali dalam dua jam terakhir. "
     "Log menunjukkan power supply unit sempat drop."),
    ("CPU utilization router {site} di atas 90%", "high",
     "Router core {site} menunjukkan CPU sustained 92–96% selama 30 menit. "
     "Belum ada dampak ke trafik pelanggan."),
    ("Koneksi intermittent di {site}", "medium",
     "Pengguna melaporkan koneksi putus-nyambung setiap 10–15 menit "
     "sejak kemarin sore di {site}."),
    ("Suhu perangkat {site} melewati ambang batas", "high",
     "Sensor suhu rack di {site} membaca 46°C, di atas ambang 40°C. "
     "Perlu pengecekan pendingin ruangan."),
    ("Backup link {site} tidak aktif saat failover", "urgent",
     "Saat uji failover, backup link {site} tidak mengambil alih trafik. "
     "Diduga konfigurasi routing protocol belum benar."),
    ("Interface error counter naik di {site}", "medium",
     "CRC error pada interface Gi0/1 {site} bertambah ±400 per jam. "
     "Kemungkinan masalah pada patch cord atau SFP."),
    ("Bandwidth utilization {site} mendekati kapasitas", "medium",
     "Utilisasi uplink {site} konsisten di 88–94% pada jam sibuk. "
     "Perlu evaluasi upgrade kapasitas."),
    ("UPS {site} beralih ke baterai", "high",
     "UPS di {site} melaporkan on-battery selama 12 menit. "
     "Perlu konfirmasi kondisi listrik PLN setempat."),
    ("Latency tinggi ke gateway {site}", "medium",
     "Ping ke gateway {site} rata-rata 180 ms, normalnya di bawah 15 ms."),
    ("Perangkat switch akses {site} tidak terbaca NMS", "low",
     "Switch akses lantai 3 di {site} hilang dari topologi NMS "
     "walau perangkat masih menyala."),
]

FEATURE_SUBJECTS = [
    ("Tambahkan notifikasi WhatsApp untuk alarm kritikal", "high",
     "Tim lapangan meminta alarm severity Disaster dan High juga dikirim "
     "ke grup WhatsApp, tidak hanya email."),
    ("Laporan SLA otomatis per bulan", "medium",
     "Permintaan agar laporan SLA bulanan dikirim otomatis setiap tanggal 1 "
     "tanpa perlu ditarik manual."),
    ("Dashboard khusus untuk manajemen", "medium",
     "Manajemen meminta tampilan ringkas berisi tren tiket dan SLA saja, "
     "tanpa detail teknis."),
    ("Filter tiket berdasarkan wilayah", "low",
     "Agent meminta filter per wilayah (Jabodetabek, Jawa Barat, dsb.) "
     "supaya tidak perlu memilih kode site satu per satu."),
    ("Ekspor laporan dalam format PDF", "low",
     "Selain Excel, diminta opsi ekspor PDF untuk lampiran surat resmi."),
    ("Integrasi tiket dengan alarm Zabbix otomatis", "high",
     "Alarm severity Disaster diminta langsung membuat tiket tanpa input "
     "manual agent, lengkap dengan kode site."),
    ("Mode gelap pada antarmuka", "low",
     "Tim shift malam meminta tema gelap untuk mengurangi kelelahan mata."),
    ("Template balasan cepat untuk kasus berulang", "medium",
     "Agent meminta kumpulan template balasan agar tidak mengetik ulang "
     "jawaban yang sama setiap hari."),
]

REPLIES = [
    "Sudah dicek dari sisi NMS, perangkat masih unreachable. "
    "Tim lapangan sedang dalam perjalanan ke lokasi.",
    "Konfirmasi dari teknisi: ada pekerjaan galian di sekitar jalur fiber. "
    "Estimasi perbaikan 4 jam.",
    "Sudah dilakukan restart remote pada perangkat, layanan kembali normal. "
    "Monitoring dilanjutkan 1x24 jam.",
    "Terima kasih laporannya. Tiket sudah kami eskalasi ke tim Network Engineer.",
    "Update: link sudah up kembali pukul 11.20. Mohon konfirmasi dari sisi pengguna.",
    "Penggantian SFP sudah dilakukan, error counter berhenti bertambah.",
    "Mohon informasi tambahan: apakah gangguan terjadi di semua perangkat "
    "atau hanya sebagian?",
    "Sudah dijadwalkan maintenance window malam ini pukul 23.00–01.00.",
]

NOTES = [
    "Catatan internal: koordinasi dengan vendor sudah dilakukan via telepon.",
    "Catatan internal: perangkat masih dalam masa garansi, klaim RMA disiapkan.",
    "Catatan internal: pelapor cukup sensitif soal SLA, harap update berkala.",
]

CLOSE_REASONS = [
    ("Perbaikan selesai", "Jalur fiber yang putus sudah disambung ulang oleh tim "
     "lapangan. Link kembali normal dan stabil setelah dipantau 2 jam."),
    ("Perbaikan selesai", "Penggantian SFP pada interface uplink menyelesaikan "
     "masalah CRC error. Counter tidak bertambah lagi."),
    ("Perbaikan selesai", "Konfigurasi routing protocol pada backup link "
     "diperbaiki, uji failover berhasil."),
    ("Selesai oleh pelapor", "Pelapor mengonfirmasi koneksi sudah normal "
     "setelah perangkat sisi pengguna di-restart."),
    ("Tidak dapat direproduksi", "Setelah dipantau 24 jam, gejala tidak muncul "
     "kembali. Tiket ditutup dengan catatan monitoring."),
    ("Duplikat tiket lain", "Gangguan sama sudah ditangani pada tiket sebelumnya "
     "untuk site yang sama."),
]

FOLDERS = [
    (Category.PROBLEM, "Konektivitas & Link", "Link down, packet loss, latensi tinggi", 1),
    (Category.PROBLEM, "Perangkat & Hardware", "Router, switch, OLT, SFP, UPS", 2),
    (Category.PROBLEM, "Performa Jaringan", "Utilisasi, CPU, memori, bottleneck", 3),
    (Category.PROBLEM, "Monitoring & Alarm", "Zabbix, NMS, ambang batas alarm", 4),
    (Category.FEATURE, "Permintaan Fitur Aplikasi", "Usulan fitur baru pada sistem", 1),
    (Category.FEATURE, "Integrasi & Otomasi", "Integrasi antar sistem, otomasi kerja", 2),
    (Category.FEATURE, "Pelaporan", "Format laporan, ekspor, penjadwalan", 3),
]

ARTICLES = [
    ("Konektivitas & Link", "Langkah standar menangani link down pada site",
     "Prosedur baku dari alarm muncul sampai tiket bisa ditutup.",
     "Gejala\n\nPerangkat di site tidak merespons ping dan alarm ICMP "
     "unavailable muncul di NMS. Umumnya seluruh layanan di site tersebut "
     "ikut terdampak.\n\n"
     "Langkah pemeriksaan\n\n"
     "1. Pastikan alarm bukan false positive — cek dari dua sumber monitoring "
     "yang berbeda.\n"
     "2. Lakukan ping dan traceroute dari core menuju gateway site.\n"
     "3. Periksa status interface uplink pada perangkat hulu terdekat.\n"
     "4. Cek apakah ada tiket gangguan massal dari penyedia transmisi.\n"
     "5. Kalau perangkat masih dapat diakses out-of-band, ambil log terakhir "
     "sebelum link putus.\n\n"
     "Solusi\n\n"
     "Bila penyebabnya putus fiber, koordinasikan dengan tim lapangan dan "
     "catat estimasi perbaikan pada tiket. Bila penyebabnya perangkat, "
     "lakukan restart remote lebih dulu; kalau tidak pulih, jadwalkan "
     "penggantian perangkat.\n\n"
     "Catatan\n\n"
     "Selalu pantau 1x24 jam setelah link up sebelum menutup tiket. Tulis "
     "waktu open dan close sebenarnya karena angka itu yang dipakai laporan SLA.",
     "link-down, fiber, icmp, sla", 412, 38, 2),

    ("Konektivitas & Link", "Menangani packet loss tinggi pada uplink",
     "Cara mempersempit penyebab packet loss sebelum eskalasi ke vendor.",
     "Gejala\n\nPacket loss di atas 5% disertai kenaikan latensi. Pengguna "
     "melaporkan koneksi terasa lambat atau putus-nyambung.\n\n"
     "Langkah pemeriksaan\n\n"
     "1. Jalankan ping berkelanjutan ke beberapa titik: gateway lokal, "
     "perangkat hulu, lalu tujuan di luar jaringan.\n"
     "2. Catat pada titik mana loss mulai muncul — itu menunjukkan segmen "
     "yang bermasalah.\n"
     "3. Periksa error counter pada interface di kedua ujung segmen tersebut.\n"
     "4. Bandingkan utilisasi interface dengan kapasitasnya; loss pada "
     "utilisasi di atas 90% biasanya masalah kapasitas, bukan perangkat.\n\n"
     "Solusi\n\n"
     "CRC error yang terus naik menunjuk pada masalah fisik: ganti patch cord "
     "atau SFP lebih dulu karena paling murah dan cepat. Kalau bersih, "
     "eskalasi ke penyedia transmisi dengan lampiran hasil ping dan counter.",
     "packet-loss, latency, crc, sfp", 287, 24, 1),

    ("Perangkat & Hardware", "Prosedur penggantian SFP pada perangkat aktif",
     "Urutan aman mengganti SFP tanpa memperpanjang gangguan.",
     "Kapan SFP perlu diganti\n\nCRC atau input error terus bertambah pada "
     "satu interface sementara interface lain di perangkat sama bersih, dan "
     "level daya optik di luar rentang normal.\n\n"
     "Langkah penggantian\n\n"
     "1. Siapkan SFP pengganti dengan tipe dan panjang gelombang yang sama.\n"
     "2. Ajukan maintenance window kalau interface membawa trafik produksi.\n"
     "3. Catat konfigurasi interface sebelum perangkat disentuh.\n"
     "4. Lepas SFP lama, bersihkan konektor fiber, pasang SFP baru.\n"
     "5. Verifikasi level daya optik dan pastikan error counter berhenti naik.\n\n"
     "Setelah penggantian\n\n"
     "Pantau minimal dua jam. Catat nomor seri SFP lama dan baru pada tiket "
     "untuk keperluan klaim garansi.",
     "sfp, hardware, optik, maintenance", 198, 19, 0),

    ("Perangkat & Hardware", "Menangani perangkat yang restart berulang",
     "Membedakan penyebab daya, panas, dan kerusakan perangkat.",
     "Gejala\n\nPerangkat melakukan reboot beberapa kali dalam rentang "
     "singkat tanpa perintah dari operator.\n\n"
     "Cara membedakan penyebab\n\n"
     "Periksa log terakhir sebelum reboot. Pesan terkait power supply "
     "menunjuk ke masalah daya; pesan terkait suhu menunjuk ke pendingin "
     "ruangan; reboot tanpa pesan apa pun biasanya kerusakan perangkat keras.\n\n"
     "Tindakan\n\n"
     "Untuk masalah daya, verifikasi kondisi UPS dan sumber listrik. Untuk "
     "masalah suhu, cek pendingin dan kebersihan filter rack. Untuk kerusakan "
     "perangkat, siapkan penggantian dan proses RMA bila masih bergaransi.",
     "restart, power, suhu, rma", 156, 14, 1),

    ("Performa Jaringan", "Menangani CPU utilization tinggi pada router",
     "Membedakan beban wajar dari gejala serangan atau salah konfigurasi.",
     "Gejala\n\nCPU router bertahan di atas 90% lebih dari 15 menit.\n\n"
     "Pemeriksaan\n\n"
     "1. Identifikasi proses yang mengonsumsi CPU terbesar.\n"
     "2. Bandingkan dengan pola beban pada hari dan jam yang sama minggu lalu.\n"
     "3. Periksa apakah ada lonjakan trafik broadcast atau perubahan "
     "konfigurasi terakhir.\n\n"
     "Solusi\n\n"
     "Beban wajar pada jam sibuk cukup didokumentasikan dan dijadikan bahan "
     "evaluasi kapasitas. Lonjakan tidak wajar perlu ditelusuri: kemungkinan "
     "routing loop, broadcast storm, atau proses yang salah konfigurasi.",
     "cpu, router, kapasitas", 174, 16, 2),

    ("Monitoring & Alarm", "Menentukan ambang batas alarm yang tidak berisik",
     "Menyetel ambang agar alarm yang muncul benar-benar perlu ditindak.",
     "Masalah\n\nAmbang yang terlalu sensitif membuat agent terbiasa "
     "mengabaikan alarm — dan alarm yang benar-benar penting ikut terlewat.\n\n"
     "Pendekatan\n\n"
     "1. Ambil data tujuh hari untuk melihat pola normal setiap metrik.\n"
     "2. Tetapkan ambang di atas puncak normal, bukan di atas rata-rata.\n"
     "3. Tambahkan durasi minimal sebelum alarm dikirim, misalnya lima menit, "
     "supaya lonjakan sesaat tidak memicu alarm.\n"
     "4. Tinjau ulang setiap bulan berdasarkan alarm yang ternyata tidak "
     "perlu ditindak.\n\n"
     "Hasil yang diharapkan\n\nJumlah alarm turun, dan setiap alarm yang "
     "muncul memang butuh tindakan.",
     "zabbix, alarm, threshold, monitoring", 231, 27, 1),

    ("Permintaan Fitur Aplikasi", "Cara mengajukan permintaan fitur baru",
     "Isi yang perlu ada agar permintaan bisa dinilai dan dijadwalkan.",
     "Tuliskan tiga hal ini\n\n"
     "Pertama, masalah yang ingin diselesaikan — bukan solusi yang "
     "dibayangkan. Kedua, seberapa sering masalah itu terjadi dan siapa yang "
     "terdampak. Ketiga, cara kerja saat ini beserta waktu yang dihabiskan.\n\n"
     "Alur permintaan\n\n"
     "Buat tiket dengan tipe Feature Request. Nomor tiket otomatis berawalan "
     "FR sehingga mudah dipisahkan dari tiket gangguan. Permintaan ditinjau "
     "setiap awal bulan dan diurutkan berdasarkan dampak.\n\n"
     "Yang membuat permintaan cepat disetujui\n\n"
     "Angka. Permintaan yang menyebutkan berapa jam kerja yang bisa dihemat "
     "per minggu jauh lebih mudah dinilai daripada yang tidak.",
     "feature-request, prosedur", 143, 21, 0),

    ("Integrasi & Otomasi", "Pembuatan tiket otomatis dari alarm NMS",
     "Rancangan alur alarm severity tinggi menjadi tiket tanpa input manual.",
     "Tujuan\n\nMengurangi jeda antara alarm muncul dan tiket dibuat, serta "
     "menghilangkan salah ketik kode site.\n\n"
     "Rancangan alur\n\n"
     "Alarm dengan severity Disaster atau High ditarik berkala dari NMS. "
     "Setiap alarm dipetakan ke kode site, lalu dibuat tiket bertipe Problem "
     "dengan prioritas mengikuti severity. Alarm yang sudah punya tiket "
     "terbuka untuk site sama tidak membuat tiket baru, melainkan menambah "
     "catatan pada tiket yang ada.\n\n"
     "Yang perlu dijaga\n\n"
     "Pemetaan kode site harus satu sumber. Kalau kode di NMS berbeda dengan "
     "yang dipakai tim, sediakan kolom alias supaya tidak muncul dua "
     "kebenaran.",
     "otomasi, integrasi, nms, alarm", 167, 18, 1),

    ("Pelaporan", "Membaca laporan harian dan bulanan",
     "Arti setiap sheet dan angka pada berkas Excel hasil ekspor.",
     "Isi berkas\n\n"
     "Sheet Rekap memuat jumlah dan persentase tiket per status beserta "
     "rincian per tipe. Sheet Detail Tiket memuat satu baris per tiket "
     "lengkap dengan waktu open, close, durasi, dan alasan penutupan. Sheet "
     "Performa Agent memuat sebaran tiket dan rasio penyelesaian per agent.\n\n"
     "Angka yang sering ditanyakan\n\n"
     "Durasi dihitung dari waktu open sampai waktu close. Tiket yang belum "
     "ditutup dihitung sampai saat laporan ditarik, jadi angkanya akan "
     "berubah kalau laporan ditarik ulang di hari berbeda.\n\n"
     "Rasio penyelesaian adalah jumlah tiket Close dibagi total tiket yang "
     "ditugaskan pada agent tersebut dalam rentang laporan.",
     "laporan, excel, ekspor, sla", 209, 23, 1),
]


class Command(BaseCommand):
    help = "Mengisi database dengan data peragaan (agent, tiket, artikel, log)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Hapus data tiket, artikel, log, dan notifikasi lebih dulu.",
        )
        parser.add_argument(
            "--tickets", type=int, default=210,
            help="Jumlah tiket yang dibuat (default 210).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(SEED)

        if options["reset"]:
            TicketReply.objects.all().delete()
            Ticket.objects.all().delete()
            Article.objects.all().delete()
            Folder.objects.all().delete()
            ActivityLog.objects.all().delete()
            Notification.objects.all().delete()
            self.stdout.write(self.style.WARNING("Data lama dihapus."))

        users = self._seed_users()
        folders = self._seed_folders()
        self._seed_articles(folders, users)
        tickets = self._seed_tickets(users, options["tickets"])
        self._seed_notifications(tickets, users)

        self.stdout.write(self.style.SUCCESS(
            f"Selesai — {len(users)} agent, {len(tickets)} tiket, "
            f"{Article.objects.count()} artikel, "
            f"{ActivityLog.objects.count()} baris log."
        ))
        self.stdout.write("Login demo: rizky.pratama / demo1234 (administrator)")

    # ── Bagian-bagian seed ────────────────────────────────────────────────

    def _seed_users(self):
        users = []
        for username, first, last, position, shift, dept, is_admin in AGENTS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@initech.co.id",
                    "position": position,
                    "shift": shift,
                    "department": dept,
                    "nik": f"INI{random.randint(10000, 99999)}",
                    "phone": f"08{random.randint(1000000000, 1999999999)}",
                    "is_staff": is_admin,
                    "is_superuser": is_admin,
                },
            )
            if created:
                user.set_password("demo1234")
                user.save()
            users.append(user)
        return users

    def _seed_folders(self):
        folders = {}
        for category, name, description, order in FOLDERS:
            folder, _ = Folder.objects.get_or_create(
                name=name,
                defaults={"category": category, "description": description,
                          "order": order},
            )
            folders[name] = folder
        return folders

    def _seed_articles(self, folders, users):
        now = timezone.now()
        for i, (folder_name, title, summary, body, tags, views, helpful, bad) in enumerate(ARTICLES):
            article, created = Article.objects.get_or_create(
                title=title,
                defaults={
                    "folder": folders[folder_name],
                    "summary": summary,
                    "body": body,
                    "tags": tags,
                    "views": views,
                    "helpful": helpful,
                    "not_helpful": bad,
                    "author": users[i % len(users)],
                    "status": Article.Status.PUBLISHED,
                },
            )
            if created:
                written = now - timedelta(days=random.randint(3, 90),
                                          hours=random.randint(0, 23))
                Article.objects.filter(pk=article.pk).update(
                    created_at=written, updated_at=written)
                ActivityLog.objects.create(
                    actor=article.author,
                    actor_label=article.author.display_name,
                    verb=ActivityLog.Verb.ARTICLE_CREATE,
                    target_label=article.category_label,
                    subject=article.title,
                    status="Terbit",
                    pic=article.author.display_name,
                    url=article.get_absolute_url(),
                    created_at=written,
                )

    def _seed_tickets(self, users, count):
        now = timezone.now()
        tickets = []

        for i in range(count):
            # Sebaran waktu condong ke belakang tetapi tetap menyisakan volume
            # pada 30 hari sebelumnya — kalau tidak, angka pembanding periode
            # di dashboard jadi tidak masuk akal.
            age_days = random.choice(
                [random.randint(0, 6)] * 2
                + [random.randint(7, 29)] * 3
                + [random.randint(30, 59)] * 3
                + [random.randint(60, 89)] * 2
            )
            opened = now - timedelta(days=age_days,
                                     hours=random.randint(0, 23),
                                     minutes=random.choice([0, 12, 25, 38, 47]))

            is_problem = random.random() < 0.76
            pool = PROBLEM_SUBJECTS if is_problem else FEATURE_SUBJECTS
            template, priority, description = random.choice(pool)
            site = random.choice(SITE_CODES)

            ticket_type = Ticket.Type.PROBLEM if is_problem else Ticket.Type.FEATURE
            assignee = random.choice(users)

            # Tiket lama lebih besar kemungkinannya sudah ditutup
            if age_days > 20:
                status = random.choices(
                    [Ticket.Status.CLOSED, Ticket.Status.OUTSTANDING, Ticket.Status.OPEN],
                    weights=[88, 9, 3])[0]
            elif age_days > 6:
                status = random.choices(
                    [Ticket.Status.CLOSED, Ticket.Status.OUTSTANDING, Ticket.Status.OPEN],
                    weights=[62, 26, 12])[0]
            else:
                status = random.choices(
                    [Ticket.Status.CLOSED, Ticket.Status.OUTSTANDING, Ticket.Status.OPEN],
                    weights=[30, 34, 36])[0]

            closed_at = close_reason = None
            if status == Ticket.Status.CLOSED:
                resolve_hours = random.choice([1, 2, 3, 4, 6, 9, 14, 22, 36, 52])
                closed_at = min(opened + timedelta(hours=resolve_hours,
                                                   minutes=random.randint(0, 59)), now)
                category, detail = random.choice(CLOSE_REASONS)
                close_reason = f"{category} — {detail}"

            ticket = Ticket(
                ticket_type=ticket_type,
                subject=template.format(site=site),
                description=description.format(site=site),
                status=status,
                priority=priority if is_problem else random.choice(
                    [Ticket.Priority.LOW, Ticket.Priority.MEDIUM, Ticket.Priority.HIGH]),
                source=random.choices(
                    [Ticket.Source.NMS, Ticket.Source.EMAIL, Ticket.Source.PHONE,
                     Ticket.Source.PORTAL, Ticket.Source.CHAT],
                    weights=[40, 22, 16, 16, 6])[0],
                requester_name=random.choice(REQUESTERS),
                requester_email=f"{random.choice(REQUESTERS).split()[0].lower()}@initech.co.id",
                company=random.choice(COMPANIES),
                site_code=site if is_problem else "",
                assignee=assignee,
                group=random.choice(["NOC", "Field Engineer", "Network Engineer",
                                     "Helpdesk", "Product"]),
                opened_at=opened,
                due_at=opened + timedelta(hours=random.choice([4, 8, 24, 48])),
                first_response_at=opened + timedelta(minutes=random.randint(4, 90)),
                closed_at=closed_at,
                close_reason=close_reason or "",
                tags=", ".join(random.sample(
                    ["link-down", "fiber", "hardware", "sla", "eskalasi", "vendor",
                     "monitoring", "kapasitas", "prioritas"], k=random.randint(1, 3))),
                created_by=random.choice(users),
            )
            ticket.number = Ticket.next_number(ticket_type, opened)
            # next_number membaca dari database; nomor yang belum tersimpan
            # dalam batch ini ditambahkan manual supaya tidak bentrok.
            while Ticket.objects.filter(number=ticket.number).exists() or \
                    any(t.number == ticket.number for t in tickets):
                prefix, seq = ticket.number[:4], int(ticket.number[4:])
                ticket.number = f"{prefix}{seq + 1:04d}"
            ticket.save()
            Ticket.objects.filter(pk=ticket.pk).update(created_at=opened)
            tickets.append(ticket)

            self._seed_conversation(ticket, users, status)
            self._seed_ticket_logs(ticket, users)

        return tickets

    def _seed_conversation(self, ticket, users, status):
        reply_count = {
            Ticket.Status.OPEN: random.randint(0, 1),
            Ticket.Status.OUTSTANDING: random.randint(1, 3),
            Ticket.Status.CLOSED: random.randint(2, 4),
        }[status]

        cursor = ticket.opened_at
        for _ in range(reply_count):
            cursor += timedelta(minutes=random.randint(20, 300))
            if ticket.closed_at and cursor > ticket.closed_at:
                break
            is_private = random.random() < 0.25
            reply = TicketReply.objects.create(
                ticket=ticket,
                author=ticket.assignee,
                author_label=ticket.assignee.display_name,
                body=random.choice(NOTES if is_private else REPLIES),
                is_private=is_private,
            )
            TicketReply.objects.filter(pk=reply.pk).update(
                created_at=cursor, updated_at=cursor)

    def _seed_ticket_logs(self, ticket, users):
        creator = ticket.created_by or ticket.assignee
        ActivityLog.objects.create(
            actor=creator, actor_label=creator.display_name,
            verb=ActivityLog.Verb.TICKET_CREATE,
            target_label=ticket.number, subject=ticket.subject,
            status="Open",
            pic=ticket.assignee.display_name if ticket.assignee else "Belum ditugaskan",
            url=ticket.get_absolute_url(), created_at=ticket.opened_at,
        )
        if ticket.closed_at:
            ActivityLog.objects.create(
                actor=ticket.assignee, actor_label=ticket.assignee.display_name,
                verb=ActivityLog.Verb.TICKET_CLOSE,
                target_label=ticket.number, subject=ticket.subject,
                status="Close", pic=ticket.assignee.display_name,
                reason=ticket.close_reason,
                url=ticket.get_absolute_url(), created_at=ticket.closed_at,
            )

    def _seed_notifications(self, tickets, users):
        recent = sorted(tickets, key=lambda t: t.opened_at, reverse=True)[:14]
        for i, ticket in enumerate(recent):
            if ticket.is_closed:
                title = f"Tiket {ticket.number} ditutup"
                body = f"{ticket.subject[:70]} · oleh {ticket.assignee.display_name}"
                level = Notification.Level.SUCCESS
                when = ticket.closed_at
            else:
                title = f"Tiket baru {ticket.number}"
                body = f"{ticket.subject[:70]} · {ticket.get_priority_display()}"
                level = (Notification.Level.DANGER
                         if ticket.priority == Ticket.Priority.URGENT
                         else Notification.Level.INFO)
                when = ticket.opened_at

            Notification.objects.create(
                title=title, body=body, url=ticket.get_absolute_url(),
                level=level, actor=ticket.assignee,
                is_read=i >= 5,  # lima teratas sengaja dibiarkan belum dibaca
                created_at=when,
            )
