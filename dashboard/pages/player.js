import { batRows, bowlRows, aggBat, aggBowl, PHASE_LABEL, store } from '../js/data.js';
import { card, chartBox, fmt, esc, empty, table, avatar, flag, teamBadge, def, expPill, playerPicker } from '../js/ui.js';
import { lines, bars, radar } from '../js/charts.js';

const IMPACT = [['batting_impact', 'Batting'], ['bowling_impact', 'Bowling'], ['pressure_impact', 'Pressure'], ['winning_contribution', 'Winning'], ['overall_impact', 'Overall']];

export async function render(root, env) {
  let c = env.ctxs[0];
  if (env.ctxs.length > 1) c = env.ctxs.find(x => x.G.g === env.params.g) || env.ctxs[0];
  else if (env.params.g && env.params.g !== c.G.g) {
    root.innerHTML = `<div class="note warn">This player belongs to the ${esc(env.params.g === 'men' ? "men's" : "women's")} data. <button class="btn sm" id="sw">Switch gender</button></div>`;
    root.querySelector('#sw').addEventListener('click', () => env.setF({ gender: env.params.g }));
    return;
  }
  const G = c.G;
  let name = env.params.p || (c.F.player && G.playerIdx.has(c.F.player) ? c.F.player : null);
  if (!name || !G.playerIdx.has(name) || G.playerIdx.get(name) >= G.nElig) {
    const best = [...G.P.values()].filter(p => p.overall_impact != null).sort((a, b) => b.overall_impact - a.overall_impact)[0];
    if (env.params.p && !G.playerIdx.has(env.params.p)) root.innerHTML = '<div class="note warn">That player is not among the eligible players (11+ matches) for this selection.</div>';
    name = best?.name;
  }
  const p = G.playerIdx.get(name);
  const P = G.P.get(p);
  const genderTabs = env.ctxs.length > 1 ? `<div class="tabs">${env.ctxs.map(x => `<button data-g="${x.G.g}" class="${x.G.g === G.g ? 'on' : ''}">${esc(x.G.label)}</button>`).join('')}</div>` : '';
  root.insertAdjacentHTML('beforeend', `<div class="toolbar">${genderTabs}<div id="pk" style="flex:1;max-width:520px"></div></div><div id="prof" class="grid"></div>`);
  root.querySelectorAll('[data-g]').forEach(b => b.addEventListener('click', () => env.nav(`#/player?g=${b.dataset.g}`)));
  playerPicker(root.querySelector('#pk'), G, { placeholder: `Search ${G.label.toLowerCase()}'s players by name, country or team…`, onPick: n => env.nav(`#/player?g=${G.g}&p=${encodeURIComponent(n)}`) });
  if (!P) { root.querySelector('#prof').innerHTML = empty('Player not found.'); return; }
  draw(root.querySelector('#prof'), c, p, P, env);
}

function statGrid(items) {
  return `<div class="stat-grid">${items.map(([l, v, tip]) => `<div class="stat"${tip ? ` data-tip="${esc(tip)}"` : ''}><div class="s-l">${esc(l)}</div><div class="s-v">${v}</div></div>`).join('')}</div>`;
}

function draw(el, c, p, P, env) {
  const G = c.G, B = G.bat, O = G.bowl, M = G.M;
  const c0 = { ...c, phase: '' };
  const br = batRows(c0).filter(r => B.p[r] === p);
  const or = bowlRows(c0).filter(r => O.p[r] === p);
  const ba = aggBat(c0, br).get(p);
  const oa = aggBowl(c0, or).get(p);
    const id = s => `pf-${s}`;
  const roles = [...P.batRoles, ...P.bowlRoles];
  const countryTxt = P.countries.length ? P.countries.map(x => `${flag(G, x, 'lg')} ${esc(x)}`).join(' ') : '<span class="muted">No T20I appearances in 2026</span>';
  const v = (k, f) => fmt(P[k], f || def(k).fmt);  // advanced metrics: season level
  el.innerHTML = `
    <section class="profile-head glass">${avatar(P.name, 'lg')}
      <div style="flex:1;min-width:260px"><h2>${esc(P.name)}</h2>
        <div class="profile-meta">${countryTxt} <span class="pill">${esc(P.role || 'Role n/a')}</span>${roles.map(r => `<span class="pill role">${esc(r)}</span>`).join('')}</div>
        <div class="profile-meta">${P.teams.slice(0, 8).map(t => `<span class="pill role">${teamBadge(G, t)} ${esc(t)}</span>`).join('')}</div>
        <div class="profile-meta muted">🏆 ${P.comps.map(esc).join(' · ')}</div>
      </div>
      <div class="stat-grid" style="min-width:300px;flex:0 0 auto">
        <div class="stat"><div class="s-l">Matches</div><div class="s-v">${fmt(P.matches, 'int')}</div></div>
        <div class="stat"><div class="s-l">Win %</div><div class="s-v">${v('win_rate')}</div></div>
        <div class="stat"><div class="s-l">Impact</div><div class="s-v">${fmt(P.overall_impact, 'dec1')}</div></div>
        <div class="stat"><div class="s-l">Season</div><div class="s-v" style="font-size:14px">${esc(P.first || '')}<br>→ ${esc(P.last || '')}</div></div>
      </div>
    </section>
    ${c.matchFiltersActive ? '<div class="note">Batting, bowling, trend, phase, position and recent-match panels reflect the current filters. Impact, advanced and winning metrics are season-level (all 2026 matches).</div>' : ''}
    <div class="grid g2">
      ${card('🏏 Batting', ba ? statGrid([['Innings', fmt(ba.inns, 'int')], ['Runs', fmt(ba.runs, 'int')], ['Average', fmt(ba.avg, 'dec2')], ['Strike rate', fmt(ba.sr, 'dec2')], ['Highest', ba.hsText],
        ['Not outs', fmt(ba.notOuts, 'int')], ['30s / 50s / 100s', `${ba.f30} / ${ba.f50} / ${ba.f100}`], ['4s / 6s', `${ba.f4} / ${ba.f6}`], ['Boundary %', fmt(ba.bndPct, 'pct')], ['Dot %', fmt(ba.dotPct, 'pct')],
        ['SR vs expected', `<span class="${ba.srVs > 0 ? 'pos' : 'neg'}">${fmt(ba.srVs, 'signed1')}</span>`, def('sr_above_avg').desc], ['Team run %', fmt(ba.teamPct, 'pct'), def('team_run_contribution_pct').desc]]) : empty('No batting in this selection.'))}
      ${card('🎳 Bowling', oa ? statGrid([['Innings', fmt(oa.inns, 'int')], ['Overs', oa.overs], ['Wickets', fmt(oa.wkts, 'int')], ['Economy', fmt(oa.econ, 'dec2')], ['Average', fmt(oa.avg, 'dec2')],
        ['Strike rate', fmt(oa.sr, 'dec1')], ['Best', oa.bestText], ['Dot %', fmt(oa.dotPct, 'pct')], ['Maidens', fmt(oa.md, 'int')], ['4W / 5W', `${oa.w4} / ${oa.w5}`],
        ['Runs saved', `<span class="${oa.saved > 0 ? 'pos' : 'neg'}">${fmt(oa.saved, 'signed1')}</span>`, def('runs_saved').desc], ['Wkt contribution', fmt(oa.wktPct, 'pct'), def('wicket_contribution_pct').desc]]) : empty('Did not bowl in this selection.', '🎳'))}
    </div>
    <div class="grid g2">
      ${card('Impact profile', `<div class="impact-bars">${IMPACT.map(([k, l]) => {
        const val = P[k];
        return `<div class="ib-row" data-tip="${esc(def(k).desc)}"><span>${l}</span><div class="ib-track"><div class="ib-fill" style="width:${val == null ? 0 : val}%"></div></div><b>${val == null ? '<span class="muted" title="Not applicable or insufficient sample">n/a</span>' : fmt(val, 'dec1')}</b></div>`;
      }).join('')}</div><div class="sub" style="margin-top:10px">Percentiles within ${esc(G.label.toLowerCase())}'s eligible players, season-level. “n/a” = not applicable (e.g. does not bowl) or too small a sample — never scored as zero. Fielding impact is unavailable (no fielder data).</div>`, { right: expPill })}
      ${card('Impact radar', chartBox(id('radar')), { sub: 'Component percentiles (0-100)' })}
    </div>
    ${card('Advanced metrics', statGrid(['team_run_contribution_pct', 'boundary_dependency_pct', 'non_boundary_pct', 'consistency_index', 'impact_innings_pct', 'powerplay_aggression_index', 'middle_over_control_index',
      'death_finishing_index', 'pressure_sr_delta', 'chase_contribution_pct', 'chase_success_contribution_pct', 'wicket_contribution_pct', 'dot_ball_share_pct', 'runs_saved_per_24', 'economy_advantage',
      'boundary_suppression_index', 'pressure_bowling_index', 'death_over_effectiveness', 'bowling_consistency'].map(k => [def(k).label, v(k), def(k).desc])), { sub: 'Season-level (all 2026 matches). Hover a tile for its definition.' })}
    <div class="grid g2">
      ${card('Batting trend', br.length ? chartBox(id('bt')) : empty('No innings.'), { sub: 'Runs per innings (chronological) with a 5-innings rolling average' })}
      ${card('Bowling trend', or.length ? chartBox(id('ot')) : empty('No bowling.', '🎳'), { sub: 'Wickets and runs conceded per match' })}
    </div>
    <div class="grid g2">
      ${card('Phase analysis — batting', chartBox(id('pb')), { sub: 'Strike rate by phase vs the expected strike rate for the same balls' })}
      ${card('Phase analysis — bowling', chartBox(id('po')), { sub: 'Economy by phase vs expected economy for the same balls' })}
    </div>
    <div class="grid g2">
      ${card('Position analysis', `<div id="${id('pos')}"></div>`)}
      ${card('Winning contribution (season)', statGrid([['Wins', v('wins', 'int')], ['Win rate', v('win_rate')], ['Runs in wins', v('runs_in_victories', 'int')], ['Wickets in wins', v('wickets_in_victories', 'int')],
        ['Win run share', v('winning_run_share_pct'), def('winning_run_share_pct').desc], ['Win wicket share', v('winning_wicket_share_pct'), def('winning_wicket_share_pct').desc],
        ['Significant wins', v('wins_significant', 'int'), def('wins_significant').desc], ['Match-winning', v('wins_exceptional', 'int'), def('wins_exceptional').desc],
        ['MW innings', v('match_winning_innings', 'int'), def('match_winning_innings').desc], ['MW spells', v('match_winning_bowling', 'int'), def('match_winning_bowling').desc],
        ['Avg in wins', v('bat_avg_in_wins')], ['Econ in wins', v('economy_in_wins')]]))}
    </div>
    ${card('Recent performances', `<div id="${id('recent')}"></div>`, { sub: 'Most recent matches first (current filters)' })}`;

  const imp = IMPACT.slice(0, 4);
  radar(id('radar'), imp.map(x => x[1]), [{ label: P.name, data: imp.map(([k]) => P[k] ?? null) }]);

  if (br.length) {
    const seq = [...br].sort((a, b) => (M.date[B.m[a]] < M.date[B.m[b]] ? -1 : 1));
    const rs = seq.map(r => B.r[r]);
    const roll = rs.map((_, i) => { const w = rs.slice(Math.max(0, i - 4), i + 1); return +(w.reduce((s, x) => s + x, 0) / w.length).toFixed(1); });
    lines(id('bt'), seq.map(r => M.date[B.m[r]].slice(5)), [{ label: 'Runs', data: rs }, { label: '5-innings average', data: roll }], { beginAtZero: true });
  }
  if (or.length) {
    const byM = new Map();
    or.forEach(r => { const k = O.m[r]; const o = byM.get(k) || { w: 0, r: 0 }; o.w += O.w[r]; o.r += O.r[r]; byM.set(k, o); });
    const ks = [...byM.keys()].sort((a, b) => (M.date[a] < M.date[b] ? -1 : 1));
    bars(id('ot'), ks.map(k => M.date[k].slice(5)), [{ label: 'Wickets', data: ks.map(k => byM.get(k).w) }], { fmt: x => `${x} wkts` });
  }
  const phB = ['pp', 'mid', 'dth'].map(ph => aggBat({ ...c, phase: ph }, br).get(p));
  bars(id('pb'), ['Powerplay', 'Middle', 'Death'], [
    { label: 'Strike rate', data: phB.map(a => (a && a.balls >= 6 ? +a.sr.toFixed(1) : null)) },
    { label: 'Expected SR', data: phB.map(a => (a && a.balls >= 6 ? +(a.er / a.balls * 100).toFixed(1) : null)) },
  ], { fmt: x => (x == null ? 'n/a' : x) });
  const phO = ['pp', 'mid', 'dth'].map(ph => aggBowl({ ...c, phase: ph }, or).get(p));
  if (or.length) bars(id('po'), ['Powerplay', 'Middle', 'Death'], [
    { label: 'Economy', data: phO.map(a => (a && a.balls >= 6 ? +a.econ.toFixed(2) : null)) },
    { label: 'Expected economy', data: phO.map(a => (a && a.balls >= 6 ? +a.expEcon.toFixed(2) : null)) },
  ], { fmt: x => (x == null ? 'n/a' : x + ' rpo') });
  else document.getElementById(id('po')).parentElement.innerHTML = empty('Did not bowl.', '🎳');

  const pos = aggBat(c0, br, r => B.pos[r]);
  table(document.getElementById(id('pos')), {
    rows: [...pos.values()].map(a => ({ ...a, name: `No. ${a.key}` })), sortKey: 'inns', rank: false, pageSize: 11,
    columns: [{ key: 'key', label: 'Position', l: true, html: r => `<b>No. ${r.key}</b>`, asc: true }, { key: 'inns', label: 'Inns', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' },
      { key: 'avg', label: 'Avg', fmt: 'dec2' }, { key: 'sr', label: 'SR', fmt: 'dec2' }, { key: 'teamPct', label: 'Team Run %', fmt: 'pct' }, { key: 'srVs', label: 'SR vs Avg', fmt: 'signed1', signed: true }],
  });

  const mids = [...new Set([...br.map(r => B.m[r]), ...or.map(r => O.m[r])])].sort((a, b) => (M.date[a] < M.date[b] ? 1 : -1)).slice(0, 15);
  const rec = mids.map(m => {
    const b = br.filter(r => B.m[r] === m), o = or.filter(r => O.m[r] === m);
    const t = b.length ? B.t[b[0]] : O.t[o[0]], opp = b.length ? B.o[b[0]] : O.o[o[0]], res = b.length ? B.res[b[0]] : O.res[o[0]];
    return { m, date: M.date[m], comp: G.dims.comp[M.comp[m]], team: G.dims.team[t], opp: G.dims.team[opp], res,
      bat: b.length ? `${b.reduce((s, r) => s + B.r[r], 0)}${b.some(r => B.out[r]) ? '' : '*'} (${b.reduce((s, r) => s + B.b[r], 0)})` : '–', runs: b.reduce((s, r) => s + B.r[r], 0),
      bowl: o.length ? `${o.reduce((s, r) => s + O.w[r], 0)}/${o.reduce((s, r) => s + O.r[r], 0)} (${(x => `${Math.floor(x / 6)}.${x % 6}`)(o.reduce((s, r) => s + O.bl[r], 0))})` : '–' };
  });
  table(document.getElementById(id('recent')), {
    rows: rec, sortKey: 'date', rank: false, pageSize: 15, onRow: r => env.nav(`#/match?g=${G.g}&id=${encodeURIComponent(M.id[r.m])}`),
    columns: [{ key: 'date', label: 'Date', l: true, html: r => esc(r.date) }, { key: 'comp', label: 'Competition', l: true, html: r => esc(r.comp) },
      { key: 'opp', label: 'Match', l: true, html: r => `${esc(r.team)} v ${esc(r.opp)}` }, { key: 'runs', label: 'Batting', html: r => r.bat }, { key: 'bowl', label: 'Bowling', html: r => r.bowl, sort: false },
      { key: 'res', label: 'Result', html: r => ({ W: '<span class="pos">Won</span>', L: '<span class="neg">Lost</span>', T: 'Tied', N: 'No result' }[r.res]) }],
  });
  void PHASE_LABEL; void store;
}
