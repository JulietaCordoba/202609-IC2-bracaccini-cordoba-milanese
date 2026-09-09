// === Config ===
const API_BASE = '/api';
const REFRESH_INTERVAL = 4000; // 4s
const WARNING_THRESHOLD = 700;    // ajustá si querés
const DANGER_THRESHOLD  = 1500;   // ajustá si querés
const DISPLAY_TZ = 'America/Argentina/Buenos_Aires';

let refreshTimer = null;
let mainChart = null;
let lastKnownStatus = null;
let lastKnownFan = { fan_on: null, manual_mode: null };

const chartColors = { text:'#e0e0e0', grid:'#404040', primary:'#4CAF50' };

// === Charts ===
function initCharts() {
  Chart.defaults.color = chartColors.text;
  Chart.defaults.borderColor = chartColors.grid;

  const ctx1 = document.getElementById('mainChart').getContext('2d');
  mainChart = new Chart(ctx1, {
    type:'line',
    data:{ labels:[], datasets:[{ label:'Calidad del Aire (ADC)', data:[], borderColor:chartColors.primary, backgroundColor:'rgba(76,175,80,.1)', borderWidth:2, tension:.3, fill:true, pointRadius:0 }] },
    options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ y:{beginAtZero:true}, x:{grid:{display:false}} } }
  });
}

// === Helpers para el panel ESP32 ===
function updateDevicePanelFromTs(tsNs) {
  if (!tsNs) {
    document.getElementById('deviceStatus').textContent = '--';
    document.getElementById('lastSignal').textContent = '--';
    return;
  }
  const now = Date.now();
  const ageSec = Math.max(0, Math.round(now - tsNs/1e6) / 1000);

  let status;
  if (ageSec < 10)      status = 'ACTIVO';
  else if (ageSec < 60) status = 'INACTIVO';
  else                  status = 'OFFLINE';

  document.getElementById('deviceStatus').textContent = status;
  document.getElementById('lastSignal').textContent   = ageSec < 60 ? `${Math.round(ageSec)}s` : '>1min';
}

// === API calls ===
async function fetchLatest() {
  try {
    const r = await fetch(`${API_BASE}/latest`);
    const d = await r.json();

    if (d.gas != null) updateCurrentValue(d.gas);
    if (d.status) {
      const pretty = d.status.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
      document.getElementById('currentStatus').textContent = `Estado: ${pretty}`;
      lastKnownStatus = d.status;
      updateSafetyAlert();
    }
    if (d.ts) {
      const t = new Date(d.ts/1e6);
      document.getElementById('currentTimestamp').textContent = t.toLocaleString('es-AR', {timeZone: DISPLAY_TZ});
      document.getElementById('lastUpdate').textContent     = t.toLocaleTimeString('es-AR', {timeZone: DISPLAY_TZ});
      // Actualizamos el panel del ESP32 usando el timestamp del último dato
      updateDevicePanelFromTs(d.ts);
    }
  } catch(e) {
    console.warn('[latest] error', e);
  }
}

async function fetchHistory() {
  try {
    const r = await fetch(`${API_BASE}/query?limit=50`);
    const arr = await r.json(); // /api/query devuelve una LISTA
    updateMainChart(arr);
  } catch(e) {
    console.warn('[query] error', e);
  }
}

async function fetchStatistics() {
  try {
    const r = await fetch(`${API_BASE}/statistics`);
    const j = await r.json();
    if (j.statistics) updateStatistics(j.statistics);
  } catch(e) {
    console.warn('[stats] error', e);
  }
}

// === Control de ventilación (modo manual) ===
async function fetchFanStatus() {
  try {
    const r = await fetch(`${API_BASE}/fan`);
    const d = await r.json();
    updateFanPanel(d);
  } catch(e) {
    console.warn('[fan] error', e);
  }
}

async function toggleFan() {
  const btn = document.getElementById('fanToggleBtn');
  btn.disabled = true;
  try {
    const r = await fetch(`${API_BASE}/fan/toggle`, { method: 'POST' });
    const d = await r.json();
    updateFanPanel(d);
  } catch(e) {
    console.warn('[fan/toggle] error', e);
  } finally {
    btn.disabled = false;
  }
}

async function toggleFanMode() {
  const btn = document.getElementById('fanModeBtn');
  btn.disabled = true;
  try {
    // Si está en automático (o todavía no sabemos), pasamos a manual;
    // si ya está en manual, volvemos a automático.
    const goingManual = lastKnownFan.manual_mode !== true;
    const endpoint = goingManual ? '/fan/manual' : '/fan/auto';
    const r = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
    const d = await r.json();
    updateFanPanel(d);
  } catch(e) {
    console.warn('[fan/mode] error', e);
  } finally {
    btn.disabled = false;
  }
}

function updateFanPanel(d) {
  const el = document.getElementById('fanState');
  const manual = d.manual_mode;

  if (d.fan_on === null || d.fan_on === undefined) {
    el.innerHTML = '<span class="unit">AUTOMÁTICO</span>';
    el.className = 'value-display';
  } else {
    const on = !!d.fan_on;
    el.innerHTML = on
      ? '<span class="unit">ENCENDIDO</span>'
      : '<span class="unit">APAGADO</span>';
    el.className = 'value-display ' + (on ? 'normal' : '');
  }

  const note = document.getElementById('fanSimulatedNote');
  const parts = [];
  if (manual === true) parts.push('Modo manual');
  else if (manual === false) parts.push('Modo automático');
  if (d.simulated) parts.push('simulado (sin conexión con el relé físico)');
  note.textContent = parts.length ? parts.join(' — ') : '\u00A0';

  // Botón único de modo: muestra el modo actual y alterna al apretarlo.
  const modeBtn = document.getElementById('fanModeBtn');
  if (manual === true) {
    modeBtn.textContent = 'Modo: Manual';
    modeBtn.className = 'btn';
  } else if (manual === false) {
    modeBtn.textContent = 'Modo: Automático';
    modeBtn.className = 'btn active';
  } else {
    modeBtn.textContent = 'Modo: --';
    modeBtn.className = 'btn';
  }

  // El botón de encender/apagar solo se puede usar en modo manual.
  // En automático queda bloqueado hasta que se cambie a manual explícitamente.
  document.getElementById('fanToggleBtn').disabled = (manual !== true);

  lastKnownFan = { fan_on: d.fan_on, manual_mode: d.manual_mode };
  updateSafetyAlert();
}

function updateSafetyAlert() {
  const alertBox = document.getElementById('fanSafetyAlert');
  const isDanger = lastKnownStatus === 'aire_peligroso';
  const isManualOff = lastKnownFan.manual_mode === true && lastKnownFan.fan_on === false;
  alertBox.style.display = (isDanger && isManualOff) ? 'block' : 'none';
}

// === UI helpers ===
function updateCurrentValue(value) {
  const el = document.getElementById('currentValue');
  el.innerHTML = `${Math.round(value)} <span class="unit">ADC</span>`;
  el.className = 'value-display';
  if (value >= DANGER_THRESHOLD) el.className += ' danger';
  else if (value >= WARNING_THRESHOLD) el.className += ' warning';
  else el.className += ' normal';
}

function updateStatistics(stats) {
  document.getElementById('avgValue').textContent = Math.round(stats.average ?? 0);
  document.getElementById('maxValue').textContent = Math.round(stats.maximum ?? 0);
  document.getElementById('minValue').textContent = Math.round(stats.minimum ?? 0);
}

function updateMainChart(data) {
  const labels = [];
  const values = [];
  data.forEach(it => {
    const d = new Date(it.ts/1e6);
    labels.push(d.toLocaleTimeString('es-AR',{hour:'2-digit',minute:'2-digit', timeZone: DISPLAY_TZ}));
    values.push(it.gas);
  });
  mainChart.data.labels = labels;
  mainChart.data.datasets[0].data = values;
  mainChart.update();
}

// === Refresh ===
async function refreshData() {
  await Promise.all([ fetchLatest(), fetchStatistics(), fetchHistory(), fetchFanStatus() ]);
}

function startAuto() {
  stopAuto();
  refreshTimer = setInterval(() => { refreshData(); }, REFRESH_INTERVAL);
}
function stopAuto() { if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; } }

// === Init ===
document.addEventListener('DOMContentLoaded', async () => {
  initCharts();
  await refreshData();
  startAuto();
});