if (document.querySelector(".preview-banner")) {
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      window.alert("Это предпросмотр верстки. Данные не отправляются.");
    });
  });
}

var menuButton = document.querySelector(".menu-toggle");
var mainNavigation = document.querySelector(".main-nav");
if (menuButton && mainNavigation) {
  menuButton.addEventListener("click", function () {
    var isOpen = mainNavigation.classList.toggle("is-open");
    menuButton.setAttribute("aria-expanded", String(isOpen));
    menuButton.textContent = isOpen ? "×" : "☰";
  });
  mainNavigation.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      mainNavigation.classList.remove("is-open");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.textContent = "☰";
    });
  });
}

document.querySelectorAll("[data-copy-target]").forEach(function (button) {
  button.addEventListener("click", function () {
    var target = document.getElementById(button.getAttribute("data-copy-target"));
    if (target) {
      navigator.clipboard.writeText(target.value);
    }
  });
});

document.querySelectorAll("[data-reveal-target]").forEach(function (button) {
  button.addEventListener("click", function () {
    var target = document.getElementById(button.getAttribute("data-reveal-target"));
    if (target) {
      target.hidden = false;
      button.hidden = true;
    }
  });
});

var pushButton = document.querySelector("[data-push-subscribe]");
if (pushButton) {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    pushButton.hidden = true;
  } else {
    pushButton.addEventListener("click", function () {
      pushButton.disabled = true;
      subscribeToPush()
        .then(function () {
          pushButton.textContent = "Уведомления включены";
        })
        .catch(function (error) {
          pushButton.disabled = false;
          window.alert("Не получилось включить уведомления: " + error.message);
        });
    });
  }
}

function urlBase64ToUint8Array(base64String) {
  var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  var rawData = window.atob(base64);
  var outputArray = new Uint8Array(rawData.length);
  for (var i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

async function subscribeToPush() {
  var permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("разрешение не дано");
  }
  var registration = await navigator.serviceWorker.register("/sw.js");
  var keyResponse = await fetch("/push/vapid-public-key");
  var keyData = await keyResponse.json();
  var subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(keyData.key),
  });
  var subscriptionJson = subscription.toJSON();
  await fetch("/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: subscriptionJson.endpoint,
      keys: subscriptionJson.keys,
    }),
  });
}
