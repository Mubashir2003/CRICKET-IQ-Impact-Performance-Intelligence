// CRICKET IQ - application shell: routing, global filters, theme.
import { store, loadManifest, loadGender, makeCtx, EMPTY_FILTERS } from './data.js';
import { esc, initTooltips } from './ui.js';
import { destroyAll } from './charts.js';

const PAGES = {
  overview: { title: 'Executive Overview', sub: 'The 2026 T20 landscape at a glance' },
  batting: { title: 'Batting Analytics', sub: 'Traditional and opportunity-adjusted batting intelligence' },
  bowling: { title: 'Bowling Analytics', sub: 'Wicket-taking, control and phase specialists' },
  winning: { title: 'Winning Intelligence', sub: 'Who contributes most when teams win' },
  pressure: { title: 'Pressure Intelligence', sub: 'Clutch performance in chases, collapses and close finishes' },
  positions: { title: 'Position & Role Intelligence', sub: 'Batting positions, effectiveness and inferred roles' },
  partnerships: { title: 'Partnership Intelligence', sub: 'Stands, pairs and match situations' },
  teams: { title: 'Team Intelligence', sub: 'Team performance, phases and competition views' },
  player: { title: 'Player Profile', sub: 'Everything about one player' },
  compare: { title: 'Player Comparison', sub: 'Compare up to four players of the same gender' },
  match: { title: 'Match Intelligence', sub: 'Scorecards, progression and match-winning contributions' },
};

const app = document.getElementById('app');
let F = { ...EMPTY_FILTERS };
try { const s = sessionStorage.getItem('ciq-filters'); if (s) F = { ...EMPTY_FILTERS, ...JSON.parse(s) }; } catch (e) { /* ignore */ }
let renderToken = 0;

function route() {
  const h = location.hash.replace(/^#\/?/, '') || 'overview';
  const [page, qs] = h.split('?');
  return { page: PAGES[page] ? page : 'overview', params: Object.fromEntries(new URLSearchParams(qs || '')) };
}

async function gendersFor(F) {
  const keys = store.manifest.genders.map(g => g.key);
  const want = F.gender === 'both' ? keys : keys.filter(k => k === F.gender);
  return Promise.all((want.length ? want : keys.slice(0, 1)).map(loadGender));
}

// ------------------------------------------------------------------ filter bar
function optionsFrom(Gs) {
  const uniq = arr => [...new Set(arr.filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const comps = new Map();
  Gs.forEach(G => G.core.comps.forEach(c => { const o = comps.get(c.name) || { name: c.name, type: c.type, n: 0, g: [] }; o.n += c.n; o.g.push(G.label); comps.set(c.name, o); }));
  return {
    comps: [...comps.values()].sort((a, b) => b.n - a.n),
    types: uniq(Gs.flatMap(G => G.core.comps.map(c => c.type))),
    countries: uniq(Gs.flatMap(G => [...G.P.values()].flatMap(p => p.countries || []))),
    teams: uniq(Gs.flatMap(G => G.dims.team)),
    venues: uniq(Gs.flatMap(G => G.dims.venue)),
    players: uniq(Gs.flatMap(G => [...G.P.values()].map(p => p.name))),
    minDate: Gs.map(G => G.M.date[0]).sort()[0], maxDate: Gs.map(G => G.M.date[G.nM - 1]).sort().slice(-1)[0],
  };
}

function sel(id, label, opts, val, all = 'All') {
  return `<div class="f-group"><label for="${id}">${label}</label><select id="${id}"><option value="">${all}</option>${opts.map(o => {
    const [v, t] = Array.isArray(o) ? o : [o, o];
    return `<option value="${esc(v)}" ${String(val) === String(v) ? 'selected' : ''}>${esc(t)}</option>`;
  }).join('')}</select></div>`;
}

let filterExpanded = false;
function renderFilterBar(Gs) {
  const o = optionsFrom(Gs);
  const bar = document.getElementById('filterbar');
  const compLabel = F.comps.length === 0 ? 'All competitions' : F.comps.length === 1 ? F.comps[0] : `${F.comps.length} competitions`;
  const gbtn = (v, t) => `<button type="button" data-g="${v}" class="${F.gender === v ? 'on' : ''}">${t}</button>`;
  bar.classList.toggle('expanded', filterExpanded);
  bar.innerHTML = `
    <div class="f-group"><label>Gender</label><div class="seg" role="group" aria-label="Gender">${gbtn('men', '♂ Men')}${gbtn('women', '♀ Women')}${gbtn('both', 'Both')}</div></div>
    <div class="f-group ms" id="msComp"><label>Competition</label><button type="button" class="ms-btn" aria-haspopup="true">${esc(compLabel)} ▾</button>
      <div class="ms-pop"><input class="search-input ms-search" type="search" placeholder="Find competition…" aria-label="Find competition">
        <div class="ms-list">${o.comps.map(c => `<label data-name="${esc(c.name.toLowerCase())}"><input type="checkbox" value="${esc(c.name)}" ${F.comps.includes(c.name) ? 'checked' : ''}> ${esc(c.name)} <span class="ms-type">${esc(c.type)} · ${c.n}</span></label>`).join('')}</div></div></div>
    ${sel('fType', 'Competition type', o.types, F.compType)}
    ${sel('fCountry', 'Country', o.countries, F.country)}
    ${sel('fRole', 'Role', ['Batter', 'Bowler', 'All-Rounder'], F.role)}
    <div class="f-group"><label for="fPlayer">Player</label><input id="fPlayer" list="dlPlayers" placeholder="Any player" value="${esc(F.player)}"><datalist id="dlPlayers">${o.players.map(p => `<option value="${esc(p)}">`).join('')}</datalist></div>
    <div class="f-actions"><button type="button" class="btn" id="btnMore">${filterExpanded ? 'Fewer filters ▴' : 'More filters ▾'}</button><button type="button" class="btn primary" id="btnClear">✕ Clear all</button></div>
    <div class="more-filters">
      ${sel('fTeam', 'Team', o.teams, F.team)}
      ${sel('fOpp', 'Opponent', o.teams, F.opponent)}
      ${sel('fVenue', 'Venue', o.venues, F.venue)}
      <div class="f-group"><label for="fFrom">From</label><input id="fFrom" type="date" min="${o.minDate}" max="${o.maxDate}" value="${F.from}"></div>
      <div class="f-group"><label for="fTo">To</label><input id="fTo" type="date" min="${o.minDate}" max="${o.maxDate}" value="${F.to}"></div>
      ${sel('fInn', 'Innings', [['1', '1st innings (setting)'], ['2', '2nd innings (chasing)']], F.innings)}
      ${sel('fPos', 'Batting position', Array.from({ length: 11 }, (_, i) => [String(i + 1), `No. ${i + 1}`]), F.position)}
      ${sel('fPhase', 'Phase', [['powerplay', 'Powerplay (1-6)'], ['middle', 'Middle (7-15)'], ['death', 'Death (16-20)']], F.phase)}
      ${sel('fRes', 'Match result', [['W', 'Won'], ['L', 'Lost'], ['T', 'Tied'], ['N', 'No result']], F.result)}
    </div>`;
  bar.querySelectorAll('[data-g]').forEach(b => b.addEventListener('click', () => setF({ gender: b.dataset.g })));
  const bind = (id, key) => bar.querySelector('#' + id).addEventListener('change', e => setF({ [key]: e.target.value }));
  [['fType', 'compType'], ['fCountry', 'country'], ['fRole', 'role'], ['fTeam', 'team'], ['fOpp', 'opponent'], ['fVenue', 'venue'], ['fFrom', 'from'], ['fTo', 'to'],
    ['fInn', 'innings'], ['fPos', 'position'], ['fPhase', 'phase'], ['fRes', 'result']].forEach(([id, k]) => bind(id, k));
  const pl = bar.querySelector('#fPlayer');
  pl.addEventListener('change', e => { const v = e.target.value.trim(); if (!v || o.players.includes(v)) setF({ player: v }); });
  bar.querySelector('#btnMore').addEventListener('click', () => { filterExpanded = !filterExpanded; renderFilterBar(Gs); });
  bar.querySelector('#btnClear').addEventListener('click', () => setF({ ...EMPTY_FILTERS, gender: F.gender }, true));
  const ms = bar.querySelector('#msComp');
  ms.querySelector('.ms-btn').addEventListener('click', e => { e.stopPropagation(); ms.classList.toggle('open'); ms.querySelector('.ms-search').focus(); });
  ms.querySelector('.ms-pop').addEventListener('click', e => e.stopPropagation());
  ms.querySelector('.ms-search').addEventListener('input', e => { const q = e.target.value.toLowerCase(); ms.querySelectorAll('.ms-list label').forEach(l => { l.style.display = l.dataset.name.includes(q) ? '' : 'none'; }); });
  ms.querySelectorAll('input[type=checkbox]').forEach(cb => cb.addEventListener('change', () => {
    const vals = [...ms.querySelectorAll('input[type=checkbox]:checked')].map(x => x.value);
    F.comps = vals; ms.querySelector('.ms-btn').textContent = (vals.length === 0 ? 'All competitions' : vals.length === 1 ? vals[0] : `${vals.length} competitions`) + ' ▾';
    pendingComp = true;
  }));
  renderChips();
}
let pendingComp = false;
document.addEventListener('click', () => {
  const ms = document.querySelector('#msComp.open');
  if (ms) { ms.classList.remove('open'); if (pendingComp) { pendingComp = false; setF({ comps: F.comps }); } }
});

const CHIP_LABELS = { compType: 'Type', country: 'Country', role: 'Role', player: 'Player', team: 'Team', opponent: 'Opponent', venue: 'Venue', from: 'From', to: 'To',
  innings: 'Innings', position: 'Position', phase: 'Phase', result: 'Result' };
function renderChips() {
  const el = document.getElementById('activeFilters');
  const chips = [];
  F.comps.forEach(c => chips.push([`comp:${c}`, `🏆 ${c}`]));
  for (const [k, l] of Object.entries(CHIP_LABELS)) if (F[k]) chips.push([k, `${l}: ${k === 'result' ? { W: 'Won', L: 'Lost', T: 'Tied', N: 'No result' }[F[k]] : F[k]}`]);
  el.innerHTML = chips.map(([k, t]) => `<span class="chip">${esc(t)}<button type="button" data-k="${esc(k)}" aria-label="Remove filter">✕</button></span>`).join('');
  el.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    const k = b.dataset.k;
    if (k.startsWith('comp:')) setF({ comps: F.comps.filter(c => c !== k.slice(5)) }); else setF({ [k]: '' });
  }));
}

function setF(patch, replace = false) {
  F = replace ? { ...patch } : { ...F, ...patch };
  try { sessionStorage.setItem('ciq-filters', JSON.stringify(F)); } catch (e) { /* ignore */ }
  render(true);
}

// ------------------------------------------------------------------ render
async function render(filtersChanged = false) {
  const token = ++renderToken;
  const { page, params } = route();
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  document.getElementById('pageTitle').textContent = PAGES[page].title;
  document.getElementById('pageSub').textContent = PAGES[page].sub;
  document.getElementById('sidebar').classList.remove('open');
  let Gs;
  try { Gs = await gendersFor(F); } catch (e) { showError(); return; }
  if (token !== renderToken) return;
  renderFilterBar(Gs);
  destroyAll();
  app.innerHTML = '<div class="loading"><div class="spinner"></div><p>Crunching the numbers…</p></div>';
  try {
    const mod = await import(`../pages/${page}.js`);
    if (token !== renderToken) return;
    const ctxs = Gs.map(G => makeCtx(G, F));
    app.innerHTML = '';
    await mod.render(app, { ctxs, F, params, setF, loadGender, nav: h => { location.hash = h; } });
    if (!filtersChanged) window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
  } catch (e) {
    console.error(e);
    app.innerHTML = `<div class="empty glass"><div class="big">🌧️</div><div><b>This view is unavailable right now.</b><br>Try clearing filters or reloading the page.</div></div>`;
  }
}

function showError() {
  app.innerHTML = `<div class="empty glass"><div class="big">🏏</div><div><b>Cricket data is not available yet.</b><br>Please prepare the data and open the dashboard through the local server.</div></div>`;
}

function initTheme() {
  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('ciq-theme', next); } catch (e) { /* ignore */ }
    render(true);
  });
  document.getElementById('menuBtn').addEventListener('click', e => { e.stopPropagation(); document.getElementById('sidebar').classList.toggle('open'); });
}

async function boot() {
  initTheme();
  initTooltips();
  try { await loadManifest(); } catch (e) { showError(); return; }
  const m = store.manifest;
  if (!m.genders.length) { showError(); return; }
  if (F.gender !== 'both' && !m.genders.some(g => g.key === F.gender)) F.gender = m.genders[0].key;
  document.getElementById('coverageNote').innerHTML = m.genders.map(g => `<div><b>${esc(g.label)}:</b> ${g.matches.toLocaleString()} matches · ${g.competitions} competitions · ${g.eligible_players} eligible players<br><span>${g.from} → ${g.to}</span></div>`).join('') +
    `<div style="margin-top:6px">Players qualify with ${m.min_matches}+ matches. Coverage reflects the matches available in the supplied data.</div>`;
  window.addEventListener('hashchange', () => render());
  render();
}
boot();
