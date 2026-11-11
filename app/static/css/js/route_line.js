(function () {
  var OSRM_URL = "https://router.project-osrm.org/route/v1/driving/";
  var MIN_GAP_MS = 15000;   // never ask the free server more often than this
  var REFRESH_MS = 60000;   // re-ask at least this often, so the time estimate stays fresh
  var MIN_MOVE_M = 75;      // otherwise only re-ask when the rider has moved this far

  function metres(a, b) {
    var R = 6371008.8, rad = Math.PI / 180;
    var dLat = (b[0] - a[0]) * rad, dLng = (b[1] - a[1]) * rad;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function RouteLine(map) {
    this.map = map;
    this.layer = null;
    this.lastAt = 0;
    this.lastFrom = null;
    this.lastTo = null;
    this.busy = false;
    map.attributionControl.addAttribution('Routing: <a href="https://project-osrm.org/">OSRM</a>');
  }

  RouteLine.prototype._draw = function (latlngs, dashed) {
    if (this.layer) this.map.removeLayer(this.layer);
    var style = dashed
      ? { color: "#1b4f8a", weight: 4, opacity: 0.7, dashArray: "6 8" }
      : { color: "#1b4f8a", weight: 5, opacity: 0.85 };
    this.layer = L.polyline(latlngs, style).addTo(this.map);
  };

  // from, to: [lat, lng]. done({km, minutes, straight}) runs each time a route was actually fetched.
  RouteLine.prototype.update = function (from, to, done) {
    var self = this, now = Date.now();
    if (this.busy || now - this.lastAt < MIN_GAP_MS) return;
    var sameTarget = this.lastTo && metres(this.lastTo, to) < 5;
    if (sameTarget && this.layer && now - this.lastAt < REFRESH_MS && metres(this.lastFrom, from) < MIN_MOVE_M) return;

    this.busy = true;
    this.lastAt = now;
    this.lastFrom = from;
    this.lastTo = to;

    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, 8000);
    var url = OSRM_URL + from[1] + "," + from[0] + ";" + to[1] + "," + to[0] + "?overview=full&geometries=geojson";

    fetch(url, ctrl ? { signal: ctrl.signal } : {})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.code !== "Ok" || !data.routes || !data.routes.length) throw new Error("no route");
        var route = data.routes[0];
        var latlngs = route.geometry.coordinates.map(function (c) { return [c[1], c[0]]; });
        self._draw(latlngs, false);
        if (done) done({ km: route.distance / 1000, minutes: Math.max(1, Math.round(route.duration / 60)), straight: false });
      })
      .catch(function () {
        self._draw([from, to], true);
        if (done) done({ km: metres(from, to) / 1000, minutes: null, straight: true });
      })
      .then(function () { clearTimeout(timer); self.busy = false; });
  };

  window.PautosRouteLine = RouteLine;
})();