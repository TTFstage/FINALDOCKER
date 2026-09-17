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
        statusEl.innerHTML = `Connected as <strong>${user.displayName}</strong> · <a href="#" id="osm-logout">Logout</a>`;
        document.getElementById("osm-logout").addEventListener("click", async (e) => {
          e.preventDefault();
          await fetch("/api/v1/osm/logout", { method: "POST" });
          window.location.reload();
        });
      } else {
        window.osmAuthenticated = false;
        const returnTo = encodeURIComponent(window.location.pathname);
        statusEl.innerHTML = `<a href="/api/v1/osm/auth/start?returnTo=${returnTo}">Sign in with OpenStreetMap</a> to contribute.`;
      }
    } catch {
      statusEl.textContent = "Unable to verify OSM login status.";
    }
    updateSubmitState();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedLatLng) return;
    submitBtn.disabled = true;
    resultEl.textContent = "Sending…";

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
        resultEl.textContent = `Error: ${data.error || response.status}`;
      } else {
        resultEl.innerHTML = `Created successfully! <a href="${data.osmUrl}" target="_blank" rel="noopener">View on OSM</a>`;
      }
    } catch {
      resultEl.textContent = "Network error during submission.";
    } finally {
      updateSubmitState();
    }
  });

  checkAuth();
})();
