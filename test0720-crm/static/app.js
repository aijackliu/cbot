const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const titles = {
  dashboard: ["儀表板", "KPI · 管道 · 近期活動 · War Room"],
  accounts: ["客戶帳戶", "PostgreSQL accounts 表"],
  opps: ["銷售機會", "管道階段與金額（NTD）"],
  customers: ["電商客戶", "web_customers RFM / LTV"],
  competitors: ["競品情報", "competitors + signals"],
  ai: ["客服 AI · 路由", "文字 · 表單 · mic · 知識庫路由（多庫）"],
  mmrag: ["多模態 RAG", "文字／URL／圖／音 · 可選 HyDE 檢索 · Gemini 回答"],
  agri: ["農業客戶", "天氣 · 作物曆 · 病蟲害檢索 · Qwen 多工具"],
  wikiband: ["Wiki 樂團", "Wikipedia + BM25 · Qwen 有根據回答"],
  expenses: ["收據費用", "Gemini 識圖 + Qwen 潤飾 · PostgreSQL 帳本"],
  infra: ["基礎設施", "Qwen · FastAPI · Redis · PostgreSQL"],
};

const money = (n) => {
  const v = Number(n || 0);
  if (v >= 1e8) return (v / 1e8).toFixed(2) + " 億";
  if (v >= 1e4) return (v / 1e4).toFixed(1) + " 萬";
  return v.toLocaleString("zh-Hant");
};

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json();
}

function badgeStage(stage) {
  const s = (stage || "").toLowerCase();
  let cls = "badge";
  if (s.includes("won") || s.includes("closed_won") || s === "成交") cls += " green";
  else if (s.includes("lost") || s.includes("risk")) cls += " red";
  else if (s.includes("negot") || s.includes("propos")) cls += " warn";
  return `<span class="${cls}">${stage || "—"}</span>`;
}

function setView(name) {
  $$("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  const [t, s] = titles[name] || [name, ""];
  $("#pageTitle").textContent = t;
  $("#pageSub").textContent = s;
  location.hash = name;
}

async function loadInfra() {
  const el = $("#view-infra");
  el.innerHTML = `<div class="empty">探測服務中…</div>`;
  try {
    const data = await api("/api/infra/status");
    const remote = await api("/api/remote/overview").catch(() => null);
    const s = data.services || {};
    $("#liveDot").className = "dot " + (data.ok ? "ok" : "bad");
    $("#liveText").textContent = data.ok ? "四服務連線正常" : "部分服務異常";

    const card = (key, title, extra = "") => {
      const x = s[key] || {};
      return `
        <div class="status-card">
          <h4>${title} · <span class="${x.ok ? "ok" : "bad"}">${x.ok ? "ONLINE" : "DOWN"}</span></h4>
          <div class="mono">${x.url || ""}</div>
          <div class="muted" style="margin-top:6px">${x.detail || ""}</div>
          ${x.model ? `<div class="muted">model: ${x.model}</div>` : ""}
          ${x.database ? `<div class="muted">db: ${x.database}</div>` : ""}
          ${x.note ? `<div class="muted">${x.note}</div>` : ""}
          ${x.counts ? `<ul>${Object.entries(x.counts).map(([k,v]) => `<li>${k}: ${v}</li>`).join("")}</ul>` : ""}
          ${extra}
        </div>`;
    };

    let remoteExtra = "";
    if (remote) {
      remoteExtra = `
        <div class="status-card">
          <h4>遠端 FastAPI OpenAPI · <span class="${remote.ok ? "ok" : "bad"}">${remote.ok ? "OK" : "FAIL"}</span></h4>
          <div class="muted">${remote.title || ""} @ ${remote.base || ""}</div>
          <ul>${(remote.paths_sample || []).slice(0, 12).map((p) => `<li class="mono">${p}</li>`).join("")}</ul>
        </div>`;
    }

    el.innerHTML = `
      <div class="card">
        <h3>整合拓撲</h3>
        <p class="muted">本 CRM 展示站作為 BFF：讀取 catch_crm（Postgres）、快取於 Redis、助理走 Qwen、並探測 glasses_backend FastAPI。</p>
        <pre class="mono" style="white-space:pre-wrap;line-height:1.6;margin:10px 0 0">
瀏覽器 → 本機 FastAPI(:18720)
          ├─ PostgreSQL 100.88.220.82:5432 / catch_crm
          ├─ Redis      100.88.220.82:6379
          ├─ Qwen       100.88.220.82:8080/v1/chat/completions
          └─ 探測       100.88.220.82:9000  glasses_backend
        </pre>
      </div>
      <div class="status-grid">
        ${card("qwen", "Qwen Chat")}
        ${card("postgresql", "PostgreSQL")}
        ${card("redis", "Redis")}
        ${card("remote_fastapi", "Remote FastAPI")}
        ${remoteExtra}
      </div>`;
  } catch (e) {
    $("#liveDot").className = "dot bad";
    $("#liveText").textContent = "BFF 連線失敗";
    el.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

async function loadDashboard() {
  const el = $("#view-dashboard");
  el.innerHTML = `<div class="empty">載入 KPI…</div>`;
  try {
    const d = await api("/api/dashboard");
    const k = d.kpis || {};
    const maxAmt = Math.max(1, ...(d.pipeline_by_stage || []).map((x) => Number(x.amount || 0)));
    el.innerHTML = `
      <div class="kpis">
        <div class="kpi"><label>帳戶</label><b>${k.accounts}</b></div>
        <div class="kpi"><label>商機數</label><b>${k.opportunities}</b></div>
        <div class="kpi"><label>管道金額</label><b>${money(k.pipeline_ntd)}</b><br><small>NTD</small></div>
        <div class="kpi"><label>電商客戶</label><b>${k.web_customers}</b></div>
        <div class="kpi"><label>訂單數</label><b>${k.web_orders}</b></div>
        <div class="kpi"><label>電商營收</label><b>${money(k.web_revenue_ntd)}</b><br><small>cache: ${d.cache}</small></div>
      </div>
      <div class="grid2">
        <div class="card">
          <h3>管道 by Stage</h3>
          <div class="bars">
            ${(d.pipeline_by_stage || []).map((s) => `
              <div class="bar-row">
                <span>${s.stage || "—"}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${Math.round((Number(s.amount)||0)/maxAmt*100)}%"></div></div>
                <span>${money(s.amount)}</span>
              </div>`).join("") || '<div class="muted">無資料</div>'}
          </div>
        </div>
        <div class="card">
          <h3>高價值電商客戶</h3>
          <table>
            <thead><tr><th>名稱</th><th>分群</th><th>LTV</th><th>風險</th></tr></thead>
            <tbody>
              ${(d.top_customers || []).map((c) => `
                <tr>
                  <td>${c.name || "—"}</td>
                  <td>${c.segment || "—"}</td>
                  <td>${money(c.lifetime_value)}</td>
                  <td>${c.risk_flag ? badgeStage(c.risk_flag) : "—"}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>
      <div class="grid2">
        <div class="card">
          <h3>近期活動</h3>
          <table>
            <thead><tr><th>類型</th><th>主旨</th><th>帳戶</th></tr></thead>
            <tbody>
              ${(d.recent_activities || []).map((a) => `
                <tr>
                  <td>${badgeStage(a.kind)}</td>
                  <td>${a.subject || a.body || "—"}</td>
                  <td>${a.account_name || "—"}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
        <div class="card">
          <h3>War Room 快照</h3>
          ${(d.war_room || []).map((w) => `
            <div style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--line)">
              <div><strong>${w.title || w.snap_month || "—"}</strong></div>
              <div class="muted">${w.summary || ""}</div>
            </div>`).join("") || '<div class="muted">無快照</div>'}
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

function tableCard(title, headers, rowsHtml) {
  return `
    <div class="card">
      <h3>${title}</h3>
      <div style="overflow:auto">
        <table>
          <thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    </div>`;
}

async function loadAccounts() {
  const el = $("#view-accounts");
  el.innerHTML = `<div class="empty">載入帳戶…</div>`;
  try {
    const { items } = await api("/api/accounts");
    el.innerHTML = tableCard(
      `帳戶（${items.length}）`,
      ["名稱", "產業", "門市", "階段", "來源", "負責人"],
      items
        .map(
          (a) => `<tr>
          <td><strong>${a.name || "—"}</strong></td>
          <td>${a.industry || "—"}</td>
          <td>${a.stores ?? "—"}</td>
          <td>${badgeStage(a.stage)}</td>
          <td>${a.source || "—"}</td>
          <td>${a.owner || "—"}</td>
        </tr>`
        )
        .join("")
    );
  } catch (e) {
    el.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

async function loadOpps() {
  const el = $("#view-opps");
  el.innerHTML = `<div class="empty">載入商機…</div>`;
  try {
    const { items } = await api("/api/opportunities");
    el.innerHTML = tableCard(
      `銷售機會（${items.length}）`,
      ["商機", "客戶", "金額", "階段", "機率", "競品"],
      items
        .map(
          (o) => `<tr>
          <td><strong>${o.title || "—"}</strong></td>
          <td>${o.account_name || "—"}</td>
          <td>${money(o.amount_ntd)}</td>
          <td>${badgeStage(o.stage)}</td>
          <td>${o.probability ?? "—"}%</td>
          <td>${o.competitor || "—"}</td>
        </tr>`
        )
        .join("")
    );
  } catch (e) {
    el.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

async function loadCustomers() {
  const el = $("#view-customers");
  el.innerHTML = `<div class="empty">載入電商客戶…</div>`;
  try {
    const { items } = await api("/api/customers");
    el.innerHTML = tableCard(
      `電商客戶（${items.length}）`,
      ["名稱", "分群", "RFM", "訂單", "LTV", "最近下單", "風險"],
      items
        .map(
          (c) => `<tr>
          <td><strong>${c.name || "—"}</strong><div class="muted">${c.email || ""}</div></td>
          <td>${c.segment || "—"}</td>
          <td>${c.rfm_score ?? "—"}</td>
          <td>${c.order_count ?? "—"}</td>
          <td>${money(c.lifetime_value)}</td>
          <td>${c.last_order_date || "—"}</td>
          <td>${c.risk_flag ? badgeStage(c.risk_flag) : "—"}</td>
        </tr>`
        )
        .join("")
    );
  } catch (e) {
    el.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

async function loadCompetitors() {
  const el = $("#view-competitors");
  el.innerHTML = `<div class="empty">載入競品…</div>`;
  try {
    const { items } = await api("/api/competitors");
    el.innerHTML = tableCard(
      `競品（${items.length}）`,
      ["代碼", "名稱", "類別", "威脅", "訊號數", "備註"],
      items
        .map(
          (c) => `<tr>
          <td class="mono">${c.code || "—"}</td>
          <td><strong>${c.name || "—"}</strong></td>
          <td>${c.category || "—"}</td>
          <td>${badgeStage(c.threat_level)}</td>
          <td>${c.signal_count ?? 0}</td>
          <td class="muted">${c.notes || "—"}</td>
        </tr>`
        )
        .join("")
    );
  } catch (e) {
    el.innerHTML = `<div class="err">${e.message}</div>`;
  }
}

function loadAI() {
  const el = $("#view-ai");
  const sessionId =
    sessionStorage.getItem("crmFormSession") ||
    Math.random().toString(16).slice(2, 10);
  sessionStorage.setItem("crmFormSession", sessionId);

  el.innerHTML = `
    <div class="card">
      <h3>客服 AI · 多模態總線</h3>
      <p class="muted">
        輸入：<strong>文字</strong> · <strong>表單</strong> · <strong>麥克風</strong> →
        可選 <strong>知識庫路由</strong>（自動選 support／mmrag／Wiki 樂團／SQL／農業…，弱檢索回退 FAQ）。
        另有部門 resolve／escalate。
      </p>
      <div class="cs-user-bar">
        <label class="muted">客戶 ID / 名稱
          <input id="csCustomer" value="Alex" />
        </label>
        <button type="button" class="btn ghost" id="btnCsGreet">載入問候</button>
        <button type="button" class="btn ghost" id="btnCsSeed">示範記憶</button>
        <button type="button" class="btn ghost" id="btnCsClear">清除記憶</button>
      </div>
      <div class="form-mode-bar">
        <label class="muted"><input type="radio" name="aiMode" value="kb" checked /> 知識庫路由</label>
        <label class="muted"><input type="radio" name="aiMode" value="route" /> 部門路由</label>
        <label class="muted"><input type="radio" name="aiMode" value="support" /> 客服記憶</label>
        <label class="muted"><input type="radio" name="aiMode" value="crm" /> CRM 問答</label>
        <label class="muted"><input type="radio" name="aiMode" value="form" /> 填表</label>
        <label class="muted"><input type="radio" name="aiMode" value="sql" /> 中文查庫</label>
        <span class="muted" id="formModeHint">知識庫路由：一問自動選庫 · 弱命中回退客服 FAQ</span>
      </div>
      <div class="sql-samples muted" id="kbSamples"></div>
      <div class="sql-samples muted" id="sqlSamples"></div>
      <div class="sql-samples muted" id="routeSamples"></div>
    </div>
    <div class="ai-split ai-split-3">
      <div class="chat">
        <div class="chat-log" id="chatLog">
          <div class="bubble bot">預設「知識庫路由」：退貨／查帳戶數／樂團／農業會自動選庫。也可點 🎤。</div>
        </div>
        <div class="chat-input chat-input-multi">
          <button type="button" class="btn ghost mic-btn" id="chatMic" title="麥克風輸入（Gemini STT）" aria-pressed="false">🎤</button>
          <input id="chatInput" placeholder="文字輸入，或按 🎤 錄音後自動送入目前模式" />
          <button class="btn primary" id="chatSend">送出</button>
        </div>
        <div class="mic-bar muted" id="micBar">
          <span id="micStatus">麥克風待命</span>
          <span id="micTimer" class="mic-timer">00:00</span>
          <div class="mic-level-wrap"><div id="micLevel" class="mic-level"></div></div>
        </div>
      </div>
      <div class="card form-panel" id="rightPanel">
        <div id="panelRoute" class="">
          <div class="form-panel-head">
            <h3>路由決策</h3>
            <span class="pill" id="routePill">待命</span>
          </div>
          <div class="route-box muted" id="routeBox">送出訊息後顯示部門／置信度／resolve|escalate</div>
        </div>
        <div id="panelForm" class="hidden">
          <div class="form-panel-head">
            <h3 id="formTitle">服務申請表</h3>
            <span class="pill" id="formStatus">未完成</span>
          </div>
          <p class="muted" id="formDesc" style="margin-top:0"></p>
          <form id="serviceForm" class="service-form"></form>
          <div class="form-actions">
            <button type="button" class="btn ghost" id="btnFormClear">清空</button>
            <button type="button" class="btn ghost" id="btnFormFromChat">從上則對話抽取</button>
            <button type="button" class="btn primary" id="btnFormSubmit" disabled>提交申請</button>
          </div>
          <p class="muted" id="formMsg"></p>
          <div class="muted" id="formMissing"></div>
        </div>
        <div id="panelSql" class="hidden">
          <div class="form-panel-head">
            <h3>SQL 推理與結果</h3>
            <span class="pill" id="sqlStatus">待命</span>
          </div>
          <p class="muted" id="sqlRationale"></p>
          <pre class="sql-box" id="sqlCode">—</pre>
          <div class="muted" id="sqlSteps"></div>
          <div class="sql-table-wrap" id="sqlTable"></div>
        </div>
      </div>
      <div class="card mem-panel">
        <div class="form-panel-head">
          <h3>客服記憶</h3>
          <span class="pill" id="memCount">0</span>
        </div>
        <p class="muted" style="margin:0 0 8px">按客戶隔離 · Redis</p>
        <ul class="mem-list" id="memList"><li class="muted">尚未載入</li></ul>
      </div>
    </div>`;
  const log = $("#chatLog");
  const input = $("#chatInput");
  const send = $("#chatSend");
  let lastUserMsg = "";
  let formValues = {};
  let formHistory = [];
  let template = null;

  const customerId = () => ($("#csCustomer").value || "Alex").trim() || "Alex";

  const mode = () =>
    ($("input[name=aiMode]:checked") || {}).value || "kb";

  const refreshMemories = async () => {
    try {
      const d = await api(
        `/api/cs/memory?customer_id=${encodeURIComponent(customerId())}`
      );
      const list = d.results || [];
      $("#memCount").textContent = String(list.length);
      if (!list.length) {
        $("#memList").innerHTML = '<li class="muted">（尚無記憶）</li>';
        return;
      }
      $("#memList").innerHTML = list
        .map(
          (m) =>
            `<li><span class="mem-kind">${m.kind || "fact"}</span> ${m.memory || ""}</li>`
        )
        .join("");
    } catch (e) {
      $("#memList").innerHTML = `<li class="err">${e.message}</li>`;
    }
  };

  const syncRightPanel = () => {
    const m = mode();
    if (m === "route" || m === "kb") {
      $("#panelRoute").classList.remove("hidden");
      $("#panelForm").classList.remove("hidden");
      $("#panelSql").classList.add("hidden");
    } else if (m === "sql") {
      $("#panelRoute").classList.add("hidden");
      $("#panelForm").classList.add("hidden");
      $("#panelSql").classList.remove("hidden");
    } else if (m === "form") {
      $("#panelRoute").classList.add("hidden");
      $("#panelForm").classList.remove("hidden");
      $("#panelSql").classList.add("hidden");
    } else {
      $("#panelRoute").classList.add("hidden");
      $("#panelForm").classList.add("hidden");
      $("#panelSql").classList.add("hidden");
    }
    const hint = $("#formModeHint");
    if (m === "form") hint.textContent = "填表：說出公司／聯絡人／需求";
    else if (m === "sql") hint.textContent = "查庫：schema → SELECT → 結果";
    else if (m === "support")
      hint.textContent = "客服記憶：回憶過去 → 回答 → 寫入新事實";
    else if (m === "route")
      hint.textContent = "部門路由：FAQ+訊號 → resolve 或 escalate（預填表單）";
    else if (m === "kb")
      hint.textContent =
        "知識庫路由：support／mmrag／wikiband／sql／agri／crm／form · 弱命中→FAQ";
    else hint.textContent = "CRM 問答：KPI 建議（不跑 SQL）";
  };

  $$("input[name=aiMode]").forEach((r) => {
    r.addEventListener("change", syncRightPanel);
  });
  syncRightPanel();
  refreshMemories();

  // KB routing samples
  const kbQs = [
    "到貨三天內可以退貨嗎？",
    "目前有多少客戶帳戶？",
    "Who was the lead singer of Audioslave?",
    "番茄黃葉怎麼辦？",
    "想填服務申請表約演示",
  ];
  const kbox = $("#kbSamples");
  if (kbox) {
    kbox.innerHTML =
      "<span class='muted'>知識庫路由示例：</span> " +
      kbQs
        .map(
          (q) =>
            `<button type="button" class="chip-btn" data-kq="${q.replace(/"/g, "&quot;")}">${q}</button>`
        )
        .join(" ");
    kbox.querySelectorAll("[data-kq]").forEach((b) => {
      b.onclick = () => {
        const r = document.querySelector('input[name=aiMode][value=kb]');
        if (r) {
          r.checked = true;
          syncRightPanel();
        }
        input.value = b.getAttribute("data-kq");
        input.focus();
      };
    });
  }

  // department route sample chips
  const routeQs = [
    "到貨三天內可以退貨嗎？",
    "發票怎麼開統編？",
    "API 一直 401 怎麼辦？",
    "訂單延遲三天了氣死了要找律師",
    "想了解企業方案報價",
  ];
  const rbox = $("#routeSamples");
  if (rbox) {
    rbox.innerHTML =
      "<span class='muted'>部門路由示例：</span> " +
      routeQs
        .map(
          (q) =>
            `<button type="button" class="chip-btn" data-rq="${q.replace(/"/g, "&quot;")}">${q}</button>`
        )
        .join(" ");
    rbox.querySelectorAll("[data-rq]").forEach((b) => {
      b.onclick = () => {
        const r = document.querySelector('input[name=aiMode][value=route]');
        if (r) {
          r.checked = true;
          syncRightPanel();
        }
        input.value = b.getAttribute("data-rq");
        input.focus();
      };
    });
  }

  // sample questions for SQL
  api("/api/sql/samples")
    .then((d) => {
      const box = $("#sqlSamples");
      box.innerHTML = (d.items || [])
        .map(
          (q) =>
            `<button type="button" class="chip-btn" data-q="${q.replace(/"/g, "&quot;")}">${q}</button>`
        )
        .join(" ");
      box.querySelectorAll("[data-q]").forEach((b) => {
        b.onclick = () => {
          const sqlRadio = document.querySelector('input[name=aiMode][value=sql]');
          if (sqlRadio) {
            sqlRadio.checked = true;
            syncRightPanel();
          }
          input.value = b.getAttribute("data-q");
          input.focus();
        };
      });
    })
    .catch(() => {});

  const push = (role, text) => {
    const d = document.createElement("div");
    d.className = `bubble ${role === "user" ? "user" : "bot"}`;
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  };

  const renderSqlResult = (res) => {
    const st = $("#sqlStatus");
    st.textContent = res.ok ? `OK · ${res.row_count ?? 0} 列` : "失敗";
    st.className = "pill " + (res.ok ? "ok" : "warn");
    $("#sqlRationale").textContent = res.rationale_zh || "";
    $("#sqlCode").textContent = res.sql || res.error || "—";
    const steps = (res.steps || [])
      .map((s) => `${s.ok ? "✓" : "✗"} ${s.step}${s.detail ? ": " + s.detail : ""}${s.error ? " — " + s.error : ""}`)
      .join(" · ");
    $("#sqlSteps").textContent = steps;
    const cols = res.columns || [];
    const rows = res.rows || [];
    if (!cols.length) {
      $("#sqlTable").innerHTML = "<p class='muted'>無結果列</p>";
      return;
    }
    const head = cols.map((c) => `<th>${c}</th>`).join("");
    const body = rows
      .slice(0, 50)
      .map(
        (r) =>
          `<tr>${cols.map((c) => `<td>${r[c] == null ? "—" : r[c]}</td>`).join("")}</tr>`
      )
      .join("");
    $("#sqlTable").innerHTML = `<table class="sql-result"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  };

  const renderForm = () => {
    if (!template) return;
    $("#formTitle").textContent = template.title || "服務申請表";
    $("#formDesc").textContent = template.description || "";
    const form = $("#serviceForm");
    form.innerHTML = (template.fields || [])
      .map((f) => {
        const req = f.required ? '<span class="req">*</span>' : "";
        const val = formValues[f.key] || "";
        if (f.multiline) {
          return `<label>${f.label}${req}<textarea data-key="${f.key}" rows="3" placeholder="${f.placeholder || ""}">${val}</textarea></label>`;
        }
        return `<label>${f.label}${req}<input data-key="${f.key}" value="${val.replace(/"/g, "&quot;")}" placeholder="${f.placeholder || ""}" /></label>`;
      })
      .join("");
    form.querySelectorAll("[data-key]").forEach((el) => {
      el.addEventListener("change", () => {
        formValues[el.getAttribute("data-key")] = el.value;
        updateMissingUI();
      });
      el.addEventListener("input", () => {
        formValues[el.getAttribute("data-key")] = el.value;
      });
    });
    updateMissingUI();
  };

  const readFormDom = () => {
    $$("#serviceForm [data-key]").forEach((el) => {
      formValues[el.getAttribute("data-key")] = el.value;
    });
    return formValues;
  };

  const updateMissingUI = (missing) => {
    const fields = (template && template.fields) || [];
    if (!missing) {
      missing = fields
        .filter((f) => f.required && !(formValues[f.key] || "").trim())
        .map((f) => ({ key: f.key, label: f.label }));
    }
    const complete = missing.length === 0;
    const st = $("#formStatus");
    st.textContent = complete ? "可提交" : `缺 ${missing.length} 項`;
    st.className = "pill " + (complete ? "ok" : "warn");
    $("#btnFormSubmit").disabled = !complete;
    $("#formMissing").textContent = complete
      ? "必填已齊，請確認後提交。"
      : "仍缺：" + missing.map((m) => m.label).join("、");
  };

  const applyFormResult = (res) => {
    formValues = { ...formValues, ...(res.values || {}) };
    renderForm();
    updateMissingUI(res.missing);
    let reply = res.reply || "";
    if (res.ask_next) reply += (reply ? "\n" : "") + res.ask_next;
    if (res.patched_keys && res.patched_keys.length) {
      reply += `\n（已填入：${res.patched_keys.join("、")}）`;
    }
    return reply || "已更新表單。";
  };

  // load template
  api("/api/forms/template")
    .then((d) => {
      template = d.template;
      formValues = {};
      (template.fields || []).forEach((f) => {
        formValues[f.key] = "";
      });
      renderForm();
    })
    .catch((e) => {
      $("#formMsg").textContent = "載入表單失敗：" + e.message;
    });

  const goCrm = async (msg) => {
    push("bot", "思考中…");
    const thinking = log.lastChild;
    try {
      const res = await api("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message: msg }),
      });
      thinking.textContent = res.reply || "（空回應）";
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    }
  };

  const goSupport = async (msg) => {
    push("bot", "回憶中…");
    const thinking = log.lastChild;
    try {
      const res = await api("/api/cs/chat", {
        method: "POST",
        body: JSON.stringify({
          customer_id: customerId(),
          message: msg,
        }),
      });
      thinking.textContent = res.reply || "（空）";
      const n = (res.new_memories || []).length;
      if (n) {
        const m = document.createElement("div");
        m.className = "muted";
        m.style.fontSize = "11px";
        m.textContent = `新記憶 +${n} · 命中舊記憶 ${(res.relevant_memories || []).length}`;
        log.appendChild(m);
      }
      await refreshMemories();
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    }
  };

  const renderRoute = (res) => {
    const d = res.decision || {};
    const routing = res.routing || {};
    const pill = $("#routePill");
    const act = res.action || d.action;
    const isKb = !!(res.routing || res.handler);
    if (isKb && routing.database) {
      pill.textContent =
        (routing.database_zh || routing.database) +
        (res.fallback_used ? " · 回退" : "");
      pill.className = "pill " + (res.fallback_used ? "warn" : "ok");
      const srcs = (res.sources || [])
        .slice(0, 5)
        .map((s) => {
          if (s.url) return `${s.band || s.label || ""} ${s.url}`.trim();
          if (s.sql) return "SQL";
          if (s.title) return s.title;
          if (s.label) return s.label + (s.score != null ? ` (${s.score})` : "");
          return JSON.stringify(s).slice(0, 60);
        })
        .join(" · ");
      $("#routeBox").innerHTML = `
        <div><b>知識庫</b>：${routing.database_zh || routing.database || "—"}
          <span class="muted">(${routing.database || ""})</span></div>
        <div><b>handler</b>：${res.handler || "—"} · <b>置信度</b>：${routing.confidence || d.confidence || "—"}</div>
        <div><b>理由</b>：${routing.reason_zh || d.reason_zh || "—"}</div>
        <div><b>方法</b>：${routing.method || "—"} · <b>耗時</b>：${res.elapsed_ms != null ? res.elapsed_ms + "ms" : "—"}</div>
        <div><b>回退</b>：${res.fallback_used ? "是 → " + (res.fallback_chain || []).join("→") : "否"}</div>
        <div><b>來源</b>：${srcs || "—"}</div>
        ${res.case_id ? `<div><b>案號</b>：${res.case_id}</div>` : ""}
      `;
    } else {
      pill.textContent = act === "escalate" ? "升級" : "自動回覆";
      pill.className = "pill " + (act === "escalate" ? "warn" : "ok");
      const sig = (res.signals || []).join(", ") || "無";
      const faq = (res.faq_hits || [])
        .map((f) => f.title || f.id)
        .join("、");
      $("#routeBox").innerHTML = `
        <div><b>部門</b>：${d.department_zh || d.department || "—"}</div>
        <div><b>動作</b>：${act} · <b>置信度</b>：${d.confidence || "—"}</div>
        <div><b>理由</b>：${d.reason_zh || "—"}</div>
        <div><b>訊號</b>：${sig}</div>
        <div><b>FAQ</b>：${faq || "—"}</div>
        ${res.case_id ? `<div><b>案號</b>：${res.case_id}</div>` : ""}
      `;
    }
    // prefill form on escalate or form_hints
    const hints = res.form_hints || (res.payload && res.payload.form_hints);
    if ((act === "escalate" || res.handler === "form") && hints) {
      formValues = { ...formValues, ...hints };
      if (!formValues.contact) formValues.contact = customerId();
      renderForm();
      updateMissingUI();
      $("#formMsg").textContent =
        act === "escalate"
          ? "已依升級預填需求欄，請補齊必填後提交"
          : "已依路由預填需求，可改填表模式補齊";
    }
    // SQL panel if sql handler
    if (res.handler === "sql" && res.payload) {
      $("#panelSql").classList.remove("hidden");
      renderSqlResult(res.payload);
    }
  };

  const goKb = async (msg) => {
    push("bot", "知識庫路由中（分類→檢索→回答）…");
    const thinking = log.lastChild;
    try {
      const res = await api("/api/cs/kb-route", {
        method: "POST",
        body: JSON.stringify({
          customer_id: customerId(),
          message: msg,
        }),
      });
      renderRoute(res);
      thinking.textContent = res.reply || "（空）";
      const meta = document.createElement("div");
      meta.className = "muted";
      meta.style.fontSize = "11px";
      const rt = res.routing || {};
      meta.textContent = `KB→${rt.database_zh || rt.database || ""} · ${rt.confidence || ""}${
        res.fallback_used ? " · fallback" : ""
      }${res.case_id ? " · " + res.case_id : ""} · ${res.elapsed_ms || "?"}ms`;
      log.appendChild(meta);
      await refreshMemories();
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    }
  };

  const goRoute = async (msg) => {
    push("bot", "路由中（訊號+FAQ+編排）…");
    const thinking = log.lastChild;
    try {
      const res = await api("/api/cs/route", {
        method: "POST",
        body: JSON.stringify({
          customer_id: customerId(),
          message: msg,
        }),
      });
      renderRoute(res);
      thinking.textContent = res.reply || "（空）";
      const meta = document.createElement("div");
      meta.className = "muted";
      meta.style.fontSize = "11px";
      const d = res.decision || {};
      meta.textContent = `${d.department_zh || ""} · ${res.action} · conf=${d.confidence}${
        res.case_id ? " · " + res.case_id : ""
      }`;
      log.appendChild(meta);
      await refreshMemories();
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    }
  };

  const goForm = async (msg) => {
    push("bot", "填表中…");
    const thinking = log.lastChild;
    try {
      const res = await api("/api/forms/turn", {
        method: "POST",
        body: JSON.stringify({
          message: msg,
          values: readFormDom(),
          history: formHistory.slice(-8),
          session_id: sessionId,
        }),
      });
      formHistory.push({ role: "user", content: msg });
      const reply = applyFormResult(res);
      formHistory.push({ role: "assistant", content: reply });
      thinking.textContent = reply;
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    }
  };

  const goSql = async (msg) => {
    push("bot", "查 schema → 寫 SQL → 執行中…");
    const thinking = log.lastChild;
    $("#sqlStatus").textContent = "查詢中";
    $("#sqlStatus").className = "pill warn";
    try {
      const res = await api("/api/sql/ask", {
        method: "POST",
        body: JSON.stringify({ question: msg }),
      });
      renderSqlResult(res);
      thinking.textContent = res.answer_zh || res.error || "完成";
      if (res.sql) {
        const m = document.createElement("div");
        m.className = "muted";
        m.style.fontSize = "11px";
        m.textContent = "SQL: " + res.sql.replace(/\s+/g, " ").slice(0, 160);
        log.appendChild(m);
      }
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
      $("#sqlStatus").textContent = "失敗";
    }
  };

  const go = async () => {
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    lastUserMsg = msg;
    push("user", msg);
    send.disabled = true;
    try {
      const m = mode();
      if (m === "form") await goForm(msg);
      else if (m === "sql") await goSql(msg);
      else if (m === "support") await goSupport(msg);
      else if (m === "kb") await goKb(msg);
      else if (m === "route") await goRoute(msg);
      else await goCrm(msg);
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  };

  // ----- Mic → Gemini STT → same bus as text -----
  const micState = {
    recording: false,
    stream: null,
    recorder: null,
    chunks: [],
    t0: 0,
    timerId: null,
    raf: 0,
    analyser: null,
  };

  const micPickMime = () => {
    const cands = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    for (const t of cands) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(t)) return t;
    }
    return "";
  };

  const micStopTracks = () => {
    if (micState.stream) {
      micState.stream.getTracks().forEach((t) => t.stop());
      micState.stream = null;
    }
  };

  const micStopLevel = () => {
    if (micState.raf) cancelAnimationFrame(micState.raf);
    micState.raf = 0;
    const bar = $("#micLevel");
    if (bar) bar.style.width = "0%";
    if (micState.analyser && micState.analyser.ctx) {
      try {
        micState.analyser.ctx.close();
      } catch (_) {
        /* */
      }
      micState.analyser = null;
    }
  };

  const micStartLevel = (stream) => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      micState.analyser = { ctx, analyser };
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        const avg = sum / data.length / 255;
        const bar = $("#micLevel");
        if (bar) bar.style.width = Math.min(100, Math.round(avg * 140)) + "%";
        micState.raf = requestAnimationFrame(tick);
      };
      tick();
    } catch (_) {
      /* */
    }
  };

  const micFmt = (sec) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  };

  const handleVoiceResult = async (res) => {
    const transcript = res.transcript || "";
    lastUserMsg = transcript;
    push("user", "🎤 " + transcript);
    const m = res.mode || mode();
    if (m === "kb" || m === "kbroute" || res.routing) {
      renderRoute(res);
      push("bot", res.reply || "（空）");
      const meta = document.createElement("div");
      meta.className = "muted";
      meta.style.fontSize = "11px";
      const rt = res.routing || {};
      meta.textContent = `語音→KB · ${rt.database_zh || rt.database || ""}${
        res.fallback_used ? " · fallback" : ""
      }`;
      log.appendChild(meta);
      await refreshMemories();
    } else if (m === "route") {
      renderRoute(res);
      push("bot", res.reply || "（空）");
      const meta = document.createElement("div");
      meta.className = "muted";
      meta.style.fontSize = "11px";
      const d = res.decision || {};
      meta.textContent = `語音→路由 · ${d.department_zh || ""} · ${res.action || ""} · conf=${d.confidence || ""}${
        res.case_id ? " · " + res.case_id : ""
      }`;
      log.appendChild(meta);
      await refreshMemories();
    } else if (m === "support") {
      push("bot", res.reply || "（空）");
      const n = (res.new_memories || []).length;
      if (n) {
        const meta = document.createElement("div");
        meta.className = "muted";
        meta.style.fontSize = "11px";
        meta.textContent = `語音→記憶 · 新記憶 +${n}`;
        log.appendChild(meta);
      }
      await refreshMemories();
    } else if (m === "form") {
      const formRes = res.form || res;
      const reply = applyFormResult(formRes);
      formHistory.push({ role: "user", content: transcript });
      formHistory.push({ role: "assistant", content: reply });
      push("bot", reply);
    } else if (m === "sql") {
      const sqlRes = res.sql || res;
      renderSqlResult(sqlRes);
      push("bot", res.reply || sqlRes.answer_zh || sqlRes.error || "完成");
    } else {
      push("bot", res.reply || "（空）");
    }
  };

  const micSendBlob = async (blob, mimeType) => {
    push("bot", "語音辨識中（Gemini）…");
    const thinking = log.lastChild;
    send.disabled = true;
    $("#chatMic").disabled = true;
    try {
      const fd = new FormData();
      const ext = (mimeType || "").includes("mp4")
        ? "m4a"
        : (mimeType || "").includes("ogg")
          ? "ogg"
          : "webm";
      fd.append("file", blob, `cs-mic.${ext}`);
      fd.append("mode", mode());
      fd.append("customer_id", customerId());
      fd.append("session_id", sessionId);
      fd.append("form_values", JSON.stringify(readFormDom()));
      fd.append("form_history", JSON.stringify(formHistory.slice(-8)));
      const r = await fetch("/api/cs/voice", { method: "POST", body: fd });
      const res = await r.json();
      if (thinking && thinking.parentNode) thinking.remove();
      if (!res.ok) {
        push("bot", "語音失敗：" + (res.error || "無法辨識"));
        if (res.transcript) push("user", "🎤 " + res.transcript);
        return;
      }
      await handleVoiceResult(res);
    } catch (e) {
      if (thinking && thinking.parentNode) thinking.remove();
      push("bot", "語音錯誤：" + e.message);
    } finally {
      send.disabled = false;
      $("#chatMic").disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  };

  const micStop = () => {
    if (micState.timerId) {
      clearInterval(micState.timerId);
      micState.timerId = null;
    }
    if (micState.recorder && micState.recorder.state !== "inactive") {
      micState.recorder.stop();
    }
    micState.recording = false;
    const btn = $("#chatMic");
    btn.classList.remove("recording");
    btn.setAttribute("aria-pressed", "false");
    btn.textContent = "🎤";
    $("#micStatus").textContent = "處理錄音…";
  };

  const micStart = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      $("#micStatus").textContent = "瀏覽器不支援麥克風";
      return;
    }
    try {
      micState.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      $("#micStatus").textContent = "無法開麥克風：" + (e.message || e);
      return;
    }
    const mime = micPickMime();
    micState.chunks = [];
    try {
      micState.recorder = mime
        ? new MediaRecorder(micState.stream, { mimeType: mime })
        : new MediaRecorder(micState.stream);
    } catch (e) {
      $("#micStatus").textContent = "MediaRecorder 失敗：" + (e.message || e);
      micStopTracks();
      return;
    }
    micState.recorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size) micState.chunks.push(ev.data);
    };
    micState.recorder.onstop = () => {
      micStopLevel();
      const type = micState.recorder.mimeType || mime || "audio/webm";
      const blob = new Blob(micState.chunks, { type });
      micStopTracks();
      $("#micStatus").textContent =
        `已錄 ${micFmt((Date.now() - micState.t0) / 1000)} · ${(blob.size / 1024).toFixed(1)} KB`;
      if (blob.size < 800) {
        $("#micStatus").textContent = "錄音太短，請再試";
        return;
      }
      micSendBlob(blob, type);
    };
    micState.recorder.start(250);
    micState.recording = true;
    micState.t0 = Date.now();
    const btn = $("#chatMic");
    btn.classList.add("recording");
    btn.setAttribute("aria-pressed", "true");
    btn.textContent = "⏹";
    $("#micStatus").textContent = "錄音中… 再點結束並送入目前模式";
    micStartLevel(micState.stream);
    if (micState.timerId) clearInterval(micState.timerId);
    micState.timerId = setInterval(() => {
      $("#micTimer").textContent = micFmt((Date.now() - micState.t0) / 1000);
    }, 200);
  };

  $("#chatMic").onclick = async () => {
    if (micState.recording) micStop();
    else await micStart();
  };

  send.onclick = go;
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") go();
  });

  $("#btnCsGreet").onclick = async () => {
    try {
      const g = await api(
        `/api/cs/greeting?customer_id=${encodeURIComponent(customerId())}`
      );
      push("bot", g.reply || "");
      await refreshMemories();
    } catch (e) {
      push("bot", "問候失敗：" + e.message);
    }
  };
  $("#btnCsSeed").onclick = async () => {
    try {
      const d = await api(
        `/api/cs/seed?customer_id=${encodeURIComponent(customerId())}`,
        { method: "POST", body: "{}" }
      );
      push("bot", (d.greeting && d.greeting.reply) || "已載入示範記憶");
      await refreshMemories();
    } catch (e) {
      push("bot", "Seed 失敗：" + e.message);
    }
  };
  $("#btnCsClear").onclick = async () => {
    try {
      await api(
        `/api/cs/memory?customer_id=${encodeURIComponent(customerId())}`,
        { method: "DELETE" }
      );
      push("bot", `已清除 ${customerId()} 的記憶`);
      await refreshMemories();
    } catch (e) {
      push("bot", "清除失敗：" + e.message);
    }
  };
  $("#csCustomer").addEventListener("change", () => refreshMemories());

  $("#btnFormClear").onclick = () => {
    formValues = {};
    (template.fields || []).forEach((f) => {
      formValues[f.key] = "";
    });
    formHistory = [];
    renderForm();
    $("#formMsg").textContent = "已清空";
  };

  $("#btnFormFromChat").onclick = async () => {
    const msg = lastUserMsg || input.value.trim();
    if (!msg) {
      $("#formMsg").textContent = "請先在對話送出一則訊息";
      return;
    }
    $("#formMsg").textContent = "抽取中…";
    try {
      const res = await api("/api/forms/turn", {
        method: "POST",
        body: JSON.stringify({
          message: msg,
          values: readFormDom(),
          session_id: sessionId,
        }),
      });
      applyFormResult(res);
      $("#formMsg").textContent = "已從對話更新欄位";
      push("bot", res.reply || "已從對話抽取到表單。");
    } catch (e) {
      $("#formMsg").textContent = e.message;
    }
  };

  $("#btnFormSubmit").onclick = async () => {
    $("#formMsg").textContent = "提交中…";
    try {
      const res = await api("/api/forms/submit", {
        method: "POST",
        body: JSON.stringify({
          values: readFormDom(),
          session_id: sessionId,
        }),
      });
      $("#formMsg").textContent =
        "已提交 #" + ((res.submission && res.submission.id) || "");
      push(
        "bot",
        "申請已提交（演示存 Redis）。單號 " +
          ((res.submission && res.submission.id) || "")
      );
      updateMissingUI([]);
    } catch (e) {
      $("#formMsg").textContent = e.message;
    }
  };
}

function loadAgri() {
  const el = $("#view-agri");
  el.innerHTML = `
    <div class="card">
      <h3>農業客戶助理</h3>
      <p class="muted">
        與客服總線並列的<strong>垂直分頁</strong>：多工具 Agent（天氣 / 作物曆 / 農業新聞檢索）→ Qwen 繁中建議。
        模式參考 llm_agri_bot；天氣預設 wttr.in（可設 OPENWEATHER_API_KEY）。
        <em>非正式農藥處方。</em>
      </p>
      <div class="sql-samples muted" id="agriSamples"></div>
    </div>
    <div class="ai-split">
      <div class="chat">
        <div class="chat-log" id="agriLog">
          <div class="bubble bot">你好，我是農業客戶助理。可問天氣、種植曆、病蟲害一般建議。</div>
        </div>
        <div class="chat-input">
          <input id="agriInput" placeholder="例：番茄黃葉怎麼辦？一期水稻何時插秧？" />
          <button class="btn primary" id="agriSend">送出</button>
        </div>
      </div>
      <div class="card form-panel">
        <div class="form-panel-head">
          <h3>工具軌跡</h3>
          <span class="pill" id="agriPill">待命</span>
        </div>
        <pre class="sql-box" id="agriPlan">—</pre>
        <div class="muted" id="agriTools"></div>
        <p class="muted" id="agriDisc" style="margin-top:12px"></p>
      </div>
    </div>`;

  const log = $("#agriLog");
  const input = $("#agriInput");
  const send = $("#agriSend");

  const push = (role, text) => {
    const d = document.createElement("div");
    d.className = `bubble ${role === "user" ? "user" : "bot"}`;
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  };

  api("/api/agri/samples")
    .then((d) => {
      const box = $("#agriSamples");
      box.innerHTML =
        "<span class='muted'>示例：</span> " +
        (d.items || [])
          .map(
            (q) =>
              `<button type="button" class="chip-btn" data-aq="${q.replace(/"/g, "&quot;")}">${q}</button>`
          )
          .join(" ");
      box.querySelectorAll("[data-aq]").forEach((b) => {
        b.onclick = () => {
          input.value = b.getAttribute("data-aq");
          input.focus();
        };
      });
    })
    .catch(() => {});

  const go = async () => {
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    push("user", msg);
    send.disabled = true;
    push("bot", "選工具 → 抓資料 → 生成建議…");
    const thinking = log.lastChild;
    $("#agriPill").textContent = "執行中";
    $("#agriPill").className = "pill warn";
    try {
      const res = await api("/api/agri/ask", {
        method: "POST",
        body: JSON.stringify({ question: msg }),
      });
      thinking.textContent = res.answer_zh || "（空）";
      $("#agriPlan").textContent = JSON.stringify(res.plan || {}, null, 2);
      const tools = res.tools || [];
      $("#agriTools").innerHTML = tools
        .map((t) => {
          const ok = t.ok ? "OK" : "失敗";
          let extra = "";
          if (t.tool === "weather" && t.ok) {
            extra = `${t.location} ${t.temp_c}°C ${t.desc || ""} 濕度${t.humidity}`;
          } else if (t.tool === "crop_calendar" && t.crops) {
            extra = t.crops.map((c) => c.crop).join("、");
          } else if (t.tool === "agri_search") {
            extra = `${(t.items || []).length} 則`;
          } else if (t.error) {
            extra = t.error;
          }
          return `<div class="brand-ch"><strong>${t.tool}</strong> · ${ok}<div class="muted">${extra}</div></div>`;
        })
        .join("");
      $("#agriDisc").textContent = res.disclaimer_zh || "";
      $("#agriPill").textContent = "完成";
      $("#agriPill").className = "pill ok";
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
      $("#agriPill").textContent = "失敗";
      $("#agriPill").className = "pill warn";
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  };

  send.onclick = go;
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") go();
  });
}

function loadExpenses() {
  const el = $("#view-expenses");
  el.innerHTML = `
    <div class="card">
      <h3>收據 OCR · 費用帳本</h3>
      <p class="muted">
        識圖：<strong>Google AI Studio / Gemini</strong> ·
        分類潤飾：<strong>LAN Qwen</strong>（:8080）·
        帳本：<strong>PostgreSQL</strong> catch_crm.receipt_expenses（:5432）·
        記憶快取：<strong>Redis</strong>（:6379）。可編輯後再存。
      </p>
      <div class="expense-upload">
        <input type="file" id="expFile" accept="image/*" />
        <button type="button" class="btn primary" id="btnExpExtract">辨識收據</button>
        <button type="button" class="btn ghost" id="btnExpSave" disabled>存入帳本</button>
        <button type="button" class="btn ghost" id="btnExpRefresh">重新整理列表</button>
        <span class="muted" id="expStatus"></span>
      </div>
    </div>
    <div class="ai-split">
      <div class="card form-panel">
        <div class="form-panel-head">
          <h3>抽取結果（可改）</h3>
          <span class="pill" id="expPill">待命</span>
        </div>
        <form id="expForm" class="service-form">
          <label>店家<input id="expVendor" /></label>
          <label>日期<input id="expDate" placeholder="YYYY-MM-DD" /></label>
          <label>幣別<input id="expCurrency" value="TWD" /></label>
          <label>小計<input id="expSubtotal" type="number" step="0.01" /></label>
          <label>稅<input id="expTax" type="number" step="0.01" /></label>
          <label>總額<input id="expTotal" type="number" step="0.01" /></label>
          <label>分類
            <select id="expCategory">
              <option>餐飲</option><option>交通</option><option>辦公</option>
              <option>農資</option><option>設備</option><option>住宿</option>
              <option>通訊</option><option>其他</option>
            </select>
          </label>
          <label>備註 / 摘要<textarea id="expNotes" rows="3"></textarea></label>
          <label>明細 JSON<textarea id="expLines" rows="4" placeholder='[{"name":"…","qty":1,"price":0}]'></textarea></label>
        </form>
        <pre class="sql-box" id="expRaw" style="max-height:120px">—</pre>
      </div>
      <div class="card form-panel">
        <div class="form-panel-head">
          <h3>帳本</h3>
          <span class="pill" id="expCount">0</span>
        </div>
        <div id="expByCat" class="muted" style="margin-bottom:10px"></div>
        <div id="expList" class="muted">—</div>
      </div>
    </div>`;

  let lastExtracted = null;

  const fillForm = (ex) => {
    lastExtracted = ex || {};
    $("#expVendor").value = ex.vendor || ex.vendor_zh || "";
    $("#expDate").value = ex.date || "";
    $("#expCurrency").value = ex.currency || "TWD";
    $("#expSubtotal").value = ex.subtotal ?? "";
    $("#expTax").value = ex.tax ?? "";
    $("#expTotal").value = ex.total ?? "";
    const cat = ex.category || "其他";
    $("#expCategory").value = cat;
    $("#expNotes").value = ex.summary_zh || ex.notes || "";
    $("#expLines").value = JSON.stringify(ex.line_items || [], null, 2);
    $("#expRaw").textContent = JSON.stringify(ex, null, 2).slice(0, 2000);
    $("#btnExpSave").disabled = false;
    $("#expPill").textContent = "已辨識";
    $("#expPill").className = "pill ok";
  };

  const readForm = () => {
    let lines = [];
    try {
      lines = JSON.parse($("#expLines").value || "[]");
    } catch {
      lines = [];
    }
    const num = (id) => {
      const v = $(id).value;
      if (v === "" || v == null) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };
    return {
      vendor: $("#expVendor").value.trim(),
      date: $("#expDate").value.trim(),
      currency: $("#expCurrency").value.trim() || "TWD",
      subtotal: num("#expSubtotal"),
      tax: num("#expTax"),
      total: num("#expTotal"),
      category: $("#expCategory").value,
      notes: $("#expNotes").value.trim(),
      line_items: lines,
      summary_zh: $("#expNotes").value.trim(),
    };
  };

  const refreshList = async () => {
    try {
      const d = await api("/api/expenses?limit=40");
      const items = d.items || [];
      $("#expCount").textContent = String(items.length);
      const by = d.by_category || [];
      $("#expByCat").innerHTML = by.length
        ? by
            .map(
              (c) =>
                `<span class="chip-btn" style="cursor:default">${c.category}: ${c.n} 筆 / ${c.sum_total}</span>`
            )
            .join(" ")
        : "尚無分類統計";
      if (!items.length) {
        $("#expList").textContent = "尚無費用紀錄";
        return;
      }
      $("#expList").innerHTML = items
        .map(
          (e) =>
            `<div class="brand-ch">
              <strong>${e.vendor || "—"}</strong> · ${e.date || "—"} ·
              ${e.category || ""} · <b>${e.total ?? "—"} ${e.currency || ""}</b>
              <button type="button" class="btn ghost" style="padding:4px 8px;margin-left:8px" data-del="${e.id}">刪</button>
              <div class="muted">${e.notes || ""}</div>
            </div>`
        )
        .join("");
      $$("#expList [data-del]").forEach((b) => {
        b.onclick = async () => {
          if (!confirm("刪除此筆？")) return;
          await api("/api/expenses/" + b.getAttribute("data-del"), {
            method: "DELETE",
          });
          await refreshList();
        };
      });
    } catch (e) {
      $("#expList").textContent = e.message;
    }
  };

  $("#btnExpExtract").onclick = async () => {
    const f = $("#expFile").files && $("#expFile").files[0];
    if (!f) {
      $("#expStatus").textContent = "請先選擇圖片";
      return;
    }
    $("#expStatus").textContent = "Gemini 識圖中…";
    $("#expPill").textContent = "辨識中";
    $("#expPill").className = "pill warn";
    $("#btnExpExtract").disabled = true;
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("polish", "true");
      const res = await fetch("/api/expenses/extract", {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      fillForm(d.extracted || {});
      $("#expStatus").textContent = "完成（可改欄位後存入帳本）";
    } catch (e) {
      $("#expStatus").textContent = "失敗：" + e.message;
      $("#expPill").textContent = "失敗";
      $("#expPill").className = "pill warn";
    } finally {
      $("#btnExpExtract").disabled = false;
    }
  };

  $("#btnExpSave").onclick = async () => {
    $("#expStatus").textContent = "儲存中…";
    try {
      const body = readForm();
      // if still have file, extract-and-save to keep image
      const f = $("#expFile").files && $("#expFile").files[0];
      if (f && lastExtracted) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("polish", "false");
        // save edited fields via expenses after extract-and-save overwrites —
        // simpler: just POST /api/expenses with form
        await api("/api/expenses", {
          method: "POST",
          body: JSON.stringify(body),
        });
      } else {
        await api("/api/expenses", {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      $("#expStatus").textContent = "已存入帳本";
      await refreshList();
    } catch (e) {
      $("#expStatus").textContent = e.message;
    }
  };

  $("#btnExpRefresh").onclick = () => refreshList();
  refreshList();
}

function loadMmRag() {
  const el = $("#view-mmrag");
  el.innerHTML = `
    <div class="card">
      <h3>多模態 RAG</h3>
      <p class="muted">
        參考 Hands-On <strong>multimodal_rag</strong> + <strong>hyde_rag</strong>：
        文字／URL／圖片／音訊 → Redis 索引 → 可選 <strong>HyDE</strong>
        （假想答案 → 向量平均 → 檢索）→ Gemini 回答並引用。無 ChromaDB／LangChain／GPU。
      </p>
      <div class="muted" id="mmStats">載入中…</div>
      <div class="form-actions" style="margin-top:10px">
        <button type="button" class="btn ghost" id="btnMmRefresh">重新整理</button>
        <button type="button" class="btn ghost" id="btnMmClear">清空知識庫</button>
        <button type="button" class="btn ghost" id="btnMmSeed">載入示範文字</button>
      </div>
    </div>
    <div class="ai-split">
      <div class="card form-panel">
        <div class="form-panel-head">
          <h3>加入來源</h3>
          <span class="pill" id="mmInPill">待命</span>
        </div>
        <label class="muted">貼上文字
          <textarea id="mmText" rows="4" placeholder="產品說明、FAQ、政策條文…"></textarea>
        </label>
        <label class="muted">標籤（可選）
          <input id="mmTextLabel" placeholder="例：退貨政策" />
        </label>
        <button type="button" class="btn primary" id="btnMmText">索引文字</button>
        <hr class="mm-hr" />
        <label class="muted">網頁 URL
          <input id="mmUrl" placeholder="https://…" />
        </label>
        <button type="button" class="btn ghost" id="btnMmUrl">抓取並索引</button>
        <hr class="mm-hr" />
        <label class="muted">圖片
          <input type="file" id="mmImg" accept="image/*" />
        </label>
        <button type="button" class="btn ghost" id="btnMmImg">Gemini 描述並索引</button>
        <hr class="mm-hr" />
        <label class="muted">音訊檔
          <input type="file" id="mmAudio" accept="audio/*,video/webm" />
        </label>
        <div class="form-actions" style="margin-top:8px">
          <button type="button" class="btn ghost" id="btnMmMic">🎤 錄一段再索引</button>
          <button type="button" class="btn ghost" id="btnMmAudio">索引音訊檔</button>
        </div>
        <p class="muted" id="mmInMsg" style="margin-top:10px"></p>
      </div>
      <div class="chat">
        <div class="chat-log" id="mmLog">
          <div class="bubble bot">先加入來源（或載入示範）。可開 HyDE 再問：退貨期限是多久？</div>
        </div>
        <div class="mm-hyde-bar">
          <label class="muted">
            <input type="checkbox" id="mmHyde" checked />
            HyDE 檢索（假想答案 → 向量平均）
          </label>
          <label class="muted">N
            <select id="mmHydeN">
              <option value="2">2</option>
              <option value="3" selected>3</option>
              <option value="4">4</option>
            </select>
          </label>
        </div>
        <div class="chat-input">
          <input id="mmQ" placeholder="針對知識庫提問…" />
          <button class="btn primary" id="mmAsk">提問</button>
        </div>
        <div class="card" style="margin:10px 0 0;padding:12px">
          <div class="form-panel-head">
            <h3 style="margin:0;font-size:14px">HyDE 假想文件</h3>
            <span class="pill" id="mmHydePill">關</span>
          </div>
          <div id="mmHydeDocs" class="muted">開啟 HyDE 後，此處顯示用於檢索的假想段落。</div>
        </div>
        <div class="card" style="margin:10px 0 0;padding:12px">
          <div class="form-panel-head">
            <h3 style="margin:0;font-size:14px">檢索命中</h3>
            <span class="pill" id="mmHitPill">—</span>
          </div>
          <div id="mmHits" class="muted">—</div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:14px">
      <h3>已索引來源</h3>
      <ul class="mem-list" id="mmSources"><li class="muted">—</li></ul>
    </div>`;

  const push = (role, text) => {
    const d = document.createElement("div");
    d.className = `bubble ${role === "user" ? "user" : "bot"}`;
    d.textContent = text;
    $("#mmLog").appendChild(d);
    $("#mmLog").scrollTop = $("#mmLog").scrollHeight;
  };

  const refresh = async () => {
    try {
      const s = await api("/api/mmrag/stats");
      $("#mmStats").textContent =
        `來源 ${s.sources} · 區塊 ${s.chunks} · Redis ${s.redis} · embed ${s.embed_model} · gen ${s.gen_model}` +
        (s.by_type
          ? " · " +
            Object.entries(s.by_type)
              .map(([k, v]) => `${k}:${v}`)
              .join(" ")
          : "");
      const items = s.items || [];
      if (!items.length) {
        $("#mmSources").innerHTML = '<li class="muted">（尚無）</li>';
      } else {
        $("#mmSources").innerHTML = items
          .map(
            (x) =>
              `<li><span class="mem-kind">${x.source_type}</span> ${x.label || x.id} · ${x.chunks || 0} chunks` +
              (x.preview ? `<div class="muted">${x.preview}</div>` : "") +
              `</li>`
          )
          .join("");
      }
    } catch (e) {
      $("#mmStats").textContent = "狀態失敗：" + e.message;
    }
  };

  const setIn = (msg, ok) => {
    $("#mmInMsg").textContent = msg;
    $("#mmInPill").textContent = ok ? "完成" : "處理中";
    $("#mmInPill").className = "pill " + (ok ? "ok" : "warn");
  };

  $("#btnMmRefresh").onclick = () => refresh();
  $("#btnMmClear").onclick = async () => {
    if (!confirm("清空多模態知識庫？")) return;
    try {
      await api("/api/mmrag", { method: "DELETE" });
      setIn("已清空", true);
      await refresh();
    } catch (e) {
      setIn(e.message, false);
    }
  };
  $("#btnMmSeed").onclick = async () => {
    setIn("索引示範…", false);
    try {
      await api("/api/mmrag/text", {
        method: "POST",
        body: JSON.stringify({
          label: "示範·退貨政策",
          text:
            "CATCH 展示電商退貨政策：一般商品到貨後 7 日內可申請退貨（未拆封）。" +
            "客製化商品與易腐農產不適用。退款於審核通過後 3–5 個工作天入帳。" +
            "企業方案請聯繫業務；技術 API 401 請檢查 API Key 與時區。",
        }),
      });
      await api("/api/mmrag/text", {
        method: "POST",
        body: JSON.stringify({
          label: "示範·客服升級",
          text:
            "若客戶提到律師、消保會、立刻退款且情緒激烈，應升級至爭議處理並建立案號。" +
            "一般 FAQ 可由一線客服自動回覆。",
        }),
      });
      setIn("已載入 2 則示範文字", true);
      await refresh();
    } catch (e) {
      setIn(e.message, false);
    }
  };

  $("#btnMmText").onclick = async () => {
    const text = $("#mmText").value.trim();
    if (!text) return setIn("請先貼上文字", false);
    setIn("索引文字中…", false);
    try {
      const r = await api("/api/mmrag/text", {
        method: "POST",
        body: JSON.stringify({
          text,
          label: $("#mmTextLabel").value.trim() || "貼上文字",
        }),
      });
      setIn(`已索引 ${r.chunks_added} 區塊`, true);
      $("#mmText").value = "";
      await refresh();
    } catch (e) {
      setIn(e.message, false);
    }
  };

  $("#btnMmUrl").onclick = async () => {
    const url = $("#mmUrl").value.trim();
    if (!url) return setIn("請輸入 URL", false);
    setIn("抓取 URL…", false);
    try {
      const r = await api("/api/mmrag/url", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      setIn(`URL 已索引 ${r.chunks_added} 區塊`, true);
      await refresh();
    } catch (e) {
      setIn(e.message, false);
    }
  };

  const uploadMedia = async (file, kind) => {
    if (!file) return setIn("請選檔", false);
    setIn(`Gemini 描述 ${kind}…`, false);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);
    fd.append("label", file.name || kind);
    try {
      const res = await fetch("/api/mmrag/media", { method: "POST", body: fd });
      const r = await res.json();
      if (!res.ok) throw new Error(r.detail || r.error || res.statusText);
      setIn(`${kind} 已索引 ${r.chunks_added} 區塊`, true);
      await refresh();
    } catch (e) {
      setIn(e.message, false);
    }
  };

  $("#btnMmImg").onclick = () => {
    const f = $("#mmImg").files && $("#mmImg").files[0];
    uploadMedia(f, "image");
  };
  $("#btnMmAudio").onclick = () => {
    const f = $("#mmAudio").files && $("#mmAudio").files[0];
    uploadMedia(f, "audio");
  };

  // short mic record → index as audio
  let mmRec = null;
  let mmChunks = [];
  $("#btnMmMic").onclick = async () => {
    const btn = $("#btnMmMic");
    if (mmRec && mmRec.state === "recording") {
      mmRec.stop();
      btn.textContent = "🎤 錄一段再索引";
      btn.classList.remove("recording");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      return setIn("不支援麥克風", false);
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      mmChunks = [];
      mmRec = new MediaRecorder(stream, { mimeType: mime });
      mmRec.ondataavailable = (e) => {
        if (e.data.size) mmChunks.push(e.data);
      };
      mmRec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(mmChunks, { type: mmRec.mimeType || "audio/webm" });
        const file = new File([blob], "mm-mic.webm", { type: blob.type });
        await uploadMedia(file, "audio");
      };
      mmRec.start(200);
      btn.textContent = "⏹ 停止並索引";
      btn.classList.add("recording");
      setIn("錄音中…", false);
    } catch (e) {
      setIn("麥克風：" + e.message, false);
    }
  };

  const ask = async () => {
    const q = $("#mmQ").value.trim();
    if (!q) return;
    $("#mmQ").value = "";
    const useHyde = !!($("#mmHyde") && $("#mmHyde").checked);
    const nHyde = parseInt(($("#mmHydeN") && $("#mmHydeN").value) || "3", 10) || 3;
    push("user", (useHyde ? "🔬 HyDE · " : "") + q);
    push("bot", useHyde ? "HyDE：假想答案 → 平均向量 → 檢索 → 回答…" : "標準檢索 + Gemini 回答中…");
    const thinking = $("#mmLog").lastChild;
    $("#mmAsk").disabled = true;
    try {
      const r = await api("/api/mmrag/ask", {
        method: "POST",
        body: JSON.stringify({
          question: q,
          top_k: 5,
          hyde: useHyde,
          n_hyde: nHyde,
        }),
      });
      thinking.textContent = r.answer || "（空）";
      const hits = r.hits || [];
      const mode = r.hyde ? "HyDE" : "標準";
      $("#mmHitPill").textContent =
        `${mode} · ${hits.length} hits · media ${r.media_attached || 0} · ${r.embed_method || ""}`;
      $("#mmHitPill").className = "pill ok";
      $("#mmHits").innerHTML = hits.length
        ? hits
            .map(
              (h) =>
                `<div class="mm-hit"><b>${h.source_type}</b> ${h.source_label} · ${h.score}` +
                `<div class="muted">${h.snippet || ""}</div></div>`
            )
            .join("")
        : "—";
      const hypos = r.hypothetical_docs || [];
      if (r.hyde && hypos.length) {
        $("#mmHydePill").textContent = `${hypos.length} 篇 · ${r.hyde_generator || ""}`;
        $("#mmHydePill").className = "pill ok";
        $("#mmHydeDocs").innerHTML = hypos
          .map(
            (d, i) =>
              `<div class="mm-hit"><b>假想 #${i + 1}</b><div class="muted">${d}</div></div>`
          )
          .join("");
      } else {
        $("#mmHydePill").textContent = r.hyde ? "無假想文" : "關";
        $("#mmHydePill").className = "pill";
        $("#mmHydeDocs").textContent = r.hyde
          ? "HyDE 未產出假想文件（已回退）。"
          : "開啟 HyDE 後，此處顯示用於檢索的假想段落。";
      }
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    } finally {
      $("#mmAsk").disabled = false;
      $("#mmLog").scrollTop = $("#mmLog").scrollHeight;
    }
  };
  $("#mmAsk").onclick = ask;
  $("#mmQ").addEventListener("keydown", (e) => {
    if (e.key === "Enter") ask();
  });
  refresh();
}

function loadWikiBand() {
  const el = $("#view-wikiband");
  el.innerHTML = `
    <div class="card">
      <h3>Wiki 樂團 RAG</h3>
      <p class="muted">
        參考 Hands-On <strong>rock_music_rag</strong>：從 <strong>Wikipedia</strong> 拉樂團條目 →
        <strong>BM25</strong> 關鍵字檢索 → <strong>Qwen</strong> 只依摘錄回答並附來源 URL。
        與「農業客戶」並列的垂直知識庫 demo（非客服總線）。
      </p>
      <div class="muted" id="wbStats">載入中…</div>
      <div class="form-actions" style="margin-top:10px">
        <button type="button" class="btn primary" id="btnWbDefaults">載入預設 10 團</button>
        <button type="button" class="btn ghost" id="btnWbRefresh">重新整理</button>
        <button type="button" class="btn ghost" id="btnWbClear">清空知識庫</button>
      </div>
      <p class="muted" id="wbMsg" style="margin-top:8px"></p>
    </div>
    <div class="ai-split">
      <div class="card form-panel">
        <div class="form-panel-head">
          <h3>樂團知識庫</h3>
          <span class="pill" id="wbPill">待命</span>
        </div>
        <label class="muted">新增 Wikipedia 團名
          <input id="wbName" placeholder="例：Nirvana / Radiohead / 五月天" />
        </label>
        <label class="muted">語系
          <select id="wbLang">
            <option value="en" selected>English (en)</option>
            <option value="zh">中文 (zh)</option>
          </select>
        </label>
        <button type="button" class="btn primary" id="btnWbAdd">抓取並索引</button>
        <div class="sql-samples muted" id="wbSamples" style="margin-top:12px"></div>
        <h3 style="margin-top:16px;font-size:14px">已索引</h3>
        <ul class="mem-list" id="wbList"><li class="muted">—</li></ul>
      </div>
      <div class="chat">
        <div class="chat-log" id="wbLog">
          <div class="bubble bot">先「載入預設 10 團」或新增團名，再問：Who was the lead singer of Audioslave?</div>
        </div>
        <div class="chat-input">
          <input id="wbQ" placeholder="例：Nirvana 的突破專輯是哪一張？" />
          <button class="btn primary" id="wbAsk">提問</button>
        </div>
        <div class="card" style="margin:10px 0 0;padding:12px">
          <div class="form-panel-head">
            <h3 style="margin:0;font-size:14px">BM25 命中</h3>
            <span class="pill" id="wbHitPill">—</span>
          </div>
          <div id="wbHits" class="muted">—</div>
        </div>
      </div>
    </div>`;

  const push = (role, text) => {
    const d = document.createElement("div");
    d.className = `bubble ${role === "user" ? "user" : "bot"}`;
    d.textContent = text;
    $("#wbLog").appendChild(d);
    $("#wbLog").scrollTop = $("#wbLog").scrollHeight;
  };

  const setMsg = (t, ok) => {
    $("#wbMsg").textContent = t || "";
    $("#wbPill").textContent = ok ? "完成" : "處理中";
    $("#wbPill").className = "pill " + (ok ? "ok" : "warn");
  };

  const refresh = async () => {
    try {
      const s = await api("/api/wikiband/stats");
      $("#wbStats").textContent =
        `樂團 ${s.bands} · 區塊 ${s.chunks} · BM25 · Redis ${s.redis}`;
      const items = s.items || [];
      if (!items.length) {
        $("#wbList").innerHTML = '<li class="muted">（尚無 — 請載入預設或新增）</li>';
      } else {
        $("#wbList").innerHTML = items
          .map(
            (b) =>
              `<li><span class="mem-kind">${b.lang || "en"}</span> ` +
              `<a href="${b.url || "#"}" target="_blank" rel="noopener">${b.title || ""}</a>` +
              ` · ${b.chunks || 0} chunks ` +
              `<button type="button" class="chip-btn wb-del" data-t="${(b.title || "").replace(/"/g, "&quot;")}">移除</button></li>`
          )
          .join("");
        $$(".wb-del").forEach((btn) => {
          btn.onclick = async () => {
            try {
              await api("/api/wikiband/remove", {
                method: "POST",
                body: JSON.stringify({ title: btn.getAttribute("data-t") }),
              });
              await refresh();
            } catch (e) {
              setMsg(e.message, false);
            }
          };
        });
      }
      const samples = [
        "Who was the lead singer of Audioslave?",
        "What was Nirvana's breakthrough album in 1991?",
        "Green Day 的 American Idiot 在講什麼？",
        "Queen 的主唱是誰？",
      ];
      $("#wbSamples").innerHTML =
        "<span class='muted'>示例：</span> " +
        samples
          .map(
            (q) =>
              `<button type="button" class="chip-btn" data-wq="${q.replace(/"/g, "&quot;")}">${q}</button>`
          )
          .join(" ");
      $$("#wbSamples [data-wq]").forEach((b) => {
        b.onclick = () => {
          $("#wbQ").value = b.getAttribute("data-wq");
          $("#wbQ").focus();
        };
      });
    } catch (e) {
      $("#wbStats").textContent = "狀態失敗：" + e.message;
    }
  };

  $("#btnWbRefresh").onclick = () => refresh();
  $("#btnWbClear").onclick = async () => {
    if (!confirm("清空 Wiki 樂團知識庫？")) return;
    try {
      await api("/api/wikiband", { method: "DELETE" });
      setMsg("已清空", true);
      await refresh();
    } catch (e) {
      setMsg(e.message, false);
    }
  };
  $("#btnWbDefaults").onclick = async () => {
    setMsg("從 Wikipedia 載入預設 10 團（約需 30–90 秒）…", false);
    $("#btnWbDefaults").disabled = true;
    try {
      const r = await api("/api/wikiband/defaults?lang=en", {
        method: "POST",
        body: "{}",
      });
      const errN = (r.errors || []).length;
      setMsg(`已載入 ${r.loaded} 團` + (errN ? ` · 失敗 ${errN}` : ""), true);
      if (errN) {
        push(
          "bot",
          "部分失敗：" +
            (r.errors || [])
              .slice(0, 3)
              .map((e) => e.band + ": " + e.error)
              .join("；")
        );
      }
      await refresh();
    } catch (e) {
      setMsg(e.message, false);
    } finally {
      $("#btnWbDefaults").disabled = false;
    }
  };
  $("#btnWbAdd").onclick = async () => {
    const name = $("#wbName").value.trim();
    if (!name) return setMsg("請輸入團名", false);
    setMsg("抓取 Wikipedia…", false);
    try {
      const r = await api("/api/wikiband/add", {
        method: "POST",
        body: JSON.stringify({
          name,
          lang: $("#wbLang").value || "en",
        }),
      });
      setMsg(
        `已索引 ${r.band && r.band.title} · ${r.chunks_added} chunks`,
        true
      );
      $("#wbName").value = "";
      await refresh();
    } catch (e) {
      setMsg(e.message, false);
    }
  };

  const ask = async () => {
    const q = $("#wbQ").value.trim();
    if (!q) return;
    $("#wbQ").value = "";
    push("user", q);
    push("bot", "BM25 檢索 + Qwen 回答中…");
    const thinking = $("#wbLog").lastChild;
    $("#wbAsk").disabled = true;
    try {
      const r = await api("/api/wikiband/ask", {
        method: "POST",
        body: JSON.stringify({ question: q, top_k: 5 }),
      });
      thinking.textContent = r.answer || "（空）";
      const hits = r.hits || [];
      $("#wbHitPill").textContent = `BM25 · ${hits.length} · ${r.model || ""}`;
      $("#wbHitPill").className = "pill ok";
      $("#wbHits").innerHTML = hits.length
        ? hits
            .map(
              (h) =>
                `<div class="mm-hit"><b>${h.band || ""}</b> · ${h.score}` +
                (h.url
                  ? ` · <a href="${h.url}" target="_blank" rel="noopener">Wiki</a>`
                  : "") +
                `<div class="muted">${h.snippet || ""}</div></div>`
            )
            .join("")
        : "—";
      const src = (r.sources || [])
        .map((s) => s.band + " " + (s.url || ""))
        .join(" · ");
      if (src) {
        const m = document.createElement("div");
        m.className = "muted";
        m.style.fontSize = "11px";
        m.textContent = "來源：" + src;
        $("#wbLog").appendChild(m);
      }
    } catch (e) {
      thinking.textContent = "錯誤：" + e.message;
      thinking.classList.add("err");
    } finally {
      $("#wbAsk").disabled = false;
      $("#wbLog").scrollTop = $("#wbLog").scrollHeight;
    }
  };
  $("#wbAsk").onclick = ask;
  $("#wbQ").addEventListener("keydown", (e) => {
    if (e.key === "Enter") ask();
  });
  refresh();
}

const loaders = {
  dashboard: loadDashboard,
  accounts: loadAccounts,
  opps: loadOpps,
  customers: loadCustomers,
  competitors: loadCompetitors,
  ai: loadAI,
  mmrag: loadMmRag,
  agri: loadAgri,
  wikiband: loadWikiBand,
  expenses: loadExpenses,
  infra: loadInfra,
};

async function boot() {
  $$("#nav button").forEach((b) => {
    b.addEventListener("click", async () => {
      const v = b.dataset.view;
      setView(v);
      await loaders[v]?.();
    });
  });
  $("#btnRefresh").onclick = async () => {
    const v = location.hash.replace("#", "") || "dashboard";
    await loaders[v]?.();
    if (v !== "infra") await loadInfra().catch(() => {});
  };

  // initial infra heartbeat (non-blocking for UI)
  loadInfra().catch(() => {});
  const initial = (location.hash || "#dashboard").replace("#", "");
  setView(titles[initial] ? initial : "dashboard");
  await loaders[titles[initial] ? initial : "dashboard"]();
}

boot();
