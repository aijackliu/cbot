const DEFECT_TYPES = ["裂痕", "刮痕", "凹陷"];
const NOTIF_ICONS = { alert: "⚠", inspection: "🔍", system: "⚙" };
const priorityLabel = { success: "良好", warning: "注意", info: "資訊" };

const PAGE_INIT = {
  home: initHome,
  inspection: initInspection,
  judgment: initJudgment,
  stats: initStats,
  analysis: initAnalysis,
  suggestions: initSuggestions,
  notifications: initNotifications,
  admin: initAdmin,
  retrain: initRetrain,
  "retrain-dataset": initRetrainDataset,
  "retrain-train": initRetrainTrain,
};

function initHome() {
  const m = MOCK.machine;
  const s = MOCK.showcase;
  $("#homeSummary").textContent =
    `機台 ${m.machine_id} · 工單預設 ${m.default_work_order} · 員工 ${m.default_employee_id} · 樣本 ${s.sample_count} 組（NG ${s.ng_sample_count}）`;
}

function initInspection() {
  const m = MOCK.machine;
  const bs = MOCK.batchSummary;
  const img = "assets/demo-ng.svg";

  $("#machineId").value = m.machine_id;
  $("#machineBadge").textContent = `機台 ${m.machine_id}`;
  $("#workOrder").value = m.default_work_order;
  $("#employeeId").value = m.default_employee_id;
  $("#batchId").value = m.default_batch_id;
  $("#setupPanel").classList.add("ready");
  $("#setupHint").textContent = `展示狀態：批次 BATCH-DEMO-01 已完成（120 組，NG 20 筆）。`;
  $("#setupHint").classList.add("ready");

  $$(".wf-step").forEach((el) => {
    const s = parseInt(el.dataset.step, 10);
    el.classList.remove("active");
    el.classList.add(s <= 5 ? "done" : "");
    if (s === 5) el.classList.add("active");
  });

  $("#displayImage").src = img;
  $("#displayImage").classList.remove("hidden");
  $("#placeholder").classList.add("hidden");
  $("#resultBadge").textContent = "NG";
  $("#resultBadge").className = "result-badge ng";
  $("#resultBadge").classList.remove("hidden");

  $("#sampleGallery").innerHTML = `
    <p class="sample-stats">共 <strong>120</strong> 組展示樣本，其中 <strong class="text-ng">20</strong> 組含瑕疵。<br>
    展示版顯示批次完成後狀態。</p>`;

  $("#detailContent").innerHTML = `
    <div class="batch-summary">
      <p class="batch-summary-title">批次檢測完成</p>
      <div class="detail-row"><span>檢測總數</span><strong>${bs.total}</strong></div>
      <div class="detail-row"><span>OK（未紀錄）</span><strong class="text-ok">${bs.ok_count}</strong></div>
      <div class="detail-row"><span>NG（已紀錄）</span><strong class="text-ng">${bs.ng_count}</strong></div>
      <div class="detail-row"><span>合格率</span><strong>${bs.yield_rate}%</strong></div>
    </div>`;

  const dt = bs.defect_totals;
  $("#defectTotals").innerHTML = `
    <h3>批次瑕疵總計</h3>
    <div class="defect-totals-grid">
      <div class="total-all"><span>合計</span><strong>${dt.total} 個</strong></div>
      ${DEFECT_TYPES.map((t) => `<div><span>${t}</span><span>${dt[t]} 個</span></div>`).join("")}
    </div>`;
  $("#defectTotals").classList.remove("hidden");

  const ng = bs.last_ng;
  $("#judgmentPanel").innerHTML = `
    <h3>參數判定說明</h3>
    <p class="judgment-reason">${ng.judgment_reason}</p>
    <a href="judgment.html" class="btn btn-secondary btn-sm">調整判定參數</a>`;
  $("#judgmentPanel").classList.remove("hidden");

  $("#historyBody").innerHTML = MOCK.ngRecords.map((r) => `
    <tr>
      <td>${r.sample_id}</td>
      <td>${formatTime(r.inspection_time)}</td>
      <td>${r.machine_id}</td>
      <td>${r.work_order}</td>
      <td>${r.employee_id}</td>
      <td>${r.batch_id}</td>
      <td><span class="badge ng">${r.ai_result}</span></td>
      <td>${r.defect_type}</td>
      <td>${r.qualifying_count}/${r.total_detected}</td>
      <td>${r.inference_ms}</td>
    </tr>`).join("");
}

function initJudgment() {
  const j = MOCK.judgment;
  $("#failCount").value = j.fail_defect_count_exceeds;
  $("#failArea").value = j.fail_min_area_mm2;
  $("#confThreshold").value = j.confidence_threshold;
  $("#pxPerMm").value = j.px_per_mm;
  $$("#typeChecks input").forEach((el) => {
    el.checked = j.enabled_types.includes(el.value);
  });
  $("#ruleCount").textContent = `> ${j.fail_defect_count_exceeds}`;
  $("#rulePreview").innerHTML = `
    <p>目前規則：面積 ≥ <strong>${j.fail_min_area_mm2} mm²</strong> 且信心值 ≥ <strong>${j.confidence_threshold}</strong> 的瑕疵才計入；
    計入數量 <strong>超過 ${j.fail_defect_count_exceeds} 個</strong> 判定 <span class="badge ng">NG</span>。</p>`;
  $("#previewBody").innerHTML = j.previews.map((p) => `
    <tr>
      <td>${p.sample_id}</td>
      <td>${p.total_detected}</td>
      <td>${p.qualifying_count}</td>
      <td>${p.max_area_mm2}</td>
      <td><span class="badge ${p.result.toLowerCase()}">${p.result}</span></td>
      <td>${p.reason}</td>
    </tr>`).join("");
}

function initStats() {
  const s = MOCK.stats;
  $("#totalOk").textContent = s.ok_count;
  $("#totalNg").textContent = s.ng_count;
  $("#totalAll").textContent = s.total_inspections;
  $("#totalYield").textContent = s.yield_rate + "%";
  $("#todayOk").textContent = s.today_ok;
  $("#todayNg").textContent = s.today_ng;
  $("#todayYield").textContent = s.today_yield + "%";
  $("#yieldFill").style.width = s.today_yield + "%";
  $("#avgMs").textContent = s.avg_inference_ms;
  $("#fps").textContent = s.fps;
  renderDefectBars($("#defectBars"), s.defect_distribution);
  $("#batchTable").innerHTML = MOCK.batches.map((b) => `
    <tr>
      <td>${b.batch_id}</td><td>${b.total}</td><td>${b.ok}</td><td>${b.ng}</td>
      <td>${b.yield_rate}%</td>
      <td><div class="yield-bar inline"><div class="yield-fill" style="width:${b.yield_rate}%"></div></div></td>
    </tr>`).join("");
}

function initAnalysis() {
  const data = MOCK.analysis;
  const s = data.summary;
  $("#summaryCards").innerHTML = `
    <div class="summary-card"><span>檢測總數</span><strong>${s.total_inspections}</strong></div>
    <div class="summary-card"><span>合格率</span><strong>${s.yield_rate}%</strong></div>
    <div class="summary-card"><span>準確狀態</span><strong class="text-warn">${s.accuracy_status}</strong></div>
    <div class="summary-card"><span>平均信心值</span><strong>${s.avg_confidence}</strong></div>`;
  renderChartBars($("#paretoChart"), data.defect_pareto, "type", "count");
  renderChartBars($("#confChart"), data.confidence_distribution, "range", "count");
  const trendMax = Math.max(...data.hourly_trend.map((t) => t.yield_rate), 1);
  $("#trendChart").innerHTML = data.hourly_trend.map((t) => `
    <div class="trend-bar">
      <div class="bar" style="height:${(t.yield_rate / trendMax) * 70}px" title="${t.yield_rate}%"></div>
      <span class="label">${t.hour}</span>
    </div>`).join("");
  $("#batchCompare").innerHTML = data.batch_comparison.map((b) => `
    <div class="batch-compare-row">
      <span class="batch-name">${b.batch_id}</span>
      <div class="yield-bar inline"><div class="yield-fill" style="width:${b.yield_rate}%"></div></div>
      <span>${b.yield_rate}%</span>
      <span class="text-dim">主要: ${b.top_defect}</span>
    </div>`).join("");
  const js = data.judgment_stats;
  $("#judgmentStats").innerHTML = `
    <div class="review-stat-grid">
      <div class="review-stat"><strong>${js.auto_ok}</strong><span>參數判定 OK</span></div>
      <div class="review-stat"><strong>${js.auto_ng}</strong><span>參數判定 NG</span></div>
      <div class="review-stat"><strong>${js.auto_ok + js.auto_ng}</strong><span>自動判定總數</span></div>
      <div class="review-stat"><strong>${js.legacy_pending}</strong><span>舊資料待處理</span></div>
    </div>`;
}

function initSuggestions() {
  const data = MOCK.suggestions;
  const s = data.summary;
  $("#summaryCards").innerHTML = `
    <div class="summary-card"><span>累計合格率</span><strong>${s.yield_rate}%</strong></div>
    <div class="summary-card"><span>NG 數量</span><strong class="text-ng">${s.ng_count}</strong></div>
    <div class="summary-card"><span>目標準確率</span><strong>≥90%</strong></div>
    <div class="summary-card"><span>狀態</span><strong>${s.accuracy_status}</strong></div>`;
  $("#riskAlerts").innerHTML = data.risk_alerts.map((a) =>
    `<div class="alert-item ${a.severity}">${a.message}</div>`).join("");
  $("#recommendations").innerHTML = data.recommendations.map((r) => `
    <div class="recommendation-card ${r.priority}">
      <div class="rec-header">
        <span class="rec-priority">${priorityLabel[r.priority] || r.priority}</span>
        <h3>${r.title}</h3>
      </div>
      <p class="rec-desc">${r.description}</p>
      <div class="rec-action"><strong>建議行動：</strong>${r.action}</div>
    </div>`).join("");
}

function initNotifications() {
  const data = MOCK.notifications;
  $("#notifTotal").textContent = data.total;
  $("#notifUnread").textContent = data.unread_count;
  $("#notifRecipients").textContent = data.notification_emails.join("、");
  const sevClass = { high: "high", medium: "medium", low: "low" };
  $("#notifList").innerHTML = data.items.map((n) => `
    <div class="notif-card ${n.read ? "read" : "unread"} ${sevClass[n.severity] || ""}">
      <div class="notif-icon ${n.type || ""}">${NOTIF_ICONS[n.type] || "📌"}</div>
      <div class="notif-body">
        <div class="notif-title">${n.title} ${!n.read ? '<span class="unread-dot"></span>' : ""}</div>
        <div class="notif-msg">${n.message}</div>
        <div class="notif-time">${formatTime(n.time)}</div>
      </div>
      ${n.link ? `<a href="${n.link}" class="btn btn-secondary btn-sm">前往處理</a>` : ""}
    </div>`).join("");
}

function initAdmin() {
  const s = MOCK.settings;
  $("#machineId").value = s.machine_id;
  $("#defaultWorkOrder").value = s.default_work_order;
  $("#defaultEmployeeId").value = s.default_employee_id;
  $("#defaultBatchId").value = s.default_batch_id;
  $("#notificationEmails").value = s.notification_emails.join("\n");
  $("#settingsHint").textContent = "展示版：以下為固定示意資料。";
  $("#settingsHint").classList.add("ready");
  $("#batchRunsBody").innerHTML = MOCK.batchRuns.map((r) => `
    <tr>
      <td><code>${r.run_id}</code></td>
      <td>${r.machine_id}</td>
      <td>${r.work_order}</td>
      <td>${r.employee_id}</td>
      <td>${r.batch_label}</td>
      <td>${r.total}</td>
      <td>${r.ok_count}</td>
      <td>${r.ng_count}</td>
      <td>${r.yield_rate}%</td>
      <td>${formatTime(r.completed_at)}</td>
      <td class="admin-actions">
        <button type="button" class="btn btn-secondary btn-sm" data-demo-action="展示版：編輯功能僅供預覽">編輯</button>
        <button type="button" class="btn btn-secondary btn-sm text-ng" data-demo-action="展示版：刪除功能僅供預覽">刪除</button>
      </td>
    </tr>`).join("");
}

function initRetrain() {
  const status = MOCK.retrain.status;
  const m = status.metrics;
  $("#currentModel").innerHTML = `
    <div class="detail-row"><span>版本</span><strong>${status.current_version}</strong></div>
    <div class="detail-row"><span>架構</span><span>${status.model_architecture}</span></div>
    <div class="detail-row"><span>部署日期</span><span>${status.deployed_at.slice(0, 10)}</span></div>
    <div class="detail-row"><span>Precision</span><span>${(m.precision * 100).toFixed(1)}%</span></div>
    <div class="detail-row"><span>Recall</span><span>${(m.recall * 100).toFixed(1)}%</span></div>
    <div class="detail-row"><span>mAP50</span><span>${(m.map50 * 100).toFixed(1)}%</span></div>
    <div class="detail-row"><span>待納入樣本</span><span>${status.pending_samples} 張</span></div>`;
  const d = status.dataset;
  $("#datasetInfo").innerHTML = `
    <div class="detail-row"><span>總影像</span><strong>${d.total_images.toLocaleString()}</strong></div>
    <div class="detail-row"><span>Train</span><span>${d.train.toLocaleString()}</span></div>
    <div class="detail-row"><span>Val</span><span>${d.val.toLocaleString()}</span></div>
    <div class="detail-row"><span>Test</span><span>${d.test.toLocaleString()}</span></div>
    <div class="detail-row"><span>類別</span><span>${d.classes.join(", ")}</span></div>`;
  $("#historyTable").innerHTML = MOCK.retrain.history.map((h) => `
    <tr>
      <td><strong>${h.version}</strong></td>
      <td><span class="badge ${h.status === "deployed" ? "ok" : ""}">${h.status}</span></td>
      <td>${h.trained_at}</td>
      <td>${h.employee_id}</td>
      <td>${h.dataset_size.toLocaleString()}</td>
      <td>${(h.precision * 100).toFixed(1)}%</td>
      <td>${(h.recall * 100).toFixed(1)}%</td>
      <td>${(h.map50 * 100).toFixed(1)}%</td>
      <td>${h.notes}</td>
    </tr>`).join("");
}

function initRetrainDataset() {
  const labels = ["裂痕", "刮痕", "凹陷", "正常"];
  $("#labelFilters").innerHTML = labels.map((l, i) => `
    <label><input type="checkbox" value="${l}" ${i < 3 ? "checked" : ""} disabled> ${l}</label>`).join("");
  $("#selectionCount").textContent = "已選 8 張";
  $("#goTrainBtn").disabled = false;
  $("#datasetGrid").innerHTML = MOCK.retrain.datasetImages.map((img) => `
    <div class="dataset-thumb-demo ${img.selected ? "selected" : ""}">
      <span>${img.id}</span>
      <span class="thumb-label">${img.label}</span>
    </div>`).join("");
}

function initRetrainTrain() {
  const job = MOCK.retrain.trainJob;
  $("#employeeId").value = job.employee_id;
  $("#epochs").value = job.epochs;
  $("#retrainNote").value = job.note;
  $("#employeeHint").textContent = `展示版：已選 ${job.selected_count} 張，Label：${job.labels.join("、")}`;
  $("#employeeHint").classList.add("ready");
  $("#selectionSummary").innerHTML = `
    <div class="detail-row"><span>已選圖面</span><strong>${job.selected_count} 張</strong></div>
    <div class="detail-row"><span>Label</span><span>${job.labels.join("、")}</span></div>
    <div class="detail-row"><span>Epochs</span><span>${job.epochs}</span></div>`;
  $("#startTrainBtn").classList.add("hidden");
  $("#jobPanel").classList.remove("hidden");
  $("#jobFill").style.width = "100%";
  $("#jobStatus").textContent = "訓練完成";
  $("#jobMeta").innerHTML = `<div class="detail-row"><span>版本</span><strong>${job.version}</strong></div>`;
  $("#jobMetrics").innerHTML = `
    <div class="detail-row"><span>Precision</span><span>${(job.metrics.precision * 100).toFixed(1)}%</span></div>
    <div class="detail-row"><span>Recall</span><span>${(job.metrics.recall * 100).toFixed(1)}%</span></div>
    <div class="detail-row"><span>mAP50</span><span>${(job.metrics.map50 * 100).toFixed(1)}%</span></div>`;
  $("#deployPanel").classList.remove("hidden");
  $("#deployResult").textContent = "展示版：部署狀態為示意";
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  PAGE_INIT[page]?.();
});