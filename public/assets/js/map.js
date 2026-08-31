// Plot mapping + lock (Leaflet + Leaflet-Geoman).
(function () {
  var map = L.map("map").setView([22.0, 79.0], 5);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(function (pos) {
      map.setView([pos.coords.latitude, pos.coords.longitude], 15);
    });
  }

  map.pm.addControls({
    position: "topleft",
    drawCircle: false,
    drawCircleMarker: false,
    drawMarker: false,
    drawPolyline: false,
    drawText: false,
    cutPolygon: false,
    rotateMode: false,
  });
  map.pm.setGlobalOptions({ snappable: true });

  var drawn = null;
  var lockBtn = document.getElementById("lock-btn");
  var meta = document.getElementById("plot-meta");

  function ringAreaHa(latlngs) {
    // Spherical polygon area (Shoelace on an equirectangular projection near centroid).
    var R = 6378137;
    var area = 0;
    for (var i = 0; i < latlngs.length; i++) {
      var a = latlngs[i];
      var b = latlngs[(i + 1) % latlngs.length];
      area +=
        ((b.lng - a.lng) * Math.PI) / 180 *
        (2 + Math.sin((a.lat * Math.PI) / 180) + Math.sin((b.lat * Math.PI) / 180));
    }
    return Math.abs((area * R * R) / 2) / 10000;
  }

  function setDrawn(layer) {
    if (drawn && drawn !== layer) map.removeLayer(drawn);
    drawn = layer;
    var ll = layer.getLatLngs()[0];
    meta.textContent = "≈ " + ringAreaHa(ll).toFixed(2) + " ha, " + ll.length + " points";
    lockBtn.disabled = false;
  }

  map.on("pm:create", function (e) {
    if (e.shape !== "Polygon") return;
    setDrawn(e.layer);
    e.layer.on("pm:edit", function (ev) { setDrawn(ev.target); });
  });
  map.on("pm:remove", function () {
    drawn = null;
    lockBtn.disabled = true;
    meta.textContent = "Draw a polygon to begin.";
  });

  lockBtn.addEventListener("click", async function () {
    if (!drawn) return;
    lockBtn.disabled = true;
    lockBtn.textContent = "Locking…";
    try {
      var res = await BF.api.post("/api/plots", {
        name: document.getElementById("plot-name").value || "My plot",
        geojson: drawn.toGeoJSON(),
      });
      location.href = "plot.html?id=" + res.id;
    } catch (err) {
      BF.toast("Could not lock plot: " + err.message, "danger");
      lockBtn.disabled = false;
      lockBtn.textContent = "🔒 Lock plot";
    }
  });

  // Existing plots
  (async function () {
    var list = document.getElementById("plot-list");
    try {
      var plots = await BF.api.get("/api/plots");
      if (!plots.length) {
        list.textContent = "No plots yet.";
        return;
      }
      var group = L.featureGroup().addTo(map);
      list.innerHTML = "";
      plots.forEach(function (p) {
        try {
          var layer = L.geoJSON(p.geojson, {
            pmIgnore: true,
            style: { color: "#1b7f4d", weight: 2, fillOpacity: 0.15 },
          });
          layer.bindPopup(
            "<strong>" + p.name + "</strong><br>" +
            (p.district || "?") + ", " + (p.state || "?") + "<br>" +
            '<a href="plot.html?id=' + p.id + '">Open report →</a>'
          );
          layer.addTo(group);
        } catch (e) {}
        var row = document.createElement("div");
        row.className = "d-flex justify-content-between align-items-center py-1 border-bottom";
        row.innerHTML =
          '<a href="plot.html?id=' + p.id + '">' + p.name + "</a>" +
          '<span class="badge bg-' +
          (p.analysis_status === "ready" ? "success" : p.analysis_status === "error" ? "danger" : "secondary") +
          '">' + p.analysis_status + "</span>";
        list.appendChild(row);
      });
      if (group.getBounds().isValid()) map.fitBounds(group.getBounds().pad(0.3));
    } catch (e) {
      list.textContent = "Could not load plots.";
    }
  })();
})();
