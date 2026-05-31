const CACHE_NAME = 'mastervocab-v1';

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());

self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  self.registration.showNotification(data.title || 'MasterVocab', {
    body: data.body || 'Check your vocabulary!',
    icon: '/icon.png',
    badge: '/icon.png'
  });
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow('/'));
});
