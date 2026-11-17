// Chart.js wrappers: theme-aware colours (validated categorical palette, fixed
// slot order), thin marks, recessive grid, tooltips on every chart, one y-axis.
/* global Chart */
const registry = new Map();

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
export const series = i => css(`--s${(i % 8) + 1}`);
export const single = () => css('--single');

function applyDefaults() {
  Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
  Chart.defaults.font.size = 13;
  Chart.defaults.color = css('--chart-text');
  Chart.defaults.borderColor = css('--chart-grid');
  Chart.defaults.plugins.tooltip.backgroundColor = css('--glass-strong');
  Chart.defaults.plugins.tooltip.titleColor = css('--text');
  Chart.defaults.plugins.tooltip.bodyColor = css('--text-2');
  Chart.defaults.plugins.tooltip.borderColor = css('--line-strong');
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
  Chart.defaults.plugins.tooltip.boxPadding = 4;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.animation.duration = 500;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.responsive = true;
}

export function destroyAll() { for (const c of registry.values()) c.destroy(); registry.clear(); }

function make(id, config) {
  const el = document.getElementById(id);
  if (!el || typeof Chart === 'undefined') return null;
  applyDefaults();
  if (registry.has(id)) registry.get(id).destroy();
  const ch = new Chart(el, config);
  registry.set(id, ch);
  return ch;
}

const grid = () => ({ color: css('--chart-grid'), drawTicks: false });
const fmtTick = v => (Math.abs(v) >= 1000 ? (v / 1000).toFixed(v % 1000 ? 1 : 0) + 'k' : v);
const legendFor = n => ({ display: n > 1, position: 'top', align: 'end' });

/** Horizontal bar of one measure. */
export function hbar(id, labels, values, { label = '', fmt = v => v, color } = {}) {
  return make(id, {
    type: 'bar',
    data: { labels, datasets: [{ label, data: values, backgroundColor: color || single(), borderRadius: 4, borderSkipped: false, barPercentage: 0.72, categoryPercentage: 0.9 }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${label}: ${fmt(c.raw)}` } } },
      scales: { x: { grid: grid(), ticks: { callback: fmtTick } }, y: { grid: { display: false }, ticks: { autoSkip: false } } } },
  });
}

/** Vertical bars; ``sets`` = [{label, data}] (grouped) or stacked when stacked=true. */
export function bars(id, labels, sets, { stacked = false, fmt = v => v, yTitle = '', horizontal = false, colors } = {}) {
  return make(id, {
    type: 'bar',
    data: { labels, datasets: sets.map((s, i) => ({ label: s.label, data: s.data, backgroundColor: s.color || (colors ? colors[i] : (sets.length === 1 ? single() : series(i))),
      borderRadius: 4, borderSkipped: false, borderColor: css('--surface-chart'), borderWidth: stacked ? { top: 2 } : 0, maxBarThickness: 46 })) },
    options: { indexAxis: horizontal ? 'y' : 'x', plugins: { legend: legendFor(sets.length), tooltip: { mode: 'index', intersect: false, callbacks: { label: c => ` ${c.dataset.label}: ${fmt(c.raw)}` } } },
      scales: { x: { stacked, grid: horizontal ? grid() : { display: false }, ticks: horizontal ? { callback: fmtTick } : { autoSkip: true, maxRotation: 45 } },
        y: { stacked, grid: horizontal ? { display: false } : grid(), beginAtZero: true, title: { display: !!yTitle, text: yTitle }, ticks: horizontal ? { autoSkip: false } : { callback: fmtTick } } } },
  });
}

/** Lines over a category axis; ``sets`` = [{label, data, fill}] */
export function lines(id, labels, sets, { fmt = v => v, yTitle = '', beginAtZero = false, area = false } = {}) {
  return make(id, {
    type: 'line',
    data: { labels, datasets: sets.map((s, i) => {
      const col = s.color || (sets.length === 1 ? single() : series(i));
      return { label: s.label, data: s.data, borderColor: col, backgroundColor: (area || s.fill) ? col + '33' : col, fill: !!(area || s.fill), tension: 0.3, borderWidth: 2,
        pointRadius: labels.length > 30 ? 0 : 3, pointHoverRadius: 6, spanGaps: true, stepped: s.stepped || false };
    }) },
    options: { interaction: { mode: 'index', intersect: false }, plugins: { legend: legendFor(sets.length), tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${fmt(c.raw)}` } } },
      scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } }, y: { grid: grid(), beginAtZero, title: { display: !!yTitle, text: yTitle }, ticks: { callback: fmtTick } } } },
  });
}

export function donut(id, labels, values, { fmt = v => v } = {}) {
  return make(id, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: labels.map((_, i) => series(i)), borderColor: css('--surface-chart'), borderWidth: 2, hoverOffset: 8 }] },
    options: { cutout: '62%', plugins: { legend: { position: 'right', labels: { padding: 12 } }, tooltip: { callbacks: { label: c => ` ${c.label}: ${fmt(c.raw)} (${(c.raw / c.dataset.data.reduce((a, b) => a + b, 0) * 100).toFixed(1)}%)` } } } },
  });
}

export function radar(id, labels, sets, { max = 100 } = {}) {
  return make(id, {
    type: 'radar',
    data: { labels, datasets: sets.map((s, i) => ({ label: s.label, data: s.data, borderColor: series(i), backgroundColor: series(i) + '2e', borderWidth: 2, pointRadius: 3, pointBackgroundColor: series(i) })) },
    options: { plugins: { legend: legendFor(sets.length), tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${c.raw == null ? 'n/a' : Number(c.raw).toFixed(1)}` } } },
      scales: { r: { min: 0, max, ticks: { display: false, stepSize: 25 }, grid: { color: css('--chart-grid') }, angleLines: { color: css('--chart-grid') }, pointLabels: { font: { size: 13, weight: 600 }, color: css('--chart-text') } } } },
  });
}

/** Scatter of one population; points carry a name for the tooltip. */
export function scatter(id, points, { xLabel = '', yLabel = '', fmtX = v => v, fmtY = v => v, onClick } = {}) {
  return make(id, {
    type: 'scatter',
    data: { datasets: [{ label: '', data: points, backgroundColor: single() + 'b3', borderColor: css('--surface-chart'), borderWidth: 1.5, pointRadius: points.map(p => p.r || 5), pointHoverRadius: 8 }] },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${c.raw.name}: ${xLabel} ${fmtX(c.raw.x)}, ${yLabel} ${fmtY(c.raw.y)}` } } },
      onClick: (e, els) => { if (onClick && els.length) onClick(points[els[0].index]); },
      scales: { x: { grid: grid(), title: { display: true, text: xLabel } }, y: { grid: grid(), title: { display: true, text: yLabel } } } },
  });
}
