/**
 * Intelligent Traffic Management System - Native Canvas Charting Engine
 * 100% Self-Contained, Zero-Dependency, Offline-Ready Canvas Visualizations.
 * Renders live Queue Depth, Network Throughput, Average Wait Time, and Signal Utilization.
 */

class TrafficCharts {
  constructor() {
    this.dpr = window.devicePixelRatio || 1;
  }

  // Adjust canvas resolution for crisp rendering on HiDPI/Retina screens
  setupCanvas(canvas) {
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * this.dpr;
    canvas.height = rect.height * this.dpr;
    const ctx = canvas.getContext('2d');
    ctx.resetTransform();
    ctx.scale(this.dpr, this.dpr);
    return { ctx, width: rect.width, height: rect.height };
  }

  // 1. Queue Length & Throughput Multi-Line Chart
  renderQueueThroughput(canvasId, timeline) {
    const canvas = document.getElementById(canvasId);
    const setup = this.setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    ctx.clearRect(0, 0, width, height);

    if (!timeline || timeline.length < 2) {
      this.renderEmptyState(ctx, width, height, 'Collecting simulation timeline data...');
      return;
    }

    const padding = { top: 25, right: 30, bottom: 35, left: 45 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const maxQueue = Math.max(30, ...timeline.map((t) => t.total_vehicles || 0));
    const maxThroughput = Math.max(30, ...timeline.map((t) => t.total_passed || 0));
    const maxVal = Math.max(maxQueue, maxThroughput) * 1.15;

    // Draw gridlines
    ctx.strokeStyle = '#eef2f7';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px "DM Sans", sans-serif';

    const yTicks = 4;
    for (let i = 0; i <= yTicks; i++) {
      const y = padding.top + (chartH / yTicks) * i;
      const val = Math.round(maxVal - (maxVal / yTicks) * i);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.fillText(val, 8, y + 3);
    }

    const n = timeline.length;
    const stepX = chartW / Math.max(1, n - 1);

    // Area fill for Queue
    ctx.beginPath();
    timeline.forEach((pt, idx) => {
      const x = padding.left + idx * stepX;
      const y = padding.top + chartH - ((pt.total_vehicles || 0) / maxVal) * chartH;
      if (idx === 0) ctx.moveTo(x, padding.top + chartH);
      ctx.lineTo(x, y);
      if (idx === n - 1) ctx.lineTo(x, padding.top + chartH);
    });
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
    grad.addColorStop(0, 'rgba(53, 105, 232, 0.22)');
    grad.addColorStop(1, 'rgba(53, 105, 232, 0.01)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Line 1: Queued Vehicles (Blue)
    ctx.beginPath();
    timeline.forEach((pt, idx) => {
      const x = padding.left + idx * stepX;
      const y = padding.top + chartH - ((pt.total_vehicles || 0) / maxVal) * chartH;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = '#3569e8';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Line 2: Cumulative Departures (Green dashed)
    ctx.beginPath();
    ctx.setLineDash([4, 3]);
    timeline.forEach((pt, idx) => {
      const x = padding.left + idx * stepX;
      const y = padding.top + chartH - ((pt.total_passed || 0) / maxVal) * chartH;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.setLineDash([]);

    // X-axis Tick marks & labels
    ctx.fillStyle = '#94a3b8';
    const firstTick = timeline[0].tick || 1;
    const lastTick = timeline[n - 1].tick || n;
    ctx.fillText(`Tick ${firstTick}`, padding.left, height - 12);
    ctx.fillText(`Tick ${lastTick}`, width - padding.right - 40, height - 12);

    // Legend
    this.renderLegend(ctx, [
      { color: '#3569e8', label: 'Network Queue' },
      { color: '#10b981', label: 'Processed Vehicles', dashed: true },
    ], width - 250, 14);
  }

  // 2. Average Waiting Delay Trend
  renderWaitDelay(canvasId, timeline) {
    const canvas = document.getElementById(canvasId);
    const setup = this.setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    ctx.clearRect(0, 0, width, height);

    if (!timeline || timeline.length < 2) {
      this.renderEmptyState(ctx, width, height, 'Collecting delay metrics...');
      return;
    }

    const padding = { top: 25, right: 30, bottom: 35, left: 45 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const maxWait = Math.max(25, ...timeline.map((t) => t.avg_wait_seconds || 0)) * 1.25;

    // Gridlines
    ctx.strokeStyle = '#eef2f7';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px "DM Sans", sans-serif';

    const yTicks = 4;
    for (let i = 0; i <= yTicks; i++) {
      const y = padding.top + (chartH / yTicks) * i;
      const val = Math.round(maxWait - (maxWait / yTicks) * i);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.fillText(`${val}s`, 8, y + 3);
    }

    const n = timeline.length;
    const stepX = chartW / Math.max(1, n - 1);

    // Area fill for Delay
    ctx.beginPath();
    timeline.forEach((pt, idx) => {
      const x = padding.left + idx * stepX;
      const y = padding.top + chartH - ((pt.avg_wait_seconds || 0) / maxWait) * chartH;
      if (idx === 0) ctx.moveTo(x, padding.top + chartH);
      ctx.lineTo(x, y);
      if (idx === n - 1) ctx.lineTo(x, padding.top + chartH);
    });
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
    grad.addColorStop(0, 'rgba(245, 158, 11, 0.25)');
    grad.addColorStop(1, 'rgba(245, 158, 11, 0.01)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Line: Average Wait Seconds (Amber)
    ctx.beginPath();
    timeline.forEach((pt, idx) => {
      const x = padding.left + idx * stepX;
      const y = padding.top + chartH - ((pt.avg_wait_seconds || 0) / maxWait) * chartH;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Starvation threshold line at 45s (if within range)
    if (45 < maxWait) {
      const threshY = padding.top + chartH - (45 / maxWait) * chartH;
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#ef444488';
      ctx.moveTo(padding.left, threshY);
      ctx.lineTo(width - padding.right, threshY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#ef4444';
      ctx.fillText('Starvation Threshold (45s)', width - padding.right - 140, threshY - 4);
    }

    // X-axis Labels
    ctx.fillStyle = '#94a3b8';
    const firstTick = timeline[0].tick || 1;
    const lastTick = timeline[n - 1].tick || n;
    ctx.fillText(`Tick ${firstTick}`, padding.left, height - 12);
    ctx.fillText(`Tick ${lastTick}`, width - padding.right - 40, height - 12);

    this.renderLegend(ctx, [
      { color: '#f59e0b', label: 'Average Delay (seconds)' },
    ], width - 180, 14);
  }

  // 3. Directional Signal Utilization Bar Chart
  renderSignalUtilization(canvasId, signalUtil) {
    const canvas = document.getElementById(canvasId);
    const setup = this.setupCanvas(canvas);
    if (!setup) return;
    const { ctx, width, height } = setup;

    ctx.clearRect(0, 0, width, height);

    const directions = ['North', 'East', 'South', 'West'];
    const hasData = signalUtil && Object.keys(signalUtil).length > 0;

    if (!hasData) {
      this.renderEmptyState(ctx, width, height, 'Recording signal phase utilization...');
      return;
    }

    const padding = { top: 30, right: 25, bottom: 35, left: 45 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const barW = Math.min(45, chartW / directions.length - 20);

    // Baseline gridline at 100%
    ctx.strokeStyle = '#eef2f7';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px "DM Sans", sans-serif';

    [0, 25, 50, 75, 100].forEach((pct) => {
      const y = padding.top + chartH - (pct / 100) * chartH;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.fillText(`${pct}%`, 10, y + 3);
    });

    directions.forEach((dir, i) => {
      const x = padding.left + (chartW / directions.length) * i + (chartW / directions.length - barW) / 2;
      const data = signalUtil[dir] || { GREEN: 25, YELLOW: 5, RED: 70 };
      const gPct = data.GREEN || 0;
      const yPct = data.YELLOW || 0;
      const rPct = data.RED || 0;

      let curY = padding.top + chartH;

      // Green portion
      const gH = (gPct / 100) * chartH;
      curY -= gH;
      ctx.fillStyle = '#10b981';
      ctx.fillRect(x, curY, barW, gH);

      // Yellow portion
      const yH = (yPct / 100) * chartH;
      curY -= yH;
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(x, curY, barW, yH);

      // Red portion
      const rH = (rPct / 100) * chartH;
      curY -= rH;
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(x, curY, barW, rH);

      // Label
      ctx.fillStyle = '#475569';
      ctx.font = '700 11px "DM Sans", sans-serif';
      ctx.fillText(dir, x + (barW - ctx.measureText(dir).width) / 2, height - 12);
    });

    this.renderLegend(ctx, [
      { color: '#10b981', label: 'Green %' },
      { color: '#f59e0b', label: 'Yellow %' },
      { color: '#ef4444', label: 'Red %' },
    ], width - 240, 14);
  }

  // Draw standardized legend
  renderLegend(ctx, items, startX, y) {
    ctx.font = '10px "DM Sans", sans-serif';
    let curX = startX;
    items.forEach((item) => {
      ctx.fillStyle = item.color;
      ctx.fillRect(curX, y - 6, 10, 6);
      ctx.fillStyle = '#64748b';
      ctx.fillText(item.label, curX + 14, y);
      curX += ctx.measureText(item.label).width + 24;
    });
  }

  // Draw empty/loading state placeholder
  renderEmptyState(ctx, width, height, text) {
    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px "DM Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(text, width / 2, height / 2);
    ctx.textAlign = 'left';
  }
}

window.trafficCharts = new TrafficCharts();

