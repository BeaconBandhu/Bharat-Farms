// Regional crop news feed with impact badges.
(function () {
  var LABEL = {
    positive: { text: "Good for you", cls: "success", box: "impact-positive" },
    negative: { text: "Watch out", cls: "danger", box: "impact-negative" },
    neutral: { text: "Neutral", cls: "secondary", box: "impact-neutral" },
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  async function populateCropFilter() {
    var sel = document.getElementById("f-crop");
    var crops = {};
    try {
      var wl = await BF.api.get("/api/watchlist");
      wl.forEach(function (w) { crops[w.commodity] = 1; });
    } catch (e) {}
    try {
      var plots = await BF.api.get("/api/plots");
      for (var i = 0; i < plots.length; i++) {
        try {
          var a = await BF.api.get("/api/plots/" + plots[i].id + "/analysis");
          (a.inferred_crops || []).forEach(function (c) { crops[c.crop] = 1; });
        } catch (e) {}
      }
    } catch (e) {}
    Object.keys(crops).sort().forEach(function (c) {
      var o = document.createElement("option");
      o.value = o.textContent = c;
      sel.appendChild(o);
    });
  }

  async function load() {
    var feed = document.getElementById("feed");
    var crop = document.getElementById("f-crop").value;
    var impact = document.getElementById("f-impact").value;
    var qs = [];
    if (crop) qs.push("crop=" + encodeURIComponent(crop));
    if (impact) qs.push("impact=" + encodeURIComponent(impact));
    feed.innerHTML = '<div class="col-12 text-muted small">Loading…</div>';
    try {
      var items = await BF.api.get("/api/news" + (qs.length ? "?" + qs.join("&") : ""));
      if (!items.length) {
        feed.innerHTML =
          '<div class="col-12 text-muted small">No stored news yet. Click <strong>Fetch latest</strong> ' +
          "(needs a locked plot or a watchlist entry).</div>";
        return;
      }
      feed.innerHTML = items
        .map(function (n) {
          var L = LABEL[n.impact] || LABEL.neutral;
          return (
            '<div class="col-md-6"><div class="bf-card p-3 h-100 ' + L.box + '">' +
            '<div class="d-flex justify-content-between align-items-start gap-2">' +
            '<a class="fw-semibold text-decoration-none" href="' + esc(n.url) + '" target="_blank" rel="noopener">' + esc(n.title) + "</a>" +
            '<span class="badge bg-' + L.cls + ' flex-shrink-0">' + L.text + "</span></div>" +
            '<div class="small text-muted mt-1">' + esc(n.source || "news") + " • " + esc(n.crop) +
            (n.region_state ? " • " + esc(n.region_state) : "") +
            (n.published_at ? " • " + new Date(n.published_at).toLocaleDateString() : "") + "</div>" +
            (n.impact_reason ? '<div class="small mt-1"><em>' + esc(n.impact_reason) + "</em></div>" : "") +
            "</div></div>"
          );
        })
        .join("");
    } catch (e) {
      feed.innerHTML = '<div class="col-12 text-danger small">' + esc(e.message) + "</div>";
    }
  }

  document.getElementById("refresh").addEventListener("click", async function () {
    this.disabled = true;
    this.textContent = "Fetching…";
    try {
      var r = await BF.api.post("/api/news/refresh", {});
      BF.toast(r.new_items + " new item(s) fetched.", "success");
      await load();
    } catch (e) {
      BF.toast(e.message, "warning");
    }
    this.disabled = false;
    this.textContent = "↻ Fetch latest";
  });

  document.getElementById("f-crop").addEventListener("change", load);
  document.getElementById("f-impact").addEventListener("change", load);

  (async function () {
    await populateCropFilter();
    await load();
  })();
})();
