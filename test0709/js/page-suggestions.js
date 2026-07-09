
initLayout("suggestions");
const s = MOCK.suggestions.summary;
$("#summaryCards").innerHTML = `
  <div class="summary-card"><span>合格率</span><strong>${s.yield_rate}%</strong></div>
  <div class="summary-card"><span>NG</span><strong class="text-ng">${s.ng_count}</strong></div>
  <div class="summary-card"><span>狀態</span><strong>${s.accuracy_status}</strong></div>`;
$("#recs").innerHTML = (MOCK.suggestions.recommendations||[]).map(r => `
  <div class="recommendation-card ${r.priority}">
    <h3>${r.title}</h3><p>${r.description}</p>
    <div class="rec-action"><strong>建議行動：</strong>${r.action}</div>
  </div>`).join("");
