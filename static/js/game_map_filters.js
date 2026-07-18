/**
 * Games Map filters: location type-ahead + country/state/city cascade.
 */
(function () {
  const input = document.getElementById("map-location-name-input");
  const listEl = document.getElementById("map-location-name-list");
  const choicesEl = document.getElementById("map-location-name-choices");
  const countrySelect = document.getElementById("map-country-select");
  const stateSelect = document.getElementById("map-state-select");
  const cityInput = document.getElementById("map-city-input");
  const cityDatalist = document.getElementById("map-city-datalist");
  const cascadeEl = document.getElementById("map-geo-cascade-tree");

  let names = [];
  if (choicesEl) {
    try {
      names = JSON.parse(choicesEl.textContent) || [];
    } catch (_err) {
      names = [];
    }
  }

  let cascadeTree = {};
  if (cascadeEl) {
    try {
      cascadeTree = JSON.parse(cascadeEl.textContent) || {};
    } catch (_err) {
      cascadeTree = {};
    }
  }

  function rebuildStateOptions() {
    if (!stateSelect) return;
    const country = (countrySelect?.value || "").trim().toUpperCase();
    const previous = stateSelect.value;
    const states = country
      ? Object.keys(cascadeTree[country] || {}).sort()
      : Array.from(
          new Set(
            Object.values(cascadeTree).flatMap((statesMap) =>
              Object.keys(statesMap || {}),
            ),
          ),
        ).sort();

    stateSelect.innerHTML = "";
    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = "All states";
    stateSelect.appendChild(allOpt);
    states.forEach((state) => {
      const opt = document.createElement("option");
      opt.value = state;
      opt.textContent = state;
      stateSelect.appendChild(opt);
    });
    stateSelect.value = states.includes(previous) ? previous : "";
  }

  function rebuildCityOptions() {
    if (!cityDatalist || !cityInput) return;
    const country = (countrySelect?.value || "").trim().toUpperCase();
    const state = (stateSelect?.value || "").trim();
    let cities = [];
    if (country && state) {
      cities = [...((cascadeTree[country] || {})[state] || [])];
    } else if (country) {
      cities = Object.values(cascadeTree[country] || {}).flat();
    } else if (state) {
      cities = Object.values(cascadeTree).flatMap(
        (statesMap) => statesMap[state] || [],
      );
    } else {
      cities = Object.values(cascadeTree).flatMap((statesMap) =>
        Object.values(statesMap || {}).flat(),
      );
    }
    cities = Array.from(new Set(cities)).sort((a, b) => a.localeCompare(b));
    cityDatalist.innerHTML = "";
    cities.forEach((city) => {
      const opt = document.createElement("option");
      opt.value = city;
      cityDatalist.appendChild(opt);
    });
    if (cityInput.value && !cities.includes(cityInput.value)) {
      cityInput.value = "";
    }
  }

  if (countrySelect && stateSelect) {
    countrySelect.addEventListener("change", () => {
      rebuildStateOptions();
      rebuildCityOptions();
    });
    stateSelect.addEventListener("change", rebuildCityOptions);
  }

  if (!input || !listEl || !names.length) return;

  let activeIndex = -1;
  let matches = [];

  function foldAccents(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/\p{M}/gu, "");
  }

  function normalizeForMatch(value) {
    let folded = foldAccents(value).trim().toLowerCase();
    folded = folded.replace(/[\u2018\u2019\u201A\u201B`´']/g, "'");
    folded = folded.replace(/[^a-z0-9\s']/g, "");
    return folded.replace(/\s+/g, " ").trim();
  }

  function scoreName(query, name) {
    const q = normalizeForMatch(query);
    const n = normalizeForMatch(name);
    if (!q) return 0;
    if (n === q) return 300;
    if (n.startsWith(q)) return 200 - (n.length - q.length);
    if (n.includes(q)) return 100 - (n.length - q.length);
    let qi = 0;
    for (let i = 0; i < n.length && qi < q.length; i += 1) {
      if (n[i] === q[qi]) qi += 1;
    }
    if (qi === q.length) return 10;
    return -1;
  }

  function filterNames(query) {
    const q = query.trim();
    if (!q) return names.slice(0, 12);
    return names
      .map((name) => ({ name, score: scoreName(q, name) }))
      .filter((item) => item.score >= 0)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return a.name.localeCompare(b.name);
      })
      .slice(0, 12)
      .map((item) => item.name);
  }

  function closeList() {
    listEl.hidden = true;
    listEl.innerHTML = "";
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
    matches = [];
  }

  function selectName(name) {
    input.value = name;
    closeList();
    input.focus();
  }

  function renderList() {
    listEl.innerHTML = "";
    if (!matches.length) {
      closeList();
      return;
    }
    matches.forEach((name, index) => {
      const li = document.createElement("li");
      li.className =
        "game-map-location-typeahead-option" +
        (index === activeIndex
          ? " game-map-location-typeahead-option--active"
          : "");
      li.id = "map-location-name-opt-" + index;
      li.setAttribute("role", "option");
      li.setAttribute(
        "aria-selected",
        index === activeIndex ? "true" : "false",
      );
      li.textContent = name;
      li.addEventListener("mousedown", (event) => {
        event.preventDefault();
        selectName(name);
      });
      listEl.appendChild(li);
    });
    listEl.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (activeIndex >= 0) {
      input.setAttribute(
        "aria-activedescendant",
        "map-location-name-opt-" + activeIndex,
      );
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function refresh() {
    matches = filterNames(input.value);
    activeIndex = matches.length ? 0 : -1;
    renderList();
  }

  input.addEventListener("focus", refresh);
  input.addEventListener("input", refresh);
  input.addEventListener("keydown", (event) => {
    if (listEl.hidden || !matches.length) {
      if (event.key === "Escape") closeList();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = (activeIndex + 1) % matches.length;
      renderList();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = (activeIndex - 1 + matches.length) % matches.length;
      renderList();
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectName(matches[activeIndex]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeList();
    }
  });

  input.addEventListener("blur", () => {
    window.setTimeout(closeList, 120);
  });
})();
