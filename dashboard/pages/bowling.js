import { bowlRows, aggBowl, playerOk, scopeMetrics, PHASE_LABEL } from '../js/data.js';
import { card, chartBox, fmt, esc, eachGender, empty, table, playerCell, def, scopeNote, kpi } from '../js/ui.js';
import { hbar, bars, scatter } from '../js/charts.js';

export async function render(root, env) {
  root.innerHTML = `<div class="toolbar glass card" style="padding:12px 16px"><label for="minB"><b>Minimum legal balls bowled</b></label>
    <select id="minB" class="search-input" style="min-width:110px">${[0, 30, 60, 120, 240].map(v => `<option ${v === 60 ? 'selected' : ''}>${v}</option>`).join('')}</select>
    <span class="muted">Runs conceded = bat runs + wides + no-balls. Wickets are bowler-credited only (run outs excluded).</span></div><div id="owrap" class="grid"></div>`;
  const draw = () => { const min = +root.querySelector('#minB').value; eachGender(root.querySelector('#owrap'), env.ctxs, (c, el) => section(c, el, min, env)); };
  root.querySelector('#minB').addEventListener('change', draw);
  draw();
}

function section(c, el, min, env) {
  const G = c.G;
  const id = s => `${G.g}-bowl-${s}`;
  const agg = aggBowl(c, bowlRows(c));
  const rows = [...agg.values()].filter(a => playerOk(c, a.key)).map(a => ({ ...a, name: G.dims.player[a.key], team: G.dims.team[a.mainTeam] }));
  if (!rows.length) { el.innerHTML = empty('No bowling records for these filters.'); return; }
  const qual = rows.filter(r => r.balls >= min);
  const phaseTxt = c.phase ? ` — ${PHASE_LABEL[c.phase]} only` : '';
  const t = rows.reduce((s, r) => ({ b: s.b + r.balls, r: s.r + r.runs, w: s.w + r.wkts, d: s.d + r.dots }), { b: 0, r: 0, w: 0, d: 0 });
  el.innerHTML = `
    <div class="kpis">
      ${kpi('Bowlers', fmt(rows.length, 'int'), `${qual.length} with ${min}+ balls`, '👥')}
      ${kpi('Wickets', fmt(t.w, 'int'), 'bowler-credited' + phaseTxt, '🎯')}
      ${kpi('Economy', fmt(t.b ? t.r / t.b * 6 : null, 'dec2'), 'runs per over', '📉')}
      ${kpi('Average', fmt(t.w ? t.r / t.w : null, 'dec2'), 'runs per wicket', '📊')}
      ${kpi('Dot balls', fmt(t.b ? t.d / t.b * 100 : null, 'pct'), `${fmt(t.d, 'int')} dots`, '⏺️')}
    </div>
    <div class="grid g2">
      ${card('Leading wicket-takers' + esc(phaseTxt), chartBox(id('top'), 'tall'))}
      ${card('Economy vs strike rate', chartBox(id('sc'), 'tall'), { sub: `Eligible bowlers with ${Math.max(min, 60)}+ balls and a wicket. Lower-left is best. Click a dot for the profile.` })}
    </div>
    ${card('Bowling leaderboard' + esc(phaseTxt), `<div id="${id('tbl')}"></div>`, { sub: '“Runs saved” and “Econ advantage” compare with the average for the same competition and phase.' })}
    <div class="grid g2">
      ${card('Phase economy — top 8 wicket-takers', chartBox(id('ph')), { sub: 'Economy in each phase' })}
      ${card('Death-over leaders', chartBox(id('death')), { sub: 'Lowest death-over economy (36+ death balls), current filters' })}
    </div>
    ${card('Advanced bowling metrics', `<div class="note" style="margin-bottom:10px">${scopeNote(c)}</div><div id="${id('adv')}"></div>`, { sub: 'Contribution, control, pressure and death-over effectiveness' })}`;

  const top = [...rows].sort((a, b) => b.wkts - a.wkts || a.econ - b.econ).slice(0, 15);
  hbar(id('top'), top.map(r => r.name), top.map(r => r.wkts), { label: 'Wickets', fmt: v => fmt(v, 'int') });
  const pts = rows.filter(r => r.balls >= Math.max(min, 60) && r.wkts > 0).map(r => ({ x: +r.econ.toFixed(2), y: +r.sr.toFixed(1), name: r.name, r: Math.max(3, Math.min(11, Math.sqrt(r.wkts) * 1.5)) }));
  scatter(id('sc'), pts, { xLabel: 'Economy', yLabel: 'Balls per wicket', onClick: p => env.nav(`#/player?g=${G.g}&p=${encodeURIComponent(p.name)}`) });

  table(document.getElementById(id('tbl')), {
    rows: qual, sortKey: 'wkts', search: true, minNote: `${min}+ balls`,
    columns: [
      { key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      { key: 'matches', label: 'M', fmt: 'int' }, { key: 'inns', label: 'Inns', fmt: 'int' },
      { key: 'balls', label: 'Overs', html: r => r.overs, defKey: 'overs' }, { key: 'balls2', label: 'Balls', value: r => r.balls, fmt: 'int' },
      { key: 'runs', label: 'Runs', fmt: 'int', asc: true }, { key: 'wkts', label: 'Wkts', fmt: 'int' },
      { key: 'avg', label: 'Avg', fmt: 'dec2', asc: true, defKey: 'bowling_average' }, { key: 'econ', label: 'Econ', fmt: 'dec2', asc: true, defKey: 'economy' },
      { key: 'sr', label: 'SR', fmt: 'dec1', asc: true, defKey: 'bowling_sr' }, { key: 'best', label: 'Best', value: r => r.best[0] * 1000 - r.best[1], html: r => r.bestText },
      { key: 'md', label: 'Mdns', fmt: 'int' }, { key: 'dots', label: 'Dots', fmt: 'int' }, { key: 'dotPct', label: 'Dot %', fmt: 'pct', defKey: 'bowl_dot_pct' },
      { key: 'bnd', label: 'Bdry Conc.', fmt: 'int', asc: true }, { key: 'wd', label: 'Wd', fmt: 'int', asc: true }, { key: 'nb', label: 'NB', fmt: 'int', asc: true },
      { key: 'w4', label: '4W', fmt: 'int' }, { key: 'w5', label: '5W', fmt: 'int' },
      { key: 'saved', label: 'Runs Saved', fmt: 'signed1', signed: true, defKey: 'runs_saved' },
      { key: 'econAdv', label: 'Econ Adv.', fmt: 'signed2', signed: true, defKey: 'economy_advantage' },
    ],
  });

  const c2 = { ...c, phase: '' };
  const base = aggBowl(c2, bowlRows(c2));
  const top8 = [...base.values()].filter(a => playerOk(c, a.key)).sort((a, b) => b.wkts - a.wkts).slice(0, 8);
  const sets = ['pp', 'mid', 'dth'].map(ph => {
    const a = aggBowl({ ...c, phase: ph }, bowlRows(c));
    return { label: PHASE_LABEL[ph], data: top8.map(t0 => { const x = a.get(t0.key); return x && x.balls >= 12 ? +x.econ.toFixed(2) : null; }) };
  });
  bars(id('ph'), top8.map(x => G.dims.player[x.key]), sets, { fmt: v => (v == null ? 'n/a (<2 overs)' : v + ' rpo') });
  const d = aggBowl({ ...c, phase: 'dth' }, bowlRows(c));
  const dl = [...d.values()].filter(a => playerOk(c, a.key) && a.balls >= 36).sort((a, b) => a.econ - b.econ).slice(0, 12);
  if (dl.length) hbar(id('death'), dl.map(a => `${G.dims.player[a.key]} (${a.wkts}w)`), dl.map(a => +a.econ.toFixed(2)), { label: 'Death economy', fmt: v => v + ' rpo' });
  else document.getElementById(id('death')).parentElement.innerHTML = empty('Not enough death-over bowling for these filters.');

  const adv = rows.map(r => ({ ...r, s: scopeMetrics(c, r.key) })).filter(r => r.s && (r.s.legal_balls || 0) >= min);
  const keys = ['wicket_contribution_pct', 'dot_ball_share_pct', 'boundary_prevention_rate', 'runs_saved', 'runs_saved_per_24', 'economy_advantage', 'boundary_suppression_index',
    'pressure_bowling_index', 'bowling_consistency', 'wicket_frequency', 'death_over_effectiveness', 'economy_in_wins', 'economy_in_losses', 'winning_wicket_share_pct'];
  table(document.getElementById(id('adv')), {
    rows: adv, sortKey: 'runs_saved', search: true,
    columns: [{ key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      ...keys.map(k => ({ key: k, label: def(k).label, value: r => r.s?.[k] ?? null, fmt: ['runs_saved', 'economy_advantage'].includes(k) ? 'signed2' : def(k).fmt, defKey: k,
        signed: ['runs_saved', 'runs_saved_per_24', 'economy_advantage'].includes(k), asc: def(k).hib === false }))],
  });
}
