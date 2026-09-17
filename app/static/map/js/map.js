(function () {
  const ZOOM_THRESHOLD = 14;
  const DEBOUNCE_MS = 150;
  const GEOHASH_PRECISION = 5;

  const ENTITY_CONFIG = {
    stations: { url: "/api/v1/fountains", color: "#2563eb", label: "Fountain" },
    toilets: { url: "/api/v1/toilets", color: "#16a34a", label: "Public toilet" },
    bicycleParkings: {
      url: "/api/v1/bicycle-parkings",
      color: "#ea580c",
      label: "Bicycle parking",
    },

  };

  const map = L.map("map").setView([45.4642, 9.19], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  // ── Cluster groups per entità ──────────────────────────────────────────────
  const clusterGroups = {};
  const requestedGeohashes = {};
  Object.keys(ENTITY_CONFIG).forEach((type) => {
    clusterGroups[type] = L.markerClusterGroup();
    requestedGeohashes[type] = new Set();
  });

  function getSelectedOverlays() {
    return Array.from(
      document.querySelectorAll('#overlay-selector input[type="checkbox"]:checked'),
    ).map((el) => el.dataset.overlay);
  }

  function markerFor(type, item) {
    const config = ENTITY_CONFIG[type];
    const icon = L.divIcon({
      className: "custom-marker",
      html: `<span style="background:${config.color}"></span>`,
      iconSize: [16, 16],
    });
    const marker = L.marker([item.lat, item.lng], { icon });
    marker.bindPopup(popupContent(type, item));

    // Add to navigator as waypoint if in nav mode
    marker.on("click", () => {
      if (navState.active) {
        // già gestito dal popup, niente da fare
      }
    });

    // Popup with "Add as waypoint" button
    const popup = L.popup().setContent(() => {
      const div = document.createElement("div");
      const config2 = ENTITY_CONFIG[type];
      let extra = "";
      if (type === "stations" && item.name) extra = `<br>${item.name}`;
      if (type === "toilets" && item.openingHours) extra = `<br>Hours: ${item.openingHours}`;

      div.innerHTML = `<strong>${config2.label}</strong>${extra}
        <br><button class="popup-add-btn" style="margin-top:6px;padding:3px 8px;cursor:pointer;border:1px solid #2563eb;border-radius:4px;background:#eff6ff;color:#1d4ed8;font-size:0.8rem;">
          ➞️ Add as waypoint
        </button>`;
      div.querySelector(".popup-add-btn").addEventListener("click", () => {
        addWaypointFromMap(item.lat, item.lng, `${config2.label}${item.name ? ": " + item.name : ""}`);
        map.closePopup();
      });
      return div;
    });
    marker.bindPopup(popup);
    return marker;
  }

  async function fetchEntityType(type, geohashes) {
    const config = ENTITY_CONFIG[type];
    const response = await fetch(`${config.url}?gh5=${geohashes.join(",")}`);
    if (!response.ok) return [];
    return response.json();
  }

  function boundsToGeohashes(bounds) {
    return window.geohashLib.bboxes(
      bounds.getSouth(), bounds.getWest(),
      bounds.getNorth(), bounds.getEast(),
      GEOHASH_PRECISION,
    );
  }

  let debounceTimer = null;
  function scheduleUpdate() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(updateVisibleEntities, DEBOUNCE_MS);
  }

  async function updateVisibleEntities() {
    const zoom = map.getZoom();
    const zoomHint = document.getElementById("zoom-hint");
    const selected = getSelectedOverlays();

    Object.entries(clusterGroups).forEach(([type, group]) => {
      if (!selected.includes(type) && map.hasLayer(group)) map.removeLayer(group);
    });

    if (zoom < ZOOM_THRESHOLD) {
      zoomHint.hidden = false;
      return;
    }
    zoomHint.hidden = true;

    const geohashes = boundsToGeohashes(map.getBounds());

    await Promise.all(
      selected.map(async (type) => {
        const toFetch = geohashes.filter((gh) => !requestedGeohashes[type].has(gh));
        if (toFetch.length > 0) {
          toFetch.forEach((gh) => requestedGeohashes[type].add(gh));
          const items = await fetchEntityType(type, toFetch);
          items.forEach((item) => clusterGroups[type].addLayer(markerFor(type, item)));
        }
        if (!map.hasLayer(clusterGroups[type])) map.addLayer(clusterGroups[type]);
      }),
    );
  }

  map.on("moveend zoomend load", scheduleUpdate);
  document.querySelectorAll('#overlay-selector input[type="checkbox"]').forEach((el) => {
    el.addEventListener("change", scheduleUpdate);
  });
  scheduleUpdate();

  // ── Geolocalizzazione ──────────────────────────────────────────────────────
  let userLatLng = null;
  const userIcon = L.divIcon({
    className: "user-location-marker",
    html: `<div class="user-dot"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
  let userMarker = null;

  map.locate({ setView: false, maxZoom: 16, watch: true });
  map.on("locationfound", (e) => {
    userLatLng = e.latlng;
    if (!userMarker) {
      userMarker = L.marker(e.latlng, { icon: userIcon, zIndexOffset: 1000 })
        .addTo(map)
        .bindPopup("📍 You are here");
    } else {
      userMarker.setLatLng(e.latlng);
    }
    // Update "current location" fields if selected
    refreshCurrentLocationFields();
  });

  // ── NAVIGATORE ─────────────────────────────────────────────────────────────

  const navState = {
    active: false,
    waypoints: [], // [{lat, lng, label, marker, isCurrentLocation}]
    routeLayer: null,
    routeInfo: null,
  };

  // Icone waypoint
  function makeWaypointIcon(label, color) {
    return L.divIcon({
      className: "waypoint-marker",
      html: `<div style="background:${color};color:#fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)">${label}</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  }

  const wpColors = { start: "#1d4ed8", end: "#dc2626", mid: "#d97706" };

  function buildNavPanel() {
    const panel = document.getElementById("nav-panel");

    // Open/close button
    document.getElementById("nav-toggle").addEventListener("click", () => {
      panel.classList.toggle("hidden");
      if (!panel.classList.contains("hidden")) renderWaypointList();
    });

    // Use current location (general toggle)
    document.getElementById("use-location-btn").addEventListener("click", () => {
      if (!userLatLng) {
        showNavMsg("Location not yet available. Please wait for GPS.", true);
        return;
      }
      // Se il primo waypoint non è ancora "posizione attuale", lo imposta
      if (navState.waypoints.length === 0 || !navState.waypoints[0].isCurrentLocation) {
        addWaypointAtIndex(0, userLatLng.lat, userLatLng.lng, "Current location", true);
      }
    });

    // Calculate route
    document.getElementById("calc-route-btn").addEventListener("click", calcRoute);

    // Azzera
    document.getElementById("clear-route-btn").addEventListener("click", clearRoute);

    // Search waypoint (geocoding)
    document.getElementById("wp-search-btn").addEventListener("click", geocodeAndAdd);
    document.getElementById("wp-search-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") geocodeAndAdd();
    });

    // Add nearest fountain to route
    document.getElementById("add-nearest-fountain-btn").addEventListener("click", () => addNearestOnRoute("stations"));
    document.getElementById("add-nearest-parking-btn").addEventListener("click", () => addNearestOnRoute("bicycleParkings"));

    // Click on map to add waypoint (only if nav active)
    document.getElementById("map-click-add-btn").addEventListener("click", () => {
      navState.active = !navState.active;
      const btn = document.getElementById("map-click-add-btn");
      if (navState.active) {
        btn.textContent = "✋ Stop selecting";
        btn.classList.add("active");
        map.getContainer().style.cursor = "crosshair";
      } else {
        btn.textContent = "🖱️ Select point on map";
        btn.classList.remove("active");
        map.getContainer().style.cursor = "";
      }
    });

    map.on("click", (e) => {
      if (!navState.active) return;
      addWaypointFromMap(e.latlng.lat, e.latlng.lng, formatLatLng(e.latlng.lat, e.latlng.lng));
    });
  }

  function formatLatLng(lat, lng) {
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  }

  function addWaypointFromMap(lat, lng, label) {
    addWaypointEnd(lat, lng, label, false);
  }

  function addWaypointAtIndex(idx, lat, lng, label, isCurrentLocation) {
    // Rimuovi marker precedente se esiste
    if (navState.waypoints[idx]) {
      if (navState.waypoints[idx].marker) map.removeLayer(navState.waypoints[idx].marker);
    }

    const wpEntry = { lat, lng, label, isCurrentLocation, marker: null };

    if (idx === 0 && navState.waypoints.length === 0) {
      navState.waypoints.push(wpEntry);
    } else if (idx <= navState.waypoints.length) {
      navState.waypoints.splice(idx, 0, wpEntry);
    }

    updateWaypointMarkers();
    renderWaypointList();
  }

  function addWaypointEnd(lat, lng, label, isCurrentLocation = false) {
    navState.waypoints.push({ lat, lng, label, isCurrentLocation, marker: null });
    updateWaypointMarkers();
    renderWaypointList();
  }

  function updateWaypointMarkers() {
    // Rimuovi tutti i marker precedenti
    navState.waypoints.forEach((wp) => {
      if (wp.marker) { map.removeLayer(wp.marker); wp.marker = null; }
    });

    navState.waypoints.forEach((wp, i) => {
      const n = navState.waypoints.length;
      let color, iconLabel;
      if (i === 0) { color = wpColors.start; iconLabel = "A"; }
      else if (i === n - 1 && n > 1) { color = wpColors.end; iconLabel = "B"; }
      else { color = wpColors.mid; iconLabel = String(i); }

      const marker = L.marker([wp.lat, wp.lng], {
        icon: makeWaypointIcon(iconLabel, color),
        draggable: true,
        zIndexOffset: 2000,
      }).addTo(map);

      marker.on("dragend", (e) => {
        const ll = e.target.getLatLng();
        wp.lat = ll.lat;
        wp.lng = ll.lng;
        if (!wp.isCurrentLocation) wp.label = formatLatLng(ll.lat, ll.lng);
        renderWaypointList();
        if (navState.routeLayer) calcRoute(); // recalculate if a route was already present
      });

      marker.bindPopup(`<strong>${wp.label}</strong>`);
      wp.marker = marker;
    });
  }

  function removeWaypoint(idx) {
    if (navState.waypoints[idx]?.marker) map.removeLayer(navState.waypoints[idx].marker);
    navState.waypoints.splice(idx, 1);
    updateWaypointMarkers();
    renderWaypointList();
    if (navState.routeLayer) calcRoute();
  }

  function renderWaypointList() {
    const list = document.getElementById("wp-list");
    list.innerHTML = "";

    navState.waypoints.forEach((wp, i) => {
      const n = navState.waypoints.length;
      let color;
      if (i === 0) color = wpColors.start;
      else if (i === n - 1 && n > 1) color = wpColors.end;
      else color = wpColors.mid;

      const item = document.createElement("div");
      item.className = "wp-item";
      item.innerHTML = `
        <span class="wp-dot" style="background:${color}"></span>
        <span class="wp-label" title="${wp.label}">${wp.label}</span>
        <button class="wp-remove" title="Rimuovi">✕</button>
      `;
      item.querySelector(".wp-remove").addEventListener("click", () => removeWaypoint(i));
      list.appendChild(item);
    });

    // Messaggio se vuoto
    if (navState.waypoints.length === 0) {
      list.innerHTML = '<p class="wp-empty">No waypoints added</p>';
    }

    // Show action buttons only if enough points
    const hasEnough = navState.waypoints.length >= 2;
    document.getElementById("calc-route-btn").disabled = !hasEnough;
    document.getElementById("add-nearest-fountain-btn").disabled = !hasEnough;
    document.getElementById("add-nearest-parking-btn").disabled = !hasEnough;
  }

  function refreshCurrentLocationFields() {
    navState.waypoints.forEach((wp, i) => {
      if (wp.isCurrentLocation && userLatLng) {
        wp.lat = userLatLng.lat;
        wp.lng = userLatLng.lng;
        if (wp.marker) wp.marker.setLatLng(userLatLng);
      }
    });
  }

  // ── Geocoding (Nominatim) ───────────────────────────────────────────────────
  async function geocodeAndAdd() {
    const input = document.getElementById("wp-search-input");
    const q = input.value.trim();
    if (!q) return;

    showNavMsg("🔍 Searching...");
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1&accept-language=en`,
        { headers: { "Accept-Language": "en" } }
      );
      const data = await res.json();
      if (!data.length) { showNavMsg("No results found.", true); return; }
      const place = data[0];
      addWaypointEnd(parseFloat(place.lat), parseFloat(place.lon), place.display_name.split(",")[0]);
      map.setView([place.lat, place.lon], 15);
      input.value = "";
      showNavMsg("");
    } catch {
      showNavMsg("Search error.", true);
    }
  }

  // ── Routing (OSRM cycling) ──────────────────────────────────────────────────
  async function calcRoute() {
    if (navState.waypoints.length < 2) return;
    showNavMsg("⏳ Calculating route...");

    const coords = navState.waypoints.map((wp) => `${wp.lng},${wp.lat}`).join(";");
    const url = `https://router.project-osrm.org/route/v1/cycling/${coords}?overview=full&geometries=geojson&steps=false`;

    try {
      const res = await fetch(url);
      const data = await res.json();
      if (data.code !== "Ok") { showNavMsg("Route not found.", true); return; }

      const route = data.routes[0];
      if (navState.routeLayer) map.removeLayer(navState.routeLayer);

      navState.routeLayer = L.geoJSON(route.geometry, {
        style: { color: "#2563eb", weight: 5, opacity: 0.8 },
      }).addTo(map);

      // Zoom to route
      map.fitBounds(navState.routeLayer.getBounds(), { padding: [40, 40] });

      // Route info
      const km = (route.distance / 1000).toFixed(1);
      const min = Math.round(route.duration / 60);
      navState.routeInfo = { distance: km, duration: min };
      showNavMsg(`🚴 ${km} km · ~${min} min`);
    } catch {
      showNavMsg("Route calculation error.", true);
    }
  }

  function clearRoute() {
    if (navState.routeLayer) { map.removeLayer(navState.routeLayer); navState.routeLayer = null; }
    navState.waypoints.forEach((wp) => { if (wp.marker) map.removeLayer(wp.marker); });
    navState.waypoints = [];
    renderWaypointList();
    showNavMsg("");
  }

  // ── Punto più vicino sul/nel percorso ────────────────────────────────────────
  async function addNearestOnRoute(type) {
    if (navState.waypoints.length < 2) return;
    showNavMsg("🔍 Looking for the nearest...");

    // Bounding box of the route (from waypoints)
    const lats = navState.waypoints.map((w) => w.lat);
    const lngs = navState.waypoints.map((w) => w.lng);
    const bbox = {
      s: Math.min(...lats) - 0.01,
      n: Math.max(...lats) + 0.01,
      w: Math.min(...lngs) - 0.01,
      e: Math.max(...lngs) + 0.01,
    };

    // Retrieve entities from bbox via geohash
    const geohashes = window.geohashLib.bboxes(bbox.s, bbox.w, bbox.n, bbox.e, GEOHASH_PRECISION);
    const config = ENTITY_CONFIG[type];

    try {
      const res = await fetch(`${config.url}?gh5=${geohashes.join(",")}`);
      const items = await res.json();
      if (!items.length) { showNavMsg(`No ${config.label.toLowerCase()} found nearby.`, true); return; }

      // Center of the route
      const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;
      const midLng = (Math.min(...lngs) + Math.max(...lngs)) / 2;

      // Nearest point to the center of the route
      let best = items[0], bestDist = Infinity;
      items.forEach((item) => {
        const d = Math.hypot(item.lat - midLat, item.lng - midLng);
        if (d < bestDist) { bestDist = d; best = item; }
      });

      const label = `${config.label}${best.name ? ": " + best.name : ""}`;
      // Insert as second-to-last waypoint
      const insertAt = navState.waypoints.length - 1;
      navState.waypoints.splice(insertAt, 0, { lat: best.lat, lng: best.lng, label, isCurrentLocation: false, marker: null });
      updateWaypointMarkers();
      renderWaypointList();
      await calcRoute();
    } catch {
      showNavMsg("Error fetching data.", true);
    }
  }

  function showNavMsg(msg, isError = false) {
    const el = document.getElementById("nav-msg");
    el.textContent = msg;
    el.style.color = isError ? "#dc2626" : "#374151";
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  buildNavPanel();
  renderWaypointList();
})();
