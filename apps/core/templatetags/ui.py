"""Filter & tag kecil untuk kebutuhan tampilan."""

from django import template
from django.utils import timezone

register = template.Library()


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Bangun ulang query string dengan sebagian parameter diganti.

    Dipakai paginasi dan filter supaya pindah halaman tidak menghapus filter
    yang sedang aktif. Nilai `None` menghapus parameter tersebut.

        <a href="?{% qs page=2 %}">
    """
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    # Mengubah filter berarti kembali ke halaman 1 — kecuali halaman memang
    # yang sedang diganti.
    if "page" not in kwargs:
        params.pop("page", None)
    return params.urlencode()


@register.simple_tag(takes_context=True)
def qs_toggle(context, key, value):
    """Tambah/hapus satu nilai pada parameter yang boleh berisi banyak nilai."""
    params = context["request"].GET.copy()
    current = params.getlist(key)
    value = str(value)
    if value in current:
        current.remove(value)
    else:
        current.append(value)
    params.setlist(key, current)
    params.pop("page", None)
    return params.urlencode()


@register.filter
def avatar_color(value):
    """Kelas warna avatar, diturunkan dari nama.

    Dihitung dari nama (bukan dari nomor baris) supaya satu orang selalu
    mendapat warna yang sama di halaman mana pun.
    """
    text = str(value or "?")
    return f"avatar--c{(sum(ord(c) for c in text) % 6) + 1}"


@register.filter
def initials(value):
    parts = [p for p in str(value or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "??"


@register.filter
def relative_time(value):
    """Waktu relatif singkat: '5 mnt', '3 jam', '2 hari', lalu tanggal."""
    if not value:
        return "—"
    delta = timezone.now() - value
    seconds = int(delta.total_seconds())

    if seconds < 0:
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return timezone.localtime(value).strftime("%d/%m/%Y")


@register.filter
def get_item(mapping, key):
    """Ambil nilai dict di template: {{ counts|get_item:'open' }}"""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def in_list(value, arg):
    """Cek keanggotaan untuk daftar filter tercentang."""
    return str(value) in [str(v) for v in (arg or [])]
