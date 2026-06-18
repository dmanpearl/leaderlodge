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
    return Array.from(form.querySelectorAll("[data-game-row]")).map((row) => {
      const playerId = row.dataset.playerId;
      const scoreInput = row.querySelector("[data-score-input]");
      const score = parseScore(scoreInput.value);
      const played = scoreInput.value.trim() !== "" && score !== null;
      return {
        playerId,
        score: played ? score : null,
        played,
        resultCell: row.querySelector("[data-result-cell]"),
      };
    });
  }

  function renderBadge(label, className) {
    return `<span class="badge ${className}">${label}</span>`;
  }

  function renderResults(rows, evaluation) {
    rows.forEach((row) => {
      const cell = row.resultCell;
      cell.textContent = "";
      if (!row.played || row.score === null) {
        return;
      }
      if (evaluation.winIds.has(row.playerId)) {
        const cls = evaluation.isDouble
          ? "result-badge result-badge--win-double"
          : "result-badge result-badge--win";
        cell.innerHTML = renderBadge("Win", cls);
      } else if (evaluation.tieIds.has(row.playerId)) {
        cell.innerHTML = renderBadge("Tie", "result-badge result-badge--tie");
      } else if (evaluation.lossIds.has(row.playerId)) {
        const cls = evaluation.isDouble
          ? "result-badge result-badge--loss-double"
          : "result-badge result-badge--loss";
        cell.innerHTML = renderBadge("Loss", cls);
      }
    });
  }

  function updateForm(form) {
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
    rows.forEach((row) => {
      const domRow = form.querySelector(
        `[data-game-row][data-player-id="${row.playerId}"]`
      );
      const scoreInput = domRow.querySelector("[data-score-input]");
      if (scoreInput.value.trim() !== "" && row.score === null) {
        row.score = 0;
        row.played = true;
      }
    });

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
    saveBtn.disabled = !countOk;

    if (feedback) {
      if (!countOk && evaluation.playerCount > 0) {
        feedback.textContent = `Enter scores for ${minPlayers} to ${maxPlayers} players. Currently ${evaluation.playerCount}.`;
        feedback.classList.remove("d-none");
      } else if (evaluation.isDouble) {
        feedback.textContent = "Double game — counts as 2 in standings.";
        feedback.classList.remove("d-none");
        feedback.classList.remove("alert-warning");
        feedback.classList.add("alert-info");
      } else {
        feedback.textContent = "";
        feedback.classList.add("d-none");
        feedback.classList.add("alert-warning");
        feedback.classList.remove("alert-info");
      }
    }
  }

  function initGameRecordForm() {
    const form = document.getElementById("game-record-form");
    if (!form) {
      return;
    }

    form.addEventListener("input", (event) => {
      if (event.target.matches("[data-score-input]")) {
        updateForm(form);
      }
    });

    updateForm(form);
  }

  document.addEventListener("DOMContentLoaded", initGameRecordForm);
})();
