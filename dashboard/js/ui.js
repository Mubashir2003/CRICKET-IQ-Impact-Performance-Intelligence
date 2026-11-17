// Reusable UI building blocks.
import { store } from './data.js';

export const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

export function fmt(v, type = 'dec2') {
  if (v === null || v === undefined || (typeof v === 'number' && !isFinite(v))) return '–';
  if (typeof v === 'string') return esc(v);
  switch (type) {
    case 'int': return Math.round(v).toLocaleString('en-US');
    case 'dec1': return v.toFixed(1);
    case 'dec2': return v.toFixed(2);
    case 'pct': return v.toFixed(1) + '%';
    case 'idx': return Math.round(v).toString();
    case 'signed1': return (v > 0 ? '+' : '') + v.toFixed(1);
    case 'signed2': return (v > 0 ? '+' : '') + v.toFixed(2);
    default: return String(v);
  }
}
export const signedCls = v => (v == null ? '' : v > 0 ? 'pos' : v < 0 ? 'neg' : '');

/** Metric label + description from the definitions file. */
export function def(key) { return store.defs[key] || { label: key, fmt: 'dec2', desc: '' }; }

const AV_HUES = [142, 158, 128, 172, 110, 188, 96, 150];
export function avatar(name, size = '') {
  const parts = String(name || '?').replace(/[^A-Za-z\s-]/g, '').trim().split(/\s+/);
  const ini = ((parts[0]?.[0] || '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() || '?';
  let h = 0; for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = AV_HUES[h % AV_HUES.length];
  return `<div class="avatar ${size}" style="background:linear-gradient(135deg,hsl(${hue} 55% 38%),hsl(${(hue + 30) % 360} 60% 50%))" aria-hidden="true">${esc(ini)}</div>`;
}

export function flag(G, country, size = '') {
  if (!country) return '';
  const code = G?.flags?.[country];
  if (!code) return `<span class="team-badge" title="${esc(country)}">${esc(country.slice(0, 2).toUpperCase())}</span>`;
  return `<img class="flag ${size}" src="assets/flags/${code}.svg" alt="${esc(country)} flag" title="${esc(country)}" onerror="this.style.display='none'">`;
}
export function teamBadge(G, team) {
  if (!team) return '';
  if (G?.flags?.[team]) return flag(G, team);
  const ini = team.split(/\s+/).map(w => w[0]).join('').slice(0, 3).toUpperCase();
  return `<span class="team-badge" title="${esc(team)}">${esc(ini)}</span>`;
}

export function playerLink(G, name) { return `#/player?g=${G.g}&p=${encodeURIComponent(name)}`; }
export function playerCell(G, p, sub = '') {
  const P = G.P.get(p);
  const name = G.dims.player[p];
  const meta = sub || [P?.country, P?.role].filter(Boolean).join(' · ');
  return `<div class="pcell">${avatar(name)}<div><a class="pname" href="${playerLink(G, name)}">${esc(name)}</a> ${flag(G, P?.country)}<div class="pmeta">${esc(meta)}</div></div></div>`;
}

export function kpi(label, value, sub = '', ico = '', tip = '') {
  return `<div class="kpi glass"${tip ? ` data-tip="${esc(tip)}"` : ''}>${ico ? `<div class="k-ico">${ico}</div>` : ''}<div class="k-label">${esc(label)}</div><div class="k-value">${value}</div>${sub ? `<div class="k-sub" title="${esc(String(sub).replace(/<[^>]+>/g, ''))}">${sub}</div>` : ''}</div>`;
}

export function card(title, body, { sub = '', id = '', cls = '', right = '' } = {}) {
  return `<section class="card glass ${cls}"${id ? ` id="${id}"` : ''}><div class="card-head"><div><h3>${title}</h3>${sub ? `<div class="sub">${sub}</div>` : ''}</div>${right}</div>${body}</section>`;
}
export const chartBox = (id, cls = '') => `<div class="chart-box ${cls}"><canvas id="${id}" role="img"></canvas></div>`;

export function empty(msg = 'No data matches the current filters.', icon = '🏏') {
  return `<div class="empty"><div class="big">${icon}</div><div>${esc(msg)}</div></div>`;
}
export const expPill = '<span class="pill exp" data-tip="Experimental index: transparent, configurable weights; not an established standard.">🧪 Experimental</span>';

// ------------------------------------------------------------------ data table
/**
 * columns: [{key, label, fmt, l (left align), value(row), html(row), tip, sort:false}]
 */
export function table(el, { columns, rows, sortKey, sortDir = -1, pageSize = 25, rank = true, search = false, searchKey = 'name', onRow = null, minNote = '' }) {
  const state = { sortKey: sortKey || columns.find(c => c.sort !== false && !c.l)?.key, sortDir, page: 0, q: '' };
  const val = (c, r) => (c.value ? c.value(r) : r[c.key]);
  function draw() {
    let data = rows;
    if (state.q) { const q = state.q.toLowerCase(); data = data.filter(r => String(r[searchKey] || '').toLowerCase().includes(q)); }
    const sc = columns.find(c => c.key === state.sortKey);
    if (sc) {
      data = [...data].sort((a, b) => {
        const x = val(sc, a), y = val(sc, b);
        const xn = x === null || x === undefined || (typeof x === 'number' && !isFinite(x));
        const yn = y === null || y === undefined || (typeof y === 'number' && !isFinite(y));
        if (xn && yn) return 0; if (xn) return 1; if (yn) return -1;
        if (typeof x === 'string' || typeof y === 'string') return state.sortDir === -1 ? String(y).localeCompare(String(x)) : String(x).localeCompare(String(y));
        return state.sortDir === -1 ? y - x : x - y;
      });
    }
    const pages = Math.max(1, Math.ceil(data.length / pageSize));
    state.page = Math.min(state.page, pages - 1);
    const slice = data.slice(state.page * pageSize, (state.page + 1) * pageSize);
    const head = `<tr>${rank ? '<th class="l">#</th>' : ''}${columns.map(c => {
      const d = c.tip || (c.defKey ? def(c.defKey).desc : '');
      return `<th class="${c.l ? 'l' : ''} ${c.sticky ? 'sticky' : ''} ${state.sortKey === c.key ? 'sorted' : ''}" data-k="${c.key}"${d ? ` data-tip="${esc(d)}"` : ''}>${esc(c.label)}${state.sortKey === c.key ? `<span class="arr">${state.sortDir === -1 ? '▼' : '▲'}</span>` : ''}</th>`;
    }).join('')}</tr>`;
    const body = slice.map((r, i) => `<tr class="${onRow ? 'click' : ''}" data-i="${rows.indexOf(r)}">${rank ? `<td class="rank l">${state.page * pageSize + i + 1}</td>` : ''}${columns.map(c => {
      const v = val(c, r);
      const content = c.html ? c.html(r) : fmt(v, c.fmt);
      const cls = [c.l ? 'l' : '', c.sticky ? 'sticky' : '', c.signed ? signedCls(v) : ''].join(' ');
      return `<td class="${cls}">${content}</td>`;
    }).join('')}</tr>`).join('');
    el.innerHTML = `${search ? `<div class="toolbar" style="margin-bottom:8px"><input class="search-input" type="search" placeholder="Search players…" value="${esc(state.q)}" aria-label="Search table"></div>` : ''}
      <div class="table-wrap"><table class="dt"><thead>${head}</thead><tbody>${body || `<tr><td colspan="${columns.length + 1}" class="l muted">No rows match the current filters.</td></tr>`}</tbody></table></div>
      <div class="pager"><span>${data.length.toLocaleString()} rows${minNote ? ' · ' + esc(minNote) : ''}</span>${pages > 1 ? `<span><button class="btn sm" data-p="-1" ${state.page === 0 ? 'disabled' : ''}>‹ Prev</button> Page ${state.page + 1} / ${pages} <button class="btn sm" data-p="1" ${state.page >= pages - 1 ? 'disabled' : ''}>Next ›</button></span>` : ''}</div>`;
    el.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
      const k = th.dataset.k; const c = columns.find(x => x.key === k); if (c.sort === false) return;
      if (state.sortKey === k) state.sortDir *= -1; else { state.sortKey = k; state.sortDir = c.asc ? 1 : -1; }
      draw();
    }));
    el.querySelectorAll('[data-p]').forEach(b => b.addEventListener('click', () => { state.page += +b.dataset.p; draw(); }));
    const inp = el.querySelector('.search-input');
    if (inp) inp.addEventListener('input', e => { state.q = e.target.value; state.page = 0; const pos = e.target.selectionStart; draw(); const n = el.querySelector('.search-input'); n.focus(); n.setSelectionRange(pos, pos); });
    if (onRow) el.querySelectorAll('tbody tr[data-i]').forEach(tr => tr.addEventListener('click', e => { if (e.target.closest('a')) return; onRow(rows[+tr.dataset.i]); }));
  }
  draw();
}

// ------------------------------------------------------------------ tooltips
export function initTooltips() {
  const pop = document.getElementById('tipPop');
  let cur = null;
  document.addEventListener('mouseover', e => {
    const t = e.target.closest('[data-tip]');
    if (!t || t === cur) return;
    cur = t;
    pop.textContent = t.dataset.tip;
    pop.classList.add('show');
    const r = t.getBoundingClientRect();
    const w = Math.min(320, window.innerWidth - 20);
    pop.style.left = Math.max(10, Math.min(r.left, window.innerWidth - w - 10)) + 'px';
    pop.style.top = (r.bottom + 8 + 120 > window.innerHeight ? r.top - pop.offsetHeight - 8 : r.bottom + 8) + 'px';
  });
  document.addEventListener('mouseout', e => { if (cur && !cur.contains(e.relatedTarget)) { pop.classList.remove('show'); cur = null; } });
  document.addEventListener('scroll', () => { pop.classList.remove('show'); cur = null; }, true);
}

// ------------------------------------------------------------------ player picker
export function playerPicker(el, G, { placeholder = 'Search for a player…', onPick, exclude = [] }) {
  const all = [...G.P.values()].sort((a, b) => (b.matches || 0) - (a.matches || 0));
  el.innerHTML = `<div class="picker"><input class="search-input" type="search" placeholder="${esc(placeholder)}" aria-label="${esc(placeholder)}" style="width:100%"><div class="picker-list"></div></div>`;
  const wrap = el.querySelector('.picker'), inp = wrap.querySelector('input'), list = wrap.querySelector('.picker-list');
  function show() {
    const q = inp.value.trim().toLowerCase();
    const hits = all.filter(p => !exclude.includes(p.name) && (!q || p.name.toLowerCase().includes(q) || (p.country || '').toLowerCase().includes(q) || p.teams.some(t => t.toLowerCase().includes(q)))).slice(0, 40);
    list.innerHTML = hits.map(p => `<div class="picker-item" data-n="${esc(p.name)}">${avatar(p.name)}<div><b>${esc(p.name)}</b> ${flag(G, p.country)}<div class="pmeta muted">${esc([p.role, p.teams.slice(0, 2).join(', ')].filter(Boolean).join(' · '))}</div></div></div>`).join('') || '<div class="picker-item muted">No eligible players found</div>';
    wrap.classList.add('open');
    list.querySelectorAll('[data-n]').forEach(it => it.addEventListener('mousedown', e => { e.preventDefault(); wrap.classList.remove('open'); inp.value = ''; onPick(it.dataset.n); }));
  }
  inp.addEventListener('focus', show);
  inp.addEventListener('input', show);
  inp.addEventListener('blur', () => setTimeout(() => wrap.classList.remove('open'), 120));
}

/** Render a section per selected gender. Men's and women's data are never mixed. */
export function eachGender(el, ctxs, fn) {
  if (ctxs.length === 1) { fn(ctxs[0], el); return; }
  el.innerHTML = ctxs.map(c => `<div class="gender-head">${c.G.g === 'men' ? '👨' : '👩'} ${esc(c.G.label)} <span class="pill">analysed separately</span></div><div class="grid" data-gsec="${c.G.g}"></div>`).join('');
  ctxs.forEach(c => fn(c, el.querySelector(`[data-gsec="${c.G.g}"]`)));
}

export function scopeNote(c) {
  const where = c.scopeComp ? `${esc(c.scopeComp)} only` : 'all 2026 matches';
  return `Advanced indices use ${where}${c.matchFiltersActive && !c.scopeComp ? '; date, venue, team, phase and result filters apply to the traditional statistics' : ''}.`;
}
