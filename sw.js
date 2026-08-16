// ========================================================
// VERSION: 1.0.1 Added DH logic
// ========================================================



// 1. NATIVE PUSH LISTENER (Bypasses Firebase's foreground/background rules)
self.addEventListener('push', function(event) {
  // Parse the raw push event from the browser
  const payload = event.data ? event.data.json() : {};
  
  // Only trigger if it contains our custom data payload
  if (payload.data && payload.data.title) {
    const notificationTitle = payload.data.title;
    const notificationOptions = {
      body: payload.data.body,
      icon: '/apple-touch-icon.png', 
      badge: '/favicon.ico',
      data: { url: payload.data.url },
      requireInteraction: true // Forces the notification to stay on screen until clicked/closed
    };

    // Force the browser to show the notification
    event.waitUntil(
      self.registration.showNotification(notificationTitle, notificationOptions)
    );
  }
});

// 2. Handle notification clicks (routes the user to the site)
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.notification.data && event.notification.data.url) {
      event.waitUntil(clients.openWindow(event.notification.data.url));
  }
});

// 3. Import Firebase Service Worker libraries
importScripts('https://www.gstatic.com/firebasejs/10.8.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.8.1/firebase-messaging-compat.js');

// 4. Initialize Firebase (Still required to generate the push tokens on the frontend)
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
