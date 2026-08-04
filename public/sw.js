// Service Worker für das Monatsbrett — bewusst minimal: nur Push und
// Notification-Klick, KEIN Fetch-Caching (verhindert Stale-App-Probleme;
// Offline-Shell kommt später mit Bedacht).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch {}
  e.waitUntil(self.registration.showNotification(data.title || 'Das Monatsbrett', {
    body: data.body || 'Dein Wurf wartet.',
    icon: '/assets/icon-192.png',
    badge: '/assets/icon-192.png',
    data: { url: data.url || '/play' },
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/play';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
    for (const w of wins) {
      if (w.url.includes('/play') && 'focus' in w) return w.focus();
    }
    return self.clients.openWindow(url);
  }));
});
