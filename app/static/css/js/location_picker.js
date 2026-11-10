(function () {
  var mapEl = document.getElementById("map-picker");
  if (!mapEl || !window.L) {
    return;
  }

  var message = document.getElementById("picker-msg");

  function field(id) {
    return document.getElementById(id);
  }

  function say(text) {
    if (message) {
      message.textContent = text;
    }
  }

  var targets = {
    dropoff: {
      label: "Delivery",
      color: "#0b7a4b",
      lat: field("dropoff_lat"),
      lng: field("dropoff_lng"),
      address: field("dropoff_address"),
      marker: null
    },
    pickup: {
      label: "Pickup",
      color: "#c77700",
      lat: field("pickup_lat"),
      lng: field("pickup_lng"),
      address: field("pickup_address"),
      marker: null
    }
  };

  var map = L.map(mapEl).setView([12.8797, 121.774], 5);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  function current() {
    var checked = document.querySelector("input[name=pin_target]:checked");
    return targets[checked ? checked.value : "dropoff"];
  }

  function placePin(target, lat, lng, zoomIn) {
    target.lat.value = lat.toFixed(7);
    target.lng.value = lng.toFixed(7);
    if (target.marker) {
      target.marker.setLatLng([lat, lng]);
    } else {
      target.marker = L.circleMarker([lat, lng], {
        radius: 10,
        color: target.color,
        fillColor: target.color,
        fillOpacity: 0.8
      })
        .addTo(map)
        .bindTooltip(target.label, { permanent: true, direction: "top" });
    }
    if (zoomIn) {
      map.setView([lat, lng], Math.max(map.getZoom(), 16));
    }
  }

  function removePin(target) {
    target.lat.value = "";
    target.lng.value = "";
    if (target.marker) {
      map.removeLayer(target.marker);
      target.marker = null;
    }
  }

  function fitToPins() {
    var markers = [];
    Object.keys(targets).forEach(function (key) {
      if (targets[key].marker) {
        markers.push(targets[key].marker);
      }
    });
    if (markers.length) {
      map.fitBounds(L.featureGroup(markers).getBounds().pad(0.3), { maxZoom: 16 });
    }
  }

  Object.keys(targets).forEach(function (key) {
    var target = targets[key];
    var lat = parseFloat(target.lat.value);
    var lng = parseFloat(target.lng.value);
    if (!isNaN(lat) && !isNaN(lng)) {
      placePin(target, lat, lng, false);
    }
  });
  fitToPins();

  map.on("click", function (event) {
    var target = current();
    placePin(target, event.latlng.lat, event.latlng.lng, false);
    say(target.label + " pin placed. Tap somewhere else on the map to move it.");
  });

  document.getElementById("clear-pin").addEventListener("click", function () {
    var target = current();
    removePin(target);
    say(target.label + " pin removed.");
  });

  document.getElementById("use-my-location").addEventListener("click", function () {
    if (!navigator.geolocation) {
      say("This device can't share its location. Tap the map to drop a pin instead.");
      return;
    }
    say("Getting your location...");
    navigator.geolocation.getCurrentPosition(
      function (position) {
        var target = current();
        placePin(target, position.coords.latitude, position.coords.longitude, true);
        say(target.label + " pin placed at your location.");
      },
      function () {
        say("Couldn't get your location. Tap the map to drop a pin instead.");
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  });

  document.getElementById("find-address").addEventListener("click", function () {
    var target = current();
    var query = target.address ? target.address.value.trim() : "";
    if (!query) {
      say("Type the " + target.label.toLowerCase() + " address first, then press Find.");
      return;
    }
    say("Searching...");
    var url =
      "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=ph&q=" +
      encodeURIComponent(query);
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) {
        return response.json();
      })
      .then(function (rows) {
        if (!rows.length) {
          say("Couldn't find that address. Tap the map to drop a pin instead.");
          return;
        }
        placePin(target, parseFloat(rows[0].lat), parseFloat(rows[0].lon), true);
        say(target.label + " pin placed. Tap the map to adjust it if it's off.");
      })
      .catch(function () {
        say("Address search isn't available right now. Tap the map to drop a pin instead.");
      });
  });
})();