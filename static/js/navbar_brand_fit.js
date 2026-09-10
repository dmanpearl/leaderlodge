/**
 * Mobile portrait: show full navbar logo when it fits beside nav icons.
 */
(function () {
  const nav = document.querySelector("nav.navbar.bg-primary");
  if (!nav) return;

  const brand = nav.querySelector(".navbar-brand");
  const container = nav.querySelector(":scope > .container");
  const logo = brand?.querySelector(".navbar-brand-logo");
  const duckWrap = brand?.querySelector(".navbar-brand-duck-wrap");
  if (!brand || !container || !logo || !duckWrap) return;

  const mobilePortrait = window.matchMedia(
    "(max-width: 767.98px) and (orientation: portrait)",
  );

  let pending = false;

  function otherChildrenWidth() {
    let total = 0;
    for (const child of container.children) {
      if (child === brand) continue;
      total += child.getBoundingClientRect().width;
    }
    const gap = Number.parseFloat(getComputedStyle(container).columnGap) || 0;
    const gaps = Math.max(0, container.children.length - 1);
    return total + gap * gaps;
  }

  function measureLogoWidth() {
    nav.classList.add("navbar-brand--full-logo");
    const width = logo.getBoundingClientRect().width;
    nav.classList.remove("navbar-brand--full-logo");
    return width;
  }

  function update() {
    if (!mobilePortrait.matches) {
      nav.classList.remove("navbar-brand--full-logo");
      return;
    }

    const available = container.clientWidth - otherChildrenWidth();
    const logoWidth = measureLogoWidth();
    const fits = logoWidth > 0 && logoWidth <= available - 1;

    nav.classList.toggle("navbar-brand--full-logo", fits);
  }

  function scheduleUpdate() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      update();
    });
  }

  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(scheduleUpdate);
    observer.observe(container);
  }

  mobilePortrait.addEventListener("change", scheduleUpdate);
  window.addEventListener("orientationchange", scheduleUpdate);
  if (document.fonts?.ready) {
    document.fonts.ready.then(scheduleUpdate);
  }
  logo.addEventListener("load", scheduleUpdate);
  scheduleUpdate();
})();
