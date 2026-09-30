/**
 * O'zbekiston Tuproq Qatlamlari Tahlili - Client Application
 * SoilGrids GIS Portal JavaScript
 */

let map = null;
let currentMarker = null;
let uzbekistanGeojsonLayer = null;
let currentSoilData = null;
let currentSelectedDepth = "0-5cm";
let depthProfileChart = null;
let textureChart = null;

// Boshlang'ich koordinatalar (Toshkent / O'zbekiston markazi)
let activeLat = 41.2995;
let activeLon = 69.2401;

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  loadUzbekistanBoundary();
  loadRegionsList();
  setupEventListeners();
  // Ilk tahlilni boshlash
  fetchSoilData(activeLat, activeLon);
});

/* ==========================================================================
   Xarita (Leaflet.js) Sozlamalari
   ========================================================================== */
function initMap() {
  // Basemap qatlamlari
  const satelliteLayer = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      attribution: "Tiles &copy; Esri &mdash; World Imagery",
      maxZoom: 18,
    }
  );

  const darkMatterLayer = L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    {
      attribution: "&copy; OpenStreetMap &copy; CARTO",
      subdomains: "abcd",
      maxZoom: 19,
    }
  );

  const osmLayer = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }
  );

  const topoLayer = L.tileLayer(
    "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    {
      attribution: "&copy; OpenTopoMap contributors",
      maxZoom: 17,
    }
  );

  // Xaritani O'zbekiston markaziga yo'naltirish
  map = L.map("map", {
    center: [41.3775, 64.5883],
    zoom: 6.2,
    minZoom: 5.5,
    maxBounds: [
      [36.0, 54.0],
      [46.5, 74.5],
    ],
    layers: [satelliteLayer], // Default: Sun'iy yo'ldosh
    zoomControl: false,
  });

  // Zoom boshqaruvini pastki o'ng burchakka joylash
  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Qatlamlar almashtirgichi (Layer Control)
  const baseMaps = {
    "🛰️ Sun'iy yo'ldosh (Esri)": satelliteLayer,
    "🗺️ Qorong'u rejim (Dark Matter)": darkMatterLayer,
    "🏔️ Relyef / Topografik": topoLayer,
    "🚗 Standart ko'cha (OSM)": osmLayer,
  };

  L.control.layers(baseMaps, null, { position: "topright" }).addTo(map);

  // Boshlang'ich marker
  createOrMoveMarker(activeLat, activeLon);

  // Xaritada sichqoncha bosilganda
  map.on("click", (e) => {
    const lat = parseFloat(e.latlng.lat.toFixed(5));
    const lon = parseFloat(e.latlng.lng.toFixed(5));
    updateSelectedPoint(lat, lon);
  });

  // Sichqoncha harakatlanganda HUD koordinatalarini ko'rsatish
  map.on("mousemove", (e) => {
    const hudLat = document.getElementById("hudLat");
    const hudLon = document.getElementById("hudLon");
    if (hudLat && hudLon) {
      hudLat.textContent = e.latlng.lat.toFixed(4);
      hudLon.textContent = e.latlng.lng.toFixed(4);
    }
  });
}

/* ==========================================================================
   O'zbekiston Chegarasi (GeoJSON)
   ========================================================================== */
async function loadUzbekistanBoundary() {
  try {
    const res = await fetch("/api/geojson/uzbekistan");
    if (!res.ok) return;
    const geojsonData = await res.json();

    uzbekistanGeojsonLayer = L.geoJSON(geojsonData, {
      style: {
        color: "#06b6d4",
        weight: 2.5,
        opacity: 0.9,
        fillColor: "#10b981",
        fillOpacity: 0.06,
        dashArray: "4, 6",
      },
    }).addTo(map);

    // O'zbekiston hududiga moslab xaritani sig'dirish
    map.fitBounds(uzbekistanGeojsonLayer.getBounds(), {
      padding: [30, 30],
    });
  } catch (err) {
    console.warn("Uzbekistan GeoJSON yuklanmadi:", err);
  }
}

/* ==========================================================================
   Marker Boshqaruvi
   ========================================================================== */
function createOrMoveMarker(lat, lon) {
  const customIcon = L.divIcon({
    className: "custom-marker-wrapper",
    html: `
      <div class="custom-pin-pulse"></div>
      <div class="custom-pin"></div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
  });

  if (currentMarker) {
    currentMarker.setLatLng([lat, lon]);
  } else {
    currentMarker = L.marker([lat, lon], {
      icon: customIcon,
      draggable: true,
      title: "Tanlangan tuproq nuqtasi (Suring yoki bosing)",
    }).addTo(map);

    currentMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      updateSelectedPoint(
        parseFloat(pos.lat.toFixed(5)),
        parseFloat(pos.lng.toFixed(5))
      );
    });
  }
}

function updateSelectedPoint(lat, lon) {
  activeLat = lat;
  activeLon = lon;

  createOrMoveMarker(lat, lon);

  // Input qiymatlarini yangilash
  const inputLat = document.getElementById("inputLat");
  const inputLon = document.getElementById("inputLon");
  if (inputLat) inputLat.value = lat;
  if (inputLon) inputLon.value = lon;

  fetchSoilData(lat, lon);
}

/* ==========================================================================
   Tezkor Hududlar (Presets)
   ========================================================================== */
async function loadRegionsList() {
  const select = document.getElementById("regionSelect");
  if (!select) return;

  try {
    const res = await fetch("/api/regions");
    const json = await res.json();
    if (json.status === "success") {
      select.innerHTML = '<option value="">-- Viloyatni tanlang --</option>';
      json.regions.forEach((r, idx) => {
        const opt = document.createElement("option");
        opt.value = `${r.lat},${r.lon}`;
        opt.textContent = `${r.name}`;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Hududlar ro'yxatini yuklashda xatolik:", err);
  }
}

/* ==========================================================================
   Tahlil Ma'lumotlarini Olish (API)
   ========================================================================== */
async function fetchSoilData(lat, lon) {
  showLoading(true);

  try {
    const response = await fetch(`/api/soil?lat=${lat}&lon=${lon}`);
    const json = await response.json();

    if (json.status === "success" && json.data) {
      currentSoilData = json.data;
      renderSoilData(currentSoilData);
    } else {
      alert("Tuproq ma'lumotlarini olishda xatolik yuz berdi.");
    }
  } catch (error) {
    console.error("Server bilan aloqa xatoligi:", error);
    alert("Serverga ulanib bo'lmadi. Iltimos qayta urining.");
  } finally {
    showLoading(false);
  }
}

/* ==========================================================================
   Natijalarni UI da Ko'rsatish
   ========================================================================== */
function renderSoilData(data) {
  const coords = data.coordinates;
  const assessment = data.assessment;
  const layers = data.layers;

  // 1. Manzil va Ma'lumot Manbasi
  document.getElementById("dispLat").textContent = coords.lat.toFixed(4);
  document.getElementById("dispLon").textContent = coords.lon.toFixed(4);
  document.getElementById("zoneName").textContent = data.zone_name;

  const badge = document.getElementById("sourceBadge");
  if (data.source === "isric_live") {
    badge.className = "source-badge live";
    badge.innerHTML = "● Jonli ISRIC SoilGrids";
  } else {
    badge.className = "source-badge calibrated";
    badge.innerHTML = "● O'zb. Kalibrlangan Model";
  }
  document.getElementById("sourceNote").textContent = data.source_note;

  // 2. Tanlangan qatlam bo'yicha kartochkalarni yangilash
  updateDepthMetrics(currentSelectedDepth);

  // 3. Grafiklarni yangilash
  renderDepthProfileChart(layers);
  renderTextureChart(layers[currentSelectedDepth]);

  // 4. Agronomik Tavsiyalar
  renderAgronomicAdvice(assessment);

  // 5. Barcha qatlamlar jadvali
  renderLayersTable(layers);
}

function updateDepthMetrics(depthKey) {
  if (!currentSoilData || !currentSoilData.layers[depthKey]) return;

  const layer = currentSoilData.layers[depthKey];

  // pH
  const phVal = layer.phh2o ? layer.phh2o.value : "-";
  document.getElementById("valPh").textContent = phVal;
  let phBadgeText = "Neytral";
  let phBadgeClass = "badge-success";
  if (phVal < 6.5) {
    phBadgeText = "Kislotali";
    phBadgeClass = "badge-danger";
  } else if (phVal > 7.5 && phVal <= 8.2) {
    phBadgeText = "Kuchsiz ishqoriy";
    phBadgeClass = "badge-success";
  } else if (phVal > 8.2) {
    phBadgeText = "O'rtacha/Kuchli ishqoriy";
    phBadgeClass = "badge-warning";
  }
  const phBadge = document.getElementById("badgePh");
  phBadge.textContent = phBadgeText;
  phBadge.className = `metric-badge ${phBadgeClass}`;

  // SOC (Uglerod)
  const socVal = layer.soc ? layer.soc.value : "-";
  document.getElementById("valSoc").textContent = socVal;

  // Gumus (SOM %)
  const somVal = layer.gumus ? layer.gumus.value : "-";
  document.getElementById("valGumus").textContent = somVal;
  let somBadgeText = "O'rtacha chirindi";
  let somBadgeClass = "badge-success";
  if (somVal < 0.8) {
    somBadgeText = "Juda kam gumus";
    somBadgeClass = "badge-danger";
  } else if (somVal < 1.2) {
    somBadgeText = "Kam gumus";
    somBadgeClass = "badge-warning";
  } else if (somVal >= 1.8) {
    somBadgeText = "Yuqori gumus";
    somBadgeClass = "badge-success";
  }
  const somBadge = document.getElementById("badgeGumus");
  somBadge.textContent = somBadgeText;
  somBadge.className = `metric-badge ${somBadgeClass}`;

  // Azot
  const nVal = layer.nitrogen ? layer.nitrogen.value : "-";
  document.getElementById("valNitrogen").textContent = nVal;

  // CEC (Kation almashinuvi)
  const cecVal = layer.cec ? layer.cec.value : "-";
  document.getElementById("valCec").textContent = cecVal;

  // Zichlik (Bulk Density)
  const bdVal = layer.bdod ? layer.bdod.value : "-";
  document.getElementById("valBdod").textContent = bdVal;

  // Tekstura foizlari va multi-bar
  const clayVal = layer.clay ? layer.clay.value : 0;
  const sandVal = layer.sand ? layer.sand.value : 0;
  const siltVal = layer.silt ? layer.silt.value : 0;

  document.getElementById("clayVal").textContent = `${clayVal}%`;
  document.getElementById("sandVal").textContent = `${sandVal}%`;
  document.getElementById("siltVal").textContent = `${siltVal}%`;

  document.getElementById("barClay").style.width = `${clayVal}%`;
  document.getElementById("barSand").style.width = `${sandVal}%`;
  document.getElementById("barSilt").style.width = `${siltVal}%`;

  // USDA & Milliy nomi
  const textureInfo = currentSoilData.assessment.texture;
  document.getElementById("textureName").textContent = `${textureInfo.uz} (${textureInfo.usda})`;
  document.getElementById("textureCategory").textContent = textureInfo.category;

  // Gumus zaxirasi hisobi (t/ga)
  // Zaxira = Gumus% * Zichlik * Qatlam qalinligi (sm)
  const depthThickness = getDepthThickness(depthKey);
  if (somVal !== "-" && bdVal !== "-") {
    const stock = (parseFloat(somVal) * parseFloat(bdVal) * depthThickness).toFixed(1);
    document.getElementById("humusStock").textContent = `~${stock} t/ga qatlam zaxirasi`;
  }
}

function getDepthThickness(depthKey) {
  if (depthKey === "0-5cm") return 5;
  if (depthKey === "5-15cm") return 10;
  if (depthKey === "15-30cm") return 15;
  if (depthKey === "30-60cm") return 30;
  if (depthKey === "60-100cm") return 40;
  return 20;
}

/* ==========================================================================
   Grafiklar (Chart.js)
   ========================================================================== */
function renderDepthProfileChart(layers) {
  const ctx = document.getElementById("depthProfileChart");
  if (!ctx) return;

  const depths = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm"];
  const phData = [];
  const somData = [];
  const nData = [];

  depths.forEach((d) => {
    if (layers[d]) {
      phData.push(layers[d].phh2o ? layers[d].phh2o.value : null);
      somData.push(layers[d].gumus ? layers[d].gumus.value : null);
      nData.push(layers[d].nitrogen ? layers[d].nitrogen.value : null);
    }
  });

  if (depthProfileChart) {
    depthProfileChart.destroy();
  }

  depthProfileChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: depths,
      datasets: [
        {
          label: "pH darajasi",
          data: phData,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.15)",
          borderWidth: 2.5,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: "#f59e0b",
          yAxisID: "yPh",
        },
        {
          label: "Gumus miqdori (%)",
          data: somData,
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          borderWidth: 2.5,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: "#10b981",
          yAxisID: "ySom",
        },
        {
          label: "Umumiy Azot (g/kg)",
          data: nData,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.15)",
          borderWidth: 2,
          borderDash: [5, 5],
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: "#06b6d4",
          yAxisID: "ySom",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          labels: {
            color: "#9ca3af",
            font: { family: "Plus Jakarta Sans", size: 11 },
          },
        },
        tooltip: {
          backgroundColor: "rgba(17, 24, 39, 0.95)",
          titleColor: "#f9fafb",
          bodyColor: "#d1d5db",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#9ca3af", font: { family: "JetBrains Mono", size: 11 } },
        },
        yPh: {
          type: "linear",
          position: "left",
          min: 6,
          max: 9.5,
          title: { display: true, text: "pH birligi", color: "#f59e0b" },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#f59e0b" },
        },
        ySom: {
          type: "linear",
          position: "right",
          min: 0,
          title: { display: true, text: "Gumus (%) / Azot (g/kg)", color: "#10b981" },
          grid: { drawOnChartArea: false },
          ticks: { color: "#10b981" },
        },
      },
    },
  });
}

function renderTextureChart(layer) {
  const ctx = document.getElementById("textureChart");
  if (!ctx) return;

  const clay = layer.clay ? layer.clay.value : 20;
  const sand = layer.sand ? layer.sand.value : 40;
  const silt = layer.silt ? layer.silt.value : 40;

  if (textureChart) {
    textureChart.destroy();
  }

  textureChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Loy / Gil", "Qum", "Chang / Soz"],
      datasets: [
        {
          data: [clay, sand, silt],
          backgroundColor: ["#f43f5e", "#f59e0b", "#06b6d4"],
          borderColor: "rgba(17, 24, 39, 0.8)",
          borderWidth: 2,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#9ca3af",
            font: { family: "Plus Jakarta Sans", size: 11 },
          },
        },
      },
      cutout: "68%",
    },
  });
}

/* ==========================================================================
   Agronomik Baholash va Tavsiyalar
   ========================================================================== */
function renderAgronomicAdvice(assessment) {
  document.getElementById("phAdvice").innerHTML = `<strong>pH Holati:</strong> ${assessment.ph.grade}. ${assessment.ph.advice}`;
  document.getElementById("humusAdvice").innerHTML = `<strong>Gumus Holati:</strong> ${assessment.humus.grade}. ${assessment.humus.advice}`;
  document.getElementById("cropsAdvice").innerHTML = `<strong>Tavsiya etiladigan ekinlar:</strong> ${assessment.recommended_crops}`;
}

/* ==========================================================================
   Qatlamlar Jadvali (Barcha Qatlamlar)
   ========================================================================== */
function renderLayersTable(layers) {
  const tbody = document.getElementById("layersTableBody");
  if (!tbody) return;

  tbody.innerHTML = "";
  const depths = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm"];

  depths.forEach((d) => {
    const l = layers[d] || {};
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${d}</strong></td>
      <td>${l.phh2o ? l.phh2o.value : "-"}</td>
      <td>${l.soc ? l.soc.value : "-"}</td>
      <td><span style="color:var(--accent-emerald); font-weight:600;">${l.gumus ? l.gumus.value : "-"} %</span></td>
      <td>${l.nitrogen ? l.nitrogen.value : "-"}</td>
      <td>${l.clay ? l.clay.value : "-"}%</td>
      <td>${l.sand ? l.sand.value : "-"}%</td>
      <td>${l.silt ? l.silt.value : "-"}%</td>
      <td>${l.cec ? l.cec.value : "-"}</td>
      <td>${l.bdod ? l.bdod.value : "-"}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* ==========================================================================
   Hodisalar (Events)
   ========================================================================== */
function setupEventListeners() {
  // Qatlam tablari
  const tabs = document.querySelectorAll(".depth-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      const depth = tab.getAttribute("data-depth");
      currentSelectedDepth = depth;

      const singleView = document.getElementById("singleDepthMetrics");
      const tableView = document.getElementById("tableViewContainer");

      if (depth === "all") {
        singleView.style.display = "none";
        tableView.style.display = "block";
      } else {
        singleView.style.display = "grid";
        tableView.style.display = "none";
        updateDepthMetrics(depth);
        if (currentSoilData && currentSoilData.layers[depth]) {
          renderTextureChart(currentSoilData.layers[depth]);
        }
      }
    });
  });

  // Hudud tanlash select
  const regSelect = document.getElementById("regionSelect");
  if (regSelect) {
    regSelect.addEventListener("change", (e) => {
      if (!e.target.value) return;
      const [lat, lon] = e.target.value.split(",").map(Number);
      map.flyTo([lat, lon], 10, { duration: 1.5 });
      updateSelectedPoint(lat, lon);
    });
  }

  // Koordinatalarni qidirish tugmasi
  const btnSearch = document.getElementById("btnSearchCoord");
  if (btnSearch) {
    btnSearch.addEventListener("click", () => {
      const latVal = parseFloat(document.getElementById("inputLat").value);
      const lonVal = parseFloat(document.getElementById("inputLon").value);

      if (isNaN(latVal) || isNaN(lonVal)) {
        alert("Iltimos, to'g'ri raqamli koordinatalarni kiriting!");
        return;
      }
      map.flyTo([latVal, lonVal], 9, { duration: 1.2 });
      updateSelectedPoint(latVal, lonVal);
    });
  }

  // CSV yuklab olish
  const btnCsv = document.getElementById("btnExportCsv");
  if (btnCsv) {
    btnCsv.addEventListener("click", () => {
      window.location.href = `/api/export/csv?lat=${activeLat}&lon=${activeLon}`;
    });
  }

  // JSON nusxalash
  const btnJson = document.getElementById("btnCopyJson");
  if (btnJson) {
    btnJson.addEventListener("click", () => {
      if (!currentSoilData) return;
      navigator.clipboard.writeText(JSON.stringify(currentSoilData, null, 2));
      alert("Tuproq tahlili JSON formatida buferga (clipboard) nusxalandi!");
    });
  }

  // Chop etish / PDF
  const btnPrint = document.getElementById("btnPrint");
  if (btnPrint) {
    btnPrint.addEventListener("click", () => {
      window.print();
    });
  }
}

function showLoading(show) {
  const overlay = document.getElementById("loadingOverlay");
  if (overlay) {
    if (show) {
      overlay.classList.add("active");
    } else {
      overlay.classList.remove("active");
    }
  }
}
