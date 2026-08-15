// Import Firebase Service Worker libraries (using compat versions for background scripts)
importScripts('https://www.gstatic.com/firebasejs/10.8.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.8.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyC1siO6niUMzrm_RXpcDxFDiLQ8xjSAAkw",
  authDomain: "nbastartingfive-8b420.firebaseapp.com",
  databaseURL: "https://nbastartingfive-8b420-default-rtdb.firebaseio.com",
  projectId: "nbastartingfive-8b420",
  storageBucket: "nbastartingfive-8b420.firebasestorage.app",
  messagingSenderId: "348101109842",
  appId: "1:348101109842:web:8713e5ba9b0bc9691ed78b"
});

const messaging = firebase.messaging();

// Handle background messages
// This runs if the user's browser is closed or they are on a different tab
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);

  // 🚀 FIXED: Pull the title and body directly from the 'data' payload 
  const notificationTitle = payload.data.title || 'MLB9 Lineup Alert';
  const notificationOptions = {
    body: payload.data.body,
    icon: '/apple-touch-icon.png', // The icon that appears in the push
    badge: '/favicon.ico',
    data: { url: payload.data.url } // Pass URL data to click events
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification clicks (e.g., routing the user to the game page)
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.notification.data && event.notification.data.url) {
      event.waitUntil(clients.openWindow(event.notification.data.url));
  }
});
