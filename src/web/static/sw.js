self.addEventListener("push", function (event) {
  var data = { title: "Правбюро", body: "" };
  try {
    data = event.data.json();
  } catch (e) {
    data.body = event.data ? event.data.text() : "";
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Правбюро", {
      body: data.body || "",
    })
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  event.waitUntil(clients.openWindow("/cabinet"));
});
