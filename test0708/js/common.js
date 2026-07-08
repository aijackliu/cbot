const ICONS = {
  inspection: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/><path d="M11 8v6M8 11h6"/></svg>',
  judgment: '<svg viewBox="0 0 24 24"><path d="M12 15a3 3 0 100-6 3 3 0 000 6z"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  stats: '<svg viewBox="0 0 24 24"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>',
  analysis: '<svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M7 14l4-4 4 4 5-6"/></svg>',
  suggestions: '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 00-4 12.7V17h8v-2.3A7 7 0 0012 2z"/></svg>',
  retrain: '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 11-3-6.7"/><path d="M21 3v6h-6"/></svg>',
  notifications: '<svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>',
  admin: '<svg viewBox="0 0 24 24"><path d="M12 15a3 3 0 100-6 3 3 0 000 6z"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
};

const NAV_SECTIONS = [
  {
    label: "檢測作業",
    items: [
      { href: "inspection.html", label: "檢測流程", id: "inspection", icon: "inspection" },
      { href: "judgment.html", label: "判定參數設定", id: "judgment", icon: "judgment" },
    ],
  },
  {
    label: "數據分析",
    items: [
      { href: "stats.html", label: "統計", id: "stats", icon: "stats" },
      { href: "analysis.html", label: "數據分析", id: "analysis", icon: "analysis" },
      { href: "suggestions.html", label: "AI 建議", id: "suggestions", icon: "suggestions" },
    ],
  },
  {
    label: "系統管理",
    items: [
      { href: "admin.html", label: "系統管理", id: "admin", icon: "admin" },
      { href: "retrain.html", label: "重新訓練", id: "retrain", icon: "retrain" },
      { href: "notifications.html", label: "通知", id: "notifications", icon: "notifications", badge: "navNotifBadge" },
    ],
  },
];

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function demoToast(msg) {
  const el = document.createElement("div");
  el.className = "demo-toast";
  el.textContent = msg;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => el.remove(), 2200);
}

function initLayout(activeId) {
  const sidebar = $("#sidebar");
  if (!sidebar) return;

  const navHtml = NAV_SECTIONS.map((section) => `
    <div class="nav-section-label">${section.label}</div>
    ${section.items.map((n) => `
      <a href="${n.href}" class="nav-item ${n.id === activeId ? "active" : ""}" data-id="${n.id}">
        <span class="nav-icon">${ICONS[n.icon] || ""}</span>
        <span class="nav-label">${n.label}</span>
        ${n.badge ? `<span class="nav-badge ${MOCK.notifications.unread_count ? "" : "hidden"}" id="${n.badge}">${MOCK.notifications.unread_count}</span>` : ""}
      </a>`).join("")}
  `).join("");

  const onHome = activeId === "home";
  sidebar.innerHTML = `
    <a href="index.html" class="sidebar-brand ${onHome ? "active" : ""}" title="返回首頁">
      <div class="logo">AOI</div>
      <div>
        <div class="brand-title">軸心 AI 檢測</div>
        <div class="brand-sub">Edge AI · 展示系統</div>
      </div>
    </a>
    <nav class="sidebar-nav">${navHtml}</nav>
    <div class="sidebar-footer">
      <span class="status-dot"></span>
      <span id="sidebarStatus">${MOCK.machine.machine_id} · ${MOCK.showcase.sample_count} 組樣本</span>
    </div>`;
}

function renderDefectBars(container, dist) {
  const colors = { 裂痕: "#fb7185", 刮痕: "#fb923c", 凹陷: "#a78bfa" };
  const max = Math.max(...Object.values(dist), 1);
  container.innerHTML = Object.entries(dist).map(([name, count]) => `
    <div class="defect-bar-row">
      <span class="label">${name}</span>
      <div class="bar-bg"><div class="bar-fill" style="width:${(count / max) * 100}%;background:${colors[name]}"></div></div>
      <span class="count">${count}</span>
    </div>`).join("");
}

function renderChartBars(container, items, labelKey, valueKey) {
  const max = Math.max(...items.map((i) => i[valueKey]), 1);
  container.innerHTML = items.length ? items.map((item) => `
    <div class="chart-row">
      <span class="chart-label">${item[labelKey]}</span>
      <div class="chart-bar-bg"><div class="chart-bar-fill" style="width:${(item[valueKey] / max) * 100}%"></div></div>
      <span class="chart-val">${item[valueKey]}</span>
    </div>`).join("") : '<p class="empty-hint">尚無資料</p>';
}

function formatTime(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-TW");
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-demo-action]");
  if (!btn) return;
  e.preventDefault();
  demoToast(btn.dataset.demoAction || "展示版：此操作僅供介面預覽");
});

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page) initLayout(page);
});