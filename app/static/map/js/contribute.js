(function () {
  const statusEl = document.getElementById("osm-auth-status");
  const submitBtn = document.getElementById("poi-submit");
  const resultEl = document.getElementById("poi-result");
  const form = document.getElementById("poi-form");

  let selectedLatLng = null;

  const map = L.map("mini-map").setView([45.4642, 9.19], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  let marker = null;
  map.on("click", (e) => {
    selectedLatLng = e.latlng;
    if (marker) marker.setLatLng(e.latlng);
    else marker = L.marker(e.latlng).addTo(map);
    updateSubmitState();
  });

  function updateSubmitState() {
    submitBtn.disabled = !(selectedLatLng && window.osmAuthenticated);
  }

  async function checkAuth() {
    try {
      const response = await fetch("/api/v1/osm/me");
      if (response.ok) {
        const user = await response.json();
        window.osmAuthenticated = true;
        statusEl.innerHTML = `Connesso come <strong>${user.displayName}</strong> · <a href="#" id="osm-logout">Esci</a>`;
        document.getElementById("osm-logout").addEventListener("click", async (e) => {
          e.preventDefault();
          await fetch("/api/v1/osm/logout", { method: "POST" });
          window.location.reload();
        });
      } else {
        window.osmAuthenticated = false;
        const returnTo = encodeURIComponent(window.location.pathname);
        statusEl.innerHTML = `<a href="/api/v1/osm/auth/start?returnTo=${returnTo}">Accedi con OpenStreetMap</a> per contribuire.`;
      }
    } catch {
      statusEl.textContent = "Impossibile verificare lo stato del login OSM.";
    }
    updateSubmitState();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedLatLng) return;
    submitBtn.disabled = true;
    resultEl.textContent = "Invio in corso…";

    try {
      const response = await fetch("/api/v1/osm/poi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: selectedLatLng.lat,
          lng: selectedLatLng.lng,
          type: document.getElementById("poi-type").value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        resultEl.textContent = `Errore: ${data.error || response.status}`;
      } else {
        resultEl.innerHTML = `Creato con successo! <a href="${data.osmUrl}" target="_blank" rel="noopener">Vedi su OSM</a>`;
      }
    } catch {
      resultEl.textContent = "Errore di rete durante l'invio.";
    } finally {
      updateSubmitState();
    }
  });

  checkAuth();
})();
