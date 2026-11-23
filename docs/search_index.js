// Автосборка: build_html.py. Куски поискового индекса подключает index.html.
(function () {
  if (window.__searchChunksLoaded) return;
  window.__searchChunksLoaded = true;
  var base = ["search_index_PART_0.js"];
  window.__searchExpected = base.length;
  var host = document.currentScript ? document.currentScript.parentNode : document.head;
  (function next(k) {
    if (k >= base.length) return;
    var s = document.createElement('script');
    s.src = base[k];
    s.onload = function () { next(k + 1); };
    s.onerror = function () { next(k + 1); };
    host.appendChild(s);
  })(0);
})();
