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
  const applyIcon = root.querySelector("[data-voice-apply-icon]");
  const spinner = root.querySelector("[data-voice-spinner]");
  const transcriptEl = root.querySelector("[data-voice-transcript]");
  const statusEl = root.querySelector("[data-voice-status]");
  const notesEl = root.querySelector("[data-voice-notes]");
  const titleClosed = root.dataset.voiceTitleClosed || "AI game entry";
  const titleOpen = root.dataset.voiceTitleOpen || titleClosed;

  let processing = false;

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
    if (!applyBtn || !transcriptEl) {
      return;
    }
    applyBtn.disabled = processing || !transcriptEl.value.trim();
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
    }
    setNotes(notes);
    setStatus(
      added >= 2
        ? "Draft filled. Review players and scores, then Save Game."
        : "Draft partially filled. Edit as needed.",
      added >= 2 ? "ok" : "error"
    );
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

  if (transcriptEl) {
    transcriptEl.addEventListener("input", syncApplyEnabled);
    transcriptEl.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || event.shiftKey) {
        return;
      }
      event.preventDefault();
      if (!processing && transcriptEl.value.trim()) {
        parseTranscript();
      }
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener("click", function () {
      parseTranscript();
    });
  }

  syncApplyEnabled();
})();
