/**
 * Intelligent Traffic Management System - Client Controller
 * Coordinates dashboard polling, UI updates, user controls, 3-phase signal display,
 * scenario switching, persistent SQLite analytics, native canvas charts, and REST API communication.
 */

const $ = (id) => document.getElementById(id);
let state = null;
let toastTimer = null;
let pollTimer = null;
let analyticsTimer = null;
let chartTimer = null;

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
  if (!toastEl) return;
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

  // KPI Overview Cards
  if ($('active-junctions')) {
    $('active-junctions').textContent = newState.summary.junctions || (newState.intersections ? newState.intersections.length : 4);
  }
  if ($('vehicles')) {
    $('vehicles').textContent = newState.summary.vehicles.toLocaleString();
  }
  if ($('passed')) {
    $('passed').textContent = newState.summary.passed.toLocaleString();
  }
  if ($('heavy')) {
    $('heavy').textContent = newState.summary.heavy;
  }
  if ($('tick')) {
    $('tick').textContent = newState.tick.toLocaleString();
  }
  if ($('updated')) {
    $('updated').textContent = new Date(newState.last_updated).toLocaleTimeString();
  }

  // Network Average Delay & Peak Delay
  if (newState.intersections && newState.intersections.length > 0) {
    const totalWait = newState.intersections.reduce((acc, j) => acc + (j.avg_wait_seconds || 0), 0);
    const netAvgWait = (totalWait / newState.intersections.length).toFixed(1);
    if ($('avg-delay')) $('avg-delay').textContent = netAvgWait;

    const peakWait = Math.max(0, ...newState.intersections.map((j) => j.avg_wait_seconds || 0));
    if ($('peak-delay-label')) $('peak-delay-label').textContent = `● Peak delay: ${peakWait.toFixed(1)}s`;
  }

  // Congestion Status Label
  if ($('congestion-status-label')) {
    const heavyCount = newState.summary.heavy || 0;
    $('congestion-status-label').textContent = heavyCount === 0
      ? '● Smooth traffic flow'
      : (heavyCount <= 2 ? '● Moderate traffic' : '● Heavy congestion');
  }

  // Session ID badge
  const sessionBadge = $('session-badge');
  if (sessionBadge && newState.session_id) {
    sessionBadge.textContent = `Session: ${newState.session_id}`;
    sessionBadge.title = `Active SQLite Session: ${newState.session_id}`;
  }

  // Engine Status & Speed
  const isRunning = newState.running;
  if ($('engine')) {
    $('engine').textContent = isRunning ? 'Running normally' : 'Paused by operator';
  }
  
  const livePill = $('live-pill');
  if (livePill) {
    if (isRunning) {
      livePill.classList.remove('paused');
      $('live').textContent = 'LIVE SIMULATION';
      $('pause').textContent = 'Ⅱ Pause';
    } else {
      livePill.classList.add('paused');
      $('live').textContent = 'SIMULATION PAUSED';
      $('pause').textContent = '▶ Resume';
    }
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
  if ($('speed-label')) $('speed-label').textContent = `● ${speed}x Speed`;
  document.querySelectorAll('.speed-btn').forEach((btn) => {
    btn.classList.toggle('selected', parseFloat(btn.dataset.speed) === speed);
  });

  // Scenario updates
  const scenario = newState.scenario || 'medium';
  document.querySelectorAll('.scen-btn:not(.emergency-btn)').forEach((btn) => {
    btn.classList.toggle('selected', btn.dataset.scen === scenario);
  });
  if (newState.scenario_info && newState.scenario_info.description && $('active-scenario-desc')) {
    $('active-scenario-desc').textContent = `${newState.scenario_info.name} — ${newState.scenario_info.description}`;
  }

  // Flow rate slider
  if (newState.arrival_multiplier !== undefined && $('flow')) {
    $('flow').value = newState.arrival_multiplier;
    if ($('flowval')) $('flowval').textContent = newState.arrival_multiplier;
  }

  // Operating Mode
  if ($('auto')) $('auto').classList.toggle('selected', newState.auto_mode);
  if ($('manual')) $('manual').classList.toggle('selected', !newState.auto_mode);
  if ($('mode-desc')) {
    $('mode-desc').textContent = newState.auto_mode
      ? 'Adaptive mode optimizes green phases using normalized queue density, waiting times, and starvation prevention.'
      : 'Manual mode enabled: operator commands specific approaches to turn green.';
  }

  // Adaptive Timing Rules Inputs
  if ($('min') && $('max')) {
    $('min').value = newState.settings.min_green;
    $('max').min = newState.settings.min_green;
    $('max').value = Math.max(newState.settings.max_green, newState.settings.min_green);
    if ($('minval')) $('minval').textContent = newState.settings.min_green;
    if ($('maxval')) $('maxval').textContent = $('max').value;
  }

  // Intersections Grid & Event Log
  renderJunctions(newState.intersections, newState.auto_mode);
  renderEvents(newState.events);
}

// Render intersection cards and approaches with 3-phase lights & priority scores
function renderJunctions(junctions, isAuto) {
  const directions = ['North', 'East', 'South', 'West'];
  const dirMeta = {
    North: { arrow: '↑', label: 'North' },
    East:  { arrow: '→', label: 'East' },
    South: { arrow: '↓', label: 'South' },
    West:  { arrow: '←', label: 'West' },
  };

  $('junction-grid').innerHTML = junctions
    .map((j) => {
      const phase = j.current_phase || 'GREEN';
      const phaseRemaining = j.phase_remaining || 0;
      
      let phaseLabel = `PHASE: GREEN (${phaseRemaining}s)`;
      if (phase === 'YELLOW') {
        phaseLabel = `PHASE: YELLOW (${phaseRemaining}s)`;
      } else if (phase === 'ALL_RED') {
        phaseLabel = `PHASE: ALL-RED CLEARANCE (${phaseRemaining}s)`;
      }

      // Approach signals for crossroad schematic
      const nSig = (j.lanes.North && j.lanes.North.signal ? j.lanes.North.signal.toLowerCase() : 'red');
      const eSig = (j.lanes.East && j.lanes.East.signal ? j.lanes.East.signal.toLowerCase() : 'red');
      const sSig = (j.lanes.South && j.lanes.South.signal ? j.lanes.South.signal.toLowerCase() : 'red');
      const wSig = (j.lanes.West && j.lanes.West.signal ? j.lanes.West.signal.toLowerCase() : 'red');

      return `
      <article class="junction" id="junction-${esc(j.id)}">
        <div class="jhead">
          <div class="jtitle">
            <!-- Visual Crossroads Schematic -->
            <div class="mini-crossroad" title="Intersection Crossroad Layout (${j.name}) - Active Green: ${esc(j.active_direction)}">
              <div class="road-arm north ${nSig}" title="North Approach: ${nSig.toUpperCase()}">↑</div>
              <div class="road-arm west ${wSig}" title="West Approach: ${wSig.toUpperCase()}">←</div>
              <div class="road-center ${phase.toLowerCase()}" title="Center Intersection: ${phase}">${phase === 'ALL_RED' ? '■' : '●'}</div>
              <div class="road-arm east ${eSig}" title="East Approach: ${eSig.toUpperCase()}">→</div>
              <div class="road-arm south ${sSig}" title="South Approach: ${sSig.toUpperCase()}">↓</div>
            </div>
            <div>
              <h3>${esc(j.name)} ${j.emergency_active ? '🚨' : ''}</h3>
              <p>${esc(j.location)}</p>
            </div>
          </div>
          <div class="jbadges">
            <span class="badge ${esc(j.congestion.toLowerCase())}">
              ${esc(j.congestion.toUpperCase())} TRAFFIC
            </span>
            <span class="phase-pill ${phase}">
              ${phaseLabel}
            </span>
          </div>
        </div>

        <div class="jstats">
          <span><b>${j.total_vehicles}</b>Queued</span>
          <span><b>${j.total_passed}</b>Throughput</span>
          <span><b>${j.avg_wait_seconds}s</b>Avg Wait</span>
          <span><b>${j.cycle}</b>Cycles</span>
        </div>

        <div class="lanetitle">
          <span>APPROACH LANES &amp; 3-ASPECT SIGNALS</span>
          <span>PRIORITY SCORE</span>
        </div>

        <div class="lanes">
          ${directions
            .map((dir) => {
              const lane = j.lanes[dir];
              const isGreen = lane.signal === 'GREEN';
              const isYellow = lane.signal === 'YELLOW';
              const isRed = lane.signal === 'RED';
              const pct = Math.min(100, Math.round((lane.vehicles / 60) * 100));
              const arrow = dirMeta[dir].arrow;

              let laneClass = '';
              if (isGreen) laneClass = 'active-green';
              else if (isYellow) laneClass = 'active-yellow';
              if (lane.is_emergency) laneClass += ' emergency-lane';

              return `
              <div class="lane ${laneClass}">
                <div class="lanetop">
                  <div class="dir-label">
                    <span class="dir-arrow">${arrow}</span>
                    <span>${dir} ${lane.is_emergency ? '🚨' : ''}</span>
                  </div>
                  <!-- 3-State Traffic Light Head -->
                  <div class="light-box" title="Signal: ${lane.signal}">
                    <span class="light-dot red ${isRed ? 'on' : ''}"></span>
                    <span class="light-dot yellow ${isYellow ? 'on' : ''}"></span>
                    <span class="light-dot green ${isGreen ? 'on' : ''}"></span>
                  </div>
                </div>

                <div class="count">${lane.vehicles}</div>
                <div class="caption">vehicles queued</div>
                
                <div class="signal ${lane.signal}">
                  ● ${lane.signal}
                </div>

                <div class="time">
                  ${isGreen ? lane.green_remaining + 's green' : (lane.waiting_seconds ? Math.round(lane.waiting_seconds) + 's wait' : lane.waiting + ' waiting')}
                </div>

                <div class="score-badge" title="Normalized Priority Score (Formula: 0.45*Q + 0.35*W + 0.20*Starve)">
                  Score: ${lane.is_emergency ? '999 (EMERG)' : lane.priority_score}
                </div>

                <div class="bar" title="Queue occupancy vs 60 vehicle capacity">
                  <span style="width:${pct}%"></span>
                </div>

                <button class="inject-btn" data-inj-j="${esc(j.id)}" data-inj-d="${dir}" title="Inject +5 simulated vehicles to test adaptive response">
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
        fetchChartData();
      } catch (err) {
        showToast(err.message, true);
      }
    };
  });
}

// Render system audit log events
function renderEvents(events) {
  if (!$('event-count') || !$('event-list')) return;
  $('event-count').textContent = `${events.length} EVENT${events.length === 1 ? '' : 'S'}`;
  if (!events.length) {
    $('event-list').innerHTML = '<p class="muted">No events recorded yet.</p>';
    return;
  }

  const icons = {
    success: '✓',
    warning: '!',
    signal: '↔',
    emergency: '🚨',
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

// Fetch state snapshot from server
async function fetchState() {
  try {
    const data = await apiCall('/api/state');
    updateDashboard(data);
  } catch (err) {
    showToast('Cannot reach server. Is app.py running?', true);
  }
}

// Fetch SQLite timeline series for canvas charts
async function fetchChartData() {
  try {
    const data = await apiCall('/api/analytics/chart-data');
    if (data && data.timeline && window.trafficCharts) {
      window.trafficCharts.renderQueueThroughput('chart-queue-throughput', data.timeline);
      window.trafficCharts.renderWaitDelay('chart-wait-delay', data.timeline);
    }
  } catch (err) {
    // Graceful fallback if chart data fails
  }
}

// Fetch SQLite analytical summary and render Signal Utilization Chart
async function fetchAnalyticsSummary() {
  try {
    const data = await apiCall('/api/analytics/summary');
    if (data && data.has_data) {
      if ($('db-avg-wait')) $('db-avg-wait').textContent = `${data.avg_wait_seconds}s`;
      if ($('db-avg-queue')) $('db-avg-queue').textContent = `${data.avg_queue_length}`;
      if ($('db-samples')) $('db-samples').textContent = `Based on ${data.total_samples} snapshots`;
      if ($('db-peak-queue')) $('db-peak-queue').textContent = `Peak Queue: ${data.peak_queue_length}`;
      if ($('cong-low')) $('cong-low').textContent = `${data.congestion_distribution.Low}%`;
      if ($('cong-mod')) $('cong-mod').textContent = `${data.congestion_distribution.Moderate}%`;
      if ($('cong-heavy')) $('cong-heavy').textContent = `${data.congestion_distribution.Heavy}%`;

      // Render Directional Signal Phase Utilization Chart
      if (window.trafficCharts && data.signal_utilization) {
        window.trafficCharts.renderSignalUtilization('chart-signal-util', data.signal_utilization);
      }
    }
  } catch (err) {
    // Graceful fallback
  }
}

// Run baseline comparison benchmark
async function runBenchmark() {
  const btn = $('run-benchmark-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Executing 60s Comparative Benchmark...';
  showToast('Running side-by-side Fixed-Time vs Adaptive comparison...');

  try {
    const resp = await apiCall('/api/analytics/compare-baseline', {
      duration_ticks: 60,
      seed: 42,
      scenario: 'medium',
    });

    const cmp = resp.comparison;
    $('benchmark-results').style.display = 'block';

    $('bench-f-wait').textContent = `${cmp.fixed_avg_wait}s`;
    $('bench-f-thru').textContent = `${cmp.fixed_throughput} vehicles`;
    $('bench-f-queue').textContent = `${cmp.fixed_avg_queue} avg`;

    $('bench-a-wait').textContent = `${cmp.adaptive_avg_wait}s`;
    $('bench-a-thru').textContent = `${cmp.adaptive_throughput} vehicles`;
    $('bench-a-queue').textContent = `${cmp.adaptive_avg_queue} avg`;

    const waitRed = cmp.wait_reduction_pct;
    $('bench-gain-wait').querySelector('b').textContent = `${waitRed > 0 ? '▼ ' : ''}${waitRed}%`;
    $('bench-gain-wait').className = `gain-badge ${waitRed >= 0 ? 'green' : 'red'}`;

    const thruInc = cmp.throughput_increase_pct;
    $('bench-gain-thru').querySelector('b').textContent = `${thruInc > 0 ? '▲ ' : ''}${thruInc}%`;
    $('bench-gain-thru').className = `gain-badge ${thruInc >= 0 ? 'blue' : 'orange'}`;

    $('bench-seed-note').textContent = `Comparison ${cmp.comparison_id} · Seed ${cmp.seed} · ${cmp.scenario} · ${cmp.duration_ticks} ticks`;
    showToast('Benchmark completed and stored in SQLite database!');
    fetchAnalyticsSummary();
    fetchChartData();
  } catch (err) {
    showToast(`Benchmark failed: ${err.message}`, true);
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Run 60s Benchmark Comparison';
  }
}

// Database reset
async function resetDatabase() {
  if (!confirm('Clear all SQLite database tables and historical snapshots for fresh testing?')) return;
  try {
    await apiCall('/api/database/reset', {});
    showToast('SQLite database re-initialized.');
    fetchAnalyticsSummary();
    fetchChartData();
    fetchState();
  } catch (err) {
    showToast(err.message, true);
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
    fetchAnalyticsSummary();
    fetchChartData();
  } catch (err) {
    showToast(err.message, true);
  }
}

// Scenario buttons listener
document.querySelectorAll('.scen-btn:not(.emergency-btn)').forEach((btn) => {
  btn.onclick = async () => {
    const scen = btn.dataset.scen;
    try {
      const data = await apiCall('/api/scenario', { scenario: scen });
      updateDashboard(data);
      showToast(`Scenario changed to ${btn.textContent}.`);
      fetchChartData();
    } catch (err) {
      showToast(err.message, true);
    }
  };
});

// Emergency Preemption button
const emergBtn = $('dispatch-emerg-btn');
if (emergBtn) {
  emergBtn.onclick = async () => {
    const jid = prompt(
      'Dispatch Simulated Emergency Vehicle (Ambulance / Fire Engine)\n\nEnter target intersection ID (J1, J2, J3, or J4):',
      'J1'
    );
    if (!jid) return;
    const targetJ = jid.trim().toUpperCase();

    const dir = prompt(
      `Select approach direction for ${targetJ} (North, East, South, or West):`,
      'North'
    );
    if (!dir) return;
    const targetDir = dir.trim();

    try {
      const data = await apiCall('/api/emergency', {
        junction: targetJ,
        direction: targetDir,
      });
      updateDashboard(data);
      showToast(`🚨 Emergency vehicle dispatched on ${targetJ} ${targetDir}! Priority corridor initiated.`);
      fetchChartData();
    } catch (err) {
      showToast(err.message, true);
    }
  };
}

// Flow rate slider
if ($('flow')) {
  $('flow').oninput = () => {
    if ($('flowval')) $('flowval').textContent = $('flow').value;
  };
}

// Wire Global Control Listeners
if ($('auto')) $('auto').onclick = () => sendControl('auto');
if ($('manual')) $('manual').onclick = () => sendControl('manual');
if ($('pause')) $('pause').onclick = () => sendControl(state && state.running ? 'pause' : 'resume');
if ($('refresh')) {
  $('refresh').onclick = () => {
    fetchState();
    fetchAnalyticsSummary();
    fetchChartData();
  };
}
if ($('run-benchmark-btn')) $('run-benchmark-btn').onclick = runBenchmark;
if ($('db-reset-btn')) $('db-reset-btn').onclick = resetDatabase;

// Single manual step button
if ($('step-btn')) {
  $('step-btn').onclick = async () => {
    try {
      const data = await apiCall('/api/tick', {});
      updateDashboard(data);
      showToast('Simulation advanced by 1 step.');
      fetchAnalyticsSummary();
      fetchChartData();
    } catch (err) {
      showToast(err.message, true);
    }
  };
}

// Reset with optional deterministic random seed prompt
if ($('reset')) {
  $('reset').onclick = () => {
    const seedInput = prompt(
      'Reset simulation to initial state.\n\nOptionally enter an integer seed for repeatable exam demonstration (e.g., 42), or leave blank for dynamic seed:'
    );
    if (seedInput === null) return;
    const trimmed = seedInput.trim();
    const seed = trimmed === '' ? null : parseInt(trimmed, 10);
    if (trimmed !== '' && isNaN(seed)) {
      showToast('Seed must be a valid integer.', true);
      return;
    }
    sendControl('reset', { seed });
  };
}

// Simulation Speed selector buttons
document.querySelectorAll('.speed-btn').forEach((btn) => {
  btn.onclick = () => {
    const speed = parseFloat(btn.dataset.speed);
    sendControl('speed', { speed });
  };
});

// Timing sliders live labels
if ($('min') && $('max')) {
  $('min').oninput = () => {
    if ($('minval')) $('minval').textContent = $('min').value;
    $('max').min = $('min').value;
    if (+$('max').value < +$('min').value) {
      $('max').value = $('min').value;
    }
    if ($('maxval')) $('maxval').textContent = $('max').value;
  };

  $('max').oninput = () => {
    if ($('maxval')) $('maxval').textContent = $('max').value;
  };
}

// Settings form submission
if ($('settings')) {
  $('settings').onsubmit = async (e) => {
    e.preventDefault();
    try {
      const minVal = parseInt($('min').value, 10);
      const maxVal = parseInt($('max').value, 10);
      const flowVal = parseFloat($('flow').value);

      let data = await apiCall('/api/settings', {
        min_green: minVal,
        max_green: maxVal,
      });

      data = await apiCall('/api/flow-rate', {
        multiplier: flowVal,
      });

      updateDashboard(data);
      showToast('Adaptive timing rules and flow rate successfully applied.');
      fetchChartData();
    } catch (err) {
      showToast(err.message, true);
    }
  };
}

// Background polling loop
function startPolling() {
  fetchState();
  fetchAnalyticsSummary();
  fetchChartData();
  clearInterval(pollTimer);
  pollTimer = setInterval(fetchState, 1000);
  clearInterval(analyticsTimer);
  analyticsTimer = setInterval(fetchAnalyticsSummary, 3000);
  clearInterval(chartTimer);
  chartTimer = setInterval(fetchChartData, 2000);
}

// Initialize on page load
startPolling();
