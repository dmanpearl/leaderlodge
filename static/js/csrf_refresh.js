(function () {
  var refreshTimer = null;
  var refreshPromise = null;
  var wasHidden = false;

  function getCsrfTokenFromCookie() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function updateCsrfInputs(token, root) {
    if (!token) {
      return;
    }
    var scope = root && root.querySelector ? root : document;
    scope
      .querySelectorAll('input[name="csrfmiddlewaretoken"]')
      .forEach(function (input) {
        input.value = token;
      });
  }

  function syncCsrfFromCookie(root) {
    updateCsrfInputs(getCsrfTokenFromCookie(), root);
  }

  function refreshCsrfTokens() {
    var url = document.body && document.body.dataset.csrfRefreshUrl;
    if (!url) {
      return Promise.resolve("");
    }
    if (refreshPromise) {
      return refreshPromise;
    }

    refreshPromise = fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        if (!response.ok) {
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        var token =
          (data && data.csrfToken) || getCsrfTokenFromCookie() || "";
        if (token) {
          updateCsrfInputs(token);
        }
        return token;
      })
      .catch(function () {
        return getCsrfTokenFromCookie() || "";
      })
      .finally(function () {
        refreshPromise = null;
      });

    return refreshPromise;
  }

  function scheduleCsrfRefresh() {
    if (refreshTimer) {
      window.clearTimeout(refreshTimer);
    }
    refreshTimer = window.setTimeout(function () {
      refreshCsrfTokens();
    }, 100);
  }

  function recoverAfterSleep() {
    syncCsrfFromCookie();
    scheduleCsrfRefresh();
  }

  window.leaderlodgeGetCsrfToken = getCsrfTokenFromCookie;
  window.leaderlodgeRefreshCsrfToken = refreshCsrfTokens;

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      wasHidden = true;
      return;
    }
    if (document.visibilityState === "visible") {
      wasHidden = false;
      recoverAfterSleep();
    }
  });

  /* Some iOS browsers fire focus but not visibilitychange on app resume */
  window.addEventListener("focus", function () {
    if (wasHidden || !getCsrfTokenFromCookie()) {
      wasHidden = false;
      recoverAfterSleep();
    }
  });

  window.addEventListener("pageshow", function () {
    /* Always refresh on pageshow: iOS bfcache restores are flaky about
       event.persisted, and a cheap token fetch beats a 403 form POST. */
    recoverAfterSleep();
  });

  document.addEventListener("DOMContentLoaded", function () {
    syncCsrfFromCookie();
    scheduleCsrfRefresh();
  });

  document.addEventListener(
    "submit",
    function (event) {
      var form = event.target;
      if (!form || !form.querySelector) {
        return;
      }
      if (!form.querySelector('input[name="csrfmiddlewaretoken"]')) {
        return;
      }

      var token = getCsrfTokenFromCookie();
      if (token) {
        updateCsrfInputs(token, form);
        return;
      }

      /* Cookie is absent (common after iOS sleep). Block submit, refresh,
         then retry only if a cookie is available. Never POST without one. */
      var url = document.body && document.body.dataset.csrfRefreshUrl;
      if (!url) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();

      refreshCsrfTokens().then(function (freshToken) {
        if (freshToken && getCsrfTokenFromCookie()) {
          updateCsrfInputs(freshToken, form);
          form.submit();
          return;
        }
        window.location.reload();
      });
    },
    true,
  );
})();
