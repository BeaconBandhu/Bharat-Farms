// Stock-style crop market: ticker, watchlist table with sparklines, quote lookup.
(function () {
  var STATES = [
    "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
  ];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  ["w-state", "q-state"].forEach(function (idv) {
    var sel = document.getElementById(idv);
    STATES.forEach(function (s) {
      var o = document.createElement("option");
      o.value = o.textContent = s;
      sel.appendChild(o);
    });
  });

  async function loadCommodities() {
    try {
      var r = await BF.api.get("/api/commodities");
      var dl = document.getElementById("commodity-list");
      dl.innerHTML = r.commodities.map(function (c) { return "<option value='" + esc(c) + "'>"; }).join("");
    } catch (e) {}
  }

  async function loadTicker() {
    var t = document.getElementById("ticker");
    try {
      var wl = await BF.api.get("/api/watchlist");
      if (!wl.length) { t.innerHTML = '<span class="ticker-item text-muted">Watchlist empty — add a crop below</span>'; return; }
      var items = wl.map(function (w) {
        var q = w.quote;
        if (!q) return '<span class="ticker-item">' + esc(w.commodity) + " —</span>";
        var cls = BF.fmt.dir(q.change_pct);
        return (
          '<span class="ticker-item">' + esc(w.commodity).toUpperCase() + " " +
          BF.fmt.inr(q.modal_price) + ' <span class="' + cls + '">' +
          BF.fmt.arrow(q.change_pct) + " " + BF.fmt.pct(q.change_pct) + "</span></span>"
        );
      });
      t.innerHTML = items.join("") + items.join("");
    } catch (e) {
      t.innerHTML = '<span class="ticker-item text-muted">Prices unavailable</span>';
    }
  }

  async function loadWatchlist() {
    var body = document.getElementById("wl-body");
    try {
      var wl = await BF.api.get("/api/watchlist");
      if (!wl.length) { body.innerHTML = '<tr><td colspan="6" class="text-muted small">Nothing yet.</td></tr>'; return; }
      body.innerHTML = wl
        .map(function (w, i) {
          var q = w.quote;
          var chg = q && q.change_pct != null
            ? '<span class="' + BF.fmt.dir(q.change_pct) + '">' + BF.fmt.arrow(q.change_pct) + " " + BF.fmt.pct(q.change_pct) + "</span>"
            : "—";
          return (
            "<tr><td><strong>" + esc(w.commodity) + "</strong></td>" +
            "<td class='small text-muted'>" + (esc(w.state) || "All India") + "</td>" +
            "<td class='text-end'>" + (q ? BF.fmt.inr(q.modal_price) : "—") + "</td>" +
            "<td class='text-end'>" + chg + "</td>" +
            "<td style='width:160px'><canvas id='wl-spark-" + i + "' height='36'></canvas></td>" +
            "<td class='text-end'><button class='btn btn-sm btn-outline-danger' data-del='" + w.id + "'>✕</button></td></tr>"
          );
        })
        .join("");
      wl.forEach(function (w, i) { spark("wl-spark-" + i, w.commodity, w.state); });
      body.querySelectorAll("[data-del]").forEach(function (b) {
        b.addEventListener("click", async function () {
          await BF.api.del("/api/watchlist/" + b.dataset.del);
          refreshAll();
        });
      });
    } catch (e) {
      body.innerHTML = '<tr><td colspan="6" class="text-danger small">' + esc(e.message) + "</td></tr>";
    }
  }

  async function spark(canvasId, commodity, state) {
    try {
      var st = state ? "&state=" + encodeURIComponent(state) : "";
      var h = await BF.api.get("/api/prices/" + encodeURIComponent(commodity) + "/history?days=45" + st);
      if (!h.length) return;
      new Chart(document.getElementById(canvasId), {
        type: "line",
        data: { labels: h.map(function (p) { return p.arrival_date; }),
          datasets: [{ data: h.map(function (p) { return p.modal_price; }), borderColor: "#1b7f4d", pointRadius: 0, tension: 0.3 }] },
        options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } },
      });
    } catch (e) {}
  }

  document.getElementById("w-add").addEventListener("click", async function () {
    var c = document.getElementById("w-commodity").value.trim();
    if (!c) return;
    try {
      await BF.api.post("/api/watchlist", { commodity: c, state: document.getElementById("w-state").value });
      document.getElementById("w-commodity").value = "";
      refreshAll();
    } catch (e) { BF.toast(e.message, "danger"); }
  });

  var qChart = null;
  document.getElementById("q-go").addEventListener("click", async function () {
    var c = document.getElementById("q-commodity").value.trim();
    var s = document.getElementById("q-state").value;
    var out = document.getElementById("q-result");
    if (!c) return;
    out.innerHTML = '<span class="text-muted small">Fetching…</span>';
    try {
      var q = await BF.api.get("/api/prices?commodity=" + encodeURIComponent(c) + (s ? "&state=" + encodeURIComponent(s) : ""));
      var cls = BF.fmt.dir(q.change_pct);
      out.innerHTML =
        '<div class="quote-value">' + BF.fmt.inr(q.modal_price) + '<span class="fs-6 text-muted">/qtl</span> ' +
        '<span class="' + cls + ' fs-6">' + BF.fmt.arrow(q.change_pct) + " " + BF.fmt.pct(q.change_pct) + "</span></div>" +
        '<div class="small text-muted">' + esc(q.commodity) + " • " + (esc(q.state) || "All India") +
        " • " + esc(q.market) + " • " + q.arrival_date + " • range " + BF.fmt.inr(q.min_price) + "–" + BF.fmt.inr(q.max_price) + "</div>";
      var h = await BF.api.get("/api/prices/" + encodeURIComponent(c) + "/history?days=90" + (s ? "&state=" + encodeURIComponent(s) : ""));
      if (qChart) qChart.destroy();
      qChart = new Chart(document.getElementById("q-chart"), {
        type: "line",
        data: { labels: h.map(function (p) { return p.arrival_date; }),
          datasets: [{ label: c, data: h.map(function (p) { return p.modal_price; }),
            borderColor: "#1b7f4d", backgroundColor: "rgba(27,127,77,.12)", fill: true, pointRadius: 0, tension: 0.3 }] },
        options: { plugins: { legend: { display: false } } },
      });
    } catch (e) {
      out.innerHTML = '<span class="text-danger small">' + esc(e.message) + "</span>";
    }
  });

  async function loadSuggestions() {
    try {
      var plots = await BF.api.get("/api/plots");
      var pairs = [];
      for (var i = 0; i < plots.length; i++) {
        try {
          var a = await BF.api.get("/api/plots/" + plots[i].id + "/analysis");
          (a.inferred_crops || []).forEach(function (c) {
            pairs.push({ crop: c.crop, state: plots[i].state || "" });
          });
        } catch (e) {}
      }
      if (!pairs.length) return;
      var seen = {};
      var html = pairs
        .filter(function (p) { var k = p.crop + "|" + p.state; if (seen[k]) return false; seen[k] = 1; return true; })
        .slice(0, 8)
        .map(function (p) {
          return '<button class="btn btn-sm btn-light border me-1 mb-1" data-crop="' + esc(p.crop) + '" data-state="' + esc(p.state) + '">+ ' + esc(p.crop) + "</button>";
        })
        .join("");
      var box = document.getElementById("w-suggest");
      box.innerHTML = '<div class="text-muted mb-1">From your plots:</div>' + html;
      box.querySelectorAll("[data-crop]").forEach(function (b) {
        b.addEventListener("click", async function () {
          await BF.api.post("/api/watchlist", { commodity: b.dataset.crop, state: b.dataset.state });
          refreshAll();
        });
      });
    } catch (e) {}
  }

  function refreshAll() {
    loadTicker();
    loadWatchlist();
    loadSuggestions();
  }

  loadCommodities();
  refreshAll();
})();
