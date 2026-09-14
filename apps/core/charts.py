"""Perhitungan geometri chart.

Chart digambar sebagai SVG inline, tanpa pustaka JavaScript: datanya kecil dan
tetap, jadi menambah 100 KB library hanya untuk satu donat tidak sepadan.
Geometri dihitung di Python supaya template tinggal mencetak angka.

Palet status sudah lolos pemeriksaan keterbacaan buta warna (protan/deutan/
tritan) terhadap latar putih. Jarak antar-segmen 2px dan label langsung pada
legenda adalah bagian dari syarat itu — identitas segmen tidak pernah hanya
mengandalkan warna.
"""

import math
from dataclasses import dataclass, field

# Warna status — terkunci pada arti, bukan pada urutan data.
STATUS_COLORS = {
    "open": "#175CD3",
    "outstanding": "#DC6803",
    "closed": "#067647",
}


def num(value):
    """Angka geometri sebagai teks dengan titik desimal.

    LANGUAGE_CODE "id" membuat Django melokalkan float di template menjadi
    koma ("80,0"). Itu sah untuk angka yang dibaca manusia, tetapi merusak
    atribut SVG dan nilai CSS. Semua angka geometri karena itu dikeluarkan
    sebagai string dari sini; persentase yang tampil di layar tetap float
    supaya justru ikut dilokalkan.
    """
    rounded = round(float(value), 2)
    text = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return text or "0"


@dataclass
class Segment:
    key: str
    label: str
    value: int
    color: str
    percent: float = 0.0
    # Geometri sebagai teks — lihat catatan pada num()
    dash: str = "0"
    gap: str = "0"
    offset: str = "0"


@dataclass
class Donut:
    segments: list = field(default_factory=list)
    total: int = 0
    radius: int = 58
    stroke: int = 20
    size: int = 160

    @property
    def center(self):
        return num(self.size / 2)

    @property
    def circumference(self):
        return 2 * math.pi * self.radius

    @property
    def is_empty(self):
        return self.total == 0


def donut(rows, radius=58, stroke=20, size=160, gap_px=2):
    """Bangun donat dari [(key, label, value)].

    `gap_px` adalah celah berwarna permukaan antar segmen — pemisah yang
    dipakai, bukan garis tepi di sekeliling segmen.
    """
    total = sum(max(0, r[2]) for r in rows)
    chart = Donut(total=total, radius=radius, stroke=stroke, size=size)
    circumference = chart.circumference

    cumulative = 0.0
    for key, label, value in rows:
        value = max(0, value)
        fraction = (value / total) if total else 0.0
        percent = round(fraction * 100, 1)

        arc = fraction * circumference
        # Segmen bernilai 0 tidak digambar; segmen tunggal (100%) tidak diberi
        # celah, kalau tidak lingkarannya terlihat retak tanpa alasan.
        if value == 0:
            dash = 0.0
        elif fraction >= 0.999:
            dash = circumference
        else:
            dash = max(arc - gap_px, 0.5)

        chart.segments.append(Segment(
            key=key,
            label=label,
            value=value,
            color=STATUS_COLORS.get(key, "#667085"),
            percent=percent,
            dash=num(dash),
            gap=num(circumference - dash),
            offset=num(-(cumulative * circumference + gap_px / 2)),
        ))
        cumulative += fraction

    return chart


def stacked_bar(rows, total=None):
    """Persentase lebar untuk bar bertumpuk performa agent.

    Mengembalikan daftar potongan dengan lebar persen; template memakai
    `width: {{ part.width }}%` dan celah 2px antar potongan.
    """
    total = total if total is not None else sum(max(0, r[2]) for r in rows)
    parts = []
    for key, label, value in rows:
        value = max(0, value)
        parts.append({
            "key": key,
            "label": label,
            "value": value,
            "color": STATUS_COLORS.get(key, "#667085"),
            "width": num(value * 100 / total) if total else "0",
        })
    return parts
