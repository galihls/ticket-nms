"""Model pengguna.

Model User custom dipasang sejak awal walaupun field tambahannya masih
sedikit: mengganti AUTH_USER_MODEL setelah tabel termigrasi jauh lebih repot
daripada menyiapkannya di depan.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Shift(models.TextChoices):
        NON_SHIFT = "non_shift", "Non-Shift"
        PAGI = "pagi", "Pagi"
        SIANG = "siang", "Siang"
        MALAM = "malam", "Malam"

    nik = models.CharField(
        "NIK / NIP", max_length=32, blank=True,
        help_text="Nomor induk karyawan. Boleh dikosongkan.",
    )
    phone = models.CharField("no. telepon", max_length=32, blank=True)
    department = models.CharField("departemen", max_length=64, blank=True)
    position = models.CharField("jabatan", max_length=64, blank=True)
    shift = models.CharField(
        "shift", max_length=16, choices=Shift.choices, default=Shift.NON_SHIFT,
    )

    class Meta:
        verbose_name = "pengguna"
        verbose_name_plural = "pengguna"
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        full = self.get_full_name().strip()
        return full or self.username

    @property
    def initials(self):
        """Dua huruf untuk avatar di pojok kanan atas."""
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts[:2]).upper()
        return self.username[:2].upper()
