
initLayout("notifications");
$("#notifBody").innerHTML = (MOCK.notifications.notifications||[]).map(n => `
  <div class="notif-item">
    <strong>${n.title}</strong>
    <div>${n.message}</div>
    <div class="text-dim">${n.time}</div>
  </div>`).join("") || '<p class="empty-hint">無通知</p>';
