import { matchRows, loadMatch } from '../js/data.js';
import { card, chartBox, fmt, esc, empty, table, teamBadge, playerLink, eachGender } from '../js/ui.js';
import { lines, bars } from '../js/charts.js';

export async function render(root, env) {
  if (env.params.id) {
    const c = env.ctxs.find(x => x.G.g === env.params.g) || env.ctxs[0];
    if (c.G.g !== env.params.g && env.params.g) {
      root.innerHTML = `<div class="note warn">This match is in the ${env.params.g === 'men' ? "men's" : "women's"} data. <button class="btn sm" id="sw">Switch gender</button></div>`;
      root.querySelector('#sw').addEventListener('click', () => env.setF({ gender: env.params.g }));
      return;
    }
    let m;
    try { m = await loadMatch(c.G.g, env.params.id); } catch (e) { root.innerHTML = empty('This match scorecard is unavailable.'); return; }
    detail(root, c, m, env);
    return;
  }
  root.innerHTML = '<div id="mwrap" class="grid"></div>';
  eachGender(root.querySelector('#mwrap'), env.ctxs, (c, el) => list(c, el, env));
}

function list(c, el, env) {
  const G = c.G, M = G.M;
  const rows = matchRows(c).map(i => ({
    i, date: M.date[i], comp: G.dims.comp[M.comp[i]], t1: G.dims.team[M.t1[i]], t2: G.dims.team[M.t2[i]], bat1: G.dims.team[M.bat1[i]],
    s1: M.r1[i] != null ? `${M.r1[i]}/${M.w1[i]}` : '–', s2: M.r2[i] != null ? `${M.r2[i]}/${M.w2[i]}` : '–',
    res: M.result[i] === 'W' ? `${G.dims.team[M.winner[i]]} won${M.mr[i] != null ? ` by ${M.mr[i]} runs` : M.mw[i] != null ? ` by ${M.mw[i]} wkts` : ''}` : M.result[i] === 'T' ? (M.winner[i] >= 0 ? `Tied — ${G.dims.team[M.winner[i]]} won super over` : 'Tied') : 'No result',
    close: M.close[i], name: `${G.dims.team[M.t1[i]]} ${G.dims.team[M.t2[i]]} ${G.dims.venue[M.venue[i]]}`, venue: G.dims.venue[M.venue[i]],
  }));
  if (!rows.length) { el.innerHTML = empty('No matches for these filters.'); return; }
  el.innerHTML = card('Matches', '<div id="ml"></div>', { sub: 'Click a match for the full scorecard, progression and match-winning contributions. Search by team or venue.' });
  table(el.querySelector('#ml'), {
    rows, sortKey: 'date', search: true, searchKey: 'name', pageSize: 20, onRow: r => env.nav(`#/match?g=${G.g}&id=${encodeURIComponent(M.id[r.i])}`),
    columns: [
      { key: 'date', label: 'Date', l: true, html: r => esc(r.date) }, { key: 'comp', label: 'Competition', l: true, html: r => esc(r.comp) },
      { key: 'name', label: 'Match', l: true, html: r => `${teamBadge(G, r.bat1)} <b>${esc(r.bat1)}</b> ${r.s1} &nbsp;v&nbsp; <b>${esc(r.bat1 === r.t1 ? r.t2 : r.t1)}</b> ${r.s2}<div class="pmeta muted">${esc(r.venue)}</div>` },
      { key: 'res', label: 'Result', l: true, html: r => `${esc(r.res)}${r.close ? ' <span class="pill">🔥 close</span>' : ''}` },
    ],
  });
}

function detail(root, c, m, env) {
  const G = c.G;
  const inn = m.innings;
  const pl = n => `<a class="pname" href="${playerLink(G, n)}">${esc(n)}</a>`;
  const score = i => (i ? `${i.runs}/${i.wkts}` : '–');
  root.innerHTML = `
    <div class="toolbar"><button class="btn" id="back">‹ All matches</button></div>
    <section class="glass card">
      <div class="muted" style="text-align:center">${esc(m.comp)}${m.series !== m.comp ? ' · ' + esc(m.series) : ''} · ${esc(m.venue || '')}${m.city ? ', ' + esc(m.city) : ''} · ${esc(m.date)}</div>
      <div class="score-head">
        <div><div class="score-team">${teamBadge(G, inn[0]?.team)} ${esc(inn[0]?.team || m.teams[0])}</div><div class="score-runs">${score(inn[0])}</div><div class="muted">${inn[0] ? inn[0].overs + ' overs' : ''}</div></div>
        <div class="muted" style="font-size:22px;font-weight:800">v</div>
        <div><div class="score-team">${teamBadge(G, inn[1]?.team)} ${esc(inn[1]?.team || m.teams[1])}</div><div class="score-runs">${score(inn[1])}</div><div class="muted">${inn[1] ? inn[1].overs + ' overs' : ''}</div></div>
      </div>
      <div class="result-banner">🏆 ${esc(m.result)} ${m.close ? '<span class="pill">🔥 close finish</span>' : ''}</div>
      ${m.super_over.length ? `<div class="muted" style="text-align:center;margin-top:6px">Super over: ${m.super_over.map(s => `${esc(s.team)} ${s.runs}/${s.wkts}`).join(' · ')}</div>` : ''}
    </section>
    ${inn.length ? `<div class="grid g2">${card('Run progression (worm)', chartBox('worm'), { sub: 'Cumulative runs after each over' })}${card('Runs per over (Manhattan)', chartBox('manh'), { sub: 'Runs scored in each over' })}</div>` : empty('Ball-by-ball data is not available for this match.')}
    ${card('Match-winning contributions', '<div id="contrib"></div>', { sub: 'Match score = runs above expected + runs saved + 10 × wickets above expected (experimental). ⭐ = match-winning, ✔ = significant contribution.' })}
    ${card('Phase breakdown', '<div id="phases"></div>')}
    <div class="tabs" id="innTabs">${inn.map((x, k) => `<button data-k="${k}" class="${k === 0 ? 'on' : ''}">${esc(x.team)} innings</button>`).join('')}</div>
    <div id="innBody" class="grid"></div>`;
  root.querySelector('#back').addEventListener('click', () => env.nav('#/match'));

  if (inn.length) {
    const maxO = Math.max(...inn.map(x => Math.max(0, ...x.overs_prog.o)));
    const labels = Array.from({ length: maxO }, (_, i) => String(i + 1));
    lines('worm', labels, inn.map(x => {
      let s = 0; const mp = new Map(x.overs_prog.o.map((o, k) => [o, k]));
      return { label: x.team, data: labels.map((_, i) => { const k = mp.get(i + 1); if (k === undefined) return null; s += x.overs_prog.r[k]; return s; }), stepped: false };
    }), { beginAtZero: true, fmt: v => v + ' runs' });
    bars('manh', labels, inn.map(x => { const mp = new Map(x.overs_prog.o.map((o, k) => [o, k])); return { label: x.team, data: labels.map((_, i) => { const k = mp.get(i + 1); return k === undefined ? null : x.overs_prog.r[k]; }) }; }), { fmt: v => v + ' runs' });
  }
  table(root.querySelector('#contrib'), {
    rows: m.contributions.map(x => ({ ...x, name: x.p })), sortKey: 'score', pageSize: 8,
    columns: [{ key: 'name', label: 'Player', l: true, html: r => `${pl(r.p)} ${r.exceptional ? '⭐' : r.significant ? '✔' : ''}<div class="pmeta muted">${esc(r.team)}</div>` },
      { key: 'runs', label: 'Batting', html: r => (r.runs != null ? `${fmt(r.runs, 'int')} (${fmt(r.balls, 'int')})` : '–') },
      { key: 'wkts', label: 'Bowling', html: r => (r.wkts != null ? `${r.wkts}/${r.conceded}` : '–') },
      { key: 'bat', label: 'Bat value', fmt: 'signed1', signed: true }, { key: 'bowl', label: 'Bowl value', fmt: 'signed1', signed: true }, { key: 'score', label: 'Match score', fmt: 'dec1' },
      { key: 'tag', label: 'Highlights', l: true, sort: false, html: r => [r.mwi ? 'Match-winning innings' : '', r.mwb ? 'Match-winning spell' : ''].filter(Boolean).map(t => `<span class="pill">${t}</span>`).join(' ') }],
  });
  const ph = [['powerplay', 'Powerplay'], ['middle', 'Middle'], ['death', 'Death']];
  root.querySelector('#phases').innerHTML = `<div class="table-wrap"><table class="dt"><thead><tr><th class="l">Innings</th>${ph.map(([, l]) => `<th>${l}</th>`).join('')}</tr></thead><tbody>${inn.map(x => `<tr><td class="l"><b>${esc(x.team)}</b></td>${ph.map(([k]) => { const p = x.phases[k]; return `<td>${p ? `${p.r}/${p.w} <span class="muted">(${Math.floor(p.b / 6)}.${p.b % 6} ov, RR ${p.b ? (p.r / p.b * 6).toFixed(2) : '–'})</span>` : '–'}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>`;

  const drawInn = k => {
    const x = inn[k];
    const body = root.querySelector('#innBody');
    body.innerHTML = `
      ${card(`🏏 ${esc(x.team)} — ${x.runs}/${x.wkts} (${x.overs} ov)`, `<div class="table-wrap" style="max-height:none"><table class="dt"><thead><tr><th class="l">Batter</th><th class="l">Dismissal</th><th>R</th><th>B</th><th>4s</th><th>6s</th><th>SR</th></tr></thead><tbody>
        ${x.batting.map(b => `<tr><td class="l">${b.pos}. ${pl(b.p)}</td><td class="l muted">${esc(b.how)}</td><td><b>${b.r}${b.out ? '' : '*'}</b></td><td>${b.b}</td><td>${b.f4}</td><td>${b.f6}</td><td>${fmt(b.sr, 'dec1')}</td></tr>`).join('')}
        <tr><td class="l" colspan="2">Extras <span class="muted">(wd ${x.extras.wides}, nb ${x.extras.no_balls}, b/lb/pen ${x.extras.other})</span></td><td><b>${x.extras.total}</b></td><td colspan="4"></td></tr>
        <tr><td class="l" colspan="2"><b>Total</b></td><td><b>${x.runs}/${x.wkts}</b></td><td colspan="4" class="l muted">${x.overs} overs · RR ${x.balls ? (x.runs / x.balls * 6).toFixed(2) : '–'}</td></tr></tbody></table></div>
        <div class="sub" style="margin-top:8px">Fielder names are not included in the source data ("c ?" = caught).</div>`)}
      ${card(`🎳 ${esc(x.opp)} bowling`, `<div class="table-wrap" style="max-height:none"><table class="dt"><thead><tr><th class="l">Bowler</th><th>O</th><th>M</th><th>R</th><th>W</th><th>Econ</th><th>Dots</th><th>Wd</th><th>NB</th></tr></thead><tbody>
        ${x.bowling.map(b => `<tr><td class="l">${pl(b.p)}</td><td>${b.o}</td><td>${b.m}</td><td>${b.r}</td><td><b>${b.w}</b></td><td>${fmt(b.econ, 'dec2')}</td><td>${b.d}</td><td>${b.wd}</td><td>${b.nb}</td></tr>`).join('')}</tbody></table></div>`)}
      <div class="grid g2">
        ${card('Fall of wickets', x.fow.length ? `<div class="table-wrap"><table class="dt"><thead><tr><th class="l">Wkt</th><th>Score</th><th>Over</th><th class="l">Batter</th></tr></thead><tbody>${x.fow.map(f => `<tr><td class="l">${f.w}</td><td>${f.score}</td><td>${f.over}</td><td class="l">${pl(f.p)}</td></tr>`).join('')}</tbody></table></div>` : empty('No wickets fell.'))}
        ${card('Partnerships', `<div class="table-wrap"><table class="dt"><thead><tr><th class="l">Wkt</th><th class="l">Pair</th><th>Runs</th><th>Balls</th><th class="l">Split</th></tr></thead><tbody>${x.partnerships.map(p => `<tr><td class="l">${p.wn}</td><td class="l">${pl(p.a)} & ${pl(p.b)}</td><td><b>${p.r}${p.ub ? '*' : ''}</b></td><td>${p.bl}</td><td class="l muted">${esc(p.a)} ${p.ra} · ${esc(p.b)} ${p.rb} · extras ${p.x}</td></tr>`).join('')}</tbody></table></div>`)}
      </div>`;
  };
  const tabs = root.querySelector('#innTabs');
  tabs.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { tabs.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); drawInn(+b.dataset.k); }));
  if (inn.length) drawInn(0);
}
