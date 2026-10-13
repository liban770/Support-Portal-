// ATU Support Portal — small progressive-enhancement helpers (no framework needed).
(function () {
  // Mobile sidebar
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  function toggleSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("-translate-x-full", !open);
    overlay && overlay.classList.toggle("hidden", !open);
    document.body.classList.toggle("overflow-hidden", open);
  }
  document.querySelectorAll("[data-sidebar-open]").forEach((b) => b.addEventListener("click", () => toggleSidebar(true)));
  document.querySelectorAll("[data-sidebar-close]").forEach((b) => b.addEventListener("click", () => toggleSidebar(false)));

  // Dropdown menus: <div data-dropdown><button data-dropdown-toggle>…</button><div data-dropdown-menu class="hidden">…</div></div>
  document.addEventListener("click", (e) => {
    const toggle = e.target.closest("[data-dropdown-toggle]");
    document.querySelectorAll("[data-dropdown-menu]").forEach((menu) => {
      if (!toggle || !toggle.parentElement.contains(menu)) menu.classList.add("hidden");
    });
    if (toggle) {
      const menu = toggle.parentElement.querySelector("[data-dropdown-menu]");
      menu && menu.classList.toggle("hidden");
    }
  });

  // Auto-dismiss toasts
  document.querySelectorAll("[data-toast]").forEach((t, i) => {
    const close = () => { t.style.transition = "opacity .3s, transform .3s"; t.style.opacity = "0"; t.style.transform = "translateY(-6px)"; setTimeout(() => t.remove(), 300); };
    t.querySelector("[data-toast-close]")?.addEventListener("click", close);
    if (!t.dataset.sticky) setTimeout(close, 6000 + i * 600);
  });

  // Tabs inside a page: buttons with data-tab-target="#id", panels with data-tab-panel
  document.querySelectorAll("[data-tabs]").forEach((group) => {
    const buttons = group.querySelectorAll("[data-tab-target]");
    buttons.forEach((btn) => btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("tab-active"));
      btn.classList.add("tab-active");
      document.querySelectorAll(group.dataset.tabs).forEach((p) => p.classList.add("hidden"));
      document.querySelector(btn.dataset.tabTarget)?.classList.remove("hidden");
    }));
  });

  // Character counters: <textarea data-maxlength="120"> + <span data-counter-for="id">
  document.querySelectorAll("[data-counter-for]").forEach((c) => {
    const el = document.getElementById(c.dataset.counterFor);
    if (!el) return;
    const max = el.getAttribute("maxlength");
    const update = () => (c.textContent = `${el.value.length}${max ? " / " + max : ""}`);
    el.addEventListener("input", update); update();
  });

  // File inputs: show the selected file names in a list
  document.querySelectorAll("[data-file-list]").forEach((list) => {
    const input = document.getElementById(list.dataset.fileList);
    if (!input) return;
    const zone = list.closest("[data-dropzone]");
    const render = () => {
      list.innerHTML = "";
      Array.from(input.files).forEach((f) => {
        const li = document.createElement("li");
        li.className = "flex items-center gap-3 p-3 rounded-xl bg-white border border-line";
        const size = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(f.size / 1024)) + " KB";
        li.innerHTML = `<span class="w-9 h-9 rounded-lg bg-primary-fixed text-primary-container flex items-center justify-center"><span class="material-symbols-outlined text-[20px]">description</span></span>
          <span class="flex-1 min-w-0"><span class="block font-label-md text-label-md truncate"></span><span class="block font-caption text-caption text-secondary">${size} · Ready to upload</span></span>`;
        li.querySelector(".truncate").textContent = f.name;
        list.appendChild(li);
      });
    };
    input.addEventListener("change", render);
    if (zone) {
      ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("ring-2", "ring-primary-container/30"); }));
      ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("ring-2", "ring-primary-container/30"); }));
      zone.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; render(); } });
    }
  });

  // Absence duration helper
  const start = document.getElementById("id_start_date");
  const end = document.getElementById("id_end_date");
  const out = document.getElementById("duration-days");
  if (start && end && out) {
    const calc = () => {
      if (!start.value || !end.value) { out.textContent = "Select dates"; return; }
      const d = Math.round((new Date(end.value) - new Date(start.value)) / 86400000) + 1;
      out.textContent = d > 0 ? `${d} day${d === 1 ? "" : "s"}` : "Invalid range";
    };
    start.addEventListener("change", calc); end.addEventListener("change", calc); calc();
  }

  // Late class: disable actual start when "did not start" is ticked
  const dns = document.getElementById("id_class_did_not_start");
  const actual = document.getElementById("id_actual_start");
  if (dns && actual) {
    const sync = () => { actual.disabled = dns.checked; if (dns.checked) actual.value = ""; };
    dns.addEventListener("change", sync); sync();
  }

  // Confirm dangerous actions: <form data-confirm="Are you sure?">
  document.querySelectorAll("form[data-confirm]").forEach((f) =>
    f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); })
  );

  // Prevent double submit
  document.querySelectorAll("form").forEach((f) => f.addEventListener("submit", () => {
    setTimeout(() => f.querySelectorAll("button[type=submit]").forEach((b) => (b.disabled = true)), 0);
  }));

  // Password visibility toggle
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => btn.addEventListener("click", () => {
    const input = document.getElementById(btn.dataset.togglePassword);
    if (!input) return;
    input.type = input.type === "password" ? "text" : "password";
    btn.querySelector("span").textContent = input.type === "password" ? "visibility" : "visibility_off";
  }));
})();
