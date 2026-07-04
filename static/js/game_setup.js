(function () {
  function syncGameTypeIcon() {
    const select = document.getElementById("game-setup-game-type-select");
    const icon = document.getElementById("game-setup-game-type-icon");
    const wrap = document.querySelector(".game-setup-game-type-wrap");
    if (!select || !icon || !wrap) {
      return;
    }

    const option = select.options[select.selectedIndex];
    const iconUrl = option?.dataset.iconUrl;
    if (iconUrl) {
      icon.src = iconUrl;
      icon.classList.remove("d-none");
      wrap.classList.add("game-setup-game-type-wrap--has-icon");
      return;
    }

    icon.removeAttribute("src");
    icon.classList.add("d-none");
    wrap.classList.remove("game-setup-game-type-wrap--has-icon");
  }

  function initGameSetupGameTypeIcon() {
    const select = document.getElementById("game-setup-game-type-select");
    if (!select) {
      return;
    }

    syncGameTypeIcon();
    select.addEventListener("change", syncGameTypeIcon);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGameSetupGameTypeIcon);
  } else {
    initGameSetupGameTypeIcon();
  }
})();
