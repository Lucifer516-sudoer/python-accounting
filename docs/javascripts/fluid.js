/* python-accounting docs — fluid layer (JS).
 * Adds a gradient scroll-progress bar. Deliberately tiny: Material's
 * instant-navigation already handles page transitions; this only adds
 * the one piece of motion Material doesn't ship. */

(function () {
  "use strict";

  var reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;
  if (reduceMotion) return;

  var bar = document.createElement("div");
  bar.className = "pa-scroll-progress";
  document.body.appendChild(bar);

  var ticking = false;

  function update() {
    var doc = document.documentElement;
    var max = doc.scrollHeight - doc.clientHeight;
    var progress = max > 0 ? doc.scrollTop / max : 0;
    bar.style.transform = "scaleX(" + progress + ")";
    ticking = false;
  }

  window.addEventListener(
    "scroll",
    function () {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    },
    { passive: true }
  );

  update();
})();
