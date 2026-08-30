// Locked-plot report: satellite strip, NDVI chart, crop history, price outlook.
(function () {
  var id = new URLSearchParams(location.search).get("id");
  if (!id) { location.href = "map.html"; return; }
  BF.currentPlotId = Number(id);

  var confBadge = { high: "success", medium: "warning", low: "secondary" };
  var dirBadge = { up: "badge-up", down: "badge-down", flat: "badge-flat", unknown: "badge-flat" };
  var ndviChart = null;
  var plot = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  async function loadPlot() {
    plot = await BF.api.get("/api/plots/" + id);
    document.getElementById("p-name").textContent = plot.name;
    document.getElementById("p-meta").textContent =
      (plot.district || "?") + ", " + (plot.state || "?") +
      " • " + plot.area_hectares.toFixed(2) + " ha • locked " +
      new Date(plot.locked_at).toLocaleDateString();
    loadWeather(plot.centroid_lat, plot.centroid_lon);
  }

  async function loadWeather(lat, lon) {
    var el = document.getElementById("weather");
    try {
      var w = await BF.api.get("/api/weather?lat=" + lat + "&lon=" + lon);
      el.innerHTML =
        "<strong>" + esc(w.location) + "</strong> — " + w.current.temp + "°C, " +
        esc(w.current.condition) + ", humidity " + w.current.humidity + "%<br>" +
        w.forecast
          .map(function (d) {
            return d.date.slice(5) + ": " + d.temp_min + "–" + d.temp_max + "°C " + esc(d.condition);
          })
          .join(" &nbsp;|&nbsp; ");
    } catch (e) {
      el.textContent = e.status === 503 ? "Weather needs OPENWEATHER_API_KEY." : "Weather unavailable.";
    }
  }

  function renderSat(thumbs) {
    var el = document.getElementById("sat");
    if (!thumbs || !thumbs.length) { el.innerHTML = '<span class="text-muted small">No imagery available.</span>'; return; }
    el.innerHTML = thumbs
      .map(function (t) {
        return (
          "<figure><img loading='lazy' src='" + esc(t.url) + "' alt='" + esc(t.date) + "' " +
          "onerror=\"this.style.visibility='hidden'\"><figcaption>" + esc(t.date) + "</figcaption></figure>"
        );
      })
      .join("");
  }

  function renderNdvi(series) {
    if (!series || !series.length) return;
    var ctx = document.getElementById("ndvi");
    if (ndviChart) ndviChart.destroy();
    ndviChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: series.map(function (p) { return p.date; }),
        datasets: [{
          label: "NDVI",
          data: series.map(function (p) { return p.ndvi; }),
          borderColor: "#1b7f4d",
          backgroundColor: "rgba(27,127,77,.15)",
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        }],
      },
      options: { plugins: { legend: { display: false } }, scales: { y: { suggestedMin: 0, suggestedMax: 0.8 } } },
    });
  }

  function renderCrops(crops, summary) {
    var el = document.getElementById("crops");
    if (!crops || !crops.length) { el.innerHTML = '<div class="col-12 text-muted small">No inference yet.</div>'; return; }
    el.innerHTML = crops
      .map(function (c) {
        return (
          '<div class="col-md-6 col-lg-4"><div class="bf-card p-3 h-100">' +
          '<div class="d-flex justify-content-between"><strong>' + esc(c.crop) + "</strong>" +
          '<span class="badge bg-' + (confBadge[c.confidence] || "secondary") + '">' + esc(c.confidence) + "</span></div>" +
          '<div class="small text-muted">' + (c.seasons || []).join(", ") + "</div>" +
          '<div class="small mt-1">' + esc(c.reason) + "</div>" +
          "</div></div>"
        );
      })
      .join("");
    document.getElementById("crop-summary").textContent = summary || "";
  }

  async function renderOutlook(outlook) {
    var el = document.getElementById("outlook");
    if (!outlook || !outlook.length) { el.innerHTML = '<div class="col-12 text-muted small">No price outlook.</div>'; return; }
    el.innerHTML = outlook
      .map(function (o, i) {
        var f = o.forecast || {};
        var q = o.quote;
        var band =
          f.projected_low != null
            ? BF.fmt.inr(f.projected_low) + " – " + BF.fmt.inr(f.projected_high)
            : "n/a";
        return (
          '<div class="col-md-6 col-lg-4"><div class="bf-card p-3 h-100">' +
          '<div class="d-flex justify-content-between align-items-center">' +
          "<strong>" + esc(o.crop) + "</strong>" +
          '<span class="badge ' + (dirBadge[f.direction] || "badge-flat") + '">' +
          esc(f.direction || "n/a") + " " + (f.change_pct != null ? BF.fmt.pct(f.change_pct) : "") + "</span></div>" +
          '<div class="quote-value mt-1">' + (q ? BF.fmt.inr(q.modal_price) : "—") +
          '<span class="fs-6 text-muted">/qtl</span></div>' +
          '<div class="small text-muted">' + (q ? "as of " + q.arrival_date : "no live quote") + "</div>" +
          '<div class="small mt-1">' + f.horizon_weeks + "-wk projection: " + band +
          ' <span class="text-muted">(' + esc(f.confidence || "low") + " confidence)</span></div>" +
          '<canvas id="spark-' + i + '" height="46" class="mt-2"></canvas>' +
          "</div></div>"
        );
      })
      .join("");
    for (var i = 0; i < outlook.length; i++) drawSpark(i, outlook[i].crop);
  }

  async function drawSpark(i, crop) {
    try {
      var st = plot && plot.state ? "&state=" + encodeURIComponent(plot.state) : "";
      var hist = await BF.api.get("/api/prices/" + encodeURIComponent(crop) + "/history?days=120" + st);
      if (!hist.length) return;
      new Chart(document.getElementById("spark-" + i), {
        type: "line",
        data: {
          labels: hist.map(function (p) { return p.arrival_date; }),
          datasets: [{ data: hist.map(function (p) { return p.modal_price; }),
            borderColor: "#135c37", pointRadius: 0, tension: 0.3 }],
        },
        options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } },
      });
    } catch (e) {}
  }

  function renderSoil(soil, acc) {
    soil = soil || {}; acc = acc || {};
    var sec = document.getElementById("soil-sec");
    var cells = [];
    if (soil.moisture_m3_m3 != null)
      cells.push(["Soil moisture", (soil.moisture_m3_m3 * 100).toFixed(1) + " %vol"]);
    if (soil.temp_10cm_c != null) cells.push(["Soil temp (10cm)", soil.temp_10cm_c + " °C"]);
    if (soil.surface_temp_c != null) cells.push(["Surface temp", soil.surface_temp_c + " °C"]);
    if (acc.rain_mm != null) cells.push(["Rain, last " + (acc.days || 120) + "d", acc.rain_mm + " mm"]);
    if (acc.gdd_base10_c != null) cells.push(["GDD (base 10°C)", Math.round(acc.gdd_base10_c)]);
    if (!cells.length) { sec.classList.add("d-none"); return; }
    sec.classList.remove("d-none");
    document.getElementById("soil").innerHTML = cells
      .map(function (c) {
        return '<div class="col-6 col-md-4"><div class="border rounded p-2"><div class="text-muted">' +
          c[0] + '</div><div class="fw-semibold">' + c[1] + "</div></div></div>";
      })
      .join("");
  }

  async function poll() {
    var a = await BF.api.get("/api/plots/" + id + "/analysis");
    var badge = document.getElementById("p-status");
    badge.textContent = a.status;
    badge.className = "badge bg-" + (a.status === "ready" ? "success" : a.status === "error" ? "danger" : "secondary");

    renderSat(a.thumbnails);
    renderNdvi(a.ndvi_series);
    document.getElementById("ndvi-src").textContent =
      a.ndvi_source === "agromonitoring" ? "Agromonitoring" : a.ndvi_source === "planetary-computer" ? "Planetary Computer" : "";
    renderCrops(a.inferred_crops, a.summary_text);
    renderOutlook(a.price_outlook);
    renderSoil(a.soil, a.accumulated);

    var note = document.getElementById("p-note");
    if (a.error) { note.classList.remove("d-none"); note.textContent = a.error; }
    else note.classList.add("d-none");

    if (a.status === "pending" || a.status === "running") setTimeout(poll, 4000);
  }

  document.getElementById("rerun").addEventListener("click", async function () {
    this.disabled = true;
    try {
      await BF.api.post("/api/plots/" + id + "/reanalyze");
      document.getElementById("p-status").textContent = "pending";
      poll();
    } catch (e) { BF.toast(e.message, "danger"); }
    this.disabled = false;
  });

  (async function () {
    try { await loadPlot(); await poll(); }
    catch (e) { BF.toast("Could not load plot: " + e.message, "danger"); }
  })();
})();
