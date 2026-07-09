
initLayout("retrain");
const r = MOCK.retrain;
$("#retrainBody").innerHTML = `
  <div class="detail-row"><span>目前版本</span><span>${r.current_version}</span></div>
  <div class="detail-row"><span>架構</span><span>${r.model_architecture}</span></div>
  <div class="detail-row"><span>資料集張數</span><span>${r.dataset.total_images}</span></div>
  <div class="detail-row"><span>類別</span><span>${r.dataset.classes.join(" / ")}</span></div>
  <p class="empty-hint" style="margin-top:12px">${r.note}</p>
  <p class="text-dim">訓練指令：python scripts/train.py --weights yolo26m.pt --imgsz 1024</p>`;
