// Floating multilingual voice assistant: STT (mic) -> assistant -> TTS playback.
(function () {
  var BF = (window.BF = window.BF || {});
  var LANGS = {
    hi: "हिन्दी", en: "English", bn: "বাংলা", te: "తెలుగు", mr: "मराठी",
    ta: "தமிழ்", gu: "ગુજરાતી", kn: "ಕನ್ನಡ", ml: "മലയാളം", pa: "ਪੰਜਾਬੀ",
    or: "ଓଡ଼ିଆ", as: "অসমীয়া", ur: "اردو",
  };

  function langOptions(sel) {
    return Object.keys(LANGS)
      .map(function (c) {
        return '<option value="' + c + '"' + (c === sel ? " selected" : "") + ">" + LANGS[c] + "</option>";
      })
      .join("");
  }

  function log(html, who) {
    var box = document.getElementById("bf-voice-log");
    var p = document.createElement("div");
    p.className = "mb-2 " + (who === "you" ? "text-end" : "");
    p.innerHTML =
      '<span class="badge bg-' +
      (who === "you" ? "secondary" : "success") +
      '">' + (who === "you" ? "You" : "Assistant") + "</span> " + html;
    box.appendChild(p);
    box.scrollTop = box.scrollHeight;
  }

  var mediaRecorder = null;
  var chunks = [];

  async function toggleRecord(btn) {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      BF.toast("Microphone recording is not supported in this browser.", "warning");
      return;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      chunks = [];
      mediaRecorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
      mediaRecorder.onstop = async function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        btn.classList.remove("bf-rec-on");
        btn.textContent = "🎙️";
        var blob = new Blob(chunks, { type: "audio/webm" });
        var lang = document.getElementById("bf-voice-lang").value;
        var fd = new FormData();
        fd.append("file", blob, "speech.webm");
        fd.append("language", lang);
        log("<em>transcribing…</em>", "you");
        try {
          var r = await BF.api.postForm("/api/voice/stt", fd);
          ask(r.text);
        } catch (err) {
          BF.toast("Speech-to-text failed: " + err.message, "danger");
        }
      };
      mediaRecorder.start();
      btn.classList.add("bf-rec-on");
      btn.textContent = "⏹️";
    } catch (err) {
      BF.toast("Could not access the microphone.", "danger");
    }
  }

  async function ask(text) {
    if (!text || !text.trim()) return;
    var lang = document.getElementById("bf-voice-lang").value;
    log(escapeHtml(text), "you");
    var input = document.getElementById("bf-voice-input");
    if (input) input.value = "";
    try {
      var r = await BF.api.post("/api/voice/assistant", {
        message: text,
        language: lang,
        plot_id: BF.currentPlotId || null,
      });
      log(escapeHtml(r.reply), "bot");
      speak(r.reply, lang);
    } catch (err) {
      log('<span class="text-danger">' + escapeHtml(err.message) + "</span>", "bot");
    }
  }

  async function speak(text, lang) {
    try {
      var blob = await BF.api.raw("POST", "/api/voice/tts", {
        json: { text: text, language: lang || "hi" },
      });
      if (blob instanceof Blob) new Audio(URL.createObjectURL(blob)).play();
    } catch (e) {
      /* TTS is best-effort */
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  BF.speak = speak;

  BF.mountVoiceWidget = function () {
    if (document.getElementById("bf-voice-btn")) return;
    var btn = document.createElement("button");
    btn.id = "bf-voice-btn";
    btn.title = "Ask Bharat Farms";
    btn.textContent = "💬";
    document.body.appendChild(btn);

    var panel = document.createElement("div");
    panel.id = "bf-voice-panel";
    panel.className = "bf-card p-3";
    panel.innerHTML =
      '<div class="d-flex justify-content-between align-items-center mb-2">' +
      '<strong>Ask Bharat Farms</strong>' +
      '<select id="bf-voice-lang" class="form-select form-select-sm w-auto">' + langOptions("hi") + "</select>" +
      "</div>" +
      '<div id="bf-voice-log" class="mb-2"><div class="text-muted small">Ask about your crop prices, plot or the latest news — in your language.</div></div>' +
      '<div class="input-group input-group-sm">' +
      '<input id="bf-voice-input" type="text" class="form-control" placeholder="Type a question…">' +
      '<button id="bf-voice-send" class="btn btn-success">Send</button>' +
      '<button id="bf-voice-mic" class="btn btn-outline-success" title="Hold to speak">🎙️</button>' +
      "</div>";
    document.body.appendChild(panel);

    btn.addEventListener("click", function () { panel.classList.toggle("open"); });
    document.getElementById("bf-voice-send").addEventListener("click", function () {
      ask(document.getElementById("bf-voice-input").value);
    });
    document.getElementById("bf-voice-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter") ask(e.target.value);
    });
    document.getElementById("bf-voice-mic").addEventListener("click", function () {
      toggleRecord(this);
    });
  };
})();
