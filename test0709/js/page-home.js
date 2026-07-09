
initLayout("home");
const s = MOCK.stats;
$("#homeCards").innerHTML = `
  <div class="summary-card"><span>模式</span><strong>${MOCK.machine.mode}</strong></div>
  <div class="summary-card"><span>模型</span><strong>${MOCK.machine.model}</strong></div>
  <div class="summary-card"><span>內嵌樣本</span><strong>${MOCK.showcase.embedded_count}</strong></div>
  <div class="summary-card"><span>抽樣合格率</span><strong>${s.yield_rate}%</strong></div>
  <div class="summary-card"><span>NG</span><strong class="text-ng">${s.ng_count}</strong></div>
  <div class="summary-card"><span>平均推論</span><strong>${s.avg_inference_ms} ms</strong></div>`;
$("#homeInfo").innerHTML = `
  <div class="detail-row"><span>匯出時間</span><span>${MOCK.exported_at}</span></div>
  <div class="detail-row"><span>權重</span><span>${MOCK.machine.model_path}</span></div>
  <div class="detail-row"><span>imgsz</span><span>${MOCK.machine.imgsz}</span></div>
  <div class="detail-row"><span>全庫樣本數</span><span>${MOCK.showcase.sample_count}</span></div>
  <div class="detail-row"><span>說明</span><span>${MOCK.showcase.disclaimer}</span></div>`;
$("#homeLinks").innerHTML = [
  ["inspection.html","檢測流程"],["stats.html","統計"],["analysis.html","數據分析"],
  ["judgment.html","判定參數"],["admin.html","系統管理"],["infra.html","資料庫後台"],
].map(([h,t]) => `<a href="${h}">${t}</a>`).join("");
