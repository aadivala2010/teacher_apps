// Auto-fit font size: bigger font for little text, smaller as text grows, so
// content always fills its box without overflowing. Applies to every text
// input and textarea on the page.
(function () {
  var MAX_PX = 30;
  var MIN_PX = 10;
  var TEXTY = /^(text|search|email|url|tel|number|password|)$/; // "" = default input type

  function isFittable(el) {
    if (!el) return false;
    if (el.tagName === "TEXTAREA") return true;
    return el.tagName === "INPUT" && TEXTY.test(el.type);
  }

  // Largest font size (MIN..MAX px) at which content doesn't overflow the box.
  // Textareas fit by height (fixed rows); single-line inputs fit by width.
  function fitFont(el) {
    if (!isFittable(el)) return;
    var isArea = el.tagName === "TEXTAREA";
    if (isArea ? el.clientHeight === 0 : el.clientWidth === 0) return; // hidden

    var lo = MIN_PX, hi = MAX_PX, best = MIN_PX;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      el.style.fontSize = mid + "px";
      var fits = isArea
        ? el.scrollHeight <= el.clientHeight + 1
        : el.scrollWidth <= el.clientWidth + 1;
      if (fits) { best = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    el.style.fontSize = best + "px";
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
      items.forEach(fitFont);
    });
  }

  function fitAll() {
    var els = document.querySelectorAll("textarea, input");
    for (var i = 0; i < els.length; i += 1) queue(els[i]);
  }

  // Typing.
  document.addEventListener("input", function (e) { queue(e.target); }, true);

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
