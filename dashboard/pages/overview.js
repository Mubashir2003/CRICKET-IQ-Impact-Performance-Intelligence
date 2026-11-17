import { matchRows, tinnRows, batRows, partRows, bowlRows, playerOk } from '../js/data.js';
import { kpi, card, chartBox, fmt, esc, eachGender, empty, playerLink, table, teamBadge } from '../js/ui.js';
import { donut, hbar, lines, bars } from '../js/charts.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const mLabel = k => `${MONTHS[+k.slice(5, 7) - 1]} ${k.slice(2, 4)}`;

export async function render(root, env) {
  eachGender(root, env.ctxs, (c, el) => section(c, el, env.ctxs.length > 1));
}

function section(c, el, both) {
  const G = c.G, M = G.M, T = G.tinn, B = G.bat, PT = G.part;
  const mrows = matchRows(c);
  if (!mrows.length) { el.innerHTML = empty('No matches match the current filters.'); return; }
  const ti = tinnRows(c);
  const br = batRows(c);
  const pr = partRows(c);
  const id = s => `${G.g}-${s}`;

  let runs = 0, wkts = 0, balls = 0;
  let hiTeam = null;
  ti.forEach(r => { runs += T.r[r]; wkts += T.w[r]; balls += T.b[r]; if (!hiTeam || T.r[r] > T.r[hiTeam]) hiTeam = r; });
  let hiInd = null; br.forEach(r => { if (hiInd === null || B.r[r] > B.r[hiInd] || (B.r[r] === B.r[hiInd] && !B.out[r])) hiInd = r; });
  let hiPart = null; pr.forEach(r => { if (hiPart === null || PT.r[r] > PT.r[hiPart]) hiPart = r; });
  const teams = new Set(); mrows.forEach(i => { teams.add(M.t1[i]); teams.add(M.t2[i]); });
  const eligSeen = new Set();
  br.forEach(r => { if (playerOk(c, B.p[r])) eligSeen.add(B.p[r]); });
  bowlRows(c).forEach(r => { if (playerOk(c, G.bowl.p[r])) eligSeen.add(G.bowl.p[r]); });
  const tn = t => G.dims.team[t];
  const pn = p => G.dims.player[p];
  const comp = i => G.dims.comp[M.comp[i]];

  el.innerHTML = `
    <div class="kpis">
      ${kpi('Matches', fmt(mrows.length, 'int'), `${new Set(mrows.map(comp)).size} competitions`, '🏟️')}
      ${kpi('Teams', fmt(teams.size, 'int'), 'in selected matches', '🛡️')}
      ${kpi('Eligible players', fmt(eligSeen.size, 'int'), `${G.nElig} qualify (11+ matches)`, '👥', 'Players with 11 or more distinct matches in 2026 who appear in the filtered matches.')}
      ${kpi('Total runs', fmt(runs, 'int'), `${fmt(runs / Math.max(1, ti.length), 'dec1')} per innings`, '🏏')}
      ${kpi('Total wickets', fmt(wkts, 'int'), `${fmt(wkts / Math.max(1, ti.length), 'dec2')} per innings`, '🎯')}
      ${kpi('Avg run rate', fmt(balls ? runs / balls * 6 : null, 'dec2'), 'runs per over', '📈')}
      ${kpi('Highest team score', hiTeam !== null ? `${T.r[hiTeam]}/${T.w[hiTeam]}` : '–', hiTeam !== null ? `${esc(tn(T.t[hiTeam]))} v ${esc(tn(T.o[hiTeam]))}` : '', '🔝')}
      ${kpi('Highest individual', hiInd !== null ? `${B.r[hiInd]}${B.out[hiInd] ? '' : '*'}` : '–', hiInd !== null ? `<a href="${playerLink(G, pn(B.p[hiInd]))}">${esc(pn(B.p[hiInd]))}</a> (${B.b[hiInd]} balls)` : '', '⭐')}
      ${kpi('Highest partnership', hiPart !== null ? fmt(PT.r[hiPart], 'int') : '–', hiPart !== null ? `${esc(pn(PT.a[hiPart]))} & ${esc(pn(PT.b[hiPart]))}` : '', '🤝')}
    </div>
    <div class="grid g2">
      ${card('Competition breakdown', chartBox(id('comp')), { sub: 'Matches by competition' })}
      ${card('Team performance', chartBox(id('teams'), 'tall'), { sub: `Top 15 teams by win % (minimum ${mrows.length > 200 ? 10 : 3} decided matches; bracket = matches)` })}
    </div>
    <div class="grid g2">
      ${card('Scoring trends', chartBox(id('trend')), { sub: 'Average innings score per month, setting vs chasing' })}
      ${card('Runs per match by month', chartBox(id('runsM')), { sub: 'Average total match runs' })}
    </div>
    <div class="grid g3">
      ${card('Wickets per match by month', chartBox(id('wktM'), 'short'), { sub: 'Average wickets in a match' })}
      ${card('Run rate by phase', chartBox(id('phRR'), 'short'), { sub: 'Batting output — runs per over' })}
      ${card('Balls per wicket by phase', chartBox(id('phBW'), 'short'), { sub: 'Bowling threat — fewer balls per wicket is more potent' })}
    </div>
    ${card('Competition coverage', '<div id="' + id('cov') + '"></div>', { sub: 'Competitions present in the supplied data for the current filters' })}`;

  // competitions donut (top 7 + other)
  const cc = new Map(); mrows.forEach(i => cc.set(comp(i), (cc.get(comp(i)) || 0) + 1));
  const cs = [...cc.entries()].sort((a, b) => b[1] - a[1]);
  const top = cs.slice(0, 7); const other = cs.slice(7).reduce((s, x) => s + x[1], 0);
  if (other) top.push(['Other competitions', other]);
  donut(id('comp'), top.map(x => x[0]), top.map(x => x[1]), { fmt: v => `${v} matches` });

  // team performance
  const tr = new Map();
  mrows.forEach(i => {
    if (M.result[i] === 'N') return;
    [M.t1[i], M.t2[i]].forEach(t => { const o = tr.get(t) || { w: 0, n: 0 }; o.n++; if (M.winner[i] === t) o.w++; else if (M.result[i] === 'T' && M.winner[i] < 0) o.w += 0.5; tr.set(t, o); });
  });
  const minN = mrows.length > 200 ? 10 : 3;
  const tl = [...tr.entries()].filter(([, o]) => o.n >= minN).sort((a, b) => b[1].w / b[1].n - a[1].w / a[1].n || b[1].n - a[1].n).slice(0, 15);
  if (tl.length) hbar(id('teams'), tl.map(([t, o]) => `${tn(t)} (${o.n})`), tl.map(([, o]) => +(o.w / o.n * 100).toFixed(1)), { label: 'Win %', fmt: v => v + '%' });
  else document.getElementById(id('teams')).parentElement.innerHTML = empty('Not enough decided matches.');

  // monthly trends
  const byM = new Map();
  ti.forEach(r => {
    const k = G.month[T.m[r]]; const o = byM.get(k) || { s1: 0, n1: 0, s2: 0, n2: 0 };
    if (T.i[r] === 1) { o.s1 += T.r[r]; o.n1++; } else { o.s2 += T.r[r]; o.n2++; } byM.set(k, o);
  });
  const mm = new Map(); mrows.forEach(i => { const k = G.month[i]; mm.set(k, (mm.get(k) || 0) + 1); });
  const runsByM = new Map(), wByM = new Map();
  ti.forEach(r => { const k = G.month[T.m[r]]; runsByM.set(k, (runsByM.get(k) || 0) + T.r[r]); wByM.set(k, (wByM.get(k) || 0) + T.w[r]); });
  const keys = [...mm.keys()].sort();
  lines(id('trend'), keys.map(mLabel), [
    { label: 'Setting (1st innings)', data: keys.map(k => byM.get(k)?.n1 ? +(byM.get(k).s1 / byM.get(k).n1).toFixed(1) : null) },
    { label: 'Chasing (2nd innings)', data: keys.map(k => byM.get(k)?.n2 ? +(byM.get(k).s2 / byM.get(k).n2).toFixed(1) : null) },
  ], { fmt: v => v + ' runs' });
  bars(id('runsM'), keys.map(mLabel), [{ label: 'Runs per match', data: keys.map(k => +((runsByM.get(k) || 0) / mm.get(k)).toFixed(1)) }], { fmt: v => v + ' runs' });
  bars(id('wktM'), keys.map(mLabel), [{ label: 'Wickets per match', data: keys.map(k => +((wByM.get(k) || 0) / mm.get(k)).toFixed(2)) }], { fmt: v => v + ' wkts' });

  // phases
  const ph = ['pp', 'mid', 'dth'], phL = ['Powerplay', 'Middle', 'Death'];
  const agg = ph.map(p => { let r = 0, b = 0, w = 0; ti.forEach(x => { r += T[`${p}_r`][x]; b += T[`${p}_b`][x]; w += T[`${p}_w`][x]; }); return { r, b, w }; });
  bars(id('phRR'), phL, [{ label: 'Run rate', data: agg.map(a => a.b ? +(a.r / a.b * 6).toFixed(2) : null) }], { fmt: v => v + ' rpo' });
  bars(id('phBW'), phL, [{ label: 'Balls per wicket', data: agg.map(a => a.w ? +(a.b / a.w).toFixed(1) : null) }], { fmt: v => v + ' balls' });

  // coverage table
  const covRows = G.core.comps.filter(x => cc.has(x.name)).map(x => ({ name: x.name, type: x.type, n: cc.get(x.name), start: x.start, end: x.end }));
  table(document.getElementById(id('cov')), {
    rows: covRows, pageSize: 12, sortKey: 'n',
    columns: [
      { key: 'name', label: 'Competition', l: true, html: r => `🏆 ${esc(r.name)}` },
      { key: 'type', label: 'Type', l: true, html: r => esc(r.type) },
      { key: 'n', label: 'Matches', fmt: 'int' },
      { key: 'start', label: 'First match', l: true, html: r => esc(r.start) },
      { key: 'end', label: 'Last match', l: true, html: r => esc(r.end) },
    ],
  });
  void both; void teamBadge;
}
