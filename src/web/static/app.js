if (document.querySelector(".preview-banner")) {
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      window.alert("Это предпросмотр верстки. Данные не отправляются.");
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
