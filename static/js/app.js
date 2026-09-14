/* Perilaku UI dasar Ticketing NMS.
   Ditulis tanpa framework — hanya beberapa interaksi kecil yang memang perlu.
   Interaksi yang butuh data server nantinya ditangani HTMX. */
(function () {
  "use strict";

  /* Menu samping di layar sempit -------------------------------------- */
  function bindSidebar() {
    var toggle = document.querySelector("[data-nav-toggle]");
    var scrim = document.querySelector("[data-nav-close]");
    if (toggle) {
      toggle.addEventListener("click", function () {
        document.body.classList.toggle("nav-open");
      });
    }
    if (scrim) {
      scrim.addEventListener("click", function () {
        document.body.classList.remove("nav-open");
      });
    }
  }

  /* Menu dropdown (pengguna & notifikasi) ------------------------------ */
  function bindDropdown(wrapSelector, triggerSelector, panelSelector) {
    var wrap = document.querySelector(wrapSelector);
    if (!wrap) return null;

    var trigger = wrap.querySelector(triggerSelector);
    var panel = wrap.querySelector(panelSelector);
    if (!trigger || !panel) return null;

    function close() {
      panel.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      var willOpen = panel.hidden;
      // Menutup panel lain dulu supaya tidak ada dua yang terbuka bersamaan
      document.querySelectorAll("[data-usermenu-panel], [data-notif-panel]")
        .forEach(function (other) {
          if (other !== panel) other.hidden = true;
        });
      panel.hidden = !willOpen;
      trigger.setAttribute("aria-expanded", String(willOpen));
    });

    document.addEventListener("click", function (e) {
      if (!panel.hidden && !wrap.contains(e.target)) close();
    });

    return close;
  }

  function bindMenus() {
    var closers = [
      bindDropdown("[data-usermenu]", "[data-usermenu-trigger]", "[data-usermenu-panel]"),
      bindDropdown("[data-notifmenu]", "[data-notif-trigger]", "[data-notif-panel]"),
    ].filter(Boolean);

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      closers.forEach(function (close) { close(); });
      document.body.classList.remove("nav-open");
    });
  }

  /* Notifikasi: tombol tutup + hilang sendiri -------------------------- */
  function bindToasts() {
    document.querySelectorAll("[data-dismiss]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var box = btn.closest(".alert");
        if (box) box.remove();
      });
    });

    document.querySelectorAll("[data-autodismiss]").forEach(function (box) {
      // Pesan error dibiarkan sampai ditutup manual; sisanya hilang otomatis.
      if (box.classList.contains("alert--error")) return;
      setTimeout(function () {
        box.style.transition = "opacity .25s ease";
        box.style.opacity = "0";
        setTimeout(function () { box.remove(); }, 260);
      }, 5000);
    });
  }

  /* Cegah kiriman form ganda karena klik dobel ------------------------- */
  function bindSubmitGuard() {
    document.querySelectorAll("form[data-guard]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var btn = form.querySelector('button[type="submit"]');
        if (btn) {
          btn.disabled = true;
          btn.dataset.label = btn.textContent;
          btn.textContent = "Menyimpan…";
          // Tombol dipulihkan kalau peramban mengembalikan halaman dari cache
          // (tombol Back), supaya form tidak terkunci permanen.
          setTimeout(function () {
            btn.disabled = false;
            btn.textContent = btn.dataset.label;
          }, 8000);
        }
      });
    });
  }

  /* Modal -------------------------------------------------------------- */
  function bindModals() {
    var lastFocus = null;

    function open(modal) {
      lastFocus = document.activeElement;
      modal.hidden = false;
      document.body.style.overflow = "hidden";
      var first = modal.querySelector("select, input, textarea, button");
      if (first) first.focus();
    }

    function close(modal) {
      modal.hidden = true;
      document.body.style.overflow = "";
      if (lastFocus) lastFocus.focus();
    }

    document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var modal = document.getElementById(btn.dataset.modalOpen);
        if (modal) open(modal);
      });
    });

    document.querySelectorAll(".modal").forEach(function (modal) {
      modal.querySelectorAll("[data-modal-close]").forEach(function (btn) {
        btn.addEventListener("click", function () { close(modal); });
      });
      // Klik pada latar gelap menutup, klik di dalam kotak tidak
      modal.addEventListener("click", function (e) {
        if (e.target === modal) close(modal);
      });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      document.querySelectorAll(".modal:not([hidden])").forEach(close);
    });
  }

  /* Bagian yang bisa dibuka-tutup (form login lokal) ------------------- */
  function bindCollapse() {
    document.querySelectorAll("[data-collapse-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = document.getElementById(btn.dataset.collapseToggle);
        if (!target) return;
        target.hidden = !target.hidden;
        if (!target.hidden) {
          var first = target.querySelector("input, select, textarea");
          if (first) first.focus();
        }
      });
    });
  }

  /* Pilih banyak tiket pada daftar ------------------------------------- */
  function bindBulkSelect() {
    var all = document.querySelector("[data-check-all]");
    var rows = document.querySelectorAll("[data-row-check]");
    var bar = document.querySelector("[data-bulkbar]");
    if (!rows.length || !bar) return;

    var counter = bar.querySelector("[data-bulk-count]");

    function refresh() {
      var checked = 0;
      rows.forEach(function (row) { if (row.checked) checked += 1; });
      bar.hidden = checked === 0;
      if (counter) counter.textContent = String(checked);
      if (all) {
        all.checked = checked === rows.length && checked > 0;
        all.indeterminate = checked > 0 && checked < rows.length;
      }
    }

    if (all) {
      all.addEventListener("change", function () {
        rows.forEach(function (row) { row.checked = all.checked; });
        refresh();
      });
    }
    rows.forEach(function (row) { row.addEventListener("change", refresh); });

    var clear = bar.querySelector("[data-bulk-clear]");
    if (clear) {
      clear.addEventListener("click", function () {
        rows.forEach(function (row) { row.checked = false; });
        if (all) all.checked = false;
        refresh();
      });
    }

    refresh();
  }

  function init() {
    bindSidebar();
    bindMenus();
    bindToasts();
    bindSubmitGuard();
    bindModals();
    bindCollapse();
    bindBulkSelect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
