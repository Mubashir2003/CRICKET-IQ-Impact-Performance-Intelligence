import { batRows, bowlRows, aggBat, aggBowl } from '../js/data.js';
import { card, chartBox, fmt, esc, empty, avatar, flag, def, expPill, playerPicker } from '../js/ui.js';
import { radar, bars } from '../js/charts.js';

const MAX = 4;

export async function render(root, env) {
  let c = env.ctxs.find(x => x.G.g === env.params.g) || env.ctxs[0];
  const G = c.G;
  let names = (env.params.p ? env.params.p.split('|') : []).filter(n => G.playerIdx.has(n) && G.playerIdx.get(n) < G.nElig).slice(0, MAX);
  if (!names.length) names = [...G.P.values()].filter(p => p.overall_impact != null).sort((a, b) => b.overall_impact - a.overall_impact).slice(0, 2).map(p => p.name);
  const go = list => env.nav(`#/compare?g=${G.g}&p=${encodeURIComponent(list.join('|'))}`);
  const genderTabs = env.ctxs.length > 1 ? `<div class="tabs">${env.ctxs.map(x => `<button data-g="${x.G.g}" class="${x.G.g === G.g ? 'on' : ''}">${esc(x.G.label)}</button>`).join('')}</div>` : '';
  root.innerHTML = `<div class="note">⚔️ Comparisons are always within one gender — ${esc(G.label.toLowerCase())}'s players are compared only with each other.</div>
    <div class="toolbar">${genderTabs}<div id="pk" style="flex:1;max-width:460px"></div>${names.map(n => `<span class="chip">${avatar(n)} ${esc(n)}<button data-rm="${esc(n)}" aria-label="Remove">✕</button></span>`).join('')}</div><div id="cmp" class="grid"></div>`;
  root.querySelectorAll('[data-g]').forEach(b => b.addEventListener('click', () => env.nav(`#/compare?g=${b.dataset.g}`)));
  root.querySelectorAll('[data-rm]').forEach(b => b.addEventListener('click', () => go(names.filter(n => n !== b.dataset.rm))));
  playerPicker(root.querySelector('#pk'), G, { placeholder: names.length >= MAX ? `Maximum ${MAX} players — remove one to add another` : 'Add a player to compare…', exclude: names, onPick: n => { if (names.length < MAX) go([...names, n]); } });
  const el = root.querySelector('#cmp');
  if (names.length < 1) { el.innerHTML = empty('Add players to compare.'); return; }
  draw(el, c, names.map(n => G.playerIdx.get(n)));
}

function draw(el, c, ps) {
  const G = c.G, B = G.bat, O = G.bowl;
  const c0 = { ...c, phase: '' };
  const brAll = batRows(c0), orAll = bowlRows(c0);
  const set = new Set(ps);
  const br = brAll.filter(r => set.has(B.p[r])), or = orAll.filter(r => set.has(O.p[r]));
  const ba = aggBat(c0, br), oa = aggBowl(c0, or);
  const Ps = ps.map(p => G.P.get(p));
  const id = s => `cmp-${s}`;

  const rowsDef = [
    ['Batting (current filters)', null],
    ['Matches', p => G.P.get(p).matches, 'int', true], ['Innings', p => ba.get(p)?.inns, 'int', true], ['Runs', p => ba.get(p)?.runs, 'int', true],
    ['Average', p => ba.get(p)?.avg, 'dec2', true], ['Strike rate', p => ba.get(p)?.sr, 'dec2', true], ['Highest', p => ba.get(p)?.hs, 'str', true, p => ba.get(p)?.hsText],
    ['50s / 100s', p => (ba.get(p)?.f50 || 0) + (ba.get(p)?.f100 || 0) * 2, 'str', true, p => (ba.get(p) ? `${ba.get(p).f50} / ${ba.get(p).f100}` : '–')],
    ['Boundary %', p => ba.get(p)?.bndPct, 'pct', true], ['Dot %', p => ba.get(p)?.dotPct, 'pct', false], ['SR vs expected', p => ba.get(p)?.srVs, 'signed1', true],
    ['Team run %', p => ba.get(p)?.teamPct, 'pct', true],
    ['Bowling (current filters)', null],
    ['Wickets', p => oa.get(p)?.wkts, 'int', true], ['Economy', p => oa.get(p)?.econ, 'dec2', false], ['Average', p => oa.get(p)?.avg, 'dec2', false],
    ['Strike rate', p => oa.get(p)?.sr, 'dec1', false], ['Dot %', p => oa.get(p)?.dotPct, 'pct', true], ['Runs saved', p => oa.get(p)?.saved, 'signed1', true],
    ['Advanced (season)', null],
    ...['consistency_index', 'impact_innings_pct', 'powerplay_aggression_index', 'middle_over_control_index', 'death_finishing_index', 'pressure_sr_delta', 'chase_contribution_pct',
      'runs_saved_per_24', 'economy_advantage', 'boundary_suppression_index', 'pressure_bowling_index', 'death_over_effectiveness', 'bowling_consistency'].map(k => [def(k).label, p => G.P.get(p)[k], def(k).fmt, def(k).hib !== false, null, k]),
    ['Winning (season)', null],
    ...['win_rate', 'winning_run_share_pct', 'winning_wicket_share_pct', 'wins_significant', 'wins_exceptional', 'match_winning_pct'].map(k => [def(k).label, p => G.P.get(p)[k], def(k).fmt, true, null, k]),
    ['Impact indices (experimental)', null],
    ...['batting_impact', 'bowling_impact', 'pressure_impact', 'winning_contribution', 'overall_impact'].map(k => [def(k).label, p => G.P.get(p)[k], 'dec1', true, null, k]),
  ];
  const head = `<tr><th class="l">Metric</th>${Ps.map(P => `<th class="l"><div class="pcell">${avatar(P.name)}<div><a class="pname" href="#/player?g=${G.g}&p=${encodeURIComponent(P.name)}">${esc(P.name)}</a> ${flag(G, P.country)}<div class="pmeta">${esc(P.role || '')}</div></div></div></th>`).join('')}</tr>`;
  const body = rowsDef.map(([label, fn, f, hib, txt, k]) => {
    if (!fn) return `<tr><td class="l" colspan="${ps.length + 1}" style="background:var(--accent-soft);font-weight:800">${esc(label)}</td></tr>`;
    const vals = ps.map(fn);
    const nums = vals.filter(x => typeof x === 'number' && isFinite(x));
    const best = ps.length > 1 && nums.length > 1 ? (hib ? Math.max(...nums) : Math.min(...nums)) : null;
    return `<tr><td class="l"${k ? ` data-tip="${esc(def(k).desc)}"` : ''}>${esc(label)}</td>${vals.map((x, i) => `<td class="l" style="${best !== null && x === best ? 'color:var(--good);font-weight:800' : ''}">${txt ? esc(txt(ps[i]) ?? '–') : fmt(x, f)}${best !== null && x === best ? ' ▲' : ''}</td>`).join('')}</tr>`;
  }).join('');
  el.innerHTML = `
    ${card('Head to head', `<div class="table-wrap" style="max-height:none"><table class="dt"><thead>${head}</thead><tbody>${body}</tbody></table></div>`, { sub: '▲ marks the better value in each row. Hover advanced metric names for definitions.', right: expPill })}
    <div class="grid g2">
      ${card('Impact radar', chartBox(id('radar')), { sub: 'Season percentiles; missing = not applicable' })}
      ${card('Winning contribution', chartBox(id('win')), { sub: 'Season-level shares' })}
    </div>
    <div class="grid g2">
      ${card('Strike rate by phase', chartBox(id('phb')))}
      ${card('Economy by phase', chartBox(id('pho')))}
    </div>
    ${card('Runs by batting position group', chartBox(id('pos')), { sub: 'Current filters' })}`;
  const lab = Ps.map(P => P.name);
  radar(id('radar'), ['Batting', 'Bowling', 'Pressure', 'Winning'], Ps.map(P => ({ label: P.name, data: ['batting_impact', 'bowling_impact', 'pressure_impact', 'winning_contribution'].map(k => P[k] ?? null) })));
  bars(id('win'), ['Win %', 'Win run share %', 'Win wkt share %', 'Match-winning freq %'], Ps.map(P => ({ label: P.name, data: ['win_rate', 'winning_run_share_pct', 'winning_wicket_share_pct', 'match_winning_pct'].map(k => (P[k] == null ? null : +P[k].toFixed(1))) })), { fmt: v => (v == null ? 'n/a' : v + '%') });
  const phs = ['pp', 'mid', 'dth'];
  const pb = phs.map(ph => aggBat({ ...c, phase: ph }, br)), po = phs.map(ph => aggBowl({ ...c, phase: ph }, or));
  bars(id('phb'), ['Powerplay', 'Middle', 'Death'], ps.map((p, i) => ({ label: lab[i], data: pb.map(m => { const a = m.get(p); return a && a.balls >= 6 ? +a.sr.toFixed(1) : null; }) })), { fmt: v => (v == null ? 'n/a' : v) });
  if (!or.length) document.getElementById(id('pho')).parentElement.innerHTML = empty('None of these players bowled in this selection.', '🎳');
  else bars(id('pho'), ['Powerplay', 'Middle', 'Death'], ps.map((p, i) => ({ label: lab[i], data: po.map(m => { const a = m.get(p); return a && a.balls >= 6 ? +a.econ.toFixed(2) : null; }) })), { fmt: v => (v == null ? 'n/a' : v + ' rpo') });
  const grp = r => (B.pos[r] <= 3 ? 0 : B.pos[r] <= 7 ? 1 : 2);
  bars(id('pos'), ['Top order (1-3)', 'Middle order (4-7)', 'Lower order (8-11)'], ps.map((p, i) => {
    const d = [0, 0, 0]; br.filter(r => B.p[r] === p).forEach(r => { d[grp(r)] += B.r[r]; }); return { label: lab[i], data: d };
  }), { fmt: v => v + ' runs' });
}
