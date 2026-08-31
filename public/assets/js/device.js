// Stable anonymous identity for this browser (no login in v1).
(function () {
  var KEY = "bf_device_id";
  var id = null;
  try {
    id = localStorage.getItem(KEY);
  } catch (e) {}
  if (!id) {
    id =
      window.crypto && crypto.randomUUID
        ? crypto.randomUUID()
        : "dev-" + Math.random().toString(36).slice(2) + "-" + Date.now();
    try {
      localStorage.setItem(KEY, id);
    } catch (e) {}
  }
  window.BF = window.BF || {};
  window.BF.deviceId = id;
})();
