
initLayout("infra");
const i = MOCK.infra;
$("#infraBody").innerHTML = Object.entries(i).map(([k,v]) => `
  <div class="detail-row"><span>${k}</span><span>${v}</span></div>`).join("");
