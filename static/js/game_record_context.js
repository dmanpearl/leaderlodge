/**
 * When Group or Game changes on the unified Record Game screen, reload with
 * the new context so roster JSON, rules, and score-type defaults stay in sync.
 * Clears in-progress participant rows by design (fresh GET).
 */
(function () {
  const form = document.getElementById("game-record-form");
  if (!form) {
    return;
  }

  const groupSelect = form.querySelector('[name="group"]');
  const gameSelect = form.querySelector("#game-setup-game-type-select");
  if (!groupSelect || !gameSelect) {
    return;
  }

  let baselineGroup = groupSelect.value;
  let baselineType = gameSelect.value;

  function reloadContext() {
    const groupId = groupSelect.value;
    const gameType = gameSelect.value;
    if (!groupId || !gameType) {
      return;
    }
    if (groupId === baselineGroup && gameType === baselineType) {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("group", groupId);
    url.searchParams.set("type", gameType);
    url.searchParams.delete("reuse_from");
    url.searchParams.delete("pick_from");
    window.LeaderLodge.navigate(url.pathname + url.search);
  }

  groupSelect.addEventListener("change", reloadContext);
  gameSelect.addEventListener("change", reloadContext);
})();
