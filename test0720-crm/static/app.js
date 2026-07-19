const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const titles = {
  dashboard: ["儀表板", "KPI · 管道 · 近期活動 · War Room"],
  accounts: ["客戶帳戶", "PostgreSQL accounts 表"],
  opps: ["銷售機會", "管道階段與金額（NTD）"],
  customers: ["電商客戶", "web_customers RFM / LTV"],
  competitors: ["競品情報", "competitors + signals"],
  ai: ["客服 AI · 路由", "記憶 + 輕量路由 + 填表 + 查庫（總線）"],
  agri: ["農業客戶", "天氣 · 作物曆 · 病蟲害檢索 · Qwen 多工具"],
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
      <h3>客服 AI · 輕量路由</h3>
      <p class="muted">
        <strong>路由模式</strong>：FAQ+記憶+訊號 → 自動回覆或升級建案（案號 ESC-…）·
        另有客服記憶／填表／中文查庫。無 VectorAI，僅 Qwen + Redis。
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
        <label class="muted"><input type="radio" name="aiMode" value="route" checked /> 輕量路由</label>
        <label class="muted"><input type="radio" name="aiMode" value="support" /> 客服記憶</label>
        <label class="muted"><input type="radio" name="aiMode" value="crm" /> CRM 問答</label>
        <label class="muted"><input type="radio" name="aiMode" value="form" /> 填表</label>
        <label class="muted"><input type="radio" name="aiMode" value="sql" /> 中文查庫</label>
        <span class="muted" id="formModeHint">路由：resolve 直接答 / escalate 給案號並預填表單</span>
      </div>
      <div class="sql-samples muted" id="sqlSamples"></div>
      <div class="sql-samples muted" id="routeSamples"></div>
    </div>
    <div class="ai-split ai-split-3">
      <div class="chat">
        <div class="chat-log" id="chatLog">
          <div class="bubble bot">預設「輕量路由」。試：退貨政策怎麼算？或：我要告你們／立刻退款！</div>
        </div>
        <div class="chat-input">
          <input id="chatInput" placeholder="例：到貨 3 天能退嗎？ / 訂單延遲氣死了要告你們" />
          <button class="btn primary" id="chatSend">送出</button>
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
    ($("input[name=aiMode]:checked") || {}).value || "route";

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
    $("#panelRoute").classList.toggle("hidden", m !== "route" && m !== "support");
    $("#panelForm").classList.toggle("hidden", m !== "form" && m !== "route");
    // route mode: show both route decision + form (for escalate prefill)
    if (m === "route") {
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
      hint.textContent = "路由：FAQ+訊號 → resolve 或 escalate（預填表單）";
    else hint.textContent = "CRM 問答：KPI 建議（不跑 SQL）";
  };

  $$("input[name=aiMode]").forEach((r) => {
    r.addEventListener("change", syncRightPanel);
  });
  syncRightPanel();
  refreshMemories();

  // route sample chips
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
      "<span class='muted'>路由示例：</span> " +
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
    const pill = $("#routePill");
    const act = res.action || d.action;
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
    // prefill form on escalate
    if (act === "escalate" && res.form_hints) {
      formValues = { ...formValues, ...res.form_hints };
      if (!formValues.contact) formValues.contact = customerId();
      renderForm();
      updateMissingUI();
      $("#formMsg").textContent = "已依升級預填需求欄，請補齊必填後提交";
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
      else if (m === "route") await goRoute(msg);
      else await goCrm(msg);
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
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

const loaders = {
  dashboard: loadDashboard,
  accounts: loadAccounts,
  opps: loadOpps,
  customers: loadCustomers,
  competitors: loadCompetitors,
  ai: loadAI,
  agri: loadAgri,
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
