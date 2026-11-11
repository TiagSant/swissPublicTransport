/* Minimal service worker: lets the page show notifications on Android, where `new Notification()` is not allowed.
   Alarms are scheduled by the page itself (web prototype); the Android app will use the system alarm manager. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    if (list.length) return list[0].focus();
    return self.clients.openWindow('./');
  }));
});
