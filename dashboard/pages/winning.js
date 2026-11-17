import { batRows, bowlRows, aggBat, aggBowl, playerOk, scopeMetrics, matchRows } from '../js/data.js';
import { card, chartBox, fmt, eachGender, empty, table, playerCell, def, scopeNote, kpi } from '../js/ui.js';
import { bars, hbar } from '../js/charts.js';

export async function render(root, env) {
  root.innerHTML = `<div class="note">🏆 <b>Three levels of winning involvement are kept separate:</b> <b>present</b> (in the XI for a win) → <b>significant contribution</b>
    (20+ runs and 20%+ of team runs, 2+ wickets, 5+ runs saved from 18+ balls, or a match score of 8+) → <b>match-winning</b> (the best match score in the winning XI, at least 15).
    Match score = runs above expected + runs saved + 10 × wickets above expected. Top-scoring in a win does not automatically make someone the match-winner.</div><div id="wwrap" class="grid"></div>`;
  eachGender(root.querySelector('#wwrap'), env.ctxs, (c, el) => section(c, el));
}

function section(c, el) {
  const G = c.G;
  const id = s => `${G.g}-win-${s}`;
  if (!matchRows(c).length) { el.innerHTML = empty('No matches match the current filters.'); return; }
  const players = [...G.P.values()].filter(p => playerOk(c, p.i)).map(p => ({ key: p.i, name: p.name, team: p.teams[0], s: scopeMetrics(c, p.i) })).filter(r => r.s && (r.s.matches_in_scope || 0) >= 5);
  if (!players.length) { el.innerHTML = empty('Not enough matches for winning analysis with these filters.'); return; }
  const v = (r, k) => r.s?.[k] ?? null;
  const ctxW = { ...c, result: 'W' }, ctxL = { ...c, result: 'L' };
  const batW = aggBat(ctxW, batRows(ctxW)), batL = aggBat(ctxL, batRows(ctxL));
  const bowW = aggBowl(ctxW, bowlRows(ctxW)), bowL = aggBowl(ctxL, bowlRows(ctxL));
  const ctxChase = { ...c, innings: 2, result: 'W' };
  const chase = [...aggBat(ctxChase, batRows(ctxChase)).values()].filter(a => playerOk(c, a.key));
  const tW = [...batW.values()].reduce((s, a) => s + a.runs, 0);

  el.innerHTML = `
    <div class="kpis">
      ${kpi('Players analysed', fmt(players.length, 'int'), '5+ matches in scope', '👥')}
      ${kpi('Runs in wins', fmt(tW, 'int'), 'eligible players, current filters', '🏏')}
      ${kpi('Successful chases', fmt(new Set(batRows(ctxChase).map(r => G.bat.m[r])).size, 'int'), 'matches won batting second', '🎯')}
      ${kpi('Match-winning displays', fmt(players.reduce((s, r) => s + (v(r, 'wins_exceptional') || 0), 0), 'int'), 'best performer in a win (score 15+)', '🌟')}
    </div>
    <div class="grid g2">
      ${card('Contribution in victories', chartBox(id('tiers'), 'tall'), { sub: 'Top 12 by match-winning displays: wins present only vs significant vs match-winning' })}
      ${card('Successful chase contributors', chartBox(id('chase'), 'tall'), { sub: 'Most runs in successful run chases (current filters)' })}
    </div>
    ${card('Player win rates & winning contribution', `<div class="note" style="margin-bottom:10px">${scopeNote(c)}</div><div id="${id('tbl')}"></div>`)}
    <div class="grid g2">
      ${card('Batting in wins vs defeats', chartBox(id('bwl')), { sub: 'Runs per innings — top 10 run scorers in wins' })}
      ${card('Bowling in wins vs defeats', chartBox(id('owl')), { sub: 'Economy — top 10 wicket-takers in wins' })}
    </div>
    ${card('Performance in victories (filterable)', `<div id="${id('vic')}"></div>`, { sub: 'Batting and bowling output in matches won, recomputed for every filter' })}`;

  const tiers = [...players].sort((a, b) => (v(b, 'wins_exceptional') || 0) - (v(a, 'wins_exceptional') || 0) || (v(b, 'wins_significant') || 0) - (v(a, 'wins_significant') || 0)).slice(0, 12);
  bars(id('tiers'), tiers.map(r => r.name), [
    { label: 'Match-winning', data: tiers.map(r => v(r, 'wins_exceptional') || 0) },
    { label: 'Significant contribution', data: tiers.map(r => (v(r, 'wins_significant') || 0) - (v(r, 'wins_exceptional') || 0)) },
    { label: 'Present only', data: tiers.map(r => (v(r, 'wins') || 0) - (v(r, 'wins_significant') || 0)) },
  ], { stacked: true, horizontal: true, fmt: x => `${x} wins` });
  const ch = chase.sort((a, b) => b.runs - a.runs).slice(0, 12);
  if (ch.length) hbar(id('chase'), ch.map(a => `${G.dims.player[a.key]} (SR ${fmt(a.sr, 'dec1')})`), ch.map(a => a.runs), { label: 'Runs in won chases', fmt: x => fmt(x, 'int') });
  else document.getElementById(id('chase')).parentElement.innerHTML = empty('No successful chases in this selection.');

  const keys = ['matches_in_scope', 'wins', 'win_rate', 'runs_in_victories', 'wickets_in_victories', 'winning_run_share_pct', 'winning_wicket_share_pct',
    'wins_significant', 'wins_exceptional', 'match_winning_pct', 'match_winning_innings', 'match_winning_bowling', 'bat_avg_in_wins', 'bat_sr_in_wins', 'economy_in_wins', 'bowl_avg_in_wins'];
  table(document.getElementById(id('tbl')), {
    rows: players, sortKey: 'wins_exceptional', search: true,
    columns: [{ key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      ...keys.map(k => ({ key: k, label: k === 'matches_in_scope' ? 'M' : def(k).label, value: r => v(r, k), fmt: k === 'matches_in_scope' ? 'int' : def(k).fmt, defKey: k, asc: def(k).hib === false }))],
  });

  const bt = [...batW.values()].filter(a => playerOk(c, a.key)).sort((a, b) => b.runs - a.runs).slice(0, 10);
  bars(id('bwl'), bt.map(a => G.dims.player[a.key]), [
    { label: 'In wins', data: bt.map(a => +(a.runs / a.inns).toFixed(1)) },
    { label: 'In defeats', data: bt.map(a => { const l = batL.get(a.key); return l && l.inns ? +(l.runs / l.inns).toFixed(1) : null; }) },
  ], { fmt: x => (x == null ? 'n/a' : x + ' runs/inns') });
  const ot = [...bowW.values()].filter(a => playerOk(c, a.key)).sort((a, b) => b.wkts - a.wkts).slice(0, 10);
  bars(id('owl'), ot.map(a => G.dims.player[a.key]), [
    { label: 'In wins', data: ot.map(a => a.econ != null ? +a.econ.toFixed(2) : null) },
    { label: 'In defeats', data: ot.map(a => { const l = bowL.get(a.key); return l && l.balls ? +l.econ.toFixed(2) : null; }) },
  ], { fmt: x => (x == null ? 'n/a' : x + ' rpo') });

  const vic = [...new Set([...batW.keys(), ...bowW.keys()])].filter(p => playerOk(c, p)).map(p => {
    const b = batW.get(p) || {}, o = bowW.get(p) || {};
    return { key: p, name: G.dims.player[p], runs: b.runs ?? null, avg: b.avg ?? null, sr: b.sr ?? null, teamPct: b.teamPct ?? null, wkts: o.wkts ?? null, econ: o.econ ?? null, bavg: o.avg ?? null, wktPct: o.wktPct ?? null, m: new Set([...(b.m || []), ...(o.m || [])]).size };
  });
  table(document.getElementById(id('vic')), {
    rows: vic, sortKey: 'runs', search: true, pageSize: 15,
    columns: [{ key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key), asc: true },
      { key: 'm', label: 'Wins', fmt: 'int' }, { key: 'runs', label: 'Runs in Wins', fmt: 'int' }, { key: 'avg', label: 'Avg in Wins', fmt: 'dec2' }, { key: 'sr', label: 'SR in Wins', fmt: 'dec2' },
      { key: 'teamPct', label: 'Win Run Share %', fmt: 'pct', tip: 'Runs / team innings totals in wins where the player batted.' },
      { key: 'wkts', label: 'Wkts in Wins', fmt: 'int' }, { key: 'econ', label: 'Econ in Wins', fmt: 'dec2', asc: true }, { key: 'bavg', label: 'Bowl Avg in Wins', fmt: 'dec2', asc: true },
      { key: 'wktPct', label: 'Win Wkt Share %', fmt: 'pct', tip: 'Wickets / team bowler wickets in wins where the player bowled.' }],
  });
}
