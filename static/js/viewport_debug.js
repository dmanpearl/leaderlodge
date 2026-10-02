/**
 * Staff-only viewport geometry overlay for debugging portaled dropdowns on
 * real devices (iOS Safari in particular).
 *
 * Enable with ?vdebug=1, disable with ?vdebug=0. The flag persists in
 * localStorage so it survives navigation and app restarts on a phone.
 *
 * It watches portaled combobox lists for inline style changes and reports
 * what the positioning code asked for against what the browser produced.
 * There are no hooks into the picker scripts, so this file can be added or
 * removed without touching them.
 */
(function () {
  const FLAG_KEY = "llViewportDebug";
  const WATCH_SELECTOR = '.combobox-list, [data-side-menu][data-portaled="1"]';
  // Shown on screen and stamped into every reading. Phone browsers cache the
  // page, and a stale script is indistinguishable from a broken one without
  // this. Bump it together with the ?v= in base.html.
  const VERSION = 12;

  function readFlag() {
    try {
      const flag = new URLSearchParams(window.location.search).get("vdebug");
      if (flag === "1") {
        window.localStorage.setItem(FLAG_KEY, "1");
        return true;
      }
      if (flag === "0") {
        window.localStorage.removeItem(FLAG_KEY);
        return false;
      }
      return window.localStorage.getItem(FLAG_KEY) === "1";
    } catch (_error) {
      return false;
    }
  }

  if (!readFlag()) {
    return;
  }

  const nodes = {
    panel: null,
    readout: null,
    copyButton: null,
    copyField: null,
    fixedProbe: null,
    unitProbe: null,
    marks: {},
  };
  let reportQueued = false;
  const counters = { mutations: 0, reports: 0, errors: 0 };
  let lastError = "";

  // One snapshot per copy forced a choreography on the phone: keep the list
  // open, get the keyboard up, then tap copy without disturbing either. Keep
  // every distinct state instead, so a single copy carries the whole session.
  const HISTORY_LIMIT = 40;
  const history = [];
  let lastSignature = "";

  // Fields that mean the geometry actually changed. Anything outside this set
  // (timestamps, counters) would make every poll tick look like a new state.
  const SIGNATURE_KEYS = [
    "ev",
    "field",
    "above",
    "typing",
    "scrollY",
    "vvH",
    "vvOffTop",
    "vvScale",
    "anchorTop",
    "askedTop",
    "maxH",
    "gotTop",
    "gotH",
  ];

  function recordState(payload) {
    const signature = SIGNATURE_KEYS.map((key) => payload[key]).join("|");
    if (signature === lastSignature) {
      return;
    }
    lastSignature = signature;
    history.push(payload);
    if (history.length > HISTORY_LIMIT) {
      history.shift();
    }
  }

  function historyText() {
    const header = `vdebug v${VERSION}`;
    if (!history.length) {
      return `${header} no reading yet`;
    }
    return [header]
      .concat(history.map((entry) => JSON.stringify(entry)))
      .join("\n");
  }

  function makeNode(key, cssText) {
    const el = document.createElement("div");
    el.dataset.viewportDebug = key;
    el.style.cssText = cssText;
    document.body.appendChild(el);
    return el;
  }

  function ensureNodes() {
    if (nodes.panel) {
      return;
    }
    nodes.panel = makeNode(
      "panel",
      [
        "position:fixed",
        "top:0",
        "left:0",
        "z-index:99999",
        "padding:3px 5px",
        "background:rgba(0,0,0,0.82)",
        "color:#7cfc7c",
        "font:11px/1.25 ui-monospace,SFMono-Regular,Menlo,monospace",
        "white-space:pre",
        "pointer-events:none",
      ].join(";")
    );
    nodes.readout = document.createElement("div");
    // An empty panel is a few invisible pixels against a dark navbar, so say
    // so plainly: no readout means the module never loaded.
    nodes.readout.textContent = `vdebug v${VERSION} ready: open a smart list`;
    nodes.panel.appendChild(nodes.readout);

    // The panel has to be tappable to offer copy, but nothing else in it
    // should swallow taps aimed at the page underneath.
    nodes.copyButton = document.createElement("button");
    nodes.copyButton.type = "button";
    nodes.copyButton.textContent = "copy";
    nodes.copyButton.style.cssText = [
      "margin-top:3px",
      "min-height:30px",
      "padding:4px 14px",
      "border:1px solid #7cfc7c",
      "border-radius:4px",
      "background:#123",
      "color:#7cfc7c",
      "font:12px/1 ui-monospace,SFMono-Regular,Menlo,monospace",
      "pointer-events:auto",
    ].join(";");
    nodes.copyButton.addEventListener("click", copyLastPayload);
    nodes.panel.appendChild(nodes.copyButton);

    nodes.copyField = document.createElement("textarea");
    nodes.copyField.dataset.viewportDebug = "copy-field";
    // Focusing this field to preselect its text would raise the keyboard and
    // change the very viewport the overlay is measuring. iOS shows no
    // keyboard for a readonly field, and selection and copy still work.
    nodes.copyField.readOnly = true;
    nodes.copyField.rows = 6;
    nodes.copyField.style.cssText = [
      "display:none",
      "width:100%",
      "margin-top:3px",
      "border:1px solid #7cfc7c",
      "background:#000",
      "color:#7cfc7c",
      // 16px floor, same reason as .form-control in site.css: focusing a
      // smaller field zooms iOS Safari, and this one is focused to copy.
      "font:16px/1.25 ui-monospace,SFMono-Regular,Menlo,monospace",
      "pointer-events:auto",
      "-webkit-user-select:text",
      "user-select:text",
    ].join(";");
    nodes.panel.appendChild(nodes.copyField);
    // A fixed element stretched to all four edges measures the real
    // containing block for position:fixed, which iOS Safari does not
    // guarantee to match documentElement.clientHeight.
    nodes.fixedProbe = makeNode(
      "fixed-probe",
      "position:fixed;top:0;left:0;right:0;bottom:0;opacity:0;pointer-events:none"
    );
    nodes.unitProbe = makeNode(
      "unit-probe",
      "position:absolute;top:0;left:0;width:0;opacity:0;pointer-events:none"
    );
  }

  // iOS keeps position:fixed pinned to the layout viewport, so the panel
  // scrolls out of sight once the keyboard offsets the visual viewport.
  function positionPanel() {
    const vv = window.visualViewport;
    if (!nodes.panel || !vv) {
      return;
    }
    nodes.panel.style.top = `${vv.offsetTop}px`;
    nodes.panel.style.left = `${vv.offsetLeft}px`;
    nodes.panel.style.maxWidth = `${vv.width}px`;
  }

  // navigator.clipboard needs a secure context, which http://<lan-ip> is not,
  // so fall back to selecting a textarea and letting the page copy command run.
  function flashCopyButton(message) {
    nodes.copyButton.textContent = message;
    window.setTimeout(() => {
      nodes.copyButton.textContent = "copy";
    }, 1500);
  }

  // iOS will not copy from an offscreen field, so show a real one with the
  // text preselected. Even when execCommand is refused, the selection puts
  // the system Copy callout one long press away.
  function showCopyField(text) {
    const field = nodes.copyField;
    field.style.display = "block";
    field.value = text;
    field.focus();
    field.setSelectionRange(0, text.length);
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (_error) {
      copied = false;
    }
    flashCopyButton(copied ? "copied" : "select and copy");
  }

  function copyLastPayload() {
    const text = historyText();
    if (window.navigator.clipboard?.writeText) {
      window.navigator.clipboard.writeText(text).then(
        () => flashCopyButton("copied"),
        () => showCopyField(text)
      );
      return;
    }
    showCopyField(text);
  }

  function mark(key, cssText) {
    if (!nodes.marks[key]) {
      nodes.marks[key] = makeNode(key, cssText);
    }
    return nodes.marks[key];
  }

  function hideMarks() {
    Object.keys(nodes.marks).forEach((key) => {
      nodes.marks[key].style.display = "none";
    });
  }

  // Fixed rules mark values written as position:fixed; the dashed rule marks
  // the anchor top in document coordinates. If they disagree on screen, then
  // fixed positioning and getBoundingClientRect are not in the same space.
  function drawMarks(askedTop, visibleBottom, anchorRect) {
    const asked = mark(
      "asked-top",
      "position:fixed;left:0;right:0;height:0;border-top:2px solid #ff3b30;z-index:99998;pointer-events:none"
    );
    const bottom = mark(
      "visible-bottom",
      "position:fixed;left:0;right:0;height:0;border-top:2px solid #34c759;z-index:99998;pointer-events:none"
    );
    const anchor = mark(
      "anchor-top",
      "position:absolute;left:0;right:0;height:0;border-top:2px dashed #0a84ff;z-index:99998;pointer-events:none"
    );
    if (Number.isFinite(askedTop)) {
      asked.style.display = "block";
      asked.style.top = `${askedTop}px`;
    } else {
      asked.style.display = "none";
    }
    bottom.style.display = "block";
    bottom.style.top = `${visibleBottom - 2}px`;
    if (anchorRect) {
      anchor.style.display = "block";
      anchor.style.top = `${anchorRect.top + window.scrollY}px`;
    } else {
      anchor.style.display = "none";
    }
  }

  function viewportUnits() {
    const probe = nodes.unitProbe;
    const read = (value) => {
      probe.style.height = value;
      return probe.getBoundingClientRect().height;
    };
    return { svh: read("100svh"), lvh: read("100lvh"), dvh: read("100dvh") };
  }

  function anchorForList(listEl) {
    if (listEl.id) {
      const owner = document.querySelector(
        `[aria-controls="${listEl.id}"][aria-expanded="true"]`
      );
      if (owner) {
        return owner;
      }
    }
    const active = document.activeElement;
    return active && active.tagName === "INPUT" ? active : null;
  }

  function anchorLabel(anchor) {
    if (!anchor) {
      return "no-anchor";
    }
    if (anchor.hasAttribute("data-add-teammate")) {
      return "teammate";
    }
    if (anchor.hasAttribute("data-player-picker")) {
      return "player";
    }
    return anchor.id || anchor.name || anchor.tagName.toLowerCase();
  }

  function round(value) {
    return Number.isFinite(value) ? Math.round(value * 10) / 10 : null;
  }

  function report(listEl) {
    ensureNodes();
    const anchor = anchorForList(listEl);
    const anchorRect = anchor ? anchor.getBoundingClientRect() : null;
    const fixedRect = nodes.fixedProbe.getBoundingClientRect();
    const units = viewportUnits();
    const vv = window.visualViewport;
    const docHeight = document.documentElement.clientHeight;
    const visibleBottom = vv ? vv.offsetTop + vv.height : docHeight;
    const askedTop = parseFloat(listEl.style.top);
    const gotRect = listEl.getBoundingClientRect();

    drawMarks(askedTop, visibleBottom, anchorRect);

    const payload = {
      ev: "list",
      t: Math.round(window.performance.now()),
      field: anchorLabel(anchor),
      above: listEl.classList.contains("combobox-list--above") ? 1 : 0,
      typing: anchor && anchor.value && anchor.value.trim() ? 1 : 0,
      docClientH: round(docHeight),
      innerH: round(window.innerHeight),
      scrollY: round(window.scrollY),
      vvH: round(vv ? vv.height : NaN),
      vvOffTop: round(vv ? vv.offsetTop : NaN),
      vvScale: round(vv ? vv.scale : NaN),
      fixedTop: round(fixedRect.top),
      fixedH: round(fixedRect.height),
      barGuess: round(docHeight - fixedRect.height),
      svh: round(units.svh),
      lvh: round(units.lvh),
      dvh: round(units.dvh),
      anchorTop: round(anchorRect ? anchorRect.top : NaN),
      anchorBot: round(anchorRect ? anchorRect.bottom : NaN),
      anchorH: round(anchorRect ? anchorRect.height : NaN),
      askedTop: round(askedTop),
      maxH: round(parseFloat(listEl.style.maxHeight)),
      gotTop: round(gotRect.top),
      gotBot: round(gotRect.bottom),
      gotH: round(gotRect.height),
      delta: round(gotRect.top - askedTop),
      // The number that actually matters: how far the list landed from the
      // edge of the field it is supposed to hug. 0 is correct. delta only
      // says the browser honored style.top, which it can do while the list
      // sits nowhere near the anchor.
      anchorErr: anchorRect
        ? round(
            listEl.classList.contains("combobox-list--above")
              ? gotRect.bottom - anchorRect.top
              : gotRect.top - anchorRect.bottom
          )
        : null,
    };

    recordState(payload);
    nodes.panel.style.display = "block";
    positionPanel();
    nodes.readout.textContent = [
      `${payload.field} above=${payload.above} typing=${payload.typing}`,
      `doc=${payload.docClientH} inner=${payload.innerH} scrollY=${payload.scrollY}`,
      `vv h=${payload.vvH} offTop=${payload.vvOffTop} scale=${payload.vvScale}`,
      `fixedCB top=${payload.fixedTop} h=${payload.fixedH} bar?=${payload.barGuess}`,
      `svh=${payload.svh} lvh=${payload.lvh} dvh=${payload.dvh}`,
      `anchor top=${payload.anchorTop} bot=${payload.anchorBot} h=${payload.anchorH}`,
      `asked top=${payload.askedTop} maxH=${payload.maxH}`,
      `got top=${payload.gotTop} bot=${payload.gotBot} h=${payload.gotH}`,
      `delta got-asked=${payload.delta} anchorErr=${payload.anchorErr}`,
      statusLine(1),
    ].join("\n");
    console.log("viewport-debug", JSON.stringify(payload));
  }

  function statusLine(openCount) {
    const base = `v${VERSION} n=${history.length} mut=${counters.mutations} rep=${counters.reports} open=${openCount} err=${counters.errors}`;
    return lastError ? `${base}\n${lastError}` : base;
  }

  // Without this, any thrown error leaves the panel silently stuck on the
  // idle message, which reads as "the tool does not work" on a phone.
  function safeReport(listEl) {
    try {
      counters.reports += 1;
      report(listEl);
    } catch (error) {
      counters.errors += 1;
      lastError = `ERR ${error && error.message ? error.message : error}`;
      if (nodes.readout) {
        nodes.readout.textContent = statusLine(1);
      }
    }
  }

  // The keyboard opening or closing while no list is open is still evidence,
  // and it is what tells us whether a later list measurement was taken with
  // the keyboard up.
  function recordViewportOnly() {
    const vv = window.visualViewport;
    recordState({
      ev: "vv",
      t: Math.round(window.performance.now()),
      field: anchorLabel(document.activeElement),
      innerH: round(window.innerHeight),
      scrollY: round(window.scrollY),
      vvH: round(vv ? vv.height : NaN),
      vvOffTop: round(vv ? vv.offsetTop : NaN),
      vvScale: round(vv ? vv.scale : NaN),
    });
  }

  function openWatchedList() {
    const lists = document.querySelectorAll(WATCH_SELECTOR);
    for (const listEl of lists) {
      if (!listEl.hidden && listEl.getBoundingClientRect().height > 0) {
        return listEl;
      }
    }
    return null;
  }

  function runReport() {
    reportQueued = false;
    positionPanel();
    const listEl = openWatchedList();
    if (listEl) {
      safeReport(listEl);
    } else {
      hideMarks();
      recordViewportOnly();
      if (nodes.readout && !counters.reports) {
        nodes.readout.textContent = `vdebug ready: open a smart list\n${statusLine(0)}`;
      }
    }
  }

  function queueReport() {
    if (reportQueued) {
      return;
    }
    reportQueued = true;
    window.requestAnimationFrame(runReport);
  }

  function watch() {
    ensureNodes();
    const observer = new MutationObserver((records) => {
      const touched = records.some((record) => {
        const target = record.target;
        return (
          target instanceof Element &&
          !target.dataset.viewportDebug &&
          target.matches(WATCH_SELECTOR)
        );
      });
      if (touched) {
        counters.mutations += 1;
        queueReport();
      }
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["style", "class", "hidden"],
    });
    window.addEventListener("resize", queueReport);
    window.addEventListener("scroll", queueReport, { passive: true });
    window.visualViewport?.addEventListener("resize", positionPanel);
    window.visualViewport?.addEventListener("scroll", positionPanel);
    window.visualViewport?.addEventListener("resize", queueReport);
    window.visualViewport?.addEventListener("scroll", queueReport);
    positionPanel();
    queueReport();
    // Mutation detection alone proved unreliable on iOS, and a debug overlay
    // can afford to poll. The poll runs outside requestAnimationFrame: a frame
    // callback that never fires (backgrounded tab) would otherwise leave
    // reportQueued stuck true and wedge every later report.
    window.setInterval(runReport, 300);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watch);
  } else {
    watch();
  }
})();
