/**
 * Live Win/Tie/Loss preview for game recording (mirrors leaderlodge.games.scoring).
 */
(function () {
  function parseScore(value) {
    if (value === "" || value === null || value === undefined) {
      return null;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function materializeInitialScores(form) {
    form.querySelectorAll("[data-score-input]").forEach((input) => {
      if (
        input.dataset.scoreTouched === "true" ||
        input.value.trim() !== "" ||
        input.dataset.initialScore === undefined ||
        input.dataset.initialScore === ""
      ) {
        return;
      }
      input.value = input.dataset.initialScore;
    });
  }

  function readScore(scoreInput) {
    const raw = scoreInput.value.trim();
    if (raw === "") {
      return { played: false, score: null };
    }
    const parsed = parseScore(raw);
    return parsed === null
      ? { played: false, score: null }
      : { played: true, score: parsed };
  }

  function evaluateResults(rows, supportsLoser, scoreDirection, winTargetScore) {
    const active = rows.filter((row) => row.played && row.score !== null);
    const count = active.length;
    if (count === 0) {
      return {
        winIds: new Set(),
        tieIds: new Set(),
        lossIds: new Set(),
        playerCount: 0,
        isDouble: false,
      };
    }

    const lowWins = scoreDirection === "low";
    const scores = active.map((row) => row.score);
    const bestScore = lowWins ? Math.min(...scores) : Math.max(...scores);
    const worstScore = lowWins ? Math.max(...scores) : Math.min(...scores);
    const atBest = active.filter((row) => row.score === bestScore);
    const atWorst = active.filter((row) => row.score === worstScore);

    const winIds = new Set();
    const tieIds = new Set();
    const lossIds = new Set();

    if (atBest.length === 1) {
      winIds.add(atBest[0].playerId);
    } else {
      atBest.forEach((row) => tieIds.add(row.playerId));
    }

    if (supportsLoser && bestScore !== worstScore) {
      atWorst.forEach((row) => lossIds.add(row.playerId));
    }

    let isDouble = false;
    if (winTargetScore && winIds.size === 1) {
      const winnerRow = active.find((row) => winIds.has(row.playerId));
      if (winnerRow && winnerRow.score >= 2 * winTargetScore) {
        isDouble = true;
      }
    }

    return { winIds, tieIds, lossIds, playerCount: count, isDouble };
  }

  function collectRows(form) {
    return Array.from(form.querySelectorAll("tr[data-game-row]"))
      .map((row) => {
        const scoreInput = row.querySelector("[data-score-input]");
        const resultCell = row.querySelector("[data-result-cell]");
        if (!scoreInput || !resultCell) {
          return null;
        }
        const { played, score } = readScore(scoreInput);
        return {
          playerId: row.dataset.playerId,
          score: played ? score : null,
          played,
          resultCell,
        };
      })
      .filter(Boolean);
  }

  function renderBadge(label, className) {
    return `<span class="badge ${className}">${label}</span>`;
  }

  const DOUBLE_MODIFIER_BADGE =
    '<span class="badge text-bg-secondary result-badge-modifier">2×</span>';

  function renderResults(rows, evaluation) {
    rows.forEach((row) => {
      row.resultCell.textContent = "";
      if (!row.played || row.score === null) {
        return;
      }
      if (evaluation.winIds.has(row.playerId)) {
        const cls = evaluation.isDouble
          ? "result-badge result-badge--win-double"
          : "result-badge result-badge--win";
        row.resultCell.innerHTML =
          renderBadge("Win", cls) + (evaluation.isDouble ? DOUBLE_MODIFIER_BADGE : "");
      } else if (evaluation.tieIds.has(row.playerId)) {
        row.resultCell.innerHTML = renderBadge("Tie", "result-badge result-badge--tie");
      } else if (evaluation.lossIds.has(row.playerId)) {
        const cls = evaluation.isDouble
          ? "result-badge result-badge--loss-double"
          : "result-badge result-badge--loss";
        row.resultCell.innerHTML =
          renderBadge("Loss", cls) + (evaluation.isDouble ? DOUBLE_MODIFIER_BADGE : "");
      }
    });
  }

  function formatPlayerCountFeedback(minPlayers, maxPlayers, current) {
    if (current <= 0) {
      return "";
    }
    if (current > maxPlayers) {
      const extra = current - maxPlayers;
      const noun = extra === 1 ? "player" : "players";
      return `Too many scores entered (${current}; ${maxPlayers} max). Remove ${extra} ${noun}.`;
    }
    if (current < minPlayers) {
      const noun = minPlayers === 1 ? "side" : "sides";
      return `Need at least ${minPlayers} ${noun} before saving (currently ${current}).`;
    }
    return "";
  }

  function updateEmptyRow(form) {
    const tbody = form.querySelector("[data-participant-rows]");
    const emptyRow = tbody ? tbody.querySelector("[data-participant-empty]") : null;
    if (!tbody || !emptyRow) {
      return;
    }
    const hasPlayers = tbody.querySelector("[data-game-row]") !== null;
    emptyRow.classList.toggle("d-none", hasPlayers);
  }

  function setFeedback(feedback, message, tone) {
    if (!feedback) {
      return;
    }
    feedback.textContent = message;
    feedback.dataset.tone = tone;
  }

  function updateForm(form) {
    if (!form) {
      return;
    }

    materializeInitialScores(form);
    updateEmptyRow(form);

    const minPlayers = Number.parseInt(form.dataset.minPlayers, 10);
    const maxPlayers = Number.parseInt(form.dataset.maxPlayers, 10);
    const supportsLoser = form.dataset.supportsLoser === "true";
    const scoreDirection = form.dataset.scoreDirection || "high";
    const winTargetScore = form.dataset.winTargetScore
      ? Number.parseInt(form.dataset.winTargetScore, 10)
      : null;
    const saveBtn = form.querySelector("[data-save-button]");
    const feedback = form.querySelector("[data-score-feedback]");

    const rows = collectRows(form);
    const activeRows = rows.filter((row) => row.played && row.score !== null);
    const evaluation = evaluateResults(
      activeRows,
      supportsLoser,
      scoreDirection,
      winTargetScore
    );
    renderResults(rows, evaluation);

    const countOk =
      evaluation.playerCount >= minPlayers &&
      evaluation.playerCount <= maxPlayers;
    if (saveBtn) {
      saveBtn.disabled = !countOk;
    }

    if (feedback) {
      const countMessage = formatPlayerCountFeedback(
        minPlayers,
        maxPlayers,
        evaluation.playerCount
      );
      if (countMessage) {
        setFeedback(feedback, countMessage, "warning");
      } else if (evaluation.isDouble) {
        setFeedback(feedback, "Double game: counts as 2 in standings.", "info");
      } else {
        setFeedback(feedback, "", "none");
      }
    }
  }

  function refreshGameRecordForm() {
    updateForm(
      document.getElementById("game-record-form") ||
        document.getElementById("game-edit-form")
    );
  }

  window.LeaderLodgeUpdateGameRecordForm = refreshGameRecordForm;

  function watchParticipantRows(form) {
    const tbody = form.querySelector("[data-participant-rows]");
    if (!tbody) {
      return;
    }

    const scheduleUpdate = () => {
      window.requestAnimationFrame(() => {
        const noScoreToggle = form.querySelector("[data-no-score-toggle]");
        if (noScoreToggle && noScoreToggle.checked) {
          // Keep a player added mid-wall-game consistent with the rest.
          applyNoScore(form);
        }
        updateForm(form);
      });
    };

    const observer = new MutationObserver(scheduleUpdate);
    observer.observe(tbody, { childList: true, subtree: true });
    tbody.addEventListener("click", (event) => {
      if (
        event.target.closest("[data-remove-side], [data-side-action]")
      ) {
        scheduleUpdate();
      }
    });
  }

  function applyNoScore(form) {
    const points = form.dataset.noScorePoints || "0";
    form.querySelectorAll("[data-score-input]").forEach((input) => {
      input.value = points;
      input.dataset.scoreTouched = "true";
      input.readOnly = true;
    });
    updateForm(form);
  }

  function clearNoScore(form) {
    form.querySelectorAll("[data-score-input]").forEach((input) => {
      input.readOnly = false;
      input.value = "0";
      input.dataset.scoreTouched = "true";
    });
    updateForm(form);
  }

  function initNoScoreToggle(form) {
    const toggle = form.querySelector("[data-no-score-toggle]");
    if (!toggle) {
      return;
    }
    toggle.addEventListener("change", () => {
      if (toggle.checked) {
        applyNoScore(form);
      } else {
        clearNoScore(form);
      }
    });
  }

  function selectDefaultScoreOnFocus(input) {
    if (input.dataset.scoreTouched === "true") {
      return;
    }
    const initial = input.dataset.initialScore;
    if (initial === undefined || initial === "") {
      return;
    }
    if (input.value === initial) {
      input.select();
    }
  }

  function initGameRecordForm() {
    const form =
      document.getElementById("game-record-form") ||
      document.getElementById("game-edit-form");
    if (!form) {
      return;
    }

    form.addEventListener("focusin", (event) => {
      if (event.target.matches("[data-score-input]")) {
        selectDefaultScoreOnFocus(event.target);
      }
    });

    form.addEventListener("input", (event) => {
      if (event.isTrusted && event.target.matches("[data-score-input]")) {
        event.target.dataset.scoreTouched = "true";
      }
      updateForm(form);
    });

    form.addEventListener("change", (event) => {
      if (event.isTrusted && event.target.matches("[data-score-input]")) {
        event.target.dataset.scoreTouched = "true";
      }
      updateForm(form);
    });

    form.addEventListener("submit", () => {
      materializeInitialScores(form);
    });

    watchParticipantRows(form);
    initNoScoreToggle(form);
    updateForm(form);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGameRecordForm);
  } else {
    initGameRecordForm();
  }
})();
