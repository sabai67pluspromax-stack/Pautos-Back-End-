(function () {
  var el = document.getElementById("presence");
  if (!el || !("geolocation" in navigator)) return;
  var url = el.dataset.url, csrf = el.dataset.csrf, last = 0;
  var out = document.getElementById("presence-status");

  function say(text) { if (out) out.textContent = text; }

  function send(pos) {
    var now = Date.now();
    if (now - last < 15000) return;
    last = now;
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ lat: pos.coords.latitude, lng: pos.coords.longitude })
    })
      .then(function (r) { say(r.ok ? "Sharing your location so you can get nearby requests." : "Couldn't share your location."); })
      .catch(function () { say("Couldn't share your location (network problem)."); });
  }

  navigator.geolocation.watchPosition(
    send,
    function () { say("Location is blocked. Allow it so you can get nearby requests."); },
    { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
  );
})();