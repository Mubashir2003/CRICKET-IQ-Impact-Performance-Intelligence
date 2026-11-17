import { tinnRows, partRows, matchRows, makeCtx } from '../js/data.js';
import { card, chartBox, fmt, esc, eachGender, empty, table, teamBadge, kpi } from '../js/ui.js';
import { bars, hbar } from '../js/charts.js';

export async function render(root, env) {
  root.innerHTML = '<div id="twrap" class="grid"></div>';
  eachGender(root.querySelector('#twrap'), env.ctxs, (c, el) => section(c, el, env));
}

/** Team aggregates from team-innings facts + match table (filters already applied). */
export function teamStats(c) {
  const G = c.G, T = G.tinn, M = G.M, P = G.part;
  const s = new Map();
  const get = t => { let o = s.get(t); if (!o) { o = { t, name: G.dims.team[t], m: new Set(), w: 0, l: 0, tie: 0, nr: 0, inns: 0, runs: 0, balls: 0, wl: 0, hi: null, lo: null, f4: 0, f6: 0,
    pp_r: 0, pp_b: 0, pp_w: 0, mid_r: 0, mid_b: 0, mid_w: 0, dth_r: 0, dth_b: 0, dth_w: 0, cr: 0, cb: 0, cw: 0, chN: 0, chW: 0, dfN: 0, dfW: 0, pn: 0, pr: 0 }; s.set(t, o); } return o; };
  const rows = tinnRows(c);
  rows.forEach(r => {
    const o = get(T.t[r]);
    o.inns++; o.runs += T.r[r]; o.balls += T.b[r]; o.wl += T.w[r]; o.f4 += T.f4[r]; o.f6 += T.f6[r];
    if (o.hi === null || T.r[r] > o.hi) o.hi = T.r[r];
    if (T.w[r] === 10 || T.b[r] >= 120) { if (o.lo === null || T.r[r] < o.lo) o.lo = T.r[r]; }
    ['pp', 'mid', 'dth'].forEach(p => { o[`${p}_r`] += T[`${p}_r`][r]; o[`${p}_b`] += T[`${p}_b`][r]; o[`${p}_w`] += T[`${p}_w`][r]; });
    if (!o.m.has(T.m[r])) {
      o.m.add(T.m[r]);
      const res = T.res[r]; if (res === 'W') o.w++; else if (res === 'L') o.l++; else if (res === 'T') o.tie++; else o.nr++;
    }
    if (T.i[r] === 2 && T.res[r] !== 'N') { o.chN++; if (T.res[r] === 'W') o.chW++; }
    if (T.i[r] === 1 && T.res[r] !== 'N') { o.dfN++; if (T.res[r] === 'W') o.dfW++; }
    if (c.team === -1) { const opp = get(T.o[r]); opp.cr += T.r[r]; opp.cb += T.b[r]; opp.cw += T.w[r]; }
  });
  if (c.team !== -1) {
    // conceded figures for the filtered team come from the opponents' batting innings
    const flip = { W: 'L', L: 'W', T: 'T', N: 'N' };
    tinnRows({ ...c, team: c.opp, opp: c.team, innings: c.innings ? 3 - c.innings : 0, result: c.result ? flip[c.result] : '' }).forEach(r => { const o = get(T.o[r]); o.cr += T.r[r]; o.cb += T.b[r]; o.cw += T.w[r]; });
  }
  partRows(c).forEach(r => { const o = s.get(P.t[r]); if (o) { o.pn++; o.pr += P.r[r]; } });
  for (const o of s.values()) {
    o.matches = o.m.size;
    const dec = o.w + o.l + o.tie;
    o.winPct = dec ? (o.w + 0.5 * o.tie) / dec * 100 : null;
    o.avgScore = o.inns ? o.runs / o.inns : null;
    o.rr = o.balls ? o.runs / o.balls * 6 : null;
    o.ppRR = o.pp_b ? o.pp_r / o.pp_b * 6 : null; o.midRR = o.mid_b ? o.mid_r / o.mid_b * 6 : null; o.dthRR = o.dth_b ? o.dth_r / o.dth_b * 6 : null;
    o.batEff = o.wl ? o.runs / o.wl : null;
    o.bowlEcon = o.cb ? o.cr / o.cb * 6 : null;
    o.bowlEff = o.cw ? o.cr / o.cw : null;
    o.chasePct = o.chN ? o.chW / o.chN * 100 : null;
    o.defPct = o.dfN ? o.dfW / o.dfN * 100 : null;
    o.avgWkts = o.inns ? o.wl / o.inns : null;
    o.bndDep = o.runs ? (o.f4 * 4 + o.f6 * 6) / o.runs * 100 : null;
    o.partAvg = o.pn ? o.pr / o.pn : null;
    o.netRR = o.rr != null && o.bowlEcon != null ? o.rr - o.bowlEcon : null;
  }
  void M;
  return [...s.values()].filter(o => o.matches > 0 && (c.team === -1 || o.t === c.team));
}

const COLS = G => [
  { key: 'name', label: 'Team', l: true, sticky: true, html: r => `${teamBadge(G, r.name)} <b>${esc(r.name)}</b>`, asc: true },
  { key: 'matches', label: 'M', fmt: 'int' }, { key: 'w', label: 'W', fmt: 'int' }, { key: 'l', label: 'L', fmt: 'int', asc: true }, { key: 'tie', label: 'T', fmt: 'int' }, { key: 'nr', label: 'NR', fmt: 'int' },
  { key: 'winPct', label: 'Win %', fmt: 'pct' }, { key: 'avgScore', label: 'Avg Score', fmt: 'dec1' }, { key: 'hi', label: 'High', fmt: 'int' }, { key: 'lo', label: 'Low', fmt: 'int', asc: true, tip: 'Lowest completed innings (all out or full 20 overs).' },
  { key: 'rr', label: 'Run Rate', fmt: 'dec2' }, { key: 'ppRR', label: 'PP RR', fmt: 'dec2' }, { key: 'midRR', label: 'Middle RR', fmt: 'dec2' }, { key: 'dthRR', label: 'Death RR', fmt: 'dec2' },
  { key: 'batEff', label: 'Runs/Wkt', fmt: 'dec1', tip: 'Batting efficiency: runs scored per wicket lost.' },
  { key: 'bowlEcon', label: 'Econ Conceded', fmt: 'dec2', asc: true, tip: 'Bowling efficiency: runs conceded per over.' },
  { key: 'bowlEff', label: 'Runs/Wkt Conceded', fmt: 'dec1', asc: true, tip: 'Runs conceded per wicket taken.' },
  { key: 'netRR', label: 'Net RR', fmt: 'signed2', signed: true, tip: 'Run rate scored minus run rate conceded (simple, unadjusted for overs-reduced matches).' },
  { key: 'chasePct', label: 'Chase Win %', fmt: 'pct' }, { key: 'defPct', label: 'Defend Win %', fmt: 'pct' },
  { key: 'avgWkts', label: 'Avg Wkts Lost', fmt: 'dec2', asc: true }, { key: 'bndDep', label: 'Bdry Dependency %', fmt: 'pct' }, { key: 'partAvg', label: 'Avg Partnership', fmt: 'dec1' },
];

function section(c, el, env) {
  const G = c.G;
  const id = s => `${G.g}-tm-${s}`;
  const stats = teamStats(c);
  if (!stats.length) { el.innerHTML = empty('No team data for these filters.'); return; }
  const minM = matchRows(c).length > 150 ? 8 : 2;
  const q = stats.filter(o => o.matches >= minM);
  el.innerHTML = `
    <div class="kpis">
      ${kpi('Teams', fmt(stats.length, 'int'), `${q.length} with ${minM}+ matches`, '🛡️')}
      ${kpi('Chasing wins', fmt(stats.reduce((s, o) => s + o.chW, 0), 'int'), `of ${fmt(stats.reduce((s, o) => s + o.chN, 0), 'int')} decided chases`, '🎯')}
      ${kpi('Defending wins', fmt(stats.reduce((s, o) => s + o.dfW, 0), 'int'), 'teams batting first', '🛡️')}
    </div>
    ${card('Team performance table', `<div id="${id('tbl')}"></div>`, { sub: 'Every column responds to the global filters (competition, dates, venue, innings, opponent…).' })}
    <div class="grid g2">
      ${card('Win percentage', chartBox(id('win'), 'tall'), { sub: `Top 15 by win % (${minM}+ matches)` })}
      ${card('Net run rate', chartBox(id('nrr'), 'tall'), { sub: `Run rate scored minus conceded — top 15 (${minM}+ matches)` })}
    </div>
    ${card('Team comparison by phase', `<div class="toolbar" style="margin-bottom:10px" id="${id('pick')}"></div>${chartBox(id('phase'))}`, { sub: 'Run rate by phase for up to 6 selected teams (pre-selected: most matches)' })}
    ${card('Competition view', `<div class="toolbar" style="margin-bottom:10px"><label for="${id('csel')}"><b>Competition</b></label><select id="${id('csel')}" class="search-input">${G.core.comps.map(x => `<option>${esc(x.name)}</option>`).join('')}</select><span class="muted">Team standings and performance inside one competition</span></div><div id="${id('ctbl')}"></div>`)}`;

  table(document.getElementById(id('tbl')), { rows: stats, sortKey: 'w', search: true, searchKey: 'name', columns: COLS(G) });
  const w = [...q].sort((a, b) => b.winPct - a.winPct).slice(0, 15);
  hbar(id('win'), w.map(o => `${o.name} (${o.matches})`), w.map(o => +o.winPct.toFixed(1)), { label: 'Win %', fmt: v => v + '%' });
  const n = [...q].filter(o => o.netRR != null).sort((a, b) => b.netRR - a.netRR).slice(0, 15);
  hbar(id('nrr'), n.map(o => o.name), n.map(o => +o.netRR.toFixed(2)), { label: 'Net run rate', fmt: v => (v > 0 ? '+' : '') + v });

  let chosen = [...stats].sort((a, b) => b.matches - a.matches).slice(0, 4).map(o => o.name);
  const pick = document.getElementById(id('pick'));
  const drawPick = () => {
    pick.innerHTML = `<select class="search-input" aria-label="Add team"><option value="">+ Add team…</option>${[...stats].sort((a, b) => a.name.localeCompare(b.name)).filter(o => !chosen.includes(o.name)).map(o => `<option>${esc(o.name)}</option>`).join('')}</select>` +
      chosen.map(t => `<span class="chip">${esc(t)}<button data-t="${esc(t)}" aria-label="Remove">✕</button></span>`).join('');
    pick.querySelector('select').addEventListener('change', e => { if (e.target.value && chosen.length < 6) { chosen.push(e.target.value); drawPick(); } });
    pick.querySelectorAll('[data-t]').forEach(b => b.addEventListener('click', () => { chosen = chosen.filter(x => x !== b.dataset.t); drawPick(); }));
    const sel = chosen.map(t => stats.find(o => o.name === t)).filter(Boolean);
    bars(id('phase'), ['Powerplay', 'Middle', 'Death', 'Overall'], sel.map(o => ({ label: o.name, data: [o.ppRR, o.midRR, o.dthRR, o.rr].map(v => (v == null ? null : +v.toFixed(2))) })), { fmt: v => v + ' rpo' });
  };
  drawPick();

  const csel = document.getElementById(id('csel'));
  if (c.F.comps.length === 1) csel.value = c.F.comps[0];
  const drawComp = () => {
    const cc = makeCtx(G, { ...c.F, comps: [csel.value] });
    table(document.getElementById(id('ctbl')), { rows: teamStats(cc), sortKey: 'w', pageSize: 20, columns: COLS(G).slice(0, 14) });
  };
  csel.addEventListener('change', drawComp);
  drawComp();
  void env;
}
