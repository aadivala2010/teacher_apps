// Auto-fit font size: bigger font for little text, smaller as text grows, so
// content always fills its box without overflowing. Applies to every text
// input and textarea on the page.
//
// Textareas inside the planner or the activity descriptor form one GROUP per
// app: every box in the group gets the same font size (the size the fullest
// box needs), so the whole page looks uniform instead of each box picking its
// own size.
(function () {
  var MAX_PX = 30;
  var MIN_PX = 10;
  var TEXTY = /^(text|search|email|url|tel|number|password|)$/; // "" = default input type
  var GROUP_ROOTS = ["#plannerApp", "#activityDescriptorApp"];

  function isFittable(el) {
    if (!el) return false;
    if (el.tagName === "TEXTAREA") return true;
    return el.tagName === "INPUT" && TEXTY.test(el.type);
  }

  // Textareas in a group share one size; everything else fits individually.
  function groupRoot(el) {
    if (el.tagName !== "TEXTAREA" || !el.closest) return null;
    for (var i = 0; i < GROUP_ROOTS.length; i += 1) {
      var root = el.closest(GROUP_ROOTS[i]);
      if (root) return root;
    }
    return null;
  }

  // Largest font size (MIN..MAX px) at which content doesn't overflow the box.
  // Textareas fit by height (fixed rows); single-line inputs fit by width.
  // Returns the size without committing it, or 0 if the element is hidden.
  function bestFontSize(el) {
    var isArea = el.tagName === "TEXTAREA";
    if (isArea ? el.clientHeight === 0 : el.clientWidth === 0) return 0; // hidden

    var lo = MIN_PX, hi = MAX_PX, best = MIN_PX;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      el.style.fontSize = mid + "px";
      var fits = isArea
        ? el.scrollHeight <= el.clientHeight + 1
        : el.scrollWidth <= el.clientWidth + 1;
      if (fits) { best = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return best;
  }

  function fitSolo(el) {
    var best = bestFontSize(el);
    if (best) el.style.fontSize = best + "px";
  }

  function fitGroup(root) {
    var els = root.querySelectorAll("textarea");
    var size = MAX_PX;
    var visible = [];
    for (var i = 0; i < els.length; i += 1) {
      var best = bestFontSize(els[i]);
      if (!best) continue;
      visible.push(els[i]);
      if (best < size) size = best;
    }
    for (var j = 0; j < visible.length; j += 1) visible[j].style.fontSize = size + "px";
  }

  // Batch fits into one animation frame so bursts of programmatic value sets
  // (loading saved data) and freshly-appended fields measure after layout.
  var queued = new Set();
  var scheduled = false;
  function queue(el) {
    if (!isFittable(el)) return;
    queued.add(el);
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      var items = queued;
      queued = new Set();
      var groups = new Set();
      items.forEach(function (el) {
        var root = groupRoot(el);
        if (root) groups.add(root); else fitSolo(el);
      });
      groups.forEach(fitGroup);
    });
  }

  function fitAll() {
    var els = document.querySelectorAll("textarea, input");
    for (var i = 0; i < els.length; i += 1) queue(els[i]);
  }

  // Typing.
  document.addEventListener("input", function (e) { queue(e.target); }, true);

  // Switching app tabs reveals boxes that were hidden (unmeasurable) — refit.
  document.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest(".app-tab")) fitAll();
  });

  // Programmatic value sets (loading data, clearing fields, new fields) go
  // through the .value setter — hook it once so every call site refits.
  ["HTMLTextAreaElement", "HTMLInputElement"].forEach(function (name) {
    var proto = window[name].prototype;
    var desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (!desc || !desc.set) return;
    Object.defineProperty(proto, "value", {
      configurable: true,
      enumerable: desc.enumerable,
      get: desc.get,
      set: function (v) { desc.set.call(this, v); queue(this); }
    });
  });

  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(fitAll, 150);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fitAll);
  } else {
    fitAll();
  }
})();
