
initLayout("admin");
const m = MOCK.machine;
$("#adminBody").innerHTML = `
  <div class="detail-row"><span>機台</span><span>${m.machine_id}</span></div>
  <div class="detail-row"><span>模型</span><span>${m.model}</span></div>
  <div class="detail-row"><span>路徑</span><span>${m.model_path}</span></div>
  <div class="detail-row"><span>imgsz</span><span>${m.imgsz}</span></div>
  <div class="detail-row"><span>版本</span><span>${MOCK.version}</span></div>`;
$("#histBody").innerHTML = (MOCK.history||[]).map(h => `
  <tr><td>${h.inspection_id}</td><td>${h.sample_id}</td><td>${h.ai_result}</td>
  <td>${h.defect_type}</td><td>${h.confidence}</td><td>${h.inference_ms}</td></tr>`).join("");
