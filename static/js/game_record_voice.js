/**
 * Keyboard / typed draft into the unified Record Game form.
 * AI fills location, date, score type, half game, and players below the panel.
 * Group stays manual; game type mismatch shows a red warning with optional switch.
 * Never auto-saves; user reviews and clicks Save Game.
 */
(function () {
  const STORAGE_KEY = "leaderlodge.recordGame.aiEntryOpen";
  const REPARSE_KEY = "leaderlodge.recordGame.reparseTranscript";

  const form = document.getElementById("game-record-form");
  const root = document.querySelector("[data-game-record-voice]");
  if (!form || !root) {
    return;
  }

  const parseUrl = form.dataset.parseRecordingUrl || "";
  if (!parseUrl) {
    return;
  }

  const gameTypeLocked = root.dataset.gameTypeLocked === "true";
  const panel = document.getElementById("game-record-voice-panel");
  const toggleBtns = Array.from(root.querySelectorAll("[data-voice-toggle]"));
  const helpBtn = root.querySelector("[data-voice-help]");
  const applyBtn = root.querySelector("[data-voice-apply]");
  const clearBtn = root.querySelector("[data-voice-clear]");
  const applyIcon = root.querySelector("[data-voice-apply-icon]");
  const spinner = root.querySelector("[data-voice-spinner]");
  const micBtn = root.querySelector("[data-voice-mic]");
  const transcriptEl = root.querySelector("[data-voice-transcript]");
  const statusEl = root.querySelector("[data-voice-status]");
  const notesEl = root.querySelector("[data-voice-notes]");

  let processing = false;
  let listening = false;
  let recognition = null;
  let finalTranscript = "";
  let conflictSwitchHandler = null;

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

  function clearConflictUi() {
    if (conflictSwitchHandler && notesEl) {
      notesEl.removeEventListener("click", conflictSwitchHandler);
      conflictSwitchHandler = null;
    }
  }

  function setNotes(lines) {
    clearConflictUi();
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

  const nativeFieldSizing =
    typeof CSS !== "undefined" && CSS.supports("field-sizing", "content");

  // Resize the field to fit its text. Resetting to "auto" first lets the
  // rows attribute set the floor and CSS max-height set the ceiling.
  // Skip when field-sizing is native so we do not fight the UA.
  function autoGrowTranscript() {
    if (nativeFieldSizing || !transcriptEl) {
      return;
    }
    if (!transcriptEl.getClientRects().length) {
      return;
    }
    transcriptEl.style.height = "auto";
    const borders = transcriptEl.offsetHeight - transcriptEl.clientHeight;
    transcriptEl.style.height = `${transcriptEl.scrollHeight + borders}px`;
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
    autoGrowTranscript();
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
    toggleBtns.forEach((btn) => {
      btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  function currentGameType() {
    const el = form.querySelector("#game-setup-game-type-select");
    return (el && el.value) || "";
  }

  function currentGroupId() {
    const el = form.querySelector('[name="group"]');
    return (el && el.value) || "";
  }

  function locationInputEl() {
    return (
      form.querySelector('[name="location_name"]') ||
      document.getElementById("id_location_name")
    );
  }

  function applyLocation(name, options) {
    const input = locationInputEl();
    if (!input) {
      return false;
    }
    // A fallback ("last location") must not replace a place already chosen,
    // including a Near me / GPS pick that has not been saved yet.
    if (options && options.keepExisting && input.value.trim()) {
      return false;
    }
    if (!name) {
      return false;
    }
    input.value = name;
    input.dataset.locationLocked = "1";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    if (window.LeaderLodgeLocationAutocomplete?.resolveInput) {
      window.LeaderLodgeLocationAutocomplete.resolveInput(input);
    }
    return true;
  }

  function applyPlayedOn(isoDate) {
    if (!isoDate) {
      return;
    }
    const input = form.querySelector('[name="played_on"]');
    if (!input) {
      return;
    }
    input.value = isoDate;
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

  function applyHalfGame(isHalf) {
    const checkbox = form.querySelector('[name="is_half_game"]');
    if (!checkbox) {
      return;
    }
    checkbox.checked = Boolean(isHalf);
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function conflictStatusText(conflict) {
    if (!conflict) {
      return "";
    }
    const mentioned = conflict.mentioned_name || conflict.mentioned_code || "another game";
    const selected = conflict.selected_name || conflict.selected_code || "the selected game";
    return `You mentioned ${mentioned}, but Game is set to ${selected}.`;
  }

  function renderConflict(conflict) {
    clearConflictUi();
    if (!notesEl || !conflict) {
      return;
    }

    const canSwitch = !gameTypeLocked && Boolean(conflict.mentioned_code);
    let html = "";

    if (canSwitch) {
      const label = conflict.mentioned_name || conflict.mentioned_code;
      html = `<button type="button" class="btn btn-sm btn-outline-danger game-record-voice-switch" data-voice-switch-game="${escapeHtml(
        conflict.mentioned_code
      )}">Switch to ${escapeHtml(label)} and re-parse</button>`;
    } else if (gameTypeLocked) {
      html =
        '<div class="small text-danger">Game type is locked for this account.</div>';
    }

    notesEl.classList.remove("d-none");
    notesEl.innerHTML = html;

    conflictSwitchHandler = function (event) {
      const btn = event.target.closest("[data-voice-switch-game]");
      if (!btn) {
        return;
      }
      event.preventDefault();
      switchGameTypeAndReparse(btn.getAttribute("data-voice-switch-game"));
    };
    notesEl.addEventListener("click", conflictSwitchHandler);
  }

  function switchGameTypeAndReparse(gameTypeCode) {
    const transcript = (transcriptEl && transcriptEl.value.trim()) || "";
    if (!transcript || !gameTypeCode) {
      return;
    }
    const groupId = currentGroupId();
    if (!groupId) {
      setStatus("Choose a group first.", "error");
      return;
    }

    try {
      window.localStorage.setItem(REPARSE_KEY, transcript);
      writeStoredOpen(true);
    } catch (err) {
      /* ignore */
    }

    const url = new URL(window.location.href);
    url.searchParams.set("group", groupId);
    url.searchParams.set("type", gameTypeCode);
    url.searchParams.delete("reuse_from");
    url.searchParams.delete("pick_from");
    window.LeaderLodge.navigate(url.pathname + url.search);
  }

  function applyDraft(draft) {
    if (!draft || !window.LeaderLodgeRecordGame) {
      return false;
    }
    const api = window.LeaderLodgeRecordGame;
    if (typeof api.clearParticipants !== "function" || typeof api.appendSide !== "function") {
      return false;
    }

    const locationSource = draft.location_source || "";
    const appliedLocation = applyLocation(draft.location_name || "", {
      keepExisting: locationSource === "last",
    });
    applyPlayedOn(draft.played_on || "");
    applyScoreType(draft.score_type || "");
    applyHalfGame(draft.is_half_game);

    api.clearParticipants();
    const sides = Array.isArray(draft.sides) ? draft.sides : [];
    let added = 0;
    sides.forEach((side) => {
      if (api.appendSide(side)) {
        added += 1;
      }
    });

    const notes = [];
    (draft.warnings || []).forEach((w) => {
      if (
        locationSource === "last" &&
        !appliedLocation &&
        /^using last location:/i.test(String(w || "").trim())
      ) {
        return;
      }
      notes.push(w);
    });
    (draft.ambiguities || []).forEach((a) => notes.push(a));
    if (added < 2) {
      notes.push("Could not add both sides. Check names and try again.");
    } else if (typeof api.collapsePlayerPicker === "function") {
      // Sides are filled; collapse Add player to the compact "+" control.
      api.collapsePlayerPicker();
    }

    if (draft.conflict) {
      renderConflict(draft.conflict);
      if (notes.length) {
        notesEl.innerHTML += notes
          .map((line) => `<div class="text-warning-emphasis mt-1">${escapeHtml(line)}</div>`)
          .join("");
        notesEl.classList.remove("d-none");
      }
      if (added < 2) {
        setStatus("Draft partially filled. Edit as needed.", "error");
      } else {
        setStatus(conflictStatusText(draft.conflict), "error");
      }
      return added >= 2;
    }

    setNotes(notes);
    if (added < 2) {
      setStatus("Draft partially filled. Edit as needed.", "error");
    } else {
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

    clearConflictUi();
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

  function restoreReparseTranscript() {
    let stored = "";
    try {
      stored = window.localStorage.getItem(REPARSE_KEY) || "";
      if (stored) {
        window.localStorage.removeItem(REPARSE_KEY);
      }
    } catch (err) {
      return;
    }
    if (!stored || !transcriptEl) {
      return;
    }
    transcriptEl.value = stored;
    syncApplyEnabled();
    autoGrowTranscript();
    parseTranscript();
  }

  if (panel) {
    panel.addEventListener("shown.bs.collapse", function () {
      writeStoredOpen(true);
      syncOpenChrome(true);
      autoGrowTranscript();
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
        autoGrowTranscript();
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
    transcriptEl.addEventListener("input", function () {
      syncApplyEnabled();
      autoGrowTranscript();
    });
    // Rotation, keyboard, or iOS visual-viewport changes rewrap the text.
    window.addEventListener("resize", autoGrowTranscript);
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", autoGrowTranscript);
    }
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

  if (helpBtn && window.bootstrap && bootstrap.Popover) {
    bootstrap.Popover.getOrCreateInstance(helpBtn);
    helpBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
    });
    document.addEventListener("click", function (event) {
      if (event.target.closest("[data-voice-help], .popover")) {
        return;
      }
      bootstrap.Popover.getInstance(helpBtn)?.hide();
    });
  }

  syncApplyEnabled();
  restoreReparseTranscript();
  autoGrowTranscript();
})();
