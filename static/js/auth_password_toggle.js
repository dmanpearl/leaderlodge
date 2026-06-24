(function () {
  function initPasswordToggle(inputId, toggleId, iconId) {
    const input = document.getElementById(inputId);
    const toggle = document.getElementById(toggleId);
    const icon = document.getElementById(iconId);
    if (!input || !toggle || !icon) {
      return;
    }

    toggle.addEventListener("click", () => {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      icon.classList.toggle("bi-eye", showing);
      icon.classList.toggle("bi-eye-slash", !showing);
      toggle.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      toggle.setAttribute("aria-pressed", String(!showing));
    });
  }

  function initAll() {
    document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
      initPasswordToggle(
        toggle.dataset.passwordInput,
        toggle.id,
        toggle.dataset.passwordIcon,
      );
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
