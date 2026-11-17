import { batRows, bowlRows, partRows, aggBat, aggBowl, playerOk, scopeMetrics, store } from '../js/data.js';
import { card, chartBox, fmt, esc, eachGender, empty, table, playerCell, def, scopeNote, kpi } from '../js/ui.js';
import { hbar, bars } from '../js/charts.js';

export async function render(root, env) {
  root.innerHTML = `<div class="note">⚡ <b>How pressure is defined:</b> ${esc(store.manifest.pressure_definition)} Expected values come from all pressure deliveries in the same competition type and phase.
    Close finish = tie, win by 10 runs or fewer, by 2 wickets or fewer, or with 6 balls or fewer to spare. Low-scoring match = first-innings total in the bottom quarter. Knockout stages are not identifiable in the supplied data.</div><div id="pwrap" class="grid"></div>`;
  eachGender(root.querySelector('#pwrap'), env.ctxs, (c, el) => section(c, el));
}

function section(c, el) {
  const G = c.G;
  const id = s => `${G.g}-pr-${s}`;
  const c0 = { ...c, phase: '' };
  const bat = [...aggBat(c0, batRows(c0)).values()].filter(a => playerOk(c, a.key)).map(a => ({ ...a, name: G.dims.player[a.key], team: G.dims.team[a.mainTeam], s: scopeMetrics(c, a.key) }));
  const bowl = [...aggBowl(c0, bowlRows(c0)).values()].filter(a => playerOk(c, a.key)).map(a => ({ ...a, name: G.dims.player[a.key], team: G.dims.team[a.mainTeam], s: scopeMetrics(c, a.key) }));
  const pb = bat.filter(r => r.pb >= 30), po = bowl.filter(r => r.pb >= 24);
  if (!pb.length && !po.length) { el.innerHTML = empty('Not enough pressure situations in this selection.'); return; }
  const T = bat.reduce((s, r) => ({ pb: s.pb + r.pb, pr: s.pr + r.pr, po: s.po + r.po, per: s.per + r.per }), { pb: 0, pr: 0, po: 0, per: 0 });
  el.innerHTML = `
    <div class="kpis">
      ${kpi('Pressure balls faced', fmt(T.pb, 'int'), 'eligible batters, current filters', '⚡')}
      ${kpi('Pressure strike rate', fmt(T.pb ? T.pr / T.pb * 100 : null, 'dec2'), `average ${fmt(T.po ? T.pr / T.po : null, 'dec2')}`, '📈')}
      ${kpi('Batters (30+ pressure balls)', fmt(pb.length, 'int'), '', '🏏')}
      ${kpi('Bowlers (24+ pressure balls)', fmt(po.length, 'int'), '', '🎳')}
    </div>
    <div class="grid g2">
      ${card('Clutch batters', chartBox(id('bd'), 'tall'), { sub: 'Pressure Performance Delta: strike rate above the expected SR in comparable pressure situations (60+ pressure balls)' })}
      ${card('Clutch bowlers', chartBox(id('od'), 'tall'), { sub: 'Runs saved per over vs expected in pressure situations (48+ pressure balls)' })}
    </div>
    ${card('Pressure batting', `<div id="${id('bt')}"></div>`, { sub: 'Recomputed for every filter (phase filter not applied — pressure spans phases). Index columns use the advanced scope.' })}
    ${card('Pressure bowling', `<div id="${id('ot')}"></div>`)}
    <div class="grid g2">
      ${card('Close finishes & low-scoring games', `<div class="note" style="margin-bottom:10px">${scopeNote(c)}</div><div id="${id('cl')}"></div>`)}
      ${card('Pressure partnerships', `<div id="${id('pp')}"></div>`, { sub: 'Stands played under pressure (current filters), by batting pair' })}
    </div>
    ${card('Chase performance', chartBox(id('ch')), { sub: 'Run contribution in successful vs unsuccessful chases — top 10 chase run-scorers' })}`;

  const bd = bat.filter(r => r.pb >= 60).sort((a, b) => b.pDelta - a.pDelta).slice(0, 12);
  if (bd.length) hbar(id('bd'), bd.map(r => `${r.name} (${r.pb}b)`), bd.map(r => +r.pDelta.toFixed(1)), { label: 'SR above expected', fmt: v => (v > 0 ? '+' : '') + v });
  else document.getElementById(id('bd')).parentElement.innerHTML = empty('Not enough pressure batting.');
  const od = bowl.filter(r => r.pb >= 48).sort((a, b) => b.pDelta - a.pDelta).slice(0, 12);
  if (od.length) hbar(id('od'), od.map(r => `${r.name} (${r.pb}b)`), od.map(r => +r.pDelta.toFixed(2)), { label: 'Runs/over saved', fmt: v => (v > 0 ? '+' : '') + v });
  else document.getElementById(id('od')).parentElement.innerHTML = empty('Not enough pressure bowling.');

  table(document.getElementById(id('bt')), {
    rows: pb, sortKey: 'pDelta', search: true, pageSize: 15, minNote: '30+ pressure balls',
    columns: [{ key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      { key: 'pb', label: 'Pressure Balls', fmt: 'int' }, { key: 'pr', label: 'Runs', fmt: 'int' }, { key: 'po', label: 'Outs', fmt: 'int', asc: true },
      { key: 'pSr', label: 'Pressure SR', fmt: 'dec2', defKey: 'pressure_sr' }, { key: 'pExpSr', label: 'Expected SR', fmt: 'dec2' },
      { key: 'pDelta', label: 'Pressure Delta', fmt: 'signed1', signed: true, defKey: 'pressure_sr_delta' }, { key: 'pAvg', label: 'Pressure Avg', fmt: 'dec2', defKey: 'pressure_avg' },
      { key: 'chaseSr', label: 'Chase SR', fmt: 'dec2', defKey: 'chase_sr' }, { key: 'chasePct', label: 'Chase Run %', fmt: 'pct', defKey: 'chase_contribution_pct' },
      { key: 'late', label: 'Late-over Eff.', value: r => r.s?.late_over_scoring_efficiency ?? null, fmt: 'idx', defKey: 'late_over_scoring_efficiency' },
      { key: 'pps', label: 'Pressure Stand %', value: r => r.s?.pressure_partnership_contribution_pct ?? null, fmt: 'pct', defKey: 'pressure_partnership_contribution_pct' }],
  });
  table(document.getElementById(id('ot')), {
    rows: po, sortKey: 'pDelta', search: true, pageSize: 15, minNote: '24+ pressure balls',
    columns: [{ key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      { key: 'pb', label: 'Pressure Balls', fmt: 'int' }, { key: 'pr', label: 'Runs', fmt: 'int', asc: true }, { key: 'pw', label: 'Wkts', fmt: 'int' },
      { key: 'pEcon', label: 'Pressure Econ', fmt: 'dec2', asc: true, defKey: 'pressure_economy' }, { key: 'pExpEcon', label: 'Expected Econ', fmt: 'dec2', asc: true },
      { key: 'pDelta', label: 'Pressure Delta', fmt: 'signed2', signed: true, defKey: 'pressure_economy_delta' },
      { key: 'pBpw', label: 'Pressure Balls/Wkt', fmt: 'dec1', asc: true, defKey: 'pressure_wicket_frequency' },
      { key: 'pbi', label: 'Pressure Bowling', value: r => r.s?.pressure_bowling_index ?? null, fmt: 'idx', defKey: 'pressure_bowling_index' },
      { key: 'doe', label: 'Death Effectiveness', value: r => r.s?.death_over_effectiveness ?? null, fmt: 'idx', defKey: 'death_over_effectiveness' }],
  });

  const cl = [...G.P.values()].filter(p => playerOk(c, p.i) && (p.close_matches || 0) >= 3).map(p => ({ key: p.i, name: p.name, ...p }));
  table(document.getElementById(id('cl')), {
    rows: cl, sortKey: 'close_runs', search: true, pageSize: 10,
    columns: [{ key: 'name', label: 'Player', l: true, html: r => playerCell(G, r.key), asc: true },
      { key: 'close_matches', label: 'Close M', fmt: 'int' }, { key: 'close_wins', label: 'Close W', fmt: 'int' }, { key: 'close_runs', label: 'Close Runs', fmt: 'int' },
      { key: 'close_bat_sr', label: 'Close SR', fmt: 'dec2', defKey: 'close_bat_sr' }, { key: 'close_wkts', label: 'Close Wkts', fmt: 'int' },
      { key: 'close_economy', label: 'Close Econ', fmt: 'dec2', asc: true, defKey: 'close_economy' }, { key: 'low_scoring_bat_avg', label: 'Low-score Avg', fmt: 'dec2', defKey: 'low_scoring_bat_avg' }],
  });

  const P = G.part, pairs = new Map();
  partRows(c).forEach(r => {
    if (!P.pr[r]) return;
    const k = `${P.a[r]}|${P.b[r]}`; const o = pairs.get(k) || { a: P.a[r], b: P.b[r], n: 0, runs: 0, balls: 0, best: 0, team: P.t[r] };
    o.n++; o.runs += P.r[r]; o.balls += P.bl[r]; o.best = Math.max(o.best, P.r[r]); pairs.set(k, o);
  });
  const pr = [...pairs.values()].filter(o => o.n >= 2).map(o => ({ ...o, name: `${G.dims.player[o.a]} & ${G.dims.player[o.b]}`, avg: o.runs / o.n, rr: o.balls ? o.runs / o.balls * 6 : null }));
  table(document.getElementById(id('pp')), {
    rows: pr, sortKey: 'runs', pageSize: 10, search: true,
    columns: [{ key: 'name', label: 'Pair', l: true, html: r => `<b>${esc(r.name)}</b><div class="pmeta muted">${esc(G.dims.team[r.team])}</div>`, asc: true },
      { key: 'n', label: 'Stands', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' }, { key: 'avg', label: 'Avg', fmt: 'dec1' }, { key: 'best', label: 'Best', fmt: 'int' }, { key: 'rr', label: 'Run Rate', fmt: 'dec2' }],
  });

  const chSucc = aggBat({ ...c0, innings: 2, result: 'W' }, batRows({ ...c0, innings: 2, result: 'W' }));
  const chFail = aggBat({ ...c0, innings: 2, result: 'L' }, batRows({ ...c0, innings: 2, result: 'L' }));
  const top = bat.filter(r => r.chaseR > 0).sort((a, b) => b.chaseR - a.chaseR).slice(0, 10);
  bars(id('ch'), top.map(r => r.name), [
    { label: 'Successful chases', data: top.map(r => { const x = chSucc.get(r.key); return x && x.tr ? +(x.runs / x.tr * 100).toFixed(1) : null; }) },
    { label: 'Unsuccessful chases', data: top.map(r => { const x = chFail.get(r.key); return x && x.tr ? +(x.runs / x.tr * 100).toFixed(1) : null; }) },
  ], { fmt: v => (v == null ? 'n/a' : v + '% of team runs') });
  void def;
}
