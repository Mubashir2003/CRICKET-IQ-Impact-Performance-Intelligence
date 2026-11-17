// Data loading, decoding and the global filter engine.
// All advanced statistics are pre-computed in Python; this module only filters
// fact rows and sums them (sums/ratios), so filtered views stay consistent.

const BASE = '../data/dashboard/';
export const store = { manifest: null, defs: {}, genders: {} };
export const PH = { powerplay: 'pp', middle: 'mid', death: 'dth' };
export const PHASE_LABEL = { pp: 'Powerplay', mid: 'Middle', dth: 'Death' };

async function getJSON(path) {
  const r = await fetch(BASE + path, { cache: 'no-cache' });
  if (!r.ok) throw new Error('unavailable');
  return r.json();
}

export async function loadManifest() {
  store.manifest = await getJSON('manifest.json');
  try { store.defs = await getJSON('definitions.json'); } catch (e) { store.defs = {}; }
  return store.manifest;
}

export async function loadGender(g) {
  if (store.genders[g]) return store.genders[g];
  const [core, bat, bowl, part, tinn, players] = await Promise.all([
    getJSON(`${g}/core.json`), getJSON(`${g}/bat.json`), getJSON(`${g}/bowl.json`),
    getJSON(`${g}/part.json`), getJSON(`${g}/teaminn.json`), getJSON(`${g}/players.json`),
  ]);
  const G = build(g, core, bat, bowl, part, tinn, players);
  store.genders[g] = G;
  return G;
}

export async function loadMatch(g, id) {
  return getJSON(`${g}/matches/${encodeURIComponent(id)}.json`);
}

function index(list) { const m = new Map(); list.forEach((v, i) => m.set(v, i)); return m; }

function build(g, core, bat, bowl, part, tinn, players) {
  const dims = core.dims;
  const M = core.matches;
  const nM = M.id.length;
  const compType = {};
  core.comps.forEach(c => { compType[c.name] = c.type; });
  const compTypeByIdx = dims.comp.map(n => compType[n] || 'Domestic');
  const month = M.date.map(d => d.slice(0, 7));
  const P = new Map();
  const fields = players.fields;
  players.rows.forEach(r => {
    const o = { i: r.i, name: r.n, country: r.c, countries: r.cs, teams: r.tm.map(t => dims.team[t]), comps: r.cp.map(c => dims.comp[c]),
      matches: r.mt, role: r.role, batRoles: r.br, bowlRoles: r.wr, first: r.fm, last: r.lm, g };
    fields.forEach((f, k) => { o[f] = r.x[k]; });
    P.set(r.i, o);
  });
  const byComp = {};
  for (const [ci, rows] of Object.entries(players.by_comp)) {
    const mp = new Map();
    rows.forEach(r => { const o = {}; players.comp_fields.forEach((f, k) => { o[f] = r[k + 1]; }); mp.set(r[0], o); });
    byComp[dims.comp[+ci]] = mp;
  }
  const pei = players.pei.map(r => Object.fromEntries(players.pei_fields.map((f, k) => [f, r[k]])));
  return {
    g, label: core.label, core, dims, M, nM, compTypeByIdx, month, P, byComp, pei, positions: players.positions,
    nElig: core.n_eligible, flags: core.flags || {}, bat, bowl, part, tinn,
    nBat: bat.m.length, nBowl: bowl.m.length, nPart: part.m.length, nTinn: tinn.m.length,
    teamIdx: index(dims.team), playerIdx: index(dims.player), venueIdx: index(dims.venue), compIdx: index(dims.comp),
    matchIdx: index(M.id),
  };
}

// ------------------------------------------------------------------ filters
export const EMPTY_FILTERS = {
  gender: 'men', comps: [], compType: '', country: '', role: '', player: '', team: '', opponent: '', venue: '',
  from: '', to: '', innings: '', position: '', phase: '', result: '',
};

/** Pre-compute everything a page needs to test rows quickly for one gender. */
export function makeCtx(G, F) {
  const compSet = F.comps.length ? new Set(F.comps.map(c => G.compIdx.get(c)).filter(x => x !== undefined)) : null;
  const venue = F.venue ? (G.venueIdx.has(F.venue) ? G.venueIdx.get(F.venue) : -2) : -1;
  const team = F.team ? (G.teamIdx.has(F.team) ? G.teamIdx.get(F.team) : -2) : -1;
  const opp = F.opponent ? (G.teamIdx.has(F.opponent) ? G.teamIdx.get(F.opponent) : -2) : -1;
  const M = G.M;
  const mm = new Uint8Array(G.nM);
  for (let i = 0; i < G.nM; i++) {
    if (compSet && !compSet.has(M.comp[i])) continue;
    if (F.compType && G.compTypeByIdx[M.comp[i]] !== F.compType) continue;
    if (venue !== -1 && M.venue[i] !== venue) continue;
    if (F.from && M.date[i] < F.from) continue;
    if (F.to && M.date[i] > F.to) continue;
    if (team !== -1 && M.t1[i] !== team && M.t2[i] !== team) continue;
    if (opp !== -1) {
      if (team !== -1) { const other = M.t1[i] === team ? M.t2[i] : M.t1[i]; if (other !== opp) continue; }
      else if (M.t1[i] !== opp && M.t2[i] !== opp) continue;
    }
    mm[i] = 1;
  }
  const player = F.player ? (G.playerIdx.has(F.player) ? G.playerIdx.get(F.player) : -2) : -1;
  const phase = F.phase ? PH[F.phase] : '';
  // single competition -> competition-level advanced metrics
  const scopeComp = F.comps.length === 1 && G.byComp[F.comps[0]] ? F.comps[0] : null;
  return { G, F, mm, team, opp, player, phase, innings: F.innings ? +F.innings : 0, position: F.position ? +F.position : 0, result: F.result || '', scopeComp,
    matchFiltersActive: !!(F.comps.length || F.compType || F.venue || F.from || F.to || F.team || F.opponent || F.innings || F.position || F.phase || F.result) };
}

/** Player-attribute filter (country / role / player) - eligible players only. */
export function playerOk(c, p) {
  if (p < 0 || p >= c.G.nElig) return false;
  if (c.player !== -1 && p !== c.player) return false;
  const P = c.G.P.get(p);
  if (!P) return false;
  if (c.F.country && !(P.countries || []).includes(c.F.country)) return false;
  if (c.F.role && P.role !== c.F.role) return false;
  return true;
}

function rowsOf(c, T, n, opts = {}) {
  const out = [];
  const { usePos = false, teamField = 't', oppField = 'o' } = opts;
  for (let r = 0; r < n; r++) {
    if (!c.mm[T.m[r]]) continue;
    if (c.team !== -1 && T[teamField][r] !== c.team) continue;
    if (c.opp !== -1 && T[oppField][r] !== c.opp) continue;
    if (c.innings && T.i[r] !== c.innings) continue;
    if (c.result && T.res[r] !== c.result) continue;
    if (usePos && c.position && T.pos[r] !== c.position) continue;
    out.push(r);
  }
  return out;
}
export const batRows = c => rowsOf(c, c.G.bat, c.G.nBat, { usePos: true });
export const bowlRows = c => rowsOf(c, c.G.bowl, c.G.nBowl);
export const partRows = c => rowsOf(c, c.G.part, c.G.nPart);
export const tinnRows = c => rowsOf(c, c.G.tinn, c.G.nTinn);
export function matchRows(c) { const o = []; for (let i = 0; i < c.G.nM; i++) if (c.mm[i]) o.push(i); return o; }

/** Column accessor honouring the phase filter. */
function col(T, base, ph, map) { return ph ? (T[`${ph}_${map || base}`] || null) : T[base]; }

// ------------------------------------------------------------------ aggregation
const nz = v => (v == null ? 0 : v);

export function aggBat(c, rows, keyFn = r => c.G.bat.p[r]) {
  const T = c.G.bat, ph = c.phase;
  const R = col(T, 'r', ph, 'r'), B = col(T, 'b', ph, 'b'), F4 = col(T, 'f4', ph, '4'), F6 = col(T, 'f6', ph, '6'),
    D = col(T, 'd', ph, 'd'), O = col(T, 'out', ph, 'o'), ER = col(T, 'er', ph, 'er');
  const res = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    let a = res.get(k);
    if (!a) { a = { key: k, inns: 0, runs: 0, balls: 0, f4: 0, f6: 0, dots: 0, outs: 0, er: 0, tr: 0, hs: -1, hsno: false, f30: 0, f50: 0, f100: 0, m: new Set(), teams: new Map(),
      pb: 0, pr: 0, po: 0, per: 0, chaseR: 0, chaseB: 0, chaseT: 0, winR: 0, winB: 0, winO: 0 }; res.set(k, a); }
    const runs = nz(R[r]), balls = nz(B[r]), out = nz(O[r]);
    if (ph && balls === 0 && out === 0) continue; // did not bat in this phase
    a.inns++; a.runs += runs; a.balls += balls; a.f4 += nz(F4[r]); a.f6 += nz(F6[r]); a.dots += nz(D[r]); a.outs += out; a.er += nz(ER[r]);
    a.tr += nz(T.tr[r]); a.m.add(T.m[r]); a.teams.set(T.t[r], (a.teams.get(T.t[r]) || 0) + 1);
    if (runs > a.hs || (runs === a.hs && !out)) { a.hs = runs; a.hsno = !out; }
    if (!ph) { if (runs >= 100) a.f100++; else if (runs >= 50) a.f50++; else if (runs >= 30) a.f30++; }
    a.pb += nz(T.pb[r]); a.pr += nz(T.pr[r]); a.po += nz(T.po[r]); a.per += nz(T.per[r]);
    if (T.i[r] === 2) { a.chaseR += runs; a.chaseB += balls; a.chaseT += nz(T.tr[r]); }
    if (T.res[r] === 'W') { a.winR += runs; a.winB += balls; a.winO += out; }
  }
  for (const a of res.values()) {
    a.matches = a.m.size;
    a.avg = a.outs ? a.runs / a.outs : null;
    a.sr = a.balls ? a.runs / a.balls * 100 : null;
    a.bndRuns = a.f4 * 4 + a.f6 * 6;
    a.bndPct = a.runs ? a.bndRuns / a.runs * 100 : null;
    a.dotPct = a.balls ? a.dots / a.balls * 100 : null;
    a.bpb = (a.f4 + a.f6) ? a.balls / (a.f4 + a.f6) : null;
    a.bpd = a.outs ? a.balls / a.outs : null;
    a.notOuts = a.inns - a.outs;
    a.rae = a.runs - a.er;
    a.srVs = a.balls ? (a.runs - a.er) / a.balls * 100 : null;
    a.teamPct = (!ph && a.tr) ? a.runs / a.tr * 100 : null;
    a.hsText = a.hs >= 0 ? `${a.hs}${a.hsno ? '*' : ''}` : '–';
    a.pSr = a.pb ? a.pr / a.pb * 100 : null;
    a.pAvg = a.po ? a.pr / a.po : null;
    a.pExpSr = a.pb ? a.per / a.pb * 100 : null;
    a.pDelta = a.pb ? (a.pr - a.per) / a.pb * 100 : null;
    a.chaseSr = a.chaseB ? a.chaseR / a.chaseB * 100 : null;
    a.chasePct = a.chaseT ? a.chaseR / a.chaseT * 100 : null;
    a.winAvg = a.winO ? a.winR / a.winO : null;
    a.winSr = a.winB ? a.winR / a.winB * 100 : null;
    a.mainTeam = [...a.teams.entries()].sort((x, y) => y[1] - x[1])[0]?.[0];
  }
  return res;
}

export function aggBowl(c, rows, keyFn = r => c.G.bowl.p[r]) {
  const T = c.G.bowl, ph = c.phase;
  const BL = col(T, 'bl', ph, 'b'), R = col(T, 'r', ph, 'r'), W = col(T, 'w', ph, 'w'), D = col(T, 'd', ph, 'd'), ER = col(T, 'er', ph, 'er');
  const res = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    const balls = nz(BL[r]);
    if (ph && balls === 0 && nz(R[r]) === 0) continue;
    let a = res.get(k);
    if (!a) { a = { key: k, inns: 0, balls: 0, runs: 0, wkts: 0, dots: 0, bnd: 0, wd: 0, nb: 0, md: 0, er: 0, ew: 0, tw: 0, td: 0, best: [-1, 0], w4: 0, w5: 0, m: new Set(), teams: new Map(),
      pb: 0, pr: 0, pw: 0, per: 0, winB: 0, winR: 0, winW: 0, lossB: 0, lossR: 0, lossW: 0 }; res.set(k, a); }
    const runs = nz(R[r]), w = nz(W[r]);
    a.inns++; a.balls += balls; a.runs += runs; a.wkts += w; a.dots += nz(D[r]); a.er += nz(ER[r]);
    a.bnd += ph ? nz(T[`${ph}_bd`][r]) : nz(T.f4[r]) + nz(T.f6[r]);
    if (!ph) { a.wd += nz(T.wd[r]); a.nb += nz(T.nb[r]); a.md += nz(T.md[r]); a.ew += nz(T.ew[r]); a.tw += nz(T.tw[r]); a.td += nz(T.td[r]);
      if (w > a.best[0] || (w === a.best[0] && runs < a.best[1])) a.best = [w, runs];
      if (w === 4) a.w4++; if (w >= 5) a.w5++; }
    a.m.add(T.m[r]); a.teams.set(T.t[r], (a.teams.get(T.t[r]) || 0) + 1);
    a.pb += nz(T.pb[r]); a.pr += nz(T.pr[r]); a.pw += nz(T.pw[r]); a.per += nz(T.per[r]);
    if (T.res[r] === 'W') { a.winB += balls; a.winR += runs; a.winW += w; }
    if (T.res[r] === 'L') { a.lossB += balls; a.lossR += runs; a.lossW += w; }
  }
  for (const a of res.values()) {
    a.matches = a.m.size;
    a.overs = `${Math.floor(a.balls / 6)}.${a.balls % 6}`;
    a.avg = a.wkts ? a.runs / a.wkts : null;
    a.econ = a.balls ? a.runs / a.balls * 6 : null;
    a.sr = a.wkts ? a.balls / a.wkts : null;
    a.dotPct = a.balls ? a.dots / a.balls * 100 : null;
    a.saved = a.er - a.runs;
    a.expEcon = a.balls ? a.er / a.balls * 6 : null;
    a.econAdv = a.balls ? (a.er - a.runs) / a.balls * 6 : null;
    a.bestText = a.best[0] >= 0 ? `${a.best[0]}/${a.best[1]}` : '–';
    a.wktPct = a.tw ? a.wkts / a.tw * 100 : null;
    a.dotShare = a.td ? a.dots / a.td * 100 : null;
    a.bndPrev = a.balls ? 100 - a.bnd / a.balls * 100 : null;
    a.pEcon = a.pb ? a.pr / a.pb * 6 : null;
    a.pExpEcon = a.pb ? a.per / a.pb * 6 : null;
    a.pDelta = a.pb ? (a.per - a.pr) / a.pb * 6 : null;
    a.pBpw = a.pw ? a.pb / a.pw : null;
    a.winEcon = a.winB ? a.winR / a.winB * 6 : null;
    a.lossEcon = a.lossB ? a.lossR / a.lossB * 6 : null;
    a.mainTeam = [...a.teams.entries()].sort((x, y) => y[1] - x[1])[0]?.[0];
    if (c.phase) { a.wd = a.nb = a.md = null; a.bestText = '–'; }
  }
  return res;
}

/** Advanced (pre-computed) metrics for a player under the current scope. */
export function scopeMetrics(c, p) {
  if (c.scopeComp) return c.G.byComp[c.scopeComp].get(p) || null;
  return c.G.P.get(p) || null;
}

export function teamName(G, t) { return t >= 0 ? G.dims.team[t] : '–'; }
export function playerName(G, p) { return p >= 0 ? G.dims.player[p] : '–'; }
