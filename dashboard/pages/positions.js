import { batRows, aggBat, playerOk } from '../js/data.js';
import { card, chartBox, fmt, esc, eachGender, empty, table, playerCell, expPill, kpi } from '../js/ui.js';
import { bars, donut } from '../js/charts.js';

const GROUPS = { top: 'Top order (1-3)', middle: 'Middle order (4-7)', lower: 'Lower order (8-11)' };
const BAT_ROLES = ['Powerplay Aggressor', 'Top-order Stabilizer', 'Middle-order Controller', 'Spin Attacker', 'Finisher', 'Pressure Specialist', 'Flexible Batter'];
const BOWL_ROLES = ['Powerplay Wicket-taker', 'Middle-over Controller', 'Spin Pressure Specialist', 'Death-over Specialist', 'Boundary Suppressor', 'Partnership Breaker'];
const ROLE_TIPS = {
  'Powerplay Aggressor': '40%+ of balls in overs 1-6 (60+ balls) with a powerplay strike rate 8%+ above expected.',
  'Top-order Stabilizer': 'Median position 1-3, 8+ innings, average 10%+ above expected.',
  'Middle-order Controller': '40%+ of balls in overs 7-15, scoring at or above expected while avoiding dots.',
  'Spin Attacker': 'Requires bowling-type data (not in the supplied data).',
  'Finisher': '30%+ of balls in overs 16-20 from No. 4 or lower, death SR 8%+ above expected.',
  'Pressure Specialist': '60+ pressure balls with a strike rate 18+ above expected for those situations.',
  'Flexible Batter': 'Batted in 4+ different positions with 3+ innings at each.',
  'Powerplay Wicket-taker': '30%+ of balls in the powerplay with wickets 15%+ above expected.',
  'Middle-over Controller': '40%+ of balls in overs 7-15 conceding 7%+ fewer runs than expected.',
  'Spin Pressure Specialist': 'Requires bowling-type data (not in the supplied data).',
  'Death-over Specialist': '30%+ of balls at the death with economy 5%+ better than expected.',
  'Boundary Suppressor': '120+ balls conceding boundaries 15%+ less often than expected.',
  'Partnership Breaker': 'Broke 6+ partnerships worth 30+ runs.',
};

export async function render(root, env) {
  root.innerHTML = '<div id="poswrap" class="grid"></div>';
  eachGender(root.querySelector('#poswrap'), env.ctxs, (c, el) => section(c, el));
}

function section(c, el) {
  const G = c.G, B = G.bat;
  const id = s => `${G.g}-pos-${s}`;
  const rows = batRows(c).filter(r => !(c.player !== -1 || c.F.country || c.F.role) || playerOk(c, B.p[r]));
  if (!rows.length) { el.innerHTML = empty('No batting innings for these filters.'); return; }
  const agg = aggBat(c, rows, r => B.pos[r]);
  const winTeam = new Map();
  rows.forEach(r => { if (B.res[r] === 'W') { const p = B.pos[r]; const o = winTeam.get(p) || { r: 0, t: 0 }; o.r += c.phase ? B[`${c.phase}_r`][r] : B.r[r]; o.t += B.tr[r]; winTeam.set(p, o); } });
  const phaseShare = new Map();
  rows.forEach(r => { const p = B.pos[r]; const o = phaseShare.get(p) || { pp: 0, mid: 0, dth: 0, all: 0 }; o.pp += B.pp_b[r]; o.mid += B.mid_b[r]; o.dth += B.dth_b[r]; o.all += B.b[r]; phaseShare.set(p, o); });
  const pt = [...agg.values()].filter(a => a.key >= 1 && a.key <= 11).sort((a, b) => a.key - b.key).map(a => {
    const w = winTeam.get(a.key), ps = phaseShare.get(a.key);
    return { ...a, name: `No. ${a.key}`, winPct: w && w.t ? w.r / w.t * 100 : null, ppS: ps.all ? ps.pp / ps.all * 100 : null, midS: ps.all ? ps.mid / ps.all * 100 : null, dthS: ps.all ? ps.dth / ps.all * 100 : null };
  });
  const roleCounts = { Batter: 0, Bowler: 0, 'All-Rounder': 0 };
  const bc = Object.fromEntries(BAT_ROLES.map(r => [r, 0])), oc = Object.fromEntries(BOWL_ROLES.map(r => [r, 0]));
  const elig = [...G.P.values()].filter(p => playerOk(c, p.i));
  elig.forEach(p => { if (p.role) roleCounts[p.role]++; p.batRoles.forEach(r => bc[r]++); p.bowlRoles.forEach(r => oc[r]++); });
  const spinNote = '<div class="note warn" style="margin-top:8px">Spin Attacker and Spin Pressure Specialist need bowler-type (spin/pace) information, which the supplied data does not include. Add it in <i>config/bowler_types.csv</i> to enable them.</div>';

  el.innerHTML = `
    <div class="kpis">
      ${kpi('Batters', fmt(roleCounts.Batter, 'int'), 'primary role', '🏏')}
      ${kpi('Bowlers', fmt(roleCounts.Bowler, 'int'), 'primary role', '🎳')}
      ${kpi('All-rounders', fmt(roleCounts['All-Rounder'], 'int'), 'bat 8+ balls/inns & bowl in half their matches', '⭐')}
    </div>
    ${card('Performance by batting position', `<div id="${id('pt')}"></div>`, { sub: 'All batters in the filtered matches. Team run % = runs / team innings total. Phase columns show where each position faces its balls.' })}
    <div class="grid g2">
      ${card('Average by position', chartBox(id('avg')))}
      ${card('Strike rate by position', chartBox(id('sr')))}
    </div>
    ${card('Position-specific leaderboard', `<div class="toolbar" style="margin-bottom:10px"><label for="${id('psel')}"><b>Position</b></label><select class="search-input" id="${id('psel')}" style="min-width:120px">${Array.from({ length: 11 }, (_, i) => `<option value="${i + 1}" ${i === 0 ? 'selected' : ''}>No. ${i + 1}</option>`).join('')}</select><span class="muted">Eligible players, 3+ innings at the position</span></div><div id="${id('plb')}"></div>`)}
    ${card('Position Effectiveness Index', `<div class="tabs" id="${id('pg')}">${Object.entries(GROUPS).map(([k, v], i) => `<button data-g="${k}" class="${i === 0 ? 'on' : ''}">${v}</button>`).join('')}</div><div id="${id('pei')}" style="margin-top:10px"></div>`,
      { sub: 'Run production 35% · team contribution 25% · scoring efficiency 25% · pressure 15% — standardised within the position group, shrunk for small samples, shown as a 0-100 percentile. Season-level (all competitions).', right: expPill })}
    <div class="grid g3">
      ${card('Primary roles', chartBox(id('rd'), 'short'))}
      ${card('Batting role tendencies', chartBox(id('br'), 'short'), { sub: 'Players can hold several roles' })}
      ${card('Bowling role tendencies', chartBox(id('or'), 'short'))}
    </div>
    ${card('Role explorer', `<div class="toolbar" id="${id('rchips')}" style="margin-bottom:10px">${[...BAT_ROLES, ...BOWL_ROLES].map(r => `<button class="btn sm" data-r="${esc(r)}" data-tip="${esc(ROLE_TIPS[r])}">${esc(r)}</button>`).join('')}</div><div id="${id('rt')}"></div>${spinNote}`,
      { sub: 'Roles are inferred from where and how each player actually batted or bowled, compared with comparable deliveries — never from reputation.' })}`;

  table(document.getElementById(id('pt')), {
    rows: pt, sortKey: 'key', sortDir: 1, rank: false, pageSize: 11,
    columns: [{ key: 'key', label: 'Position', l: true, html: r => `<b>No. ${r.key}</b>`, asc: true }, { key: 'inns', label: 'Inns', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' },
      { key: 'avg', label: 'Avg', fmt: 'dec2' }, { key: 'sr', label: 'SR', fmt: 'dec2' }, { key: 'bndPct', label: 'Bdry %', fmt: 'pct' }, { key: 'dotPct', label: 'Dot %', fmt: 'pct', asc: true },
      { key: 'teamPct', label: 'Team Run %', fmt: 'pct' }, { key: 'winPct', label: 'Share in Wins %', fmt: 'pct', tip: 'Runs from this position / team totals in matches won.' },
      { key: 'srVs', label: 'SR vs Avg', fmt: 'signed1', signed: true }, { key: 'ppS', label: 'PP Balls %', fmt: 'pct' }, { key: 'midS', label: 'Middle Balls %', fmt: 'pct' }, { key: 'dthS', label: 'Death Balls %', fmt: 'pct' }],
  });
  bars(id('avg'), pt.map(r => r.name), [{ label: 'Average', data: pt.map(r => (r.avg == null ? null : +r.avg.toFixed(2))) }], { fmt: v => v });
  bars(id('sr'), pt.map(r => r.name), [{ label: 'Strike rate', data: pt.map(r => (r.sr == null ? null : +r.sr.toFixed(1))) }], { fmt: v => v });

  const drawPos = () => {
    const pos = +document.getElementById(id('psel')).value;
    const cc = { ...c, position: pos };
    const a = [...aggBat(cc, batRows(cc)).values()].filter(x => playerOk(c, x.key) && x.inns >= 3).map(x => ({ ...x, name: G.dims.player[x.key], team: G.dims.team[x.mainTeam] }));
    table(document.getElementById(id('plb')), {
      rows: a, sortKey: 'runs', pageSize: 10, search: true,
      columns: [{ key: 'name', label: 'Player', l: true, html: r => playerCell(G, r.key, r.team), asc: true }, { key: 'inns', label: 'Inns', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' },
        { key: 'avg', label: 'Avg', fmt: 'dec2' }, { key: 'sr', label: 'SR', fmt: 'dec2' }, { key: 'teamPct', label: 'Team Run %', fmt: 'pct' }, { key: 'srVs', label: 'SR vs Avg', fmt: 'signed1', signed: true },
        { key: 'winSr', label: 'SR in Wins', fmt: 'dec2' }],
    });
  };
  document.getElementById(id('psel')).addEventListener('change', drawPos);
  drawPos();

  const drawPei = grp => {
    const rowsP = G.pei.filter(r => r.group === grp && playerOk(c, r.p)).map(r => ({ ...r, key: r.p, name: G.dims.player[r.p] }));
    table(document.getElementById(id('pei')), {
      rows: rowsP, sortKey: 'pei', pageSize: 12, search: true,
      columns: [{ key: 'name', label: 'Player', l: true, html: r => playerCell(G, r.key), asc: true }, { key: 'innings', label: 'Inns', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' },
        { key: 'run_production', label: 'Runs/Inns', fmt: 'dec1' }, { key: 'team_contribution', label: 'Team Run %', fmt: 'pct' }, { key: 'scoring_efficiency', label: 'SR vs Avg', fmt: 'signed1', signed: true },
        { key: 'pressure_performance', label: 'Pressure (adj.)', fmt: 'signed1', signed: true, tip: 'Pressure SR above expected, shrunk toward 0 for few pressure balls.' },
        { key: 'pei', label: 'PEI', fmt: 'dec1', defKey: 'pei', html: r => `<b>${fmt(r.pei, 'dec1')}</b><span class="bar-cell" style="width:${Math.round((r.pei || 0) * 0.6)}px"></span>` }],
    });
  };
  const tabs = document.getElementById(id('pg'));
  tabs.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { tabs.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); drawPei(b.dataset.g); }));
  drawPei('top');

  donut(id('rd'), Object.keys(roleCounts), Object.values(roleCounts), { fmt: v => `${v} players` });
  bars(id('br'), BAT_ROLES.filter(r => !r.startsWith('Spin')), [{ label: 'Players', data: BAT_ROLES.filter(r => !r.startsWith('Spin')).map(r => bc[r]) }], { horizontal: true });
  bars(id('or'), BOWL_ROLES.filter(r => !r.startsWith('Spin')), [{ label: 'Players', data: BOWL_ROLES.filter(r => !r.startsWith('Spin')).map(r => oc[r]) }], { horizontal: true });

  let curRole = null;
  const drawRoles = () => {
    const list = elig.filter(p => !curRole || p.batRoles.includes(curRole) || p.bowlRoles.includes(curRole)).map(p => ({ key: p.i, name: p.name, role: p.role, roles: [...p.batRoles, ...p.bowlRoles].join(', '), matches: p.matches, runs: p.runs, wickets: p.wickets, imp: p.overall_impact }));
    table(document.getElementById(id('rt')), {
      rows: list, sortKey: 'imp', pageSize: 12, search: true,
      columns: [{ key: 'name', label: 'Player', l: true, html: r => playerCell(G, r.key), asc: true }, { key: 'role', label: 'Primary', l: true, html: r => esc(r.role || '–') },
        { key: 'roles', label: 'Role tendencies', l: true, html: r => (r.roles ? r.roles.split(', ').map(x => `<span class="pill role">${esc(x)}</span>`).join(' ') : '<span class="muted">No distinct tendency</span>') },
        { key: 'matches', label: 'M', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' }, { key: 'wickets', label: 'Wkts', fmt: 'int' }, { key: 'imp', label: 'Overall Impact', fmt: 'dec1', defKey: 'overall_impact' }],
    });
  };
  const chips = document.getElementById(id('rchips'));
  chips.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
    curRole = curRole === b.dataset.r ? null : b.dataset.r;
    chips.querySelectorAll('button').forEach(x => x.classList.toggle('primary', x.dataset.r === curRole));
    drawRoles();
  }));
  drawRoles();
}
