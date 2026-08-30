// Tiny fetch wrapper: same-origin API, injects the device id, unwraps errors.
(function () {
  var BF = (window.BF = window.BF || {});

  async function req(method, path, opts) {
    opts = opts || {};
    var headers = { "X-Device-Id": BF.deviceId || "anon" };
    for (var k in opts.headers || {}) headers[k] = opts.headers[k];

    var init = { method: method, headers: headers };
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.json);
    } else if (opts.form !== undefined) {
      init.body = opts.form; // FormData - let the browser set the boundary
    }

    var res = await fetch(path, init);
    var ct = res.headers.get("content-type") || "";
    var body;
    if (ct.indexOf("application/json") !== -1) body = await res.json().catch(function () { return null; });
    else if (ct.indexOf("audio/") === 0) body = await res.blob();
    else body = await res.text().catch(function () { return null; });

    if (!res.ok) {
      var msg =
        (body && body.detail) ||
        (typeof body === "string" && body) ||
        res.statusText ||
        "HTTP " + res.status;
      var err = new Error(msg);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  BF.api = {
    get: function (p) { return req("GET", p); },
    post: function (p, json) { return req("POST", p, { json: json }); },
    del: function (p) { return req("DELETE", p); },
    postForm: function (p, form) { return req("POST", p, { form: form }); },
    raw: req,
  };

  // Formatting helpers.
  BF.fmt = {
    inr: function (n) {
      if (n === null || n === undefined || isNaN(n)) return "—";
      return "₹" + Number(n).toLocaleString("en-IN");
    },
    pct: function (n) {
      if (n === null || n === undefined || isNaN(n)) return "—";
      return (n > 0 ? "+" : "") + Number(n).toFixed(1) + "%";
    },
    dir: function (n) {
      if (n === null || n === undefined || isNaN(n)) return "flat";
      return n > 0.5 ? "up" : n < -0.5 ? "down" : "flat";
    },
    arrow: function (n) {
      var d = BF.fmt.dir(n);
      return d === "up" ? "▲" : d === "down" ? "▼" : "▬";
    },
  };

  BF.toast = function (message, kind) {
    var el = document.createElement("div");
    el.className =
      "position-fixed top-0 start-50 translate-middle-x mt-3 alert alert-" +
      (kind || "info") +
      " shadow";
    el.style.zIndex = 2000;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 4000);
  };
})();
