
initLayout("judgment");
const j = MOCK.judgment;
$("#judgmentBody").innerHTML = Object.entries(j).map(([k,v]) => `
  <div class="detail-row"><span>${k}</span><span>${Array.isArray(v)?v.join("、"):v}</span></div>`).join("");
