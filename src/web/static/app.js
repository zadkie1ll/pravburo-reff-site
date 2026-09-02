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
