(function () {
  var el = document.getElementById("feed");
  if (!el) return;

  var feedUrl = el.dataset.url;
  var acceptTpl = el.dataset.accept;
  var csrf = el.dataset.csrf;
  var onListPage = el.dataset.listPage === "1";
  var SEEN_KEY = "pautos_seen_requests";

  var stored = null;
  try { stored = JSON.parse(sessionStorage.getItem(SEEN_KEY)); } catch (e) {}
  var firstRun = !Array.isArray(stored);   // first check of this browser session stays silent
  var seen = new Set(Array.isArray(stored) ? stored : []);
  var lastKey = null;
  var cards = {};
  var timer = null;

  var stack = document.createElement("div");
  stack.id = "popup-stack";
  stack.setAttribute("aria-live", "polite");
  document.body.appendChild(stack);

  function saveSeen() {
    try { sessionStorage.setItem(SEEN_KEY, JSON.stringify(Array.from(seen).slice(-200))); } catch (e) {}
  }

  function alertRider() {
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) {
        var ctx = new Ctx(), osc = ctx.createOscillator(), gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = 880;
        gain.gain.value = 0.08;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.25);
      }
    } catch (e) {}
    try { if (navigator.vibrate) navigator.vibrate([200, 100, 200]); } catch (e) {}
  }

  function removeCard(id) {
    var card = cards[id];
    if (card && card.parentNode) card.parentNode.removeChild(card);
    delete cards[id];
  }

  function makeCard(req) {
    var card = document.createElement("div");
    card.className = "popup-card";

    function line(label, value) {
      var p = document.createElement("p");
      var b = document.createElement("strong");
      b.textContent = label + ": ";
      p.appendChild(b);
      p.appendChild(document.createTextNode(value));   // textContent only, never innerHTML
      card.appendChild(p);
    }

    var h = document.createElement("h3");
    h.textContent = "New request: " + req.category;
    card.appendChild(h);
    if (req.instructions) line("Task", req.instructions);
    line("Pickup", req.pickup);
    line("Deliver to", req.dropoff);
    line("Your fee", req.fee.toFixed(2) + " PHP");
    if (req.budget !== null) line("Item budget", req.budget.toFixed(2) + " PHP");
    if (req.distance_km !== null) line("Distance", req.distance_km + " km from you");

    var actions = document.createElement("div");
    actions.className = "actions";

    var form = document.createElement("form");
    form.method = "post";
    form.action = acceptTpl.replace("/0/", "/" + req.id + "/");
    var token = document.createElement("input");
    token.type = "hidden";
    token.name = "csrf_token";
    token.value = csrf;
    var accept = document.createElement("button");
    accept.type = "submit";
    accept.className = "btn";
    accept.textContent = "Accept";
    form.appendChild(token);
    form.appendChild(accept);

    var dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "btn secondary";
    dismiss.textContent = "Dismiss";
    dismiss.addEventListener("click", function () { removeCard(req.id); });

    actions.appendChild(form);
    actions.appendChild(dismiss);
    card.appendChild(actions);
    return card;
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(poll, 5000);
  }

  function poll() {
    if (document.hidden) { schedule(); return; }
    fetch(feedUrl, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (!data.active) {
          Object.keys(cards).forEach(removeCard);
          return;
        }
        var ids = data.requests.map(function (r) { return r.id; });

        Object.keys(cards).forEach(function (id) {
          if (ids.indexOf(Number(id)) === -1) removeCard(id);   // taken by someone else or cancelled
        });

        var fresh = data.requests.filter(function (r) { return !seen.has(r.id); });
        data.requests.forEach(function (r) { seen.add(r.id); });
        saveSeen();

        if (onListPage) {
          var key = ids.slice().sort(function (a, b) { return a - b; }).join(",");
          if (lastKey !== null && key !== lastKey) {
            if (fresh.length && !firstRun) alertRider();
            setTimeout(function () { location.reload(); }, 300);
            return;
          }
          lastKey = key;
        } else if (!firstRun && fresh.length) {
          fresh.forEach(function (r) {
            if (!cards[r.id]) {
              cards[r.id] = makeCard(r);
              stack.appendChild(cards[r.id]);
            }
          });
          alertRider();
        }
        firstRun = false;
      })
      .catch(function () {})
      .then(schedule);
  }

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { clearTimeout(timer); poll(); }
  });

  poll();
})();