/**
 * Keyboard / typed draft into the unified Record Game form.
 * AI fills fields below this panel only (location, score type, players).
 * Group, game, and date above stay as selected; mentions warn to edit manually.
 * Never auto-saves; user reviews and clicks Save Game.
 */
(function () {
  const STORAGE_KEY = "leaderlodge.recordGame.aiEntryOpen";

  const form = document.getElementById("game-record-form");
  const root = document.querySelector("[data-game-record-voice]");
  if (!form || !root) {
    return;
  }

  const parseUrl = form.dataset.parseRecordingUrl || "";
  if (!parseUrl) {
    return;
  }

  const panel = document.getElementById("game-record-voice-panel");
  const toggleBtn = root.querySelector("[data-voice-toggle]");
  const titleEl = root.querySelector("[data-voice-title]");
  const applyBtn = root.querySelector("[data-voice-apply]");
  const clearBtn = root.querySelector("[data-voice-clear]");
  const applyIcon = root.querySelector("[data-voice-apply-icon]");
  const spinner = root.querySelector("[data-voice-spinner]");
  const micBtn = root.querySelector("[data-voice-mic]");
  const transcriptEl = root.querySelector("[data-voice-transcript]");
  const statusEl = root.querySelector("[data-voice-status]");
  const notesEl = root.querySelector("[data-voice-notes]");
  const titleClosed = root.dataset.voiceTitleClosed || "AI game entry";
  const titleOpen = root.dataset.voiceTitleOpen || titleClosed;

  let processing = false;
  let listening = false;
  let recognition = null;
  let finalTranscript = "";

  function readStoredOpen() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      return null;
    }
  }

  function writeStoredOpen(isOpen) {
    try {
      window.localStorage.setItem(STORAGE_KEY, isOpen ? "true" : "false");
    } catch (err) {
      /* ignore quota / private mode */
    }
  }

  function csrfToken() {
    return (
      form.querySelector('input[name="csrfmiddlewaretoken"]')?.value ||
      (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
      ""
    );
  }

  function setStatus(text, tone) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = text || "";
    statusEl.dataset.tone = tone || "";
    statusEl.classList.toggle("text-danger", tone === "error");
    statusEl.classList.toggle("text-muted", tone !== "error");
  }

  function setNotes(lines) {
    if (!notesEl) {
      return;
    }
    const items = (lines || []).filter(Boolean);
    if (!items.length) {
      notesEl.classList.add("d-none");
      notesEl.innerHTML = "";
      return;
    }
    notesEl.classList.remove("d-none");
    notesEl.innerHTML = items
      .map((line) => `<div class="text-warning-emphasis">${escapeHtml(line)}</div>`)
      .join("");
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function syncApplyEnabled() {
    if (!transcriptEl) {
      return;
    }
    const hasText = Boolean(transcriptEl.value.trim());
    // While listening, keep Parse enabled so one tap can stop+submit.
    if (applyBtn) {
      applyBtn.disabled = processing || !(listening || hasText);
    }
    if (clearBtn) {
      clearBtn.disabled = processing || !(listening || hasText);
    }
  }

  function clearTranscript() {
    if (processing) {
      return;
    }
    if (listening) {
      stopListening({ keepStatus: true });
    }
    finalTranscript = "";
    if (transcriptEl) {
      transcriptEl.value = "";
    }
    setStatus("");
    setNotes([]);
    syncApplyEnabled();
    if (transcriptEl) {
      transcriptEl.focus();
    }
  }

  function setProcessing(isProcessing) {
    processing = Boolean(isProcessing);
    if (root) {
      root.classList.toggle("is-voice-processing", processing);
      root.setAttribute("aria-busy", processing ? "true" : "false");
    }
    if (transcriptEl) {
      transcriptEl.readOnly = processing;
    }
    if (spinner) {
      spinner.classList.toggle("d-none", !processing);
    }
    if (applyIcon) {
      applyIcon.classList.toggle("d-none", processing);
    }
    if (applyBtn) {
      applyBtn.setAttribute("aria-label", processing ? "Parsing" : "Parse");
      applyBtn.setAttribute("title", processing ? "Parsing…" : "Parse");
    }
    if (processing) {
      setStatus("AI is reading your entry…");
    }
    syncApplyEnabled();
  }

  function syncOpenChrome(isOpen) {
    root.classList.toggle("is-voice-open", isOpen);
    if (titleEl) {
      titleEl.textContent = isOpen ? titleOpen : titleClosed;
    }
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  }

  function currentGameType() {
    const el = form.querySelector("#game-setup-game-type-select");
    return (el && el.value) || "";
  }

  function currentGroupId() {
    const el = form.querySelector('[name="group"]');
    return (el && el.value) || "";
  }

  function applyLocation(name) {
    if (!name) {
      return;
    }
    const input =
      form.querySelector('[name="location_name"]') ||
      document.getElementById("id_location_name");
    if (!input) {
      return;
    }
    input.value = name;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function applyScoreType(scoreType) {
    if (!scoreType) {
      return;
    }
    const select = form.querySelector("#game-score-type");
    if (!select) {
      return;
    }
    const option = Array.from(select.options).find((o) => o.value === scoreType);
    if (option) {
      select.value = scoreType;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      if (
        window.LeaderLodgeScoreTypeSelect &&
        typeof window.LeaderLodgeScoreTypeSelect.syncIcon === "function"
      ) {
        window.LeaderLodgeScoreTypeSelect.syncIcon(select);
      }
    }
  }

  function applyDraft(draft) {
    if (!draft || !window.LeaderLodgeRecordGame) {
      return false;
    }
    const api = window.LeaderLodgeRecordGame;
    if (typeof api.clearParticipants !== "function" || typeof api.appendSide !== "function") {
      return false;
    }

    applyLocation(draft.location_name || "");
    applyScoreType(draft.score_type || "");

    api.clearParticipants();
    const sides = Array.isArray(draft.sides) ? draft.sides : [];
    let added = 0;
    sides.forEach((side) => {
      if (api.appendSide(side)) {
        added += 1;
      }
    });

    const notes = [];
    (draft.warnings || []).forEach((w) => notes.push(w));
    (draft.ambiguities || []).forEach((a) => notes.push(a));
    if (added < 2) {
      notes.push("Could not add both sides. Check names and try again.");
    } else if (typeof api.collapsePlayerPicker === "function") {
      // Sides are filled; collapse Add player to the compact "+" control.
      api.collapsePlayerPicker();
    }
    setNotes(notes);
    if (added < 2) {
      setStatus("Draft partially filled. Edit as needed.", "error");
    } else {
      // Success is obvious from filled rows; keep status for errors only.
      setStatus("");
    }
    return added >= 2;
  }

  async function parseTranscript() {
    const transcript = (transcriptEl && transcriptEl.value.trim()) || "";
    if (!transcript) {
      setStatus("Speak or type an entry first.", "error");
      return;
    }
    const groupId = currentGroupId();
    if (!groupId) {
      setStatus("Choose a group first.", "error");
      return;
    }
    if (!currentGameType()) {
      setStatus("Choose a game first.", "error");
      return;
    }

    setNotes([]);
    setProcessing(true);

    try {
      const response = await fetch(parseUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({
          group: groupId,
          transcript: transcript,
          game_type_code: currentGameType(),
        }),
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setProcessing(false);
        setStatus(data.error || "Could not parse that entry.", "error");
        return;
      }
      const draft = data.draft;
      if (!draft) {
        setProcessing(false);
        setStatus("Empty draft from server.", "error");
        return;
      }
      setProcessing(false);
      applyDraft(draft);
    } catch (err) {
      setProcessing(false);
      setStatus("Network error while parsing.", "error");
    }
  }

  if (panel) {
    panel.addEventListener("shown.bs.collapse", function () {
      writeStoredOpen(true);
      syncOpenChrome(true);
    });
    panel.addEventListener("hidden.bs.collapse", function () {
      writeStoredOpen(false);
      syncOpenChrome(false);
    });

    const stored = readStoredOpen();
    const shouldOpen = stored === "true";
    if (window.bootstrap && bootstrap.Collapse) {
      const instance = bootstrap.Collapse.getOrCreateInstance(panel, {
        toggle: false,
      });
      if (shouldOpen) {
        instance.show();
      } else {
        instance.hide();
        syncOpenChrome(false);
      }
    } else if (shouldOpen) {
      panel.classList.add("show");
      syncOpenChrome(true);
    } else {
      syncOpenChrome(false);
    }
  }

  function speechRecognitionCtor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function setListening(isListening) {
    listening = Boolean(isListening);
    if (micBtn) {
      micBtn.classList.toggle("is-listening", listening);
      micBtn.setAttribute("aria-pressed", listening ? "true" : "false");
      micBtn.setAttribute(
        "aria-label",
        listening ? "Stop listening" : "Tap to talk"
      );
      micBtn.title = listening ? "Stop listening" : "Tap to talk";
    }
    syncApplyEnabled();
  }

  function stopListening({ keepStatus } = {}) {
    if (recognition) {
      try {
        recognition.onend = null;
        recognition.stop();
      } catch (err) {
        /* ignore */
      }
      recognition = null;
    }
    setListening(false);
    if (!keepStatus && transcriptEl && transcriptEl.value.trim()) {
      setStatus("Transcript ready. Tap Parse when ready.");
    }
    syncApplyEnabled();
  }

  function startListening() {
    const Ctor = speechRecognitionCtor();
    if (!Ctor) {
      setStatus(
        "In-app mic is not supported here. Tap the text field and use the keyboard mic.",
        "error"
      );
      return;
    }
    if (processing) {
      return;
    }
    // Blur the field so the system keyboard does not open during in-app listen.
    if (transcriptEl && document.activeElement === transcriptEl) {
      transcriptEl.blur();
    }
    finalTranscript = (transcriptEl && transcriptEl.value.trim()) || "";
    if (finalTranscript) {
      finalTranscript += " ";
    }

    recognition = new Ctor();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onstart = function () {
      setListening(true);
      setStatus("Listening… tap the mic to stop.");
    };
    recognition.onerror = function (event) {
      const code = event && event.error;
      stopListening({ keepStatus: true });
      if (code === "not-allowed") {
        setStatus(
          "Microphone permission denied. Tap the text field to use the keyboard mic instead.",
          "error"
        );
      } else if (code === "no-speech") {
        setStatus("No speech heard. Tap the mic to try again.", "error");
      } else {
        setStatus(
          "In-app mic failed. Tap the text field to use the keyboard mic instead.",
          "error"
        );
      }
    };
    recognition.onend = function () {
      if (listening) {
        // Browser ended the session; treat as stop.
        setListening(false);
        if (transcriptEl && transcriptEl.value.trim()) {
          setStatus("Transcript ready. Tap Parse when ready.");
        }
        syncApplyEnabled();
      }
      recognition = null;
    };
    recognition.onresult = function (event) {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i][0].transcript || "";
        if (event.results[i].isFinal) {
          finalTranscript += piece;
        } else {
          interim += piece;
        }
      }
      if (transcriptEl) {
        transcriptEl.value = (finalTranscript + interim).trimStart();
        syncApplyEnabled();
      }
    };

    try {
      recognition.start();
    } catch (err) {
      stopListening({ keepStatus: true });
      setStatus("Could not start the microphone.", "error");
    }
  }

  if (micBtn) {
    if (!speechRecognitionCtor()) {
      micBtn.disabled = true;
      micBtn.title = "Not supported in this browser";
      micBtn.setAttribute("aria-label", "Microphone not supported");
    }
    micBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      if (listening) {
        stopListening();
        return;
      }
      startListening();
    });
    // Keep focus off the textarea when activating the mic control.
    micBtn.addEventListener("mousedown", function (event) {
      event.preventDefault();
    });
  }

  function stopListeningAndParse() {
    if (processing) {
      return;
    }
    if (listening) {
      stopListening({ keepStatus: true });
    }
    parseTranscript();
  }

  if (transcriptEl) {
    transcriptEl.addEventListener("input", syncApplyEnabled);
    transcriptEl.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || event.shiftKey) {
        return;
      }
      event.preventDefault();
      if (!processing && transcriptEl.value.trim()) {
        stopListeningAndParse();
      }
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener("click", function () {
      stopListeningAndParse();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      clearTranscript();
    });
  }

  syncApplyEnabled();
})();
