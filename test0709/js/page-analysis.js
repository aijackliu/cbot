
initLayout("analysis");
const a = MOCK.analysis, s = a.summary;
$("#summaryCards").innerHTML = `
  <div class="summary-card"><span>總數</span><strong>${s.total_inspections}</strong></div>
  <div class="summary-card"><span>合格率</span><strong>${s.yield_rate}%</strong></div>
  <div class="summary-card"><span>狀態</span><strong>${s.accuracy_status}</strong></div>
  <div class="summary-card"><span>平均信心</span><strong>${s.avg_confidence||"—"}</strong></div>`;
bars($("#pareto"), a.defect_pareto||[], "type", "count");
$("#batches").innerHTML = (a.batch_comparison||[]).map(b => `
  <div class="detail-row"><span>${b.batch_id}</span><span>${b.yield_rate}% · ${b.top_defect}</span></div>`).join("");
$("#insights").innerHTML = (a.ai_insights||[]).map(i => `
  <div class="recommendation-card ${i.level||""}"><h3>${i.title}</h3><p>${i.text}</p></div>`).join("");
