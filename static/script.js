/**
 * Intelligent Traffic Management System - Client Controller
 * Coordinates dashboard polling, UI updates, user controls, and REST API communication.
 */

const $ = (id) => document.getElementById(id);
let state = null;
let toastTimer = null;
let pollTimer = null;

// Sanitize text inputs for safe HTML insertion
function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]));
}

// Display transient feedback toasts
function showToast(msg, isError = false) {
  const toastEl = $('toast');
  toastEl.textContent = msg;
  toastEl.className = 'toast show' + (isError ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.className = 'toast';
  }, 2800);
}

// Standardized Fetch wrapper for JSON REST APIs
async function apiCall(endpoint, payload = null) {
  const options = payload
    ? {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    : { method: 'GET' };

  const res = await fetch(endpoint, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Server request failed');
  }
  return data;
}

// Main DOM update coordinator
function updateDashboard(newState) {
  state = newState;

  // KPI Metrics
  $('vehicles').textContent = newState.summary.vehicles.toLocaleString();
  $('passed').textContent = newState.summary.passed.toLocaleString();
  $('heavy').textContent = newState.summary.heavy;
  $('tick').textContent = newState.tick.toLocaleString();
  $('updated').textContent = new Date(newState.last_updated).toLocaleTimeString();

  // Engine Status & Speed
  const isRunning = newState.running;
  $('engine').textContent = isRunning ? 'Running normally' : 'Paused by operator';
  
  const livePill = $('live-pill');
  if (isRunning) {
    livePill.classList.remove('paused');
    $('live').textContent = 'LIVE SIMULATION';
    $('pause').textContent = 'Ⅱ Pause';
  } else {
    livePill.classList.add('paused');
    $('live').textContent = 'SIMULATION PAUSED';
    $('pause').textContent = '▶ Resume';
  }

  // Step button is enabled when paused
  const stepBtn = $('step-btn');
  if (stepBtn) {
    stepBtn.disabled = isRunning;
  }

  // Seed status indicator
  const seedBadge = $('seed-badge');
  if (seedBadge) {
    if (newState.seed !== null && newState.seed !== undefined) {
      seedBadge.textContent = `Seed: ${newState.seed} (Deterministic)`;
      seedBadge.style.color = '#72a5ff';
    } else {
      seedBadge.textContent = 'Seed: Dynamic (Stochastic)';
      seedBadge.style.color = '#8494ac';
    }
  }

  // Speed label & buttons
  const speed = newState.speed || 1.0;
  $('speed-label').textContent = `● ${speed}x Speed`;
  document.querySelectorAll('.speed-btn').forEach((btn) => {
    btn.classList.toggle('selected', parseFloat(btn.dataset.speed) === speed);
  });

  // Operating Mode
  $('auto').classList.toggle('selected', newState.auto_mode);
  $('manual').classList.toggle('selected', !newState.auto_mode);
  $('mode-desc').textContent = newState.auto_mode
    ? 'Adaptive control dynamically prioritizes lanes based on real-time queue pressure.'
    : 'Manual mode enabled: operator commands specific approaches to turn green.';

  // Adaptive Timing Rules Inputs
  $('min').value = newState.settings.min_green;
  $('max').min = newState.settings.min_green;
  $('max').value = Math.max(newState.settings.max_green, newState.settings.min_green);
  $('minval').textContent = newState.settings.min_green;
  $('maxval').textContent = $('max').value;

  // Intersections Grid & Event Log
  renderJunctions(newState.intersections, newState.auto_mode);
  renderEvents(newState.events);
}

// Render intersection cards and approaches
function renderJunctions(junctions, isAuto) {
  const directions = ['North', 'East', 'South', 'West'];
  const symbols = ['⌖', '⌘', '⇄', '◈'];

  $('junction-grid').innerHTML = junctions
    .map((j, i) => {
      const symbol = symbols[i % symbols.length];
      return `
      <article class="junction" id="junction-${esc(j.id)}">
        <div class="jhead">
          <div class="jtitle">
            <div class="jsymbol">${symbol}</div>
            <div>
              <h3>${esc(j.name)}</h3>
              <p>${esc(j.location)}</p>
            </div>
          </div>
          <span class="badge ${esc(j.congestion.toLowerCase())}">
            ${esc(j.congestion.toUpperCase())} TRAFFIC
          </span>
        </div>

        <div class="jstats">
          <span><b>${j.total_vehicles}</b>Vehicles queued</span>
          <span><b>${j.total_passed}</b>Throughput</span>
          <span><b>${j.cycle}</b>Signal cycles</span>
        </div>

        <div class="lanetitle">
          <span>LANE APPROACH STATUS</span>
          <span>LIVE ESTIMATE</span>
        </div>

        <div class="lanes">
          ${directions
            .map((dir) => {
              const lane = j.lanes[dir];
              const isActive = dir === j.active_direction;
              const pct = Math.min(100, Math.round((lane.vehicles / 60) * 100));
              return `
              <div class="lane ${isActive ? 'active' : ''}">
                <div class="lanetop">
                  <span>${dir}</span>
                  <i class="light ${lane.signal}"></i>
                </div>
                <div class="count">${lane.vehicles}</div>
                <div class="caption">queued</div>
                <div class="signal ${lane.signal}">● ${lane.signal}</div>
                <div class="time">
                  ${isActive ? lane.green_remaining + 's green' : lane.waiting + ' waiting'}
                </div>
                <div class="bar">
                  <span style="width:${pct}%"></span>
                </div>
                <button class="inject-btn" data-inj-j="${esc(j.id)}" data-inj-d="${dir}" title="Inject +5 simulated vehicles">
                  +5 Cars
                </button>
              </div>`;
            })
            .join('')}
        </div>

        <div class="manual ${isAuto ? '' : 'show'}">
          <small>MANUAL SIGNAL OVERRIDE (CLICK TO FORCE GREEN)</small>
          ${directions
            .map(
              (dir) => `
            <button class="mini" data-j="${esc(j.id)}" data-d="${dir}" ${isAuto ? 'disabled' : ''}>
              ${dir} → Green
            </button>`
            )
            .join('')}
        </div>
      </article>`;
    })
    .join('');

  // Wire manual override buttons
  document.querySelectorAll('[data-j]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const updated = await apiCall('/api/signal', {
          junction: btn.dataset.j,
          direction: btn.dataset.d,
        });
        updateDashboard(updated);
        showToast(`${btn.dataset.d} direction commanded GREEN.`);
      } catch (err) {
        showToast(err.message, true);
      }
    };
  });

  // Wire traffic injection buttons
  document.querySelectorAll('[data-inj-j]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const updated = await apiCall('/api/traffic', {
          junction: btn.dataset.injJ,
          direction: btn.dataset.injD,
          amount: 5,
        });
        updateDashboard(updated);
        showToast(`+5 simulated vehicles added to ${btn.dataset.injD} approach.`);
      } catch (err) {
        showToast(err.message, true);
      }
    };
  });
}

// Render system audit log events
function renderEvents(events) {
  $('event-count').textContent = `${events.length} EVENT${events.length === 1 ? '' : 'S'}`;
  if (!events.length) {
    $('event-list').innerHTML = '<p class="muted">No events recorded yet.</p>';
    return;
  }

  const icons = {
    success: '✓',
    warning: '!',
    signal: '↔',
    info: '•',
    error: '✕',
  };

  $('event-list').innerHTML = events
    .map(
      (e) => `
    <div class="eventrow">
      <div class="eventicon ${esc(e.kind)}">
        ${icons[e.kind] || '•'}
      </div>
      <div>
        <div class="message">${esc(e.message)}</div>
        <div class="timeevent">${esc(e.time)}${e.junction ? ' · ' + esc(e.junction) : ''}</div>
      </div>
    </div>`
    )
    .join('');
}

// Fetch state from server
async function fetchState() {
  try {
    const data = await apiCall('/api/state');
    updateDashboard(data);
  } catch (err) {
    showToast('Cannot reach server. Is app.py running?', true);
  }
}

// Dispatch high-level control action
async function sendControl(action, extra = {}) {
  try {
    const data = await apiCall('/api/control', { action, ...extra });
    updateDashboard(data);
    const msgs = {
      pause: 'Simulation paused.',
      resume: 'Simulation resumed.',
      auto: 'Adaptive signal mode enabled.',
      manual: 'Manual signal mode enabled.',
      reset: 'Simulation reset.',
      speed: `Speed set to ${extra.speed}x.`,
    };
    showToast(msgs[action] || 'Command executed.');
  } catch (err) {
    showToast(err.message, true);
  }
}

// Wire Global Control Listeners
$('auto').onclick = () => sendControl('auto');
$('manual').onclick = () => sendControl('manual');
$('pause').onclick = () => sendControl(state && state.running ? 'pause' : 'resume');
$('refresh').onclick = fetchState;

// Single manual step button
$('step-btn').onclick = async () => {
  try {
    const data = await apiCall('/api/tick', {});
    updateDashboard(data);
    showToast('Simulation advanced by 1 step.');
  } catch (err) {
    showToast(err.message, true);
  }
};

// Reset with optional deterministic random seed prompt
$('reset').onclick = () => {
  const seedInput = prompt(
    'Reset simulation to initial state.\n\nOptionally enter an integer seed for repeatable exam demonstration (e.g., 42), or leave blank for dynamic seed:'
  );
  if (seedInput === null) return; // cancelled
  const trimmed = seedInput.trim();
  const seed = trimmed === '' ? null : parseInt(trimmed, 10);
  if (trimmed !== '' && isNaN(seed)) {
    showToast('Seed must be a valid integer.', true);
    return;
  }
  sendControl('reset', { seed });
};

// Simulation Speed selector buttons
document.querySelectorAll('.speed-btn').forEach((btn) => {
  btn.onclick = () => {
    const speed = parseFloat(btn.dataset.speed);
    sendControl('speed', { speed });
  };
});

// Timing sliders live labels
$('min').oninput = () => {
  $('minval').textContent = $('min').value;
  $('max').min = $('min').value;
  if (+$('max').value < +$('min').value) {
    $('max').value = $('min').value;
  }
  $('maxval').textContent = $('max').value;
};

$('max').oninput = () => {
  $('maxval').textContent = $('max').value;
};

// Settings form submission
$('settings').onsubmit = async (e) => {
  e.preventDefault();
  try {
    const minVal = parseInt($('min').value, 10);
    const maxVal = parseInt($('max').value, 10);
    const data = await apiCall('/api/settings', {
      min_green: minVal,
      max_green: maxVal,
    });
    updateDashboard(data);
    showToast('Adaptive timing rules successfully applied.');
  } catch (err) {
    showToast(err.message, true);
  }
};

// Background polling loop (Decoupled: purely reads state without triggering tick)
function startPolling() {
  fetchState();
  clearInterval(pollTimer);
  pollTimer = setInterval(fetchState, 1000);
}

// Start application
startPolling();
