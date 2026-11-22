// Advanced Reports — public pages and dashboard. No build step: plain DOM, one file.
// Every piece of text from the server is placed with textContent, never as HTML.
(() => {
  "use strict";
  const TEXT = window.AR_TEXT;
  const root = document.getElementById("root");
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* private mode */ } },
  };
  let lang = store.get("ar_lang") || (navigator.language || "en").slice(0, 2);
  if (!TEXT[lang]) lang = "en";
  const t = (key, ...args) => {
    const value = TEXT[lang][key] ?? TEXT.en[key] ?? key;
    return typeof value === "function" ? value(...args) : value;
  };

  // ── Small DOM helpers ───────────────────────────────────────────────────────
  function h(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (key === "style") node.style.cssText = value;
      else if (key in node && key !== "list" && typeof value !== "string") node[key] = value;
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) node.append(kid);
    return node;
  }
  const ICONS = {
    home: '<path d="M4 11.5 12 5l8 6.5"/><path d="M6 10v9.5a.5.5 0 0 0 .5.5H10v-5h4v5h3.5a.5.5 0 0 0 .5-.5V10"/>',
    files: '<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10A.5.5 0 0 1 7 20z"/><path d="M13.5 3.5V8H18M10 12h5M10 15.5h5"/>',
    reports: '<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/>',
    history: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6 6l1.6 1.6M16.4 16.4 18 18M18 6l-1.6 1.6M7.6 16.4 6 18"/>',
    out: '<path d="M14 4h4.5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H14"/><path d="M10 16l-4-4 4-4M6 12h9"/>',
    site: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/>',
    moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>',
    play: '<path d="M8 5.5v13l10.5-6.5z"/>',
    people: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><circle cx="17" cy="9" r="2.4"/><path d="M16 14.2a4.5 4.5 0 0 1 5 4.8"/>',
    bus: '<rect x="4" y="5" width="16" height="11" rx="2.5"/><path d="M4 11h16M8 19v-3M16 19v-3"/>',
    star: '<path d="m12 4 2.4 5 5.4.7-4 3.8 1 5.4-4.8-2.6L7.2 19l1-5.4-4-3.8 5.4-.7z"/>',
    globe: '<path d="M4 6h9M8.5 4v2c0 4-2 7-5 8.500M6 10c1 2.500 3 4 6 5"/><path d="m13 20 3.500-8 3.500 8M14.300 17h4.400"/>',
    brush: '<path d="M14 5l5 5-8.500 8.500a3.500 3.500 0 0 1-5-5z"/><path d="M4 20c1.500 0 2.500-.5 3-1.500"/>',
    lock: '<rect x="5.500" y="10.500" width="13" height="9" rx="2"/><path d="M8.500 10.500V8a3.500 3.500 0 0 1 7 0v2.500"/>',
    folder: '<path d="M4 18.500V6a1 1 0 0 1 1-1h4l2 2.500h8a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/>',
    check: '<path d="m5 12.500 4.500 4.500L19 7.500"/>',
    minus: '<path d="M6 12h12"/>',
    open: '<path d="M14 5h5v5M19 5l-8 8"/><path d="M18 14v4.500a.5.5 0 0 1-.5.5h-12a.5.5 0 0 1-.5-.5v-12a.5.5 0 0 1 .5-.5H10"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    clock: '<circle cx="12" cy="12" r="8.500"/><path d="M12 7.500V12l3 2"/>',
    calendar: '<rect x="4" y="5.500" width="16" height="14.500" rx="2.500"/><path d="M4 10h16M8.500 3.500v4M15.500 3.500v4"/>',
    help: '<circle cx="12" cy="12" r="8.500"/><path d="M9.700 9.500a2.400 2.400 0 1 1 3.600 2.100c-.8.500-1.300 1-1.300 2M12 16.700v.1"/>',
    mail: '<rect x="3.500" y="5.500" width="17" height="13" rx="2.500"/><path d="m4.500 7.500 7.500 6 7.500-6"/>',
    phone: '<path d="M6.500 4h3l1.500 4-2 1.500a11 11 0 0 0 5.500 5.500l1.500-2 4 1.500v3a1.500 1.500 0 0 1-1.500 1.500A15.500 15.500 0 0 1 5 5.500 1.500 1.500 0 0 1 6.500 4z"/>',
    alert: '<path d="M12 4.500 3.500 19h17z"/><path d="M12 10v4M12 16.700v.1"/>',
    back: '<path d="M4 12a8 8 0 1 0 2.500-5.800"/><path d="M4 4.500v4h4"/>',
    eye: '<path d="M2.500 12S6 5.500 12 5.500 21.500 12 21.500 12 18 18.500 12 18.500 2.500 12 2.500 12z"/><circle cx="12" cy="12" r="2.700"/>',
    pencil: '<path d="M14 5l5 5-9.500 9.500H4.500v-5z"/>',
    trash: '<path d="M5 7h14M9.500 7V4.500h5V7M7 7l.8 12.500h8.400L17 7"/>',
  };
  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "icon");
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = ICONS[name];          // constants above, never data
    return svg;
  }
  // The product mark: a small chapel. (Mannabyte Labs appears only as the maker's credit.)
  function mark() {
    const wrap = document.createElement("span");
    wrap.innerHTML = '<svg viewBox="0 0 48 48" aria-hidden="true"><rect width="48" height="48" rx="13" fill="var(--accent)"/>' +
      '<g fill="var(--accent-fg)"><rect x="22.900" y="6.500" width="2.200" height="8" rx=".6"/><rect x="20.300" y="8.800" width="7.400" height="2.200" rx=".6"/>' +
      '<path d="M24 13.500 30 21v4h-12v-4z"/><path d="M11 38V28.500L24 22l13 6.500V38z"/></g>' +
      '<path d="M21.300 38v-6a2.700 2.700 0 0 1 5.400 0v6z" fill="var(--gold)"/><circle cx="24" cy="19.800" r="1.500" fill="var(--gold)"/></svg>';
    return wrap.firstChild;
  }
  const brandmark = () => { const svg = mark(); svg.setAttribute("class", "brandmark"); return svg; };
  const brand = (href) => h("a", { class: "brand", href, "aria-label": `${t("product")}, Mannabyte Labs` }, mark(),
    h("span", {}, h("span", { class: "name", text: t("product") }), h("span", { class: "by" }, t("by") + " ", h("b", { text: "mannabyte" }), " labs")));

  // The backdrop: soft hills in the product's greens, with a small church and a few trees
  // on the far ridge, drawn as part of the landscape (same tones as the hills, windows lit
  // at night). One SVG at a fixed shape, so nothing stretches.
  function scene({ orb = true } = {}) {
    const box = h("div", { class: "scene sky", "aria-hidden": "true" });
    for (let i = 0; i < 26; i++) {
      box.append(h("span", { class: "star", style: `left:${(i * 37) % 100}%;top:${(i * 53) % 55}%;--dur:${2.5 + (i % 5)}s;--delay:${(i % 7) * 0.4}s` }));
    }
    if (orb) box.append(h("div", { class: "orb" }));
    const hills = document.createElement("div");
    hills.innerHTML = '<svg class="hills" viewBox="0 0 1440 320">' +
      '<g transform="translate(168 3)"><g fill="var(--ridge)">' +
        '<ellipse cx="1052" cy="112" rx="15" ry="20"/><ellipse cx="1076" cy="116" rx="11" ry="15"/><ellipse cx="1212" cy="100" rx="13" ry="18"/>' +
        '<ellipse cx="1236" cy="103" rx="9" ry="13"/><ellipse cx="1262" cy="104" rx="14" ry="19"/>' +
        '<path d="M1118 76h3v-9h-5v-3h5v-6h3v6h5v3h-5v9h3l9 24v26h-27v-26z"/>' +
        '<path d="M1132 108l34-20 34 20v22h-68z"/>' +
      '</g>' +
      '<g fill="var(--ridge-light)" opacity=".9"><rect x="1121" y="106" width="5" height="9" rx="2.500"/><rect x="1152" y="110" width="5" height="10" rx="2.500"/>' +
        '<rect x="1164" y="110" width="5" height="10" rx="2.500"/><rect x="1176" y="110" width="5" height="10" rx="2.500"/></g></g>' +
      '<path d="M0 190C240 130 480 170 720 150S1200 90 1440 140V320H0Z" fill="var(--hill-far)"/>' +
      '<path d="M0 236C280 176 520 240 780 204S1220 176 1440 222V320H0Z" fill="var(--hill-mid)"/>' +
      '<path d="M0 280C300 244 620 292 900 262S1300 252 1440 272V320H0Z" fill="var(--hill-near)"/>' +
      '<path d="M0 306C360 290 960 312 1440 296V320H0Z" fill="var(--bg)"/></svg>';
    box.append(hills.firstChild);
    return box;
  }

  // ── State and server calls ──────────────────────────────────────────────────
  const state = { me: null, config: null, reports: [], runs: [], details: {}, loaded: false, events: null,
    files: { runId: null, q: "", selected: null }, wizard: null, historySel: null, settingsTab: "church", timer: null };

  async function api(path, options = {}) {
    const init = { method: options.method || "GET", headers: {}, credentials: "same-origin" };
    if (init.method !== "GET") init.headers["X-AR-CSRF"] = "1";
    if (options.body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); }
    const response = await fetch(path, init);
    if (options.blob && response.ok) return response.blob();
    let data = null;
    try { data = await response.json(); } catch (e) { /* no body */ }
    if (!response.ok) {
      const error = new Error((data && typeof data.detail === "string" && data.detail) || t("err_generic"));
      error.status = response.status;
      throw error;
    }
    return data;
  }
  const isDone = (run) => !["queued", "running"].includes(run.status);
  const activeRun = () => state.runs.find((run) => !isDone(run));
  // Google Drive: { pill, text, actions } for the connection, shared by Overview and Settings.
  function googleStatus() {
    const g = state.me.connections.google, can = state.config?.google_drive;
    if (!can && !g) return { pill: h("span", { class: "pill", text: t("coming") }), text: t("c_google_body"), actions: null };
    const ok = g && g.status === "connected";
    const pill = h("span", { class: `pill ${ok ? "ok" : "bad"}`, text: t(ok ? "connected" : g ? "needs_attention" : "not_connected") });
    const text = ok ? t("c_google_on", g.account) : g ? t("c_google_bad", g.account) : t("c_google_off");
    const disconnect = async () => {
      if (!window.confirm(t("c_google_confirm"))) return;
      await api("/api/google/disconnect", { method: "POST" });
      state.me = await api("/api/me"); render();
    };
    const actions = h("div", { class: "row", style: "gap:.5rem;margin-top:.6rem;flex-wrap:wrap" },
      ok ? h("a", { class: "btn secondary", href: `https://drive.google.com/drive/folders/${encodeURIComponent(g.folder_id)}`, target: "_blank", rel: "noopener" }, icon("open"), t("c_google_open"))
        : h("a", { class: "btn primary", href: "/auth/google/login" }, icon("folder"), t(g ? "c_google_reconnect" : "c_google_connect")),
      g ? h("button", { class: "btn ghost", type: "button", onclick: disconnect, text: t("c_google_disconnect") }) : null);
    return { pill, text, actions };
  }
  const goodRuns = () => state.runs.filter((run) => run.status === "succeeded" && run.files > 0);
  async function detail(runId) {
    if (!state.details[runId] || !isDone(state.details[runId])) state.details[runId] = await api(`/api/runs/${encodeURIComponent(runId)}`);
    return state.details[runId];
  }
  async function load() {
    state.config = await api("/api/auth/config");
    try { state.me = await api("/api/me"); } catch (error) { state.me = null; }
    if (state.me) {
      [state.reports, state.runs] = await Promise.all([
        api("/api/modules/checkin_reports").then((r) => r.reports), api("/api/runs").then((r) => r.runs)]);
      const latest = goodRuns()[0];
      if (latest) await detail(latest.id);
    }
    state.loaded = true;
  }
  function poll() {
    clearTimeout(state.timer);
    const running = activeRun();
    if (!running) return;
    state.timer = setTimeout(async () => {
      try {
        const fresh = await api(`/api/runs/${encodeURIComponent(running.id)}`);
        state.details[running.id] = fresh;
        if (isDone(fresh)) {
          state.runs = (await api("/api/runs")).runs;
          const latest = goodRuns()[0];
          if (latest) await detail(latest.id);
          state.files = { runId: null, q: "", selected: null };
          if (!state.wizard) render();
        } else {
          Object.assign(running, { status: fresh.status, progress: fresh.progress, cancelling: fresh.cancelling });
          document.getElementById("progress-card")?.replaceWith(progressCard(running));
        }
      } catch (error) { if (error.status === 401) { state.me = null; go("#/signin"); return; } }
      poll();
    }, 900);
  }
  async function runNow(button) {
    if (button) button.disabled = true;
    try {
      state.runs.unshift(await api("/api/runs", { method: "POST" }));
      if (route().tab !== "overview" && route().tab !== "schedule") go("#/app/overview"); else render();
    } catch (error) { toast(error.message); if (button) button.disabled = false; }
  }
  async function cancelRun(run, button) {
    button.disabled = true;
    try { await api(`/api/runs/${encodeURIComponent(run.id)}/cancel`, { method: "POST" }); run.cancelling = true; toast(t("cancel_sent")); }
    catch (error) { toast(error.message); }
    document.getElementById("progress-card")?.replaceWith(progressCard(run));
  }
  async function saveReports(reports, message = t("saved")) {
    state.reports = (await api("/api/modules/checkin_reports", { method: "PUT", body: { reports } })).reports;
    toast(message);
  }

  // ── Routing, theme, language ────────────────────────────────────────────────
  const TABS = ["overview", "rosters", "reports", "schedule", "help", "settings"];
  const TAB_ICONS = { overview: "home", rosters: "files", reports: "reports", schedule: "calendar", help: "help", settings: "settings" };
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/");
    if (parts[0] === "app") return { page: "app", tab: TABS.includes(parts[1]) ? parts[1] : "overview" };
    if (parts[0] === "signin") return { page: "signin" };
    return { page: "home", anchor: parts[0] };
  }
  const go = (hash) => { if (location.hash === hash) render(); else location.hash = hash; };
  const theme = () => document.documentElement.dataset.theme;
  function toggleTheme() {
    const next = theme() === "evening" ? "morning" : "evening";
    document.documentElement.dataset.theme = next;
    store.set("ar_theme", next);
    render();
  }
  function toggleLang() { lang = lang === "en" ? "es" : "en"; store.set("ar_lang", lang); render(); }
  const themeLabel = () => t(theme() === "evening" ? "theme_to_light" : "theme_to_dark");
  const themeButton = () => h("button", { class: "iconbtn", type: "button", onclick: toggleTheme, "aria-label": themeLabel(), title: themeLabel() },
    icon(theme() === "evening" ? "sun" : "moon"));
  const langButton = () => h("button", { class: "btn ghost", type: "button", onclick: toggleLang }, icon("globe"), t("lang_switch"));
  let toastTimer = null;
  function toast(message) {
    document.querySelectorAll(".toast").forEach((n) => n.remove());
    document.body.append(h("div", { class: "toast", role: "status", text: message }));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => document.querySelectorAll(".toast").forEach((n) => n.remove()), 2600);
  }
  const when = (iso) => iso ? new Date(iso).toLocaleString(lang, { dateStyle: "medium", timeStyle: "short" }) : "";
  const clock = (hhmm) => { const [hh, mm] = hhmm.split(":").map(Number); return new Date(2000, 0, 1, hh, mm).toLocaleTimeString(lang, { hour: "numeric", minute: "2-digit" }); };
  const statusPill = (status) => h("span", { class: `pill ${status === "succeeded" ? "ok" : status === "failed" ? "bad" : isDone({ status }) ? "" : "warn"}` },
    h("span", { class: "dot" }), t("st_" + status));
  const pretty = (segment) => segment.replaceAll("_", " ");
  const html = (tag, markup) => { const node = document.createElement(tag); node.innerHTML = markup; return node; };   // for our own text constants only

  // ── Public: home ────────────────────────────────────────────────────────────
  function publicNav() {
    const signedIn = !!state.me;
    return h("header", { class: "topnav" }, h("div", { class: "topnav-inner" }, brand("#/"),
      h("nav", { class: "links" }, h("a", { href: "#/roster", text: t("nav_rosters") }), h("a", { href: "#/how", text: t("nav_how") }),
        h("a", { href: "#/why", text: t("nav_why") })),
      h("span", { class: "grow" }),
      window.innerWidth >= 560 ? langButton() : h("button", { class: "iconbtn", type: "button", onclick: toggleLang, "aria-label": t("lang_switch"), title: t("lang_switch") }, icon("globe")),
      themeButton(),
      h("a", { class: "btn primary", href: signedIn ? "#/app/overview" : "#/signin", text: signedIn ? t("open_dashboard") : t("sign_in") })));
  }
  let exampleTab = null;
  function home() {
    const tab = exampleTab || (lang === "es" ? "es" : "en");
    const samples = { es: ["sample-roster-es", "ex_alt_es"], en: ["sample-roster-en", "ex_alt_en"], vol: ["sample-volunteers-en", "ex_alt_vol"] };
    const cta = () => h("a", { class: "btn primary big", href: state.me ? "#/app/overview" : "#/signin" }, state.me ? t("open_dashboard") : t("hero_cta"), icon("arrow"));
    const step = (n, title, body) => h("div", { class: "card step" }, h("div", { class: "n", text: String(n) }), h("h3", { text: t(title) }), h("p", { class: "muted", text: t(body) }));
    const feature = (name, tone, title, body) => h("div", { class: "card feature" }, h("span", { class: `badge ${tone}` }, icon(name)), h("h3", { text: t(title) }), h("p", { class: "muted", text: t(body) }));
    const call = (name, tone, title, body) => h("li", {}, h("span", { class: `sw ${tone}` }, icon(name)), h("div", {}, h("b", { text: t(title) }), h("p", { class: "muted small", text: t(body) })));
    const pair = (n) => h("div", { class: "pair" }, h("span", { class: "before", text: t(`swap${n}_before`) }), icon("arrow"), h("span", { class: "after", text: t(`swap${n}_after`) }));
    const mail = () => h("a", { href: `mailto:${t("contact_email")}`, text: t("contact_email") });
    return h("div", {}, publicNav(),
      h("section", { class: "hero" }, scene(), h("div", { class: "wrap hero-grid" },
        h("div", { class: "rise" }, h("p", { class: "eyebrow", text: t("hero_eyebrow") }),
          h("h1", { style: "margin-top:.8rem" }, t("hero_title_a"), h("br"), h("em", { text: t("hero_title_b") })),
          h("p", { class: "lead", text: t("hero_lead") }),
          h("div", { class: "row cta" }, cta(), h("a", { class: "btn glass big", href: "#/roster", text: t("hero_cta2") })),
          h("p", { class: "fine", text: t("hero_fine") })),
        h("div", { class: "hero-art rise", style: "animation-delay:.15s" },
          h("div", { class: "paper" }, h("img", { src: `/static/img/${lang === "es" ? "sample-roster-es" : "sample-roster-en"}.png`, alt: t(lang === "es" ? "ex_alt_es" : "ex_alt_en"), width: 1210, height: 935 })),
          h("span", { class: "chip gold one" }, icon("star"), t("chip_new")), h("span", { class: "chip blue two" }, icon("phone"), t("chip_back")),
          h("span", { class: "chip green three" }, icon("check"), t("chip_ready"))))),
      h("section", { class: "band" }, h("div", { class: "wrap" },
        h("p", { class: "eyebrow", text: t("swap_eyebrow") }), h("h2", { text: t("swap_title") }), h("p", { class: "intro", text: t("swap_intro") }),
        h("div", { class: "swap" }, pair(1), pair(2), pair(3), pair(4)))),
      h("section", { class: "band alt", id: "roster" }, h("div", { class: "wrap" },
        h("p", { class: "eyebrow", text: t("ex_eyebrow") }), h("h2", { text: t("ex_title") }), h("p", { class: "intro", text: t("ex_intro") }),
        h("div", { class: "examples" },
          h("div", {},
            h("div", { class: "seg", role: "tablist", style: "margin-bottom:1rem" }, ["es", "en", "vol"].map((key) =>
              h("button", { type: "button", role: "tab", "aria-selected": String(tab === key), text: t("ex_tab_" + key),
                onclick: () => { exampleTab = key; const y = scrollY; render(); scrollTo(0, y); } }))),
            h("div", { class: "paper" }, h("img", { src: `/static/img/${samples[tab][0]}.png`, alt: t(samples[tab][1]), loading: "lazy" }))),
          h("div", {},
            h("ul", { class: "callouts" },
              call("star", "gold", "call_new", "call_new_body"), call("check", "blue", "call_dots", "call_dots_body"),
              call("alert", "gold", "call_missing", "call_missing_body"), call("phone", "green", "call_parent", "call_parent_body"),
              call("back", "blue", "call_back", "call_back_body")),
            h("div", { class: "note", style: "margin-top:1.4rem" }, h("b", { text: t("ex_note_title") }), h("p", { style: "margin-top:.2rem", text: t("ex_note") })))))),
      h("section", { class: "band", id: "how" }, h("div", { class: "wrap" },
        h("p", { class: "eyebrow", text: t("how_eyebrow") }), h("h2", { text: t("how_title") }), h("p", { class: "intro", text: t("how_intro") }),
        h("div", { class: "steps" }, step(1, "step1_title", "step1_body"), step(2, "step2_title", "step2_body"), step(3, "step3_title", "step3_body")),
        h("p", { class: "eyebrow", style: "margin-top:3.5rem", text: t("feat_eyebrow") }), h("h2", { text: t("feat_title") }),
        h("div", { class: "features" }, feature("files", "", "f1_title", "f1_body"), feature("bus", "blue", "f2_title", "f2_body"),
          feature("people", "gold", "f3_title", "f3_body"), feature("globe", "blue", "f4_title", "f4_body"), feature("check", "", "f5_title", "f5_body"),
          feature("lock", "gold", "f6_title", "f6_body")))),
      h("section", { class: "band alt", id: "why" }, h("div", { class: "wrap why" },
        h("div", {}, h("p", { class: "eyebrow", text: t("why_eyebrow") }),
          h("p", { class: "big", style: "margin-top:.7rem" }, t("why_big_a"), " ", h("em", { text: t("why_big_b") }))),
        h("div", {}, h("p", { text: t("why_1") }), h("p", { text: t("why_2") }), h("p", { class: "muted" }, t("why_contact"), " ", mail(), ".")))),
      h("section", { class: "band" }, h("div", { class: "wrap" }, h("div", { class: "cta-band" }, scene({ orb: false }),
        h("div", { style: "position:relative" }, h("h2", { text: t("cta_title") }), h("p", { class: "muted", style: "margin:.6rem 0 1.4rem", text: t("cta_body") }), cta())))),
      h("footer", { class: "footer" }, h("div", { class: "wrap" },
        h("p", { class: "verse", style: "text-align:center;font-size:1.1rem;margin-bottom:1.6rem" }, t("verse"), h("cite", { text: t("verse_ref") })),
        h("div", { class: "row" }, brand("#/"), h("span", {}, `${t("footer_made")} · ${t("footer_pc")} · `, mail())),
        h("div", { class: "row", style: "justify-content:center;margin-top:1.2rem" }, langButton(),
          h("button", { class: "btn ghost", type: "button", onclick: toggleTheme }, icon(theme() === "evening" ? "sun" : "moon"), themeLabel())))));
  }

  // ── Public: sign in ─────────────────────────────────────────────────────────
  function signin() {
    const config = state.config || { pco_oauth: false, dev_churches: [] };
    const error = h("p", { class: "error", role: "alert" });
    const dev = config.dev_churches.map((church) => h("button", { class: "choice", type: "button",
      onclick: async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        try { await api("/auth/dev/login", { method: "POST", body: { church: church.id } }); await load(); go("#/app/overview"); }
        catch (failure) { error.textContent = failure.message; button.disabled = false; }
      } }, h("span", { class: "badge" }, icon("home")), h("div", {}, h("b", { text: church.name }), h("span", { text: church.note }))));
    return h("div", { class: "signin" },
      h("div", { class: "signin-art" }, scene(),
        h("div", { style: "position:absolute;top:1.2rem;left:1.5rem" }, brand("#/")),
        h("h1", { class: "rise", text: t("si_title") }), h("p", { class: "rise", text: t("si_body") })),
      h("div", { class: "signin-panel" }, h("div", { class: "signin-box" },
        h("div", { class: "row" }, h("p", { class: "eyebrow grow", text: t("product") }), langButton(), themeButton()),
        h("h2", { text: t("si_heading"), style: "font-size:1.9rem" }), h("p", { class: "muted", text: t("si_sub") }),
        config.pco_oauth
          ? h("a", { class: "btn blue big", href: "/auth/pco/login" }, t("si_pco"), icon("arrow"))
          : h("div", {}, h("button", { class: "btn blue big", type: "button", disabled: true, style: "width:100%" }, t("si_pco")),
              h("p", { class: "muted small", style: "margin-top:.5rem", text: t("si_unavailable") })),
        dev.length ? h("div", { class: "devbox" }, h("p", { class: "eyebrow", text: t("si_dev") }), dev, h("p", { class: "muted small", text: t("si_dev_note") })) : null,
        error, h("a", { href: "#/", class: "small", text: "← " + t("si_back") }))));
  }

  // ── Dashboard shell ─────────────────────────────────────────────────────────
  async function signOut() { await api("/auth/logout", { method: "POST" }); state.me = null; clearTimeout(state.timer); go("#/"); }
  function shell(tab, content) {
    const link = (name) => h("a", { href: `#/app/${name}`, "aria-current": name === tab ? "page" : null }, icon(TAB_ICONS[name]), h("span", { text: t("tab_" + name) }));
    return h("div", { class: "app" }, h("div", { class: "app-sky sky", "aria-hidden": "true" }),
      h("aside", { class: "sidebar" },
        h("div", { class: "head" }, brand("#/")),
        h("div", { class: "church" }, h("span", { class: "eyebrow", text: t("your_church") }), h("b", { text: state.me.church.name })),
        h("nav", { "aria-label": t("product") }, TABS.map(link)),
        h("div", { class: "foot" },
          h("button", { type: "button", onclick: toggleLang }, icon("globe"), t("lang_switch")),
          h("button", { type: "button", onclick: toggleTheme }, icon(theme() === "evening" ? "sun" : "moon"), themeLabel()),
          h("button", { type: "button", onclick: signOut }, icon("out"), t("sign_out")),
          h("div", { class: "me" }, h("b", { text: state.me.person.name }), h("span", { class: "muted", text: state.me.church.name })))),
      h("header", { class: "mobilebar" }, h("div", { class: "mobilebar-inner" }, brandmark(), h("span", { class: "church grow", text: state.me.church.name }),
        themeButton(), h("a", { class: "iconbtn", href: "#/app/settings", "aria-label": t("tab_settings"), title: t("tab_settings") }, icon("settings")))),
      h("main", { class: "main" },
        state.me.church.status === "needs_reconnect" ? h("div", { class: "card", style: "margin-bottom:1rem" }, h("p", { class: "error", text: t("needs_reconnect") })) : null,
        content,
        h("div", { class: "row only-narrow", style: "margin-top:2rem;justify-content:center" }, langButton(),
          h("button", { class: "btn ghost", type: "button", onclick: signOut }, icon("out"), t("sign_out")))),
      h("nav", { class: "tabbar", "aria-label": t("product") }, TABS.slice(0, 5).map(link)));
  }
  const pagehead = (title, sub, ...actions) => h("div", { class: "pagehead" },
    h("div", { class: "grow" }, h("h1", { text: title }), sub ? h("p", { class: "sub", text: sub }) : null), ...actions);
  const runButton = (cls = "btn primary big") => h("button", { class: cls, type: "button", disabled: !!activeRun() || !state.reports.some((r) => r.enabled !== false),
    onclick: (event) => runNow(event.currentTarget) }, icon("play"), t("run_now"));
  const openFiles = (query = "", runId = null) => { state.files = { runId, q: query, selected: null }; go("#/app/rosters"); };
  const startWizard = (index = null) => { state.wizard = newWizard(index); go("#/app/reports"); };

  // What the run is doing right now, in words, with a bar and a way to stop it.
  function phaseText(progress) {
    if (!progress) return t("ph_queued");
    const d = progress.detail || {};
    if (progress.phase === "event") return t("ph_event", d.event);
    if (progress.phase === "sundays") return t("ph_sundays");
    if (progress.phase === "checkins") return t("ph_checkins", d.sunday, d.of);
    if (progress.phase === "parents") return t("ph_parents", d.kids);
    if (progress.phase === "saving") return d.kind === "volunteers" ? t("ph_volunteers") : t("ph_roster", d.location);
    return t("ph_other");
  }
  // The stages of one report, ticked off as the run moves through them.
  function stageList(p) {
    const at = !p ? -1 : ({ event: 0, sundays: 0, checkins: 0, parents: 1, saving: 2 })[p.phase] ?? 0;
    const items = [["st_read", 0], ["st_people", 1], ["st_pdfs", 2]];
    const withDrive = p && p.drive !== null && p.drive !== undefined;
    const row = (label, state) => h("li", { class: state },
      state === "done" ? icon("check") : h("span", { class: "dot" }), h("span", { text: label }));
    return h("ol", { class: "stages" },
      ...items.map(([key, index]) => row(t(key), index < at ? "done" : index === at ? "active" : "todo")),
      withDrive ? row(t("st_drive", p.drive), at === 2 ? "active" : "todo") : null);
  }
  function progressCard(run) {
    const p = run.progress;
    const known = p && p.fraction !== null && p.fraction !== undefined;
    let eta = t("eta_none");
    if (known && p.eta_s !== null) eta = p.eta_s <= 2 ? t("eta_almost") : p.eta_s < 90 ? t("eta_secs", Math.max(5, Math.round(p.eta_s / 5) * 5)) : t("eta_min", Math.round(p.eta_s / 60));
    const percent = known ? Math.round(p.fraction * 100) : null;
    return h("div", { class: "card runcard", id: "progress-card", style: "margin-bottom:1rem", "aria-live": "polite" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", { text: t("live_title") }), h("p", { class: "muted small", text: t("live_leave") })),
        h("button", { class: "btn secondary", type: "button", disabled: !!run.cancelling, onclick: (event) => cancelRun(run, event.currentTarget) }, icon("x"), run.cancelling ? t("cancelling") : t("cancel"))),
      h("div", { class: `meter ${known ? "" : "unknown"}`, role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": percent === null ? null : String(percent) },
        h("i", { style: known ? `width:${Math.max(3, percent)}%` : "" })),
      h("p", { class: "now", text: run.cancelling ? t("cancel_sent") : phaseText(p) }),
      stageList(p),
      h("div", { class: "facts-row" },
        p && p.report && p.report.count ? h("span", { text: t("report_of", p.report.index, p.report.count, p.report.label) }) : null,
        percent !== null ? h("span", { class: "num", text: t("percent", percent) }) : null,
        h("span", { text: eta }), p ? h("span", { class: "num", text: t("elapsed", p.elapsed_s) }) : null));
  }

  // ── Overview ────────────────────────────────────────────────────────────────
  function classBars(rows, onPick) {
    const max = Math.max(1, ...rows.map((row) => row.active + row.inactive));
    const part = (count, color, label) => count ? h("span", { style: `width:${(count / max) * 100}%;background:var(${color})`, title: `${label}: ${count}` }) : null;
    return rows.map((row) => h("button", { class: "bar", type: "button", onclick: () => onPick(row) },
      h("span", { class: "name", text: row.location }),
      h("span", { class: "track" }, part(row.active - row.new, "--bar-active", t("lg_active")), part(row.new, "--bar-new", t("lg_new")), part(row.inactive, "--bar-inactive", t("lg_inactive"))),
      h("span", { class: "num muted", text: String(row.active) })));
  }
  const legend = () => h("div", { class: "legend" },
    h("span", {}, h("i", { style: "background:var(--bar-active)" }), t("lg_active")), h("span", {}, h("i", { style: "background:var(--bar-new)" }), t("lg_new")),
    h("span", {}, h("i", { style: "background:var(--bar-inactive)" }), t("lg_inactive")));
  const scheduleLine = () => { const s = state.me.church.schedule; return s.enabled ? t("every", t("d_" + s.day), clock(s.time)) : null; };
  function overview() {
    const hour = new Date().getHours();
    const greet = t(hour < 12 ? "greet_morning" : hour < 18 ? "greet_afternoon" : "greet_evening");
    const done = goodRuns().filter((run) => run.totals && run.totals.rosters);
    const [latest, previous] = done;
    const info = latest ? state.details[latest.id] : null;
    const running = activeRun();
    if (!state.reports.length) {
      return h("div", {}, pagehead(`${greet}.`, t("ov_sub_setup")),
        h("div", { class: "card", style: "max-width:38rem;padding:2rem" }, h("span", { class: "badge" }, icon("reports")),
          h("h3", { style: "font-size:1.4rem;margin-top:1rem", text: t("first_title") }), h("p", { class: "muted", style: "margin:.5rem 0 1.3rem", text: t("first_body") }),
          h("button", { class: "btn primary big", type: "button", onclick: () => startWizard() }, t("first_cta"), icon("arrow"))));
    }
    const tile = (key, label) => {
      const value = latest ? latest.totals[key] : null;
      let delta = h("div", { class: "delta", text: latest ? t("vs_first") : " " });
      if (latest && previous) {
        const diff = value - previous.totals[key];
        delta = h("div", { class: `delta ${diff > 0 ? "up" : diff < 0 ? "down" : ""}`, text: diff ? t("vs_last", diff) : t("vs_same") });
      }
      return h("div", { class: "card tile" }, h("div", { class: "label", text: t(label) }),
        h("div", { class: "value num", text: value === null ? "–" : value.toLocaleString(lang) }), delta);
    };
    const groups = [];
    if (info) for (const report of state.reports) {
      const rows = info.summary.filter((row) => row.report === report.id);
      if (rows.length) groups.push(h("div", { class: "group", text: `${report.icon || ""} ${report.label}` }), ...classBars(rows, (row) => openFiles(row.location)));
    }
    const pco = state.me.connections.pco;
    const line = scheduleLine();
    return h("div", {},
      pagehead(`${greet}.`, latest ? t("ov_sub", when(latest.started_at)) : t("ov_sub_none"), running ? null : runButton()),
      running ? progressCard(running) : null,
      h("div", { class: "tiles" }, tile("active", "t_active"), tile("new", "t_new"), tile("inactive", "t_inactive"), tile("workers", "t_workers")),
      h("div", { class: "grid-overview" },
        h("div", { class: "stack" }, h("div", { class: "card" },
          h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", { text: t("by_class") }), h("p", { class: "muted small", text: t("by_class_sub") })), legend()),
          groups.length ? h("div", { class: "bars" }, groups) : h("p", { class: "empty", text: t("ov_sub_none") }))),
        h("div", { class: "stack" },
          h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", { class: "grow", text: t("next_run") }),
              h("a", { class: "btn ghost", href: "#/app/schedule", text: t(line ? "next_change" : "next_set") })),
            h("div", { class: "next" }, h("span", { class: `badge ${line ? "" : "gold"}` }, icon("calendar")),
              h("div", {}, h("div", { class: "when", text: line || t("next_none") }), line ? null : h("p", { class: "muted small", text: t("next_none_body") })))),
          latest ? h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", { class: "grow", text: t("last_run") }), statusPill(latest.status)),
            h("dl", { class: "kv" },
              h("dt", { text: t("lr_when") }), h("dd", { text: when(latest.started_at) }),
              h("dt", { text: t("lr_rosters") }), h("dd", { text: String(latest.totals.rosters) }),
              h("dt", { text: t("lr_took") }), h("dd", { text: t("seconds", latest.timings?.total_s ?? "–") }))) : null,
          h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", { text: t("quick") })), h("div", { class: "quick" },
            h("button", { type: "button", onclick: () => openFiles() }, icon("files"), t("q_open")),
            h("button", { type: "button", onclick: () => startWizard() }, icon("plus"), t("q_add")),
            h("a", { href: "#/app/schedule" }, icon("calendar"), t("q_schedule")),
            h("a", { href: "#/app/help" }, icon("help"), t("q_help")))),
          h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", { text: t("connections") })),
            h("dl", { class: "kv" }, h("dt", { text: "Planning Center" }), h("dd", {}, h("span", { class: `pill ${pco ? "ok" : "bad"}`, text: t(pco ? "connected" : "not_connected") })),
              h("dt", { text: "Google Drive" }), h("dd", {}, googleStatus().pill))))));
  }

  // ── Rosters ─────────────────────────────────────────────────────────────────
  const fileUrl = (runId, path) => `/api/runs/${encodeURIComponent(runId)}/files/${path.split("/").map(encodeURIComponent).join("/")}`;
  const wide = () => window.matchMedia("(min-width: 1024px)").matches;
  function describe(file) {             // runs made before files carried details: work it out from the path
    if (file.kind) return file;
    const parts = file.path.split("/"), name = parts[parts.length - 1];
    const kind = /^Instru/i.test(name) ? "instructions" : /^Volu/i.test(name) ? "volunteers" : "roster";
    return { ...file, kind, report: "", location: pretty(parts[parts.length - 2] || name) };
  }
  function rostersView() {
    const runs = goodRuns();
    const run = runs.find((r) => r.id === state.files.runId) || runs[0];
    if (!run) return h("div", {}, pagehead(t("files_title"), state.reports.length ? t("ov_sub_none") : t("ov_sub_setup"), state.reports.length ? runButton() : null));
    const info = state.details[run.id];
    if (!info) { detail(run.id).then(render); return h("div", {}, pagehead(t("files_title"), "…")); }
    const files = info.outputs.map(describe).filter((file) => file.kind !== "instructions");
    const rosterCount = files.filter((file) => file.kind === "roster").length;
    const list = h("div", { class: "card tree" });
    const viewer = h("div", { class: "card viewer" });
    const labelOf = (file) => file.kind === "volunteers" ? t("volunteer_sheet") : file.location;
    function showViewer() {
      const file = files.find((f) => f.path === state.files.selected);
      viewer.replaceChildren(file
        ? h("div", { class: "bar-top" }, h("b", { class: "grow", style: "overflow:hidden;text-overflow:ellipsis;white-space:nowrap", text: labelOf(file) }),
            h("span", { class: "muted small", text: t("print_hint") }),
            h("a", { class: "btn secondary", href: fileUrl(run.id, file.path), target: "_blank", rel: "noopener" }, icon("open"), t("open_tab")))
        : h("p", { class: "empty", style: "padding-top:6rem", text: t("pick_file") }),
        file ? h("iframe", { src: fileUrl(run.id, file.path), title: labelOf(file) }) : null);
    }
    function showList() {
      const query = state.files.q.trim().toLowerCase();
      const groups = [...state.reports.map((r) => [r.id, `${r.icon || ""} ${r.label}`]), ["", ""]];
      const rows = [];
      for (const [id, title] of groups) {
        const mine = files.filter((f) => (f.report || "") === id || (id === "" && !state.reports.some((r) => r.id === f.report)))
          .filter((f) => !query || labelOf(f).toLowerCase().includes(query) || title.toLowerCase().includes(query))
          .sort((a, b) => (a.kind === "volunteers") - (b.kind === "volunteers") || labelOf(a).localeCompare(labelOf(b), lang, { numeric: true }));
        if (!mine.length) continue;
        if (title) rows.push(h("div", { class: "group-head" }, title, h("span", { class: "count", text: t("rosters_n", mine.filter((f) => f.kind === "roster").length) })));
        for (const file of mine) {
          const props = { class: `fileitem ${file.kind === "volunteers" ? "extra" : ""}`, "aria-current": state.files.selected === file.path ? "true" : null };
          const inside = [icon(file.kind === "volunteers" ? "people" : "files"), h("span", { class: "where" }, h("b", { text: labelOf(file) }))];
          rows.push(wide()
            ? h("button", { ...props, type: "button", onclick: () => { state.files.selected = file.path; showList(); showViewer(); } }, inside)
            : h("a", { ...props, href: fileUrl(run.id, file.path), target: "_blank", rel: "noopener" }, inside, icon("open")));
        }
      }
      list.replaceChildren(...(rows.length ? rows : [h("p", { class: "empty", text: t("no_match") })]));
    }
    if (wide() && !files.some((f) => f.path === state.files.selected)) {
      const query = state.files.q.trim().toLowerCase();
      const order = (f) => { const i = state.reports.findIndex((r) => r.id === f.report); return i < 0 ? 999 : i; };
      const first = files.filter((f) => f.kind === "roster" && (!query || labelOf(f).toLowerCase().includes(query)))
        .sort((x, y) => order(x) - order(y) || labelOf(x).localeCompare(labelOf(y), lang, { numeric: true }))[0];
      state.files.selected = first ? first.path : null;
    }
    showList(); showViewer();
    const picker = runs.length > 1 ? h("label", { class: "field", style: "min-width:14rem" }, h("span", { text: t("from_run") }),
      h("select", { onchange: (event) => { state.files = { runId: event.target.value, q: state.files.q, selected: null }; render(); } },
        runs.map((r) => h("option", { value: r.id, selected: r.id === run.id, text: when(r.started_at) })))) : null;
    return h("div", {}, pagehead(t("files_title"), t("files_sub", rosterCount, when(run.started_at)), picker),
      h("div", { class: "split" },
        h("div", { class: "listpane" }, h("input", { class: "search", type: "search", placeholder: t("search_files"), "aria-label": t("search_files"), value: state.files.q,
          oninput: (event) => { state.files.q = event.target.value; showList(); } }), list),
        viewer));
  }

  // ── Set up: the list of roster sets, and the wizard that makes or edits one ─
  const HIDE_COLUMNS = ["birthday", "phone", "grade", "attendance", "added", "address"];
  const HIDE_SECTIONS = ["parents", "workers", "inactive", "summary"];
  const KINDS = {
    classes: { icon: "📚", glyph: "reports", defaults: { volunteer_report: true, history_weeks: 26 } },
    routes: { icon: "🚌", glyph: "bus", defaults: { history_weeks: 13, hide: ["grade"] } },
    other: { icon: "📋", glyph: "files", defaults: { history_weeks: 13, hide: ["grade", "summary"] } },
  };
  const blankReport = () => ({ id: "", label: "", pco_event: "", subtitle: null, icon: "📋", enabled: true, outputs: ["simple"], start_date: null,
    history_weeks: 26, max_history_weeks: 52, route_source_event: null, show_route: false, hide: [], attendance_summary: false, instructions: false,
    volunteer_report: false, volunteer_event: null, volunteer_min_age: 16, volunteer_weeks: 4, drive_folder_prefix: null, default_weeks: 6,
    default_theme: null, demo_locations: [] });
  function newWizard(index) {
    const editing = index !== null;
    return { index, step: editing ? 2 : 0, kind: editing ? null : "classes", draft: editing ? { ...blankReport(), ...JSON.parse(JSON.stringify(state.reports[index])) } : blankReport(),
      locations: null, folderTouched: editing, labelTouched: editing, error: "", previewUrl: null, previewTimer: null };
  }
  function slugify(label, taken) {
    const base = label.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "roster";
    let id = base, n = 2;
    while (taken.includes(id)) id = `${base}-${n++}`;
    return id;
  }
  async function loadEvents() {
    if (state.events) return;
    try { state.events = (await api("/api/pco/events")).events.filter((e) => !e.archived); } catch (error) { state.events = { error: true }; }
    if (state.wizard) render();
  }
  function wizardView() {
    const w = state.wizard, d = w.draft;
    const steps = ["wz_s1", "wz_s2", "wz_s3", "wz_s4"];
    const close = () => { if (w.previewUrl) URL.revokeObjectURL(w.previewUrl); state.wizard = null; render(); };
    const setStep = (n) => { w.step = n; w.error = ""; render(); scrollTo(0, 0); };
    const previewFrame = h("iframe", { title: t("preview") });
    const previewLink = h("a", { class: "btn secondary only-narrow", target: "_blank", rel: "noopener", hidden: true }, icon("eye"), t("preview_open"));
    const previewCap = h("span", { text: t("preview_loading") });
    if (w.previewUrl) { previewFrame.src = w.previewUrl; previewLink.href = w.previewUrl; previewLink.hidden = false; previewCap.textContent = t("preview_cap"); }
    function refreshPreview() {
      clearTimeout(w.previewTimer);
      w.previewTimer = setTimeout(async () => {
        try {
          const blob = await api("/api/preview/roster", { method: "POST", blob: true, body: { report: {
            label: d.label || t("wz_new"), subtitle: d.subtitle, show_route: d.show_route, attendance_summary: d.attendance_summary, hide: d.hide, default_theme: d.default_theme } } });
          if (state.wizard !== w) return;
          if (w.previewUrl) URL.revokeObjectURL(w.previewUrl);
          w.previewUrl = URL.createObjectURL(blob);
          previewFrame.src = w.previewUrl; previewLink.href = w.previewUrl; previewLink.hidden = false; previewCap.textContent = t("preview_cap");
        } catch (error) { previewCap.textContent = error.message; }
      }, 350);
    }
    let body;
    if (w.step === 0) {
      body = h("div", { class: "card form" }, h("h3", { style: "font-size:1.3rem", text: t("wz_s1") }),
        h("div", { class: "choices three" }, Object.keys(KINDS).map((kind) => h("button", { class: "pick", type: "button", "aria-pressed": String(w.kind === kind),
          onclick: () => { w.kind = kind; Object.assign(d, blankReport(), { label: d.label, pco_event: d.pco_event }, KINDS[kind].defaults, { icon: KINDS[kind].icon }); setStep(1); } },
          h("span", { class: "badge" }, icon(KINDS[kind].glyph)), h("span", {}, h("b", { text: t("k_" + kind) }), h("span", { class: "d", text: t(`k_${kind}_d`) }))))));
    } else if (w.step === 1) {
      loadEvents();
      const used = state.reports.filter((_, i) => i !== w.index).map((r) => r.pco_event);
      let events;
      if (!state.events) events = h("p", { class: "muted", text: t("ev_loading") });
      else if (state.events.error) events = h("div", {}, h("p", { class: "error", text: t("ev_error") }), h("button", { class: "btn secondary", type: "button", style: "margin-top:.6rem", onclick: () => { state.events = null; render(); } }, icon("back"), t("wz_back")));
      else if (!state.events.length) events = h("p", { class: "muted", text: t("ev_none") });
      else events = h("div", { class: "choices", role: "radiogroup", style: "max-height:22rem;overflow:auto" }, state.events.map((event) =>
        h("button", { class: "pick", type: "button", role: "radio", "aria-checked": String(d.pco_event === event.name), onclick: async () => {
          d.pco_event = event.name; w.locations = null;
          if (!w.labelTouched) d.label = event.name;
          if (!w.folderTouched) d.drive_folder_prefix = d.label;
          render();
          try { w.locations = (await api(`/api/pco/events/${encodeURIComponent(event.id)}/locations`)).locations; } catch (error) { w.locations = []; }
          if (state.wizard === w && w.step === 1) render();
        } }, h("span", {}, h("b", { text: event.name }), used.includes(event.name) ? h("span", { class: "d", text: t("ev_used") }) : null))));
      body = h("div", { class: "card form" }, h("h3", { style: "font-size:1.3rem", text: t("ev_pick") }), events,
        d.pco_event && w.locations ? h("div", {}, h("p", { class: "small", text: w.locations.length ? t("ev_locations", w.locations.length) : t("ev_locations_none") }),
          h("div", { class: "tags", style: "margin-top:.5rem" }, w.locations.slice(0, 40).map((loc) => h("span", { class: "pill", text: loc.name })))) : null,
        d.pco_event ? h("label", { class: "field" }, h("span", { text: t("f_label") }), h("input", { value: d.label, maxLength: 80,
          oninput: (event) => { d.label = event.target.value; w.labelTouched = true; if (!w.folderTouched) d.drive_folder_prefix = d.label; } })) : null);
    } else if (w.step === 2) {
      const toggleHide = (key, shown) => { d.hide = shown ? d.hide.filter((k) => k !== key) : [...new Set([...d.hide, key])]; refreshPreview(); };
      const box = (key) => h("label", { class: "tick" }, h("input", { type: "checkbox", checked: !d.hide.includes(key), onchange: (event) => toggleHide(key, event.target.checked) }), t("h_" + key));
      const extra = (key, label, after) => h("label", { class: "tick" }, h("input", { type: "checkbox", checked: !!d[key], onchange: (event) => { d[key] = event.target.checked; after && after(); refreshPreview(); render(); } }), t(label));
      loadEvents();
      const others = Array.isArray(state.events) ? state.events.filter((e) => e.name !== d.pco_event) : [];
      const routeReport = state.reports.find((r) => r.icon === "🚌" && r.pco_event !== d.pco_event);
      body = h("div", { class: "wizard-grid" },
        h("div", { class: "card form" },
          h("div", {}, h("h3", { style: "font-size:1.3rem", text: t("show_title") }), h("p", { class: "muted small", text: t("show_names") })),
          h("div", {}, h("p", { class: "eyebrow", style: "margin-bottom:.5rem", text: t("cols") }), h("div", { class: "ticks" }, HIDE_COLUMNS.map(box))),
          h("div", {}, h("p", { class: "eyebrow", style: "margin-bottom:.5rem", text: t("sections") }), h("div", { class: "ticks" }, HIDE_SECTIONS.map(box))),
          h("div", {}, h("p", { class: "eyebrow", style: "margin-bottom:.5rem", text: t("extras") }), h("div", { class: "ticks", style: "grid-template-columns:1fr" },
            extra("show_route", "x_route", () => { if (d.show_route && !d.route_source_event) d.route_source_event = routeReport ? routeReport.pco_event : (others[0] ? others[0].name : null); if (!d.show_route) { d.route_source_event = null; d.attendance_summary = false; } }),
            d.show_route ? h("label", { class: "field", style: "padding-left:1.9rem" }, h("span", { text: t("x_route_from") }),
              others.length ? h("select", { onchange: (event) => { d.route_source_event = event.target.value; } }, others.map((e) => h("option", { value: e.name, selected: e.name === d.route_source_event, text: e.name })))
                : h("span", { class: "muted small", text: t("x_route_none") })) : null,
            d.show_route ? extra("attendance_summary", "x_summary") : null,
            extra("volunteer_report", "x_vol"), extra("instructions", "x_instr"))),
          h("label", { class: "field" }, h("span", { text: t("f_subtitle") }), h("input", { value: d.subtitle || "", maxLength: 80,
            oninput: (event) => { d.subtitle = event.target.value.trim() || null; refreshPreview(); } })),
          previewLink),
        h("div", { class: "card previewpane" }, h("div", { class: "cap" }, icon("eye"), previewCap), previewFrame));
      refreshPreview();
    } else {
      const mode = d.start_date ? "since" : "weeks";
      body = h("div", { class: "card form", style: "max-width:44rem" }, h("h3", { style: "font-size:1.3rem", text: t("who_title") }),
        h("div", {}, h("p", { class: "eyebrow", style: "margin-bottom:.5rem", text: t("who_history") }),
          h("div", { class: "choices three", style: "grid-template-columns:repeat(auto-fit,minmax(15rem,1fr))" },
            h("button", { class: "pick", type: "button", "aria-pressed": String(mode === "weeks"), onclick: () => { d.start_date = null; render(); } }, h("span", {}, h("b", { text: t("who_weeks") }), h("span", { class: "d", text: t("who_weeks_d") }))),
            h("button", { class: "pick", type: "button", "aria-pressed": String(mode === "since"), onclick: () => { d.start_date = d.start_date || new Date(Date.now() - 90 * 864e5).toISOString().slice(0, 10); render(); } }, h("span", {}, h("b", { text: t("who_since") }), h("span", { class: "d", text: t("who_since_d") }))))),
        mode === "since"
          ? h("label", { class: "field inline" }, h("span", { text: t("who_date") }), h("input", { type: "date", value: d.start_date, onchange: (event) => { d.start_date = event.target.value || null; } }))
          : h("label", { class: "field inline" }, h("span", { text: t("who_n_weeks") }), h("input", { type: "number", min: 1, max: 52, value: String(d.history_weeks), onchange: (event) => { d.history_weeks = Math.min(52, Math.max(1, Number(event.target.value) || 13)); } })),
        h("label", { class: "field inline", style: "color:var(--fg);font-size:.95rem" }, h("span", { text: t("who_active_a") }),
          h("input", { type: "number", min: 1, max: 26, value: String(d.default_weeks), onchange: (event) => { d.default_weeks = Math.min(26, Math.max(1, Number(event.target.value) || 6)); } }), h("span", { text: t("who_active_b") })),
        h("label", { class: "field" }, h("span", { text: t("f_folder") }), h("input", { value: d.drive_folder_prefix || "", maxLength: 80,
          oninput: (event) => { d.drive_folder_prefix = event.target.value.trim() || null; w.folderTouched = true; } }), h("span", { class: "small", text: t("f_folder_d") })));
    }
    async function next(button) {
      if (w.step === 1 && !d.pco_event) { w.error = t("wz_need_event"); return render(); }
      if (w.step === 1 && !d.label.trim()) { w.error = t("wz_need_label"); return render(); }
      if (w.step < 3) return setStep(w.step + 1);
      button.disabled = true;
      const list = state.reports.slice();
      d.label = d.label.trim();
      if (w.index === null) { d.id = slugify(d.label, list.map((r) => r.id)); list.push(d); } else list[w.index] = d;
      try { await saveReports(list); close(); } catch (error) { w.error = error.message; render(); }
    }
    const editing = w.index !== null;
    return h("div", { class: "wizard" },
      pagehead(editing ? t("wz_edit", d.label) : t("wz_new"), null, h("button", { class: "btn ghost", type: "button", onclick: close }, icon("x"), t("wz_cancel"))),
      h("ol", { class: "stepper" }, steps.map((key, i) => h("li", { class: i === w.step ? "on" : i < w.step || editing ? "done" : "" },
        (editing ? i >= 1 : i < w.step) ? h("button", { type: "button", text: t(key), onclick: () => setStep(i) }) : t(key)))),
      body,
      h("div", { class: "wizard-foot" },
        w.step > (editing ? 1 : 0) ? h("button", { class: "btn secondary", type: "button", onclick: () => setStep(w.step - 1) }, t("wz_back")) : null,
        w.step > 0 ? h("button", { class: "btn primary", type: "button", onclick: (event) => next(event.currentTarget) }, w.step === 3 ? t("wz_save") : t("wz_next"), w.step === 3 ? icon("check") : icon("arrow")) : null,
        w.error ? h("span", { class: "error", role: "alert", text: w.error }) : null));
  }
  function reportsView() {
    if (state.wizard) return wizardView();
    const card = (r, index) => {
      const tags = [t("tag_event", r.pco_event), r.start_date ? t("tag_since", r.start_date) : t("tag_weeks", r.history_weeks)];
      if (r.show_route) tags.push(t("tag_route"));
      if (r.volunteer_report) tags.push(t("tag_vol"));
      if (r.instructions) tags.push(t("tag_instr"));
      if ((r.hide || []).length) tags.push(t("tag_hidden", r.hide.length));
      const on = r.enabled !== false;
      return h("div", { class: "card rcard" },
        h("div", { class: "row" }, h("span", { class: "title grow", text: `${r.icon || ""} ${r.label}` }),
          h("span", { class: "muted small", text: t(on ? "on" : "off") }),
          h("button", { class: "switch", type: "button", role: "switch", "aria-checked": String(on), "aria-label": `${r.label}: ${t(on ? "on" : "off")}`,
            onclick: async () => { const list = state.reports.slice(); list[index] = { ...r, enabled: !on }; try { await saveReports(list); } catch (error) { toast(error.message); } render(); } })),
        h("div", { class: "tags" }, tags.map((text) => h("span", { class: "pill", text }))),
        h("div", { class: "row" },
          h("button", { class: "btn secondary", type: "button", onclick: () => startWizard(index) }, icon("pencil"), t("edit")),
          h("button", { class: "btn ghost", type: "button", onclick: async () => {
            if (!window.confirm(t("remove_confirm", r.label))) return;
            try { await saveReports(state.reports.filter((_, i) => i !== index)); } catch (error) { toast(error.message); }
            render();
          } }, icon("trash"), t("remove"))));
    };
    return h("div", {}, pagehead(t("reports_title"), t("reports_sub"), h("button", { class: "btn primary", type: "button", onclick: () => startWizard() }, icon("plus"), t("add_roster"))),
      h("div", { class: "cards" }, state.reports.map(card),
        h("button", { class: "addcard", type: "button", onclick: () => startWizard() }, icon("plus"), t("add_roster"))));
  }

  // ── Schedule: when rosters make themselves, and every time they were made ───
  async function saveChurch(body, button) {
    if (button) button.disabled = true;
    try { state.me.church = await api("/api/church", { method: "PUT", body }); toast(t("saved")); }
    catch (error) { toast(error.message); }
    render();
  }
  function scheduleView() {
    const church = state.me.church, s = church.schedule;
    const running = activeRun();
    const selected = state.runs.find((run) => run.id === state.historySel) || state.runs.find(isDone);
    const info = selected ? state.details[selected.id] : null;
    if (selected && !info) detail(selected.id).then(() => { if (route().tab === "schedule") render(); });
    const usage = selected ? (info || selected).usage?.pco || {} : {};
    const form = h("form", { class: "card form", onsubmit: (event) => { event.preventDefault(); const f = event.target;
        saveChurch({ schedule: { enabled: f.querySelector(".switch").getAttribute("aria-checked") === "true", day: f.day.value, time: f.time.value } }, f.querySelector("button[type=submit]")); } },
      h("div", { class: "card-head", style: "margin:0" }, h("span", { class: "badge" }, icon("calendar")),
        h("div", { class: "grow" }, h("h3", { text: t("sch_card") }), h("p", { class: "muted small", text: s.enabled ? t("every", t("d_" + s.day), clock(s.time)) : t("sch_off") }))),
      h("label", { class: "row", style: "cursor:pointer" }, h("button", { class: "switch", type: "button", role: "switch", "aria-checked": String(s.enabled), "aria-label": t("sch_on"),
        onclick: (event) => { const b = event.currentTarget; b.setAttribute("aria-checked", String(b.getAttribute("aria-checked") !== "true")); } }), h("span", { text: t("sch_on") })),
      h("div", { class: "fields two" },
        h("label", { class: "field" }, h("span", { text: t("sch_day") }), h("select", { name: "day" }, ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((day) => h("option", { value: day, selected: day === s.day, text: t("d_" + day) })))),
        h("label", { class: "field" }, h("span", { text: t("sch_time") }), h("input", { name: "time", type: "time", value: s.time, required: true }))),
      h("p", { class: "muted small", text: `${t("sch_tz", church.timezone)} ${t("sch_tip")}` }),
      state.config.dev_churches.length ? h("p", { class: "note", text: t("sch_local") }) : null,
      h("div", { class: "row" }, h("button", { class: "btn primary", type: "submit" }, t("save"))));
    const history = state.runs.length ? h("div", { class: "card scrollx" }, h("div", { class: "card-head" }, h("h3", { text: t("history") })), h("table", { class: "runs" },
      h("thead", {}, h("tr", {}, h("th", { text: t("h_when") }), h("th", { text: t("h_result") }), h("th", { text: t("h_how") }), h("th", { class: "r", text: t("h_rosters") }), h("th", { class: "r", text: t("h_time") }))),
      h("tbody", {}, state.runs.map((run) => h("tr", { class: selected && run.id === selected.id ? "sel" : "", tabIndex: 0,
        onclick: () => { state.historySel = run.id; render(); }, onkeydown: (event) => { if (event.key === "Enter") { state.historySel = run.id; render(); } } },
        h("td", { text: when(run.started_at || run.created_at) }), h("td", {}, statusPill(run.status)), h("td", { text: t(run.trigger === "schedule" ? "by_schedule" : "by_hand") }),
        h("td", { class: "r num", text: String(run.totals?.rosters ?? "") }), h("td", { class: "r num", text: run.timings?.total_s != null ? t("seconds", run.timings.total_s) : "" }))))))
      : h("div", { class: "card" }, h("h3", { text: t("history") }), h("p", { class: "empty", text: t("history_none") }));
    const details = selected ? h("div", { class: "card detail" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", { text: t("run_detail") }), h("p", { class: "muted small", text: when(selected.started_at || selected.created_at) })), statusPill(selected.status)),
      selected.error ? h("p", { class: "error", style: "margin-bottom:.8rem", text: selected.error }) : null,
      h("dl", { class: "kv" },
        h("dt", { text: t("h_how") }), h("dd", { text: selected.trigger === "schedule" ? t("by_schedule") : (selected.started_by || t("by_hand")) }),
        h("dt", { text: t("h_time") }), h("dd", { text: t("seconds", selected.timings?.total_s ?? "–") }),
        h("dt", { text: t("h_rosters") }), h("dd", { text: String(selected.totals?.rosters ?? "–") })),
      selected.status === "succeeded" && selected.files ? h("button", { class: "btn secondary", type: "button", style: "margin-top:1rem", onclick: () => openFiles("", selected.id) }, icon("files"), t("open_these")) : null,
      h("details", { class: "tech" }, h("summary", { text: t("tech") }),
        h("dl", { class: "kv", style: "margin:.7rem 0" },
          h("dt", { text: t("h_req") }), h("dd", { text: String(usage.requests ?? "–") }),
          h("dt", { text: t("h_waiting") }), h("dd", { text: usage.http_s != null ? t("seconds", usage.http_s.toFixed(1)) : "–" }),
          h("dt", { text: t("h_files") }), h("dd", { text: String(selected.files ?? "–") })),
        h("pre", { class: "log", text: info ? info.log.join("\n") : "…" }))) : null;
    return h("div", {}, pagehead(t("schedule_title"), t("schedule_sub"), running ? null : runButton("btn primary")),
      running ? progressCard(running) : null,
      h("div", { class: "split wide-list" }, h("div", { class: "stack" }, form, history), details));
  }

  // ── Help ────────────────────────────────────────────────────────────────────
  function helpView() {
    const topics = [["how1", "play"], ["how2", "reports"], ["how3", "bus"], ["how4", "calendar"], ["how5", "files"], ["how6", "x"], ["how7", "globe"], ["how8", "out"]];
    const email = t("contact_email");
    return h("div", {}, pagehead(t("help_title"), t("help_sub")),
      h("div", { class: "help-grid" },
        h("div", { class: "stack", style: "gap:.6rem" }, topics.map(([key, glyph], i) => h("details", { class: "howto", open: i === 0 },
          h("summary", {}, h("span", { class: "badge", style: "width:2.1rem;height:2.1rem;border-radius:.7rem" }, icon(glyph)), t(key)),
          h("ol", {}, t(key + "_s").map((line) => html("li", line)))))),
        h("div", { class: "card contact", style: "padding:1.6rem" }, h("span", { class: "badge", style: "background:var(--card)" }, icon("mail")),
          h("h3", { style: "font-size:1.3rem;margin-top:1rem", text: t("contact_title") }), h("p", { style: "margin:.5rem 0 1rem", text: t("contact_body") }),
          h("a", { class: "mail", href: `mailto:${email}`, text: email }),
          h("div", { style: "margin-top:1.2rem" }, h("a", { class: "btn primary", href: `mailto:${email}?subject=${encodeURIComponent(t("product"))}` }, icon("mail"), t("contact_cta"))))));
  }

  // ── Settings ────────────────────────────────────────────────────────────────
  function settingsView() {
    const church = state.me.church;
    const tabs = ["church", "look", "guides", "conn", "danger"];
    const tab = tabs.includes(state.settingsTab) ? state.settingsTab : "church";
    const field = (label, control) => h("label", { class: "field" }, h("span", { text: t(label) }), control);
    const input = (name, value, extra = {}) => h("input", { name, value: value || "", maxLength: 300, ...extra });
    const submit = () => h("div", { class: "row" }, h("button", { class: "btn primary", type: "submit" }, t("save")), h("span", { class: "muted small", text: t("look_note") }));
    let panel;
    if (tab === "church") {
      let zones = [];
      try { zones = Intl.supportedValuesOf("timeZone"); } catch (e) { /* older browsers: type it in */ }
      panel = h("form", { class: "card form", onsubmit: (event) => { event.preventDefault(); const f = event.target;
          saveChurch({ name: f.name.value, timezone: f.timezone.value.trim(), language: f.language.value }, f.querySelector("button")); } },
        h("div", { class: "fields two" }, field("f_name", input("name", church.name, { required: true, maxLength: 120 })),
          field("f_timezone", h("input", { name: "timezone", value: church.timezone, required: true, list: "zones" })),
          field("f_language", h("select", { name: "language" }, state.me.options.languages.map((code) => h("option", { value: code, selected: code === church.language, text: t("lang_" + code) }))))),
        h("datalist", { id: "zones" }, zones.map((zone) => h("option", { value: zone }))), submit());
    } else if (tab === "look") {
      panel = h("form", { class: "card form", onsubmit: (event) => { event.preventDefault(); const f = event.target;
          saveChurch({ theme: f.theme.value || null, branding: { verse_text: f.verse_text.value, verse_ref: f.verse_ref.value, help_contact: f.help_contact.value,
            feedback_url: f.feedback_url.value.trim(), video_url: f.video_url.value.trim() } }, f.querySelector("button")); } },
        h("div", { class: "fields two" },
          field("f_theme", h("select", { name: "theme" }, h("option", { value: "", text: t("theme_none") }),
            state.me.options.themes.map((key) => h("option", { value: key, selected: key === church.theme, text: t("theme_" + key) })))),
          field("f_help", input("help_contact", church.branding.help_contact)),
          field("f_verse", input("verse_text", church.branding.verse_text)), field("f_verse_ref", input("verse_ref", church.branding.verse_ref)),
          field("f_feedback", input("feedback_url", church.branding.feedback_url, { type: "url" })), field("f_video", input("video_url", church.branding.video_url, { type: "url" }))),
        submit());
    } else if (tab === "guides") {
      const chosen = church.instructions_languages || [];
      const box = (code) => h("label", { class: "check" }, h("input", { type: "checkbox", name: code, checked: chosen.includes(code) }),
        h("span", {}, h("b", { text: t("g_" + code) }), h("span", { class: "muted small", text: t(`g_${code}_body`) })));
      panel = h("form", { class: "card form", onsubmit: (event) => { event.preventDefault(); const f = event.target;
          const order = church.language === "es" ? ["es", "en"] : ["en", "es"];
          saveChurch({ instructions_languages: order.filter((code) => f[code].checked) }, f.querySelector("button")); } },
        h("div", {}, h("h3", { text: t("g_title") }), h("p", { class: "muted", style: "margin-top:.3rem", text: t("g_body") })),
        h("div", { class: "fields two" }, box("en"), box("es")), h("p", { class: "muted small", text: t("g_default") }), submit());
    } else if (tab === "conn") {
      const pco = state.me.connections.pco;
      panel = h("div", { class: "card form" },
        h("div", { class: "conn" }, h("span", { class: "badge blue" }, icon("people")), h("div", { class: "grow" }, h("div", { class: "row" }, h("b", { class: "grow", text: "Planning Center" }),
          h("span", { class: `pill ${pco ? "ok" : "bad"}`, text: t(pco ? "connected" : "not_connected") })),
          h("p", { class: "muted small", style: "margin-top:.3rem", text: pco ? t("c_pco_" + pco.kind) : "" }))),
        (() => { const g = googleStatus();
          return h("div", { class: "conn" }, h("span", { class: "badge gold" }, icon("folder")), h("div", { class: "grow" }, h("div", { class: "row" }, h("b", { class: "grow", text: t("c_google") }), g.pill),
            h("p", { class: "muted small", style: "margin-top:.3rem", text: g.text }), g.actions)); })());
    } else {
      panel = h("div", { class: "card form" }, h("div", {}, h("h3", { text: t("d_title") }), h("p", { class: "muted", style: "margin-top:.3rem", text: t("d_body") })),
        h("div", {}, h("button", { class: "btn danger", type: "button", onclick: async () => {
          if (!window.confirm(t("d_confirm"))) return;
          await api("/api/disconnect", { method: "POST" }); state.me = null; go("#/");
        } }, t("d_title"))));
    }
    return h("div", { style: "max-width:60rem" }, pagehead(t("settings_title"), church.name),
      h("div", { class: "subnav", role: "tablist", style: "margin-bottom:1rem" }, tabs.map((name) => h("button", { type: "button", role: "tab",
        "aria-selected": String(name === tab), text: t("s_" + name), onclick: () => { state.settingsTab = name; render(); } }))), panel);
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const VIEWS = { overview, rosters: rostersView, reports: reportsView, schedule: scheduleView, help: helpView, settings: settingsView };
  function render() {
    document.documentElement.lang = lang;
    if (!state.loaded) return;
    const where = route();
    if (where.page === "app" && !state.me) { location.hash = "#/signin"; return; }
    if (where.page === "signin" && state.me) { location.hash = "#/app/overview"; return; }
    if (where.page !== "app" || where.tab !== "reports") state.wizard = null;
    let view;
    if (where.page === "app") { view = shell(where.tab, VIEWS[where.tab]()); document.title = `${state.me.church.name} · ${t("product")}`; }
    else if (where.page === "signin") { view = signin(); document.title = `${t("sign_in")} · ${t("product")}`; }
    else { view = home(); document.title = `${t("product")} · Mannabyte Labs`; }
    root.replaceChildren(view);
    if (where.page === "home" && where.anchor) document.getElementById(where.anchor)?.scrollIntoView();
    if (where.page === "app") poll();
  }
  let lastRoute = "";
  window.addEventListener("hashchange", () => {
    const key = JSON.stringify(route());
    render();
    if (key !== lastRoute && route().page !== "home") scrollTo(0, 0);
    lastRoute = key;
  });
  let resizeTimer = null, wasWide = wide();
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (wide() !== wasWide) { wasWide = wide(); render(); } }, 200); });
  load().then(render, () => { state.loaded = true; render(); });
})();
