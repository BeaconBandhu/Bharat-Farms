// Shared chrome: nav active state + mount the voice assistant widget.
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var here = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".navbar-bf .nav-link").forEach(function (a) {
      var target = (a.getAttribute("href") || "").split("/").pop();
      if (target === here) a.classList.add("active");
    });
    if (window.BF && BF.mountVoiceWidget) BF.mountVoiceWidget();
  });
})();
