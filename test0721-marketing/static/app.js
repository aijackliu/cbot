const $ = (s) => document.querySelector(s);
const money = (n) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + " 億";
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(1) + " 萬";
  return v.toLocaleString("zh-Hant");
};

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function table(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.join("")}</tbody></table>`;
}

async function loadInfra() {
  try {
    const d = await api("/api/infra/status");
    const s = d.services || {};
    $("#infraMini").textContent = d.ok
      ? "✓ Qwen · Ollama · FastAPI · Redis · PostgreSQL 連線正常"
      : "部分服務異常，請看基建區塊";
    $("#infraMini").className = "trust " + (d.ok ? "ok" : "bad");

    const card = (key, title) => {
      const x = s[key] || {};
      const models = (x.models || []).slice(0, 6).join(", ");
      return `<div class="infra-card">
        <h4>${title} · <span class="${x.ok ? "ok" : "bad"}">${x.ok ? "ONLINE" : "DOWN"}</span></h4>
        <div class="mono">${x.url || ""}</div>
        <div class="muted">${x.detail || ""}</div>
        ${x.model ? `<div class="muted">model: ${x.model}</div>` : ""}
        ${x.embed_model ? `<div class="muted">embed: ${x.embed_model}</div>` : ""}
        ${x.chat_model ? `<div class="muted">chat: ${x.chat_model}</div>` : ""}
        ${x.database ? `<div class="muted">db: ${x.database}</div>` : ""}
        ${models ? `<div class="muted">tags: ${models}</div>` : ""}
        ${x.note ? `<div class="muted">${x.note}</div>` : ""}
      </div>`;
    };
    $("#infraCards").innerHTML = [
      card("qwen", "Qwen"),
      card("ollama", "Ollama"),
      card("postgresql", "PostgreSQL"),
      card("redis", "Redis"),
      card("remote_fastapi", "Remote FastAPI"),
    ].join("");
  } catch (e) {
    $("#infraMini").textContent = "BFF 連線失敗：" + e.message;
    $("#infraMini").className = "trust bad";
  }
}

async function loadOllamaTags() {
  try {
    const d = await api("/api/ollama/tags");
    $("#ollamaTags").innerHTML = table(
      ["模型", "參數量", "大小"],
      (d.models || []).map(
        (m) => `<tr>
        <td><strong>${m.name || "—"}</strong></td>
        <td>${m.parameter_size || "—"}</td>
        <td class="mono">${m.size != null ? Math.round(m.size / 1e9 * 10) / 10 + " GB" : "—"}</td>
      </tr>`
      )
    );
  } catch (e) {
    $("#ollamaTags").textContent = "無法載入 tags：" + e.message;
  }
}

async function loadTeam() {
  try {
    const d = await api("/api/team");
    const org = d.org || {};
    $("#teamMission").textContent =
      (org.mission || "") + (org.hq ? ` · ${org.hq}` : "");
    $("#teamDepts").innerHTML = Object.entries(d.departments || {})
      .map(([k, v]) => `<span>${k} ${v}</span>`)
      .join("");
    $("#teamMembers").innerHTML = (d.members || [])
      .map(
        (m) => `<article class="card">
        <div class="avatar">${m.avatar || (m.name || "?").slice(0, 1)}</div>
        <div>
          <strong>${m.name || ""}</strong>
          <div class="muted">${m.role || ""} · ${m.dept || ""}</div>
          <div class="muted">${m.focus || ""}</div>
          <div class="skill-row">${(m.skills || [])
            .map((s) => `<i>${s}</i>`)
            .join("")}</div>
        </div>
      </article>`
      )
      .join("");
  } catch (e) {
    $("#teamMembers").innerHTML = `<div class="muted">團隊載入失敗：${e.message}</div>`;
  }
}

async function loadKnowledge() {
  try {
    const d = await api("/api/knowledge");
    $("#kbStats").textContent = `共 ${d.total || 0} 份文件`;
    $("#kbSources").innerHTML =
      `<div class="source-bar">${Object.entries(d.by_source || {})
        .map(([k, v]) => `<span>${k}: ${v}</span>`)
        .join("")}</div>`;

    $("#kbArticles").innerHTML = (d.articles || [])
      .map(
        (a) => `<div class="kb-item" data-id="${a.id}">
        <strong>${a.title || ""}</strong>
        <div class="muted">${a.category || ""} · ${a.owner || ""}</div>
        <div class="muted">${a.summary || ""}</div>
      </div>`
      )
      .join("") || `<div class="muted">尚無內部文章</div>`;

    $("#kbList").innerHTML = (d.items || [])
      .map(
        (it) => `<div class="kb-item" data-id="${it.id}">
        <strong>${it.title || it.id}</strong>
        <div class="muted">${it.source} · ${it.chars || 0} 字</div>
        <div class="muted">${it.preview || ""}</div>
      </div>`
      )
      .join("");

    const openDoc = async (id) => {
      const box = $("#kbDetail");
      box.textContent = "載入中…";
      try {
        const res = await api("/api/knowledge/" + encodeURIComponent(id));
        const doc = res.doc || {};
        box.innerHTML = `<strong>${doc.title || id}</strong>
          <div class="muted" style="margin:6px 0">${doc.source || ""} · ${doc.id || ""}</div>
          <div>${(doc.text || "").replace(/</g, "&lt;")}</div>`;
      } catch (e) {
        box.textContent = e.message;
      }
    };

    document.querySelectorAll("#kbList .kb-item, #kbArticles .kb-item").forEach((el) => {
      el.onclick = () => openDoc(el.dataset.id);
    });
  } catch (e) {
    $("#kbList").innerHTML = `<div class="muted">知識庫載入失敗：${e.message}</div>`;
  }
}

function bindKbForm() {
  $("#btnKbRefresh").onclick = () => loadKnowledge();
  $("#kbForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = $("#kbMsg");
    msg.textContent = "寫入中…";
    try {
      const res = await api("/api/knowledge/articles", {
        method: "POST",
        body: JSON.stringify({
          title: fd.get("title"),
          category: fd.get("category") || "自訂",
          body: fd.get("body"),
        }),
      });
      msg.textContent = (res.hint || "已寫入") + " · id=" + (res.article?.id || "");
      e.target.reset();
      await loadKnowledge();
    } catch (err) {
      msg.textContent = "失敗：" + err.message;
    }
  };
}

async function loadClinic() {
  try {
    const [ex, pat] = await Promise.all([
      api("/api/clinic/examples"),
      api("/api/clinic/patterns"),
    ]);
    $("#clinicExamples").innerHTML = (ex.examples || [])
      .map(
        (e) =>
          `<button type="button" data-id="${e.id}"><strong>${e.title}</strong><div class="muted">${(e.preview || "").replace(/</g, "&lt;")}</div></button>`
      )
      .join("");
    $("#clinicExamples").querySelectorAll("button").forEach((btn) => {
      btn.onclick = async () => {
        const res = await api("/api/clinic/examples/" + btn.dataset.id);
        $("#clinicBug").value = res.bug || "";
        $("#clinicStatus").textContent = "已載入案例 " + btn.dataset.id;
      };
    });
    $("#clinicPatterns").innerHTML = (pat.patterns || [])
      .map((p) => `<div><strong>${p.id}</strong> ${p.name}<br/>${p.summary}</div>`)
      .join("<br/>");
  } catch (e) {
    $("#clinicExamples").innerHTML = `<div class="muted">診所載入失敗：${e.message}</div>`;
  }
}

function bindClinic() {
  $("#btnClinic").onclick = async () => {
    const bug = $("#clinicBug").value.trim();
    const out = $("#clinicOut");
    const st = $("#clinicStatus");
    if (bug.length < 20) {
      st.textContent = "請先貼上足夠詳細的故障描述（至少約 20 字）";
      return;
    }
    $("#btnClinic").disabled = true;
    st.textContent = "診斷中（Qwen，可能需數十秒）…";
    out.textContent = "執行中…";
    try {
      const res = await api("/api/clinic/diagnose", {
        method: "POST",
        body: JSON.stringify({ bug_description: bug }),
      });
      out.textContent =
        (res.assistant_markdown || "（無結果）") +
        (res.model ? `\n\n— model: ${res.model}` : "") +
        (res.report_path ? `\n— report: ${res.report_path}` : "");
      st.textContent = "完成 · 已寫入 clinic/reports/rag_failure_report.json";
    } catch (e) {
      out.textContent = "錯誤：" + e.message;
      st.textContent = "失敗";
    } finally {
      $("#btnClinic").disabled = false;
    }
  };
}

function bindRag() {
  $("#btnRagRebuild").onclick = async () => {
    const btn = $("#btnRagRebuild");
    const meta = $("#ragMeta");
    btn.disabled = true;
    meta.textContent = "重建索引中（寫入 Redis，首次較久）…";
    try {
      const res = await api("/api/rag/rebuild", { method: "POST", body: "{}" });
      const m = res.meta || {};
      meta.textContent = `索引完成：${m.chunk_count || 0} chunks · dim ${m.dim || "—"} · ${m.embed_model || ""}`;
    } catch (e) {
      meta.textContent = "重建失敗：" + e.message;
    } finally {
      btn.disabled = false;
    }
  };

  $("#btnRagAsk").onclick = async () => {
    const btn = $("#btnRagAsk");
    const out = $("#ragOut");
    const hitsEl = $("#ragHits");
    btn.disabled = true;
    out.textContent = "檢索 + 生成中…";
    hitsEl.textContent = "—";
    try {
      const res = await api("/api/rag/ask", {
        method: "POST",
        body: JSON.stringify({
          question: $("#ragQ").value.trim(),
          top_k: Number($("#ragK").value || 5),
        }),
      });
      out.textContent =
        (res.answer || "（無答案）") +
        (res.model ? `\n\n— gen: ${res.model} · embed: ${res.embed_model || ""}` : "");
      hitsEl.innerHTML = (res.hits || [])
        .map(
          (h, i) =>
            `<div style="margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--line)">
              <strong>[${i + 1}] ${h.title || h.id}</strong>
              <span class="muted"> · ${h.source} · score ${h.score}</span>
              <div class="muted">${h.text || ""}</div>
            </div>`
        )
        .join("") || "無命中";
    } catch (e) {
      out.textContent = "錯誤：" + e.message;
    } finally {
      btn.disabled = false;
    }
  };
}

async function loadOverview() {
  const d = await api("/api/marketing/overview");
  const k = d.kpis || {};
  const brand = d.brand || {};
  if (d.plan?.theme) $("#planTheme").textContent = d.plan.theme;
  $("#heroTitle").innerHTML = (brand.tagline || "把行銷預算變成可追蹤的成長").replace("變成", "變成<br />");
  $("#heroSub").textContent = brand.subtitle || "";

  $("#heroKpis").innerHTML = `
    <div><label>廣告花費</label><b>${money(k.ad_spend_ntd)}</b></div>
    <div><label>歸因營收</label><b>${money(k.ad_revenue_ntd)}</b></div>
    <div><label>ROAS</label><b>${k.roas ?? "—"}</b></div>
    <div><label>轉換</label><b>${(k.ad_conversions || 0).toLocaleString("zh-Hant")}</b></div>`;

  const plats = d.by_platform || [];
  const maxSpend = Math.max(1, ...plats.map((p) => Number(p.spend || 0)));
  $("#platformBars").innerHTML = plats
    .map(
      (p) => `<div class="bar-row">
      <span>${p.platform || "—"}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round((Number(p.spend) || 0) / maxSpend * 100)}%"></div></div>
      <span>${money(p.spend)}</span>
    </div>`
    )
    .join("") || `<div class="muted">無渠道資料</div>`;

  $("#kpis").innerHTML = [
    ["廣告花費", money(k.ad_spend_ntd)],
    ["點擊", (k.ad_clicks || 0).toLocaleString("zh-Hant")],
    ["CTR", (k.ctr_pct || 0) + "%"],
    ["CPA", money(k.cpa_ntd)],
    ["ROAS", k.roas ?? "—"],
    ["電商訂單", (k.web_orders || 0).toLocaleString("zh-Hant")],
    ["電商營收", money(k.web_revenue_ntd)],
    ["年預算", money(k.budget_ntd)],
  ]
    .map(([label, val]) => `<div class="kpi"><label>${label}</label><b>${val}</b></div>`)
    .join("");

  $("#platformTable").innerHTML = table(
    ["渠道", "花費", "點擊", "轉換", "歸因營收"],
    plats.map(
      (p) => `<tr>
      <td>${p.platform || "—"}</td>
      <td>${money(p.spend)}</td>
      <td>${Number(p.clicks || 0).toLocaleString("zh-Hant")}</td>
      <td>${Number(p.conversions || 0).toLocaleString("zh-Hant")}</td>
      <td>${money(p.revenue)}</td>
    </tr>`
    )
  );

  $("#leadsTable").innerHTML = table(
    ["姓名", "公司", "興趣", "狀態"],
    (d.leads || []).map(
      (l) => `<tr>
      <td><strong>${l.name || "—"}</strong><div class="muted">${l.email || ""}</div></td>
      <td>${l.company || "—"}</td>
      <td>${l.interest || "—"}</td>
      <td>${l.status || "—"}</td>
    </tr>`
    )
  );

  $("#cases").innerHTML = (d.cases || [])
    .map(
      (c) => `<article class="card">
      <span class="tag">${c.tag || "案例"}</span>
      <h4>${c.title || ""}</h4>
      <div class="metric">${c.metric || ""}</div>
      <p class="muted">${c.desc || ""}</p>
    </article>`
    )
    .join("");

  $("#testimonials").innerHTML = (d.testimonials || [])
    .map(
      (t) => `<article class="card">
      <p>「${t.quote || ""}」</p>
      <div class="muted" style="margin-top:10px">${t.name || ""} · ${t.role || ""} · ${t.company || ""}</div>
    </article>`
    )
    .join("");

  $("#audiences").innerHTML = table(
    ["代碼", "名稱", "預估規模", "軸向"],
    (d.audiences || []).map(
      (a) => `<tr>
      <td class="mono">${a.code || "—"}</td>
      <td><strong>${a.short_name || a.name || "—"}</strong><div class="muted">${a.description || ""}</div></td>
      <td>${a.estimated_size ?? "—"}</td>
      <td>${a.ansoff_axis || a.family || "—"}</td>
    </tr>`
    )
  );

  $("#products").innerHTML = table(
    ["SKU", "名稱", "分類"],
    (d.products || []).map(
      (p) => `<tr>
      <td class="mono">${p.sku || "—"}</td>
      <td>${p.name || "—"}</td>
      <td>${p.category || "—"}</td>
    </tr>`
    )
  );

  $("#pricing").innerHTML = (d.pricing || [])
    .map(
      (p) => `<div class="price ${p.highlight ? "hot" : ""}">
      <h3>${p.name || ""}</h3>
      <div class="amt">${p.price || ""}${p.period || ""}</div>
      <ul>${(p.features || []).map((f) => `<li>${f}</li>`).join("")}</ul>
      <a class="btn ${p.highlight ? "primary" : "ghost"}" href="#lead">${p.cta || "了解更多"}</a>
    </div>`
    )
    .join("");
}

function bindAI() {
  $("#btnCopy").onclick = async () => {
    const btn = $("#btnCopy");
    const out = $("#copyOut");
    btn.disabled = true;
    out.textContent = "生成中，請稍候（Qwen 推理模型可能需數十秒）…";
    try {
      const res = await api("/api/ai/copy", {
        method: "POST",
        body: JSON.stringify({
          topic: $("#copyTopic").value.trim(),
          channel: $("#copyChannel").value,
          tone: $("#copyTone").value.trim(),
        }),
      });
      out.textContent = res.copy + (res.model ? `\n\n— model: ${res.model}` : "");
    } catch (e) {
      out.textContent = "錯誤：" + e.message;
    } finally {
      btn.disabled = false;
    }
  };
}

function bindLead() {
  $("#leadForm").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = $("#leadMsg");
    msg.textContent = "送出中…";
    try {
      const res = await api("/api/leads", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          email: fd.get("email"),
          company: fd.get("company") || "",
          interest: fd.get("interest") || "",
          message: fd.get("message") || "",
        }),
      });
      msg.textContent = res.message || "已送出";
      e.target.reset();
    } catch (err) {
      msg.textContent = "失敗：" + err.message;
    }
  };
}

async function boot() {
  bindAI();
  bindLead();
  bindRag();
  bindKbForm();
  bindClinic();
  await Promise.all([
    loadInfra(),
    loadOllamaTags(),
    loadTeam(),
    loadKnowledge(),
    loadClinic(),
    loadOverview().catch((e) => {
      $("#kpis").innerHTML = `<div class="kpi"><label>錯誤</label><b style="font-size:14px">${e.message}</b></div>`;
    }),
  ]);
}

boot();
