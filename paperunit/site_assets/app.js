/* paperunit UI — tiny progressive-enhancement layer.
   No dependencies, no network calls. Everything degrades to usable HTML. */

(function () {
  "use strict";

  var root = document.documentElement;
  var THEME_KEY = "paperunit-theme";

  /* ---- theme ------------------------------------------------------- */

  function currentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function applyTheme(theme) {
    if (theme === "dark") {
      root.setAttribute("data-theme", "dark");
    } else {
      root.removeAttribute("data-theme");
    }
    var toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      var label = toggle.querySelector("[data-theme-label]");
      if (label) {
        label.textContent = theme === "dark" ? "Light" : "Dark";
      }
    }
  }

  var toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        window.localStorage.setItem(THEME_KEY, next);
      } catch (err) {
        /* storage unavailable: the toggle still works for this page */
      }
    });
    applyTheme(currentTheme());
  } else {
    applyTheme(currentTheme());
  }

  /* ---- copy-to-clipboard ------------------------------------------- */

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) {
      return;
    }
    var text = button.getAttribute("data-copy") || "";
    var done = function () {
      var original = button.textContent;
      button.textContent = "Copied";
      window.setTimeout(function () {
        button.textContent = original;
      }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {});
    } else {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "absolute";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy");
        done();
      } catch (err) {
        /* ignore */
      }
      document.body.removeChild(area);
    }
  });

  /* ---- registry filtering ------------------------------------------ */

  var list = document.querySelector("[data-audit-list]");
  if (!list) {
    return;
  }

  var rows = Array.prototype.slice.call(list.querySelectorAll("[data-audit]"));
  var searchInput = document.querySelector("[data-audit-search]");
  var filters = Array.prototype.slice.call(document.querySelectorAll("[data-audit-filter]"));
  var resultCount = document.querySelector("[data-result-count]");
  var emptyState = document.querySelector("[data-empty-state]");
  var activeFilter = "ALL";

  function normalise(value) {
    return (value || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function apply() {
    var query = normalise(searchInput ? searchInput.value : "");
    var tokens = query ? query.split(" ") : [];
    var visible = 0;

    rows.forEach(function (row) {
      var verdicts = row.getAttribute("data-verdicts") || "";
      var haystack = normalise(row.getAttribute("data-search"));
      var matchesFilter = activeFilter === "ALL" || verdicts.indexOf(activeFilter) !== -1;
      var matchesQuery = tokens.every(function (token) {
        return haystack.indexOf(token) !== -1;
      });
      var show = matchesFilter && matchesQuery;
      row.classList.toggle("is-hidden", !show);
      if (show) {
        visible += 1;
      }
    });

    if (resultCount) {
      resultCount.textContent =
        visible + (visible === 1 ? " audit" : " audits") + " of " + rows.length;
    }
    if (emptyState) {
      emptyState.classList.toggle("is-hidden", !(rows.length === 0 || visible === 0));
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", apply);
  }

  filters.forEach(function (button) {
    button.addEventListener("click", function () {
      activeFilter = button.getAttribute("data-audit-filter") || "ALL";
      filters.forEach(function (other) {
        other.setAttribute("aria-pressed", other === button ? "true" : "false");
      });
      apply();
    });
  });

  apply();
})();
