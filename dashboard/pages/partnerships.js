import { partRows, playerOk } from '../js/data.js';
import { card, chartBox, fmt, esc, eachGender, empty, table, playerCell, kpi, playerLink } from '../js/ui.js';
import { bars } from '../js/charts.js';

const PHN = ['Powerplay', 'Middle', 'Death'];

export async function render(root, env) {
  root.innerHTML = '<div class="note">🤝 Partnerships are rebuilt ball by ball. Partnership runs include extras; each batter\'s share counts runs off the bat only, so batter 1 + batter 2 + extras = partnership total. A new stand starts at every wicket or retirement.</div><div id="ptwrap" class="grid"></div>';
  eachGender(root.querySelector('#ptwrap'), env.ctxs, (c, el) => section(c, el));
}

function section(c, el) {
  const G = c.G, P = G.part, M = G.M;
  const id = s => `${G.g}-pt-${s}`;
  const pf = c.player !== -1 || c.F.country || c.F.role;
  const rows = partRows(c).filter(r => !pf || playerOk(c, P.a[r]) || playerOk(c, P.b[r]))
    .filter(r => !c.phase || PHN[P.ph[r]].toLowerCase().startsWith(c.F.phase.slice(0, 3)));
  if (!rows.length) { el.innerHTML = empty('No partnerships for these filters.'); return; }
  const pn = p => G.dims.player[p];
  let runs = 0, balls = 0, f50 = 0, f100 = 0, hi = rows[0];
  rows.forEach(r => { runs += P.r[r]; balls += P.bl[r]; if (P.r[r] >= 100) f100++; else if (P.r[r] >= 50) f50++; if (P.r[r] > P.r[hi]) hi = r; });
  el.innerHTML = `
    <div class="kpis">
      ${kpi('Partnerships', fmt(rows.length, 'int'), '', '🤝')}
      ${kpi('Partnership runs', fmt(runs, 'int'), `run rate ${fmt(balls ? runs / balls * 6 : null, 'dec2')}`, '🏏')}
      ${kpi('Average stand', fmt(runs / rows.length, 'dec1'), `${fmt(balls / rows.length, 'dec1')} balls`, '📊')}
      ${kpi('Highest', fmt(P.r[hi], 'int'), `${esc(pn(P.a[hi]))} & ${esc(pn(P.b[hi]))}`, '🔝')}
      ${kpi('50+ stands', fmt(f50, 'int'), `${f100} of 100+`, '⭐')}
    </div>
    <div class="grid g2">
      ${card('Average partnership by wicket', chartBox(id('wk')), { sub: 'Runs per stand for each wicket' })}
      ${card('Partnership run rate by wicket', chartBox(id('rr')), { sub: 'Runs per over during the stand' })}
    </div>
    <div class="grid g2">
      ${card('Stands in wins vs defeats', chartBox(id('wl')), { sub: 'Average partnership by wicket — matches won vs lost' })}
      ${card('Partnerships by starting phase', chartBox(id('ph')), { sub: 'Average stand and run rate depend on when the stand begins' })}
    </div>
    ${card('Best batting pairs', `<div class="tabs" id="${id('tabs')}"><button class="on" data-t="all">All stands</button><button data-t="open">Opening</button><button data-t="mid">Middle order (wkts 3-6)</button><button data-t="fin">Finishing (death start)</button><button data-t="win">In victories</button><button data-t="pr">Under pressure</button></div><div id="${id('pairs')}" style="margin-top:10px"></div>`, { sub: 'Pairs with 2+ stands together' })}
    <div class="grid g2">
      ${card('Highest partnerships', `<div id="${id('top')}"></div>`)}
      ${card('Player contribution to partnerships', `<div id="${id('pc')}"></div>`, { sub: 'Eligible players: share of partnership runs scored personally' })}
    </div>`;

  const byW = Array.from({ length: 10 }, () => ({ n: 0, r: 0, b: 0, nw: 0, rw: 0, nl: 0, rl: 0 }));
  const byP = PHN.map(() => ({ n: 0, r: 0, b: 0 }));
  rows.forEach(r => {
    const w = Math.min(10, P.wn[r]) - 1; const o = byW[w]; o.n++; o.r += P.r[r]; o.b += P.bl[r];
    if (P.res[r] === 'W') { o.nw++; o.rw += P.r[r]; } else if (P.res[r] === 'L') { o.nl++; o.rl += P.r[r]; }
    const q = byP[P.ph[r]]; q.n++; q.r += P.r[r]; q.b += P.bl[r];
  });
  const wl = byW.map((_, i) => `${i + 1}${['st', 'nd', 'rd'][i] || 'th'}`);
  bars(id('wk'), wl, [{ label: 'Average stand', data: byW.map(o => (o.n ? +(o.r / o.n).toFixed(1) : null)) }], { fmt: v => v + ' runs' });
  bars(id('rr'), wl, [{ label: 'Run rate', data: byW.map(o => (o.b ? +(o.r / o.b * 6).toFixed(2) : null)) }], { fmt: v => v + ' rpo' });
  bars(id('wl'), wl, [{ label: 'Won', data: byW.map(o => (o.nw ? +(o.rw / o.nw).toFixed(1) : null)) }, { label: 'Lost', data: byW.map(o => (o.nl ? +(o.rl / o.nl).toFixed(1) : null)) }], { fmt: v => v + ' runs' });
  bars(id('ph'), PHN, [{ label: 'Average stand', data: byP.map(o => (o.n ? +(o.r / o.n).toFixed(1) : null)) }], { fmt: v => v + ' runs' });

  const pairsFor = pred => {
    const mp = new Map();
    rows.filter(pred).forEach(r => {
      const k = `${P.a[r]}|${P.b[r]}`; const o = mp.get(k) || { a: P.a[r], b: P.b[r], team: P.t[r], n: 0, runs: 0, balls: 0, best: 0, ra: 0, rb: 0, x: 0, f50: 0 };
      o.n++; o.runs += P.r[r]; o.balls += P.bl[r]; o.best = Math.max(o.best, P.r[r]); o.ra += P.ra[r]; o.rb += P.rb[r]; o.x += P.x[r]; if (P.r[r] >= 50) o.f50++; mp.set(k, o);
    });
    return [...mp.values()].filter(o => o.n >= 2).map(o => ({ ...o, name: `${pn(o.a)} & ${pn(o.b)}`, avg: o.runs / o.n, rr: o.balls ? o.runs / o.balls * 6 : null }));
  };
  const preds = { all: () => true, open: r => P.wn[r] === 1, mid: r => P.wn[r] >= 3 && P.wn[r] <= 6, fin: r => P.ph[r] === 2, win: r => P.res[r] === 'W', pr: r => P.pr[r] === 1 };
  const drawPairs = t => table(document.getElementById(id('pairs')), {
    rows: pairsFor(preds[t]), sortKey: 'runs', pageSize: 12, search: true,
    columns: [{ key: 'name', label: 'Pair', l: true, html: r => `<a class="pname" href="${playerLink(G, pn(r.a))}">${esc(pn(r.a))}</a> & <a class="pname" href="${playerLink(G, pn(r.b))}">${esc(pn(r.b))}</a><div class="pmeta muted">${esc(G.dims.team[r.team])}</div>`, asc: true },
      { key: 'n', label: 'Stands', fmt: 'int' }, { key: 'runs', label: 'Runs', fmt: 'int' }, { key: 'avg', label: 'Avg', fmt: 'dec1' }, { key: 'best', label: 'Best', fmt: 'int' },
      { key: 'f50', label: '50+', fmt: 'int' }, { key: 'rr', label: 'Run Rate', fmt: 'dec2' }, { key: 'ra', label: 'Batter 1 Runs', fmt: 'int' }, { key: 'rb', label: 'Batter 2 Runs', fmt: 'int' }, { key: 'x', label: 'Extras', fmt: 'int' }],
  });
  const tabs = document.getElementById(id('tabs'));
  tabs.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { tabs.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); drawPairs(b.dataset.t); }));
  drawPairs('all');

  const top = [...rows].sort((a, b) => P.r[b] - P.r[a]).slice(0, 50).map(r => ({ r, name: `${pn(P.a[r])} & ${pn(P.b[r])}`, runs: P.r[r], balls: P.bl[r], wn: P.wn[r], date: M.date[P.m[r]], team: G.dims.team[P.t[r]], opp: G.dims.team[P.o[r]], mid: M.id[P.m[r]], ub: P.ub[r] }));
  table(document.getElementById(id('top')), {
    rows: top, sortKey: 'runs', pageSize: 10,
    columns: [{ key: 'name', label: 'Pair', l: true, html: x => `<b>${esc(x.name)}</b><div class="pmeta muted">${esc(x.team)} v ${esc(x.opp)} · <a href="#/match?g=${G.g}&id=${encodeURIComponent(x.mid)}">${esc(x.date)}</a></div>`, asc: true },
      { key: 'runs', label: 'Runs', html: x => `${x.runs}${x.ub ? '*' : ''}` }, { key: 'balls', label: 'Balls', fmt: 'int' }, { key: 'wn', label: 'Wkt', fmt: 'int' }],
  });

  const pc = new Map();
  rows.forEach(r => {
    [[P.a[r], P.ra[r]], [P.b[r], P.rb[r]]].forEach(([p, own]) => {
      if (!playerOk(c, p)) return;
      const o = pc.get(p) || { key: p, n: 0, own: 0, tot: 0, f50: 0 }; o.n++; o.own += own; o.tot += P.r[r]; if (P.r[r] >= 50) o.f50++; pc.set(p, o);
    });
  });
  table(document.getElementById(id('pc')), {
    rows: [...pc.values()].filter(o => o.n >= 10).map(o => ({ ...o, name: pn(o.key), share: o.tot ? o.own / o.tot * 100 : null, avg: o.tot / o.n })), sortKey: 'tot', pageSize: 10, search: true,
    columns: [{ key: 'name', label: 'Player', l: true, html: r => playerCell(G, r.key), asc: true }, { key: 'n', label: 'Stands', fmt: 'int' }, { key: 'tot', label: 'Stand Runs', fmt: 'int' },
      { key: 'avg', label: 'Avg Stand', fmt: 'dec1' }, { key: 'f50', label: '50+ Stands', fmt: 'int' }, { key: 'share', label: 'Own Share %', fmt: 'pct' }],
  });
}
