
initLayout("inspection");
const $$ = (s) => [...document.querySelectorAll(s)];
let idx = 0;
const samples = MOCK.samples;

function renderList() {
  $("#sampleList").innerHTML = samples.map((s, i) => `
    <div class="sample-list-item ${i===idx?"active":""}" data-i="${i}">
      <span>${s.sample_id} · ${s.name.replace("自有-","")}</span>
      <span class="${s.ai_result==="NG"?"ng":"ok"}">${s.ai_result}</span>
    </div>`).join("");
  $$(".sample-list-item").forEach((el) => el.addEventListener("click", () => { idx = +el.dataset.i; show(); }));
}

function show() {
  const s = samples[idx];
  if (!s) return;
  renderList();
  $("#rawImg").src = "assets/raw/" + s.raw_file;
  $("#resultImg").src = s.result_file ? ("assets/results/" + s.result_file) : "";
  const defs = (s.defects||[]).map(d =>
    `<div class="detail-row"><span>${d.class_name_zh}</span><span>conf ${d.confidence}</span></div>`
  ).join("") || "<p class=\"empty-hint\">無瑕疵框</p>";
  $("#inspectDetail").innerHTML = `
    <div class="detail-row"><span>結果</span><span class="${s.ai_result==="NG"?"badge-ng":"badge-ok"}">${s.ai_result}</span></div>
    <div class="detail-row"><span>瑕疵</span><span>${s.defect_type || "—"} × ${s.defect_count}</span></div>
    <div class="detail-row"><span>信心</span><span>${s.confidence}</span></div>
    <div class="detail-row"><span>推論</span><span>${s.inference_ms} ms</span></div>
    <div class="detail-row"><span>批次</span><span>${s.batch_id}</span></div>
    <h3 style="margin:12px 0 6px">偵測明細</h3>${defs}`;
}
$("#prevBtn").onclick = () => { idx = (idx - 1 + samples.length) % samples.length; show(); };
$("#nextBtn").onclick = () => { idx = (idx + 1) % samples.length; show(); };
show();
