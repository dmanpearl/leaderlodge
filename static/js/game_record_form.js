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

  function evaluateResults(rows, supportsLoser) {
    const active = rows.filter((row) => row.played && row.score !== null);
    const count = active.length;
    if (count === 0) {
      return {
        winIds: new Set(),
        tieIds: new Set(),
        lossIds: new Set(),
        playerCount: 0,
      };
    }

    const maxScore = Math.max(...active.map((row) => row.score));
    const minScore = Math.min(...active.map((row) => row.score));
    const atMax = active.filter((row) => row.score === maxScore);
    const atMin = active.filter((row) => row.score === minScore);

    const winIds = new Set();
    const tieIds = new Set();
    const lossIds = new Set();

    if (atMax.length === 1) {
      winIds.add(atMax[0].playerId);
    } else {
      atMax.forEach((row) => tieIds.add(row.playerId));
    }

    if (supportsLoser && maxScore !== minScore) {
      atMin.forEach((row) => lossIds.add(row.playerId));
    }

    return { winIds, tieIds, lossIds, playerCount: count };
  }

  function collectRows(form) {
    return Array.from(form.querySelectorAll("[data-game-row]")).map((row) => {
      const playerId = row.dataset.playerId;
      const scoreInput = row.querySelector("[data-score-input]");
      const playInput = row.querySelector("[data-play-input]");
      const score = parseScore(scoreInput.value);
      return {
        playerId,
        score,
        played: playInput.checked,
        resultCell: row.querySelector("[data-result-cell]"),
      };
    });
  }

  function renderResults(rows, evaluation) {
    rows.forEach((row) => {
      const cell = row.resultCell;
      cell.textContent = "";
      if (!row.played || row.score === null) {
        return;
      }
      if (evaluation.winIds.has(row.playerId)) {
        cell.innerHTML = '<span class="badge text-bg-success">Win</span>';
      } else if (evaluation.tieIds.has(row.playerId)) {
        cell.innerHTML = '<span class="badge text-bg-info">Tie</span>';
      } else if (evaluation.lossIds.has(row.playerId)) {
        cell.innerHTML = '<span class="badge text-bg-danger">Loss</span>';
      }
    });
  }

  function updateForm(form) {
    const minPlayers = Number.parseInt(form.dataset.minPlayers, 10);
    const maxPlayers = Number.parseInt(form.dataset.maxPlayers, 10);
    const supportsLoser = form.dataset.supportsLoser === "true";
    const saveBtn = form.querySelector("[data-save-button]");
    const feedback = form.querySelector("[data-score-feedback]");

    const rows = collectRows(form);
    rows.forEach((row) => {
      const domRow = form.querySelector(
        `[data-game-row][data-player-id="${row.playerId}"]`
      );
      const playInput = domRow.querySelector("[data-play-input]");
      const scoreInput = domRow.querySelector("[data-score-input]");
      if (scoreInput.value.trim() !== "") {
        playInput.checked = true;
        row.played = true;
        if (row.score === null) {
          row.score = 0;
        }
      } else {
        playInput.checked = false;
        row.played = false;
      }
    });

    const activeRows = rows.filter((row) => row.played && row.score !== null);
    const evaluation = evaluateResults(activeRows, supportsLoser);
    renderResults(rows, evaluation);

    const countOk =
      evaluation.playerCount >= minPlayers &&
      evaluation.playerCount <= maxPlayers;
    saveBtn.disabled = !countOk;

    if (feedback) {
      if (!countOk && evaluation.playerCount > 0) {
        feedback.textContent = `Enter scores for ${minPlayers} to ${maxPlayers} players. Currently ${evaluation.playerCount}.`;
        feedback.classList.remove("d-none");
      } else {
        feedback.textContent = "";
        feedback.classList.add("d-none");
      }
    }
  }

  function initGameRecordForm() {
    const form = document.getElementById("game-record-form");
    if (!form) {
      return;
    }

    form.addEventListener("input", (event) => {
      if (
        event.target.matches("[data-score-input]") ||
        event.target.matches("[data-play-input]")
      ) {
        updateForm(form);
      }
    });

    updateForm(form);
  }

  document.addEventListener("DOMContentLoaded", initGameRecordForm);
})();
