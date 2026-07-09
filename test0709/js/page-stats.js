
initLayout("stats");
const s = MOCK.stats;
$("#summaryCards").innerHTML = `
  <div class="summary-card"><span>檢測數</span><strong>${s.total_inspections}</strong></div>
  <div class="summary-card"><span>OK</span><strong class="text-ok">${s.ok_count}</strong></div>
  <div class="summary-card"><span>NG</span><strong class="text-ng">${s.ng_count}</strong></div>
  <div class="summary-card"><span>合格率</span><strong>${s.yield_rate}%</strong></div>
  <div class="summary-card"><span>平均 ms</span><strong>${s.avg_inference_ms}</strong></div>`;
const dist = Object.entries(s.defect_distribution||{}).map(([type,count])=>({type,count}));
bars($("#defectBars"), dist, "type", "count");
$("#batchList").innerHTML = (MOCK.batches||[]).map(b => `
  <div class="detail-row"><span>${b.batch_id}</span><span>良率 ${b.yield_rate}% · NG ${b.ng}/${b.total} · 主因 ${b.top_defect}</span></div>
`).join("");
