import { batRows, aggBat, playerOk, scopeMetrics, PHASE_LABEL } from '../js/data.js';
import { card, chartBox, fmt, esc, eachGender, empty, table, playerCell, def, scopeNote, kpi } from '../js/ui.js';
import { hbar, bars, scatter } from '../js/charts.js';

export async function render(root, env) {
  root.innerHTML = `<div class="toolbar glass card" style="padding:12px 16px"><label for="minBalls"><b>Minimum balls faced</b></label>
    <select id="minBalls" class="search-input" style="min-width:110px">${[0, 30, 60, 120, 200, 300].map(v => `<option ${v === (env.params.min ? +env.params.min : 60) ? 'selected' : ''}>${v}</option>`).join('')}</select>
    <span class="muted">Leaderboards include eligible players (11+ matches) only. Hover column headers for definitions.</span></div><div id="bwrap" class="grid"></div>`;
  const draw = () => {
    const min = +root.querySelector('#minBalls').value;
    eachGender(root.querySelector('#bwrap'), env.ctxs, (c, el) => section(c, el, min, env));
  };
  root.querySelector('#minBalls').addEventListener('change', draw);
  draw();
}

function section(c, el, min, env) {
  const G = c.G;
  const id = s => `${G.g}-bat-${s}`;
  const agg = aggBat(c, batRows(c));
  const rows = [...agg.values()].filter(a => playerOk(c, a.key)).map(a => ({ ...a, name: G.dims.player[a.key], team: G.dims.team[a.mainTeam] }));
  const qual = rows.filter(r => r.balls >= min);
  if (!rows.length) { el.innerHTML = empty('No batting records for these filters.'); return; }
  const phaseTxt = c.phase ? ` — ${PHASE_LABEL[c.phase]} only` : '';
  const tot = rows.reduce((s, r) => ({ runs: s.runs + r.runs, balls: s.balls + r.balls, outs: s.outs + r.outs, f6: s.f6 + r.f6 }), { runs: 0, balls: 0, outs: 0, f6: 0 });
  el.innerHTML = `
    <div class="kpis">
      ${kpi('Batters', fmt(rows.length, 'int'), `${qual.length} with ${min}+ balls`, '👥')}
      ${kpi('Runs', fmt(tot.runs, 'int'), 'eligible players' + phaseTxt, '🏏')}
      ${kpi('Average', fmt(tot.outs ? tot.runs / tot.outs : null, 'dec2'), 'runs per dismissal', '📊')}
      ${kpi('Strike rate', fmt(tot.balls ? tot.runs / tot.balls * 100 : null, 'dec2'), 'runs per 100 balls', '⚡')}
      ${kpi('Sixes', fmt(tot.f6, 'int'), `1 every ${fmt(tot.f6 ? tot.balls / tot.f6 : null, 'dec1')} balls`, '🚀')}
    </div>
    <div class="grid g2">
      ${card('Top run scorers' + esc(phaseTxt), chartBox(id('top'), 'tall'))}
      ${card('Average vs strike rate', chartBox(id('sc'), 'tall'), { sub: `Eligible batters with ${Math.max(min, 60)}+ balls (and at least one dismissal). Click a dot to open the profile.` })}
    </div>
    ${card('Batting leaderboard' + esc(phaseTxt), `<div id="${id('tbl')}"></div>`, { sub: 'Traditional statistics respond to every filter. “SR vs Avg” compares with the expected strike rate for the same competition, phase and position group.' })}
    <div class="grid g2">
      ${card('Phase strike rates — top 8 run scorers', chartBox(id('ph')), { sub: 'Strike rate in each phase (filters other than phase apply)' })}
      ${card('Runs by batting position', chartBox(id('pos')), { sub: 'Eligible batters, current filters' })}
    </div>
    ${card('Advanced batting metrics', `<div class="note" style="margin-bottom:10px">${scopeNote(c)}</div><div id="${id('adv')}"></div>`, { sub: 'Contribution, consistency, phase indices (100 = average for comparable deliveries) and chase contribution' })}`;

  const top = [...rows].sort((a, b) => b.runs - a.runs).slice(0, 15);
  hbar(id('top'), top.map(r => r.name), top.map(r => r.runs), { label: 'Runs', fmt: v => fmt(v, 'int') });
  const pts = rows.filter(r => r.balls >= Math.max(min, 60) && r.avg != null).map(r => ({ x: +r.sr.toFixed(1), y: +r.avg.toFixed(1), name: r.name, r: Math.max(3, Math.min(11, Math.sqrt(r.runs) / 3.5)) }));
  scatter(id('sc'), pts, { xLabel: 'Strike rate', yLabel: 'Average', onClick: p => env.nav(`#/player?g=${G.g}&p=${encodeURIComponent(p.name)}`) });

  table(document.getElementById(id('tbl')), {
    rows: qual, sortKey: 'runs', search: true, minNote: `${min}+ balls`,
    columns: [
      { key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      { key: 'matches', label: 'M', fmt: 'int' }, { key: 'inns', label: 'Inns', fmt: 'int' }, { key: 'notOuts', label: 'NO', fmt: 'int' },
      { key: 'runs', label: 'Runs', fmt: 'int' }, { key: 'balls', label: 'Balls', fmt: 'int' },
      { key: 'avg', label: 'Avg', fmt: 'dec2', defKey: 'average' }, { key: 'sr', label: 'SR', fmt: 'dec2', defKey: 'strike_rate' },
      { key: 'hs', label: 'HS', html: r => r.hsText, defKey: 'highest' },
      { key: 'f4', label: '4s', fmt: 'int' }, { key: 'f6', label: '6s', fmt: 'int' },
      { key: 'bndPct', label: 'Bdry %', fmt: 'pct', defKey: 'boundary_pct' }, { key: 'dotPct', label: 'Dot %', fmt: 'pct', defKey: 'dot_pct' },
      { key: 'bpb', label: 'Balls/Bdry', fmt: 'dec1', defKey: 'balls_per_boundary' },
      { key: 'f30', label: '30s', fmt: 'int' }, { key: 'f50', label: '50s', fmt: 'int' }, { key: 'f100', label: '100s', fmt: 'int' },
      { key: 'bpd', label: 'Balls/Dis', fmt: 'dec1', defKey: 'balls_per_dismissal' },
      { key: 'teamPct', label: 'Team Run %', fmt: 'pct', defKey: 'team_run_contribution_pct' },
      { key: 'srVs', label: 'SR vs Avg', fmt: 'signed1', signed: true, defKey: 'sr_above_avg' },
      { key: 'rae', label: 'Runs +/-', fmt: 'signed1', signed: true, defKey: 'runs_above_expected' },
    ],
  });

  // phase SR for top 8 (needs unphased aggregation)
  const c2 = { ...c, phase: '' };
  const base = aggBat(c2, batRows(c2));
  const top8 = [...base.values()].filter(a => playerOk(c, a.key)).sort((a, b) => b.runs - a.runs).slice(0, 8);
  const phaseSets = ['pp', 'mid', 'dth'].map(ph => {
    const a = aggBat({ ...c, phase: ph }, batRows(c));
    return { label: PHASE_LABEL[ph], data: top8.map(t => { const x = a.get(t.key); return x && x.balls >= 6 ? +x.sr.toFixed(1) : null; }) };
  });
  bars(id('ph'), top8.map(t => G.dims.player[t.key]), phaseSets, { fmt: v => (v == null ? 'n/a' : v) });

  const pos = Array.from({ length: 11 }, () => 0);
  batRows(c).forEach(r => { if (playerOk(c, G.bat.p[r])) { const p = G.bat.pos[r]; if (p >= 1 && p <= 11) pos[p - 1] += c.phase ? G.bat[`${c.phase}_r`][r] : G.bat.r[r]; } });
  bars(id('pos'), pos.map((_, i) => `No. ${i + 1}`), [{ label: 'Runs', data: pos }], { fmt: v => fmt(v, 'int') });

  const adv = rows.map(r => ({ ...r, s: scopeMetrics(c, r.key) })).filter(r => r.s && (r.s.balls || 0) >= min);
  const a = k => r => r.s?.[k] ?? null;
  table(document.getElementById(id('adv')), {
    rows: adv, sortKey: 'tr', search: true,
    columns: [
      { key: 'name', label: 'Player', l: true, sticky: true, html: r => playerCell(G, r.key, r.team), asc: true },
      ...['team_run_contribution_pct', 'boundary_dependency_pct', 'non_boundary_pct', 'runs_per_ball', 'consistency_index', 'impact_innings_pct', 'runs_per_dismissal',
        'powerplay_aggression_index', 'middle_over_control_index', 'death_finishing_index', 'chase_contribution_pct', 'chase_success_contribution_pct',
        'chase_failure_contribution_pct', 'winning_run_share_pct', 'pressure_sr_delta', 'sr_above_avg'].filter(k => !c.scopeComp || k !== 'boundary_dependency_pct' && k !== 'non_boundary_pct' && k !== 'runs_per_ball' && k !== 'runs_per_dismissal')
        .map(k => ({ key: k === 'team_run_contribution_pct' ? 'tr' : k, label: def(k).label, value: a(k), fmt: def(k).fmt, defKey: k, signed: ['pressure_sr_delta', 'sr_above_avg'].includes(k) })),
    ],
  });
}
