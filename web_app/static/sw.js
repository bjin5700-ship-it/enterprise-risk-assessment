/* ERM 移动端后台推送 — 轮询未读告警并显示系统通知 */
const POLL_MS = 90000;
let lastUnread = 0;

self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(self.clients.claim());
});

async function pollNotifications() {
  try {
    const resp = await fetch("/erm/api/notifications?unread=1");
    if (!resp.ok) return;
    const data = await resp.json();
    const unread = data.unread_count || 0;
    const items = data.notifications || [];
    if (unread > lastUnread && items.length) {
      const n = items[0];
      await self.registration.showNotification(n.title || "风险告警", {
        body: `${n.company_name || ""}: ${n.message || ""}`,
        tag: n.id || "erm-alert",
        data: { url: "/" },
        requireInteraction: unread > 3,
      });
    }
    lastUnread = unread;
  } catch (_) {}
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      if (list.length) return list[0].focus();
      return self.clients.openWindow(event.notification.data?.url || "/");
    })
  );
});

setInterval(pollNotifications, POLL_MS);
pollNotifications();
