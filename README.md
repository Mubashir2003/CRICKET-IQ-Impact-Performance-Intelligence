# 🏏 CRICKET IQ — Cricket Impact & Performance Intelligence

A cricket analytics platform for **men's and women's T20 cricket in 2026**. It goes beyond scorecards to measure how much each player contributes to team performance, winning, handling pressure and fulfilling roles.

* **Python** (pandas + NumPy) reads the CSV files, rebuilds every scorecard ball by ball, calculates all statistics, validates them and exports dashboard-ready JSON.
* **HTML / CSS / JavaScript + Chart.js** dashboard with a glassmorphism UI in light and dark mode, 11 pages and global filters.
* No database, no backend server. Everything runs from files.

The supplied 2026 data is **already included and already processed**, so you can open the dashboard straight away (steps 1, 2 and 4 below).

---

## 1. Requirements

| Tool | Version |
|---|---|
| Python | 3.10 or newer (3.12+ recommended) |
| A modern browser | Chrome, Edge, Firefox or Safari |
| VS Code (optional) | any recent version |

No internet connection is needed at runtime. Chart.js, the Inter font and the flag images are bundled.

## 2. Install (one time)

Open the project folder in VS Code, open a terminal (**Terminal → New Terminal**) and run:

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\activate.bat` from Command Prompt.

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Process the data

```bash
python run.py
```
This takes about 1–2 minutes and prints a summary:

```
=== CRICKET IQ pipeline complete ===
Matches:           {'men': 1075, 'women': 518}
Eligible players:  {'men': {'eligible': 712, ...}, 'women': {'eligible': 346, ...}}
Validation checks: {'pass': 31, 'info': 3, 'warn': 1}
```

## 4. Open the dashboard

```bash
python run.py serve
```
Your browser opens **http://localhost:8000/dashboard/**. Press `Ctrl+C` in the terminal to stop the server.

* `python run.py all` processes the data, then starts the dashboard.
* `python run.py serve --port 8080` uses another port.
* **VS Code Live Server** also works. Open the project **root** folder (not `dashboard/`), then right-click `dashboard/index.html` → *Open with Live Server*. The included `.vscode/settings.json` already sets the server root correctly.
* In VS Code you can also use **Run and Debug** → *CRICKET IQ: process + dashboard*.

> The dashboard must be opened through a local server. Double-clicking `index.html` (a `file://` address) will not load the data, because browsers block it.

## 5. Updating with new data

1. Replace the files in `data/raw/men/` and `data/raw/women/` with the new versions. Each folder needs the same 10 file names: `batting_innings, bowling_innings, data_quality_report, deliveries, excluded_players, invalid_files, matches, partnerships, player_appearances, player_match` (`.csv`).
2. Run `python run.py`.
3. Refresh the browser.

Only `matches.csv` and `deliveries.csv` are strictly required. If any other file is missing, the cross-checks that depend on it are skipped. Your original files are never modified.

To check that new files are read correctly before processing: `python run.py inspect` lists every detected column and type.

## 6. Run the tests

```bash
python run.py test        # or: python -m pytest
```
The suite (27 tests) covers cricket rules on a hand-built match with known answers (wides, no-balls, byes, retired hurt, non-striker run-outs, timed out, maidens, super overs, partnerships, batting order), the 11-match eligibility rule, ingestion and type handling, the expected-value baselines, impact-index rules, and integration checks on the real data and exported JSON.

---

## 7. Project structure

```text
CricketIQ/
├── run.py                       ← single entry point (process / serve / all / inspect / test)
├── requirements.txt, pyproject.toml, README.md
├── config/
│   ├── settings.json            ← every threshold & weight (phases, pressure, eligibility, impact weights…)
│   ├── countries.json           ← national teams (decides what counts as a T20I) + flag codes
│   └── bowler_types.csv         ← optional spin/pace list (enables spin-based roles)
├── data/
│   ├── raw/men, raw/women       ← your 20 input CSV files
│   ├── processed/
│   │   ├── combined/            ← the 10 merged, gender-tagged datasets
│   │   ├── analytics/           ← rebuilt scorecards, player metrics, contributions (CSV)
│   │   ├── validation_report.md / .json, eligibility_audit.csv, excluded_matches.csv
│   └── dashboard/               ← generated JSON consumed by the dashboard
├── python/cricketiq/
│   ├── ingestion/               ← schema definitions, CSV loading, type coercion
│   ├── processing/              ← cleaning & merging, match/delivery reconstruction, players & eligibility
│   ├── analytics/               ← baselines, fact tables, metrics, positions, roles, impact
│   ├── validation/              ← scorecard cross-checks & report
│   ├── export/                  ← dashboard JSON writer + metric definitions
│   └── pipeline.py
├── dashboard/
│   ├── index.html, css/styles.css
│   ├── js/ (app shell, data & filter engine, UI components, charts)
│   ├── pages/ (11 page modules)
│   └── assets/ (Chart.js, Inter font, flags)
└── tests/
```

## 8. Dashboard pages

| Page | Highlights |
|---|---|
| 🏟️ Executive Overview | KPIs (matches, teams, eligible players, runs, wickets, run rate, highest team/individual/partnership), competition breakdown, team performance, monthly trends, phase profile, coverage table |
| 🏏 Batting Analytics | Full traditional leaderboard, average-vs-strike-rate map, phase strike rates, runs by position, advanced metrics |
| 🎳 Bowling Analytics | Leaderboard incl. runs saved & economy advantage, economy-vs-strike-rate map, phase economy, death-over leaders, advanced metrics |
| 🏆 Winning Intelligence | Present vs significant vs match-winning contributions, win rates, winning run/wicket shares, chase contributors, wins vs defeats |
| ⚡ Pressure Intelligence | Clutch batters/bowlers (performance vs expected under pressure), close finishes, low-scoring games, pressure partnerships, chase contribution |
| 📍 Position & Role | Positions 1–11, position leaderboards, Position Effectiveness Index, role distribution and role explorer |
| 🤝 Partnerships | By wicket, wins vs defeats, starting phase, best pairs (opening, middle, finishing, in victories, under pressure), player contribution |
| 📊 Team Intelligence | Win/loss record, scoring, phase run rates, batting/bowling efficiency, chase/defend %, team comparison, competition view |
| 👤 Player Profile | Avatar, country flag, roles, teams, batting & bowling stats, impact profile & radar, advanced metrics, trends, phases, positions, winning, recent matches |
| ⚔️ Player Comparison | Up to 4 players of the same gender: head-to-head table, impact radar, phase and position charts |
| 🏟️ Match Intelligence | Every match: scorecards, fall of wickets, partnerships, worm & Manhattan charts, phase breakdown, match-winning contributions |

**Global filters:** Gender (Men / Women / Both), Competition (multi-select), Competition type, Country, Role, Player. Under **More filters**: Team, Opponent, Venue, Date range, Innings, Batting position, Phase, Match result. The **✕ Clear all** button resets them. *Both* shows men's and women's sections side by side. Their numbers are never mixed or ranked together.

How filters apply:
* Match-level filters (competition, type, venue, dates, team, opponent, innings, result, position, phase) recompute every traditional statistic, KPI and chart from the fact tables.
* Player filters (country, role, player) narrow every player-level view.
* Advanced indices are computed in Python per season, and also per competition. When exactly one competition is selected, the competition-level values are used. Each page shows a note saying which scope is in use.

---

## 9. Methodology

### Data handling
* The 10 files of each gender are merged into 10 combined datasets with a `gender` column (`data/processed/combined/`). Different data types are never merged into one table.
* **Every statistic is rebuilt from ball-by-ball deliveries**, then cross-checked against the supplied batting, bowling, partnership and player-match files. All runs, balls, 4s, 6s, wickets and economy figures match exactly. See `data/processed/validation_report.md`.
* Missing values stay missing (shown as “–”). They are never treated as zero. Duplicate rows are detected and reported. Exact duplicates only are removed.
* Season window: 1 January 2026 onward. Competitions matching “Hundred” are excluded (configurable).

### Cricket rules applied
| Rule | Treatment |
|---|---|
| Legal ball | not a wide and not a no-ball |
| Ball faced | every delivery except wides (no-balls count) |
| Bowler runs | bat runs + wides + no-balls; byes, leg-byes and penalty runs are not charged |
| Bowler wickets | bowled, caught, caught & bowled, lbw, stumped, hit wicket (run outs, retired out, obstructing, timed out are not credited) |
| Not out | retired hurt and retired not out |
| Super overs | used to decide tied matches (counted as a win for the super-over winner, configurable). Excluded from player statistics and innings totals |
| Batting position | order of arrival at the crease (striker or non-striker) |
| Maiden | six legal balls by one bowler with no runs charged to him/her |

### Eligibility (11+ matches)
A player qualifies with **11 or more distinct matches in 2026**, counted separately for men and women. Distinct match IDs come from batting, bowling, being at the crease, dismissals and the playing-XI level `player_match` file. The upstream playing-XI appearance count is used as a lower bound. Ineligible players are excluded from player rankings only. All their matches and deliveries still count toward team and match totals. Audit: `data/processed/eligibility_audit.csv`.

### Expected values (the fairness engine)
Each delivery gets an *expected* outcome: the average for comparable deliveries in the same gender, competition and phase. Batters are also matched on batting-position group (top / middle / lower order). If a bucket has fewer than 600 balls, the next broader level is used. Summing these per ball gives **runs above expected**, **strike rate vs average**, **runs saved** and **economy advantage**, all adjusted for opportunity and competition.

### Pressure situations (consistent, state-based)
A pressure delivery is either:
* in a **chase** with a required rate between 9 and 18, or with ≤ 30 balls left and a required rate up to 15; or
* bowled during a **collapse**: 3+ wickets down within the first 8 overs, or 5+ down within 15 overs.

Rain-reduced or revised-target chases are excluded from the chase rule, because revised targets are not in the data. Pressure performance is compared with the expected outcome of pressure deliveries in the same competition type and phase. **No win-probability model is used**, because no validated model could be built from the supplied data.

### Winning contribution (three levels kept separate)
1. **Present**: in the XI for a win.
2. **Significant contribution**: 20+ runs and 20%+ of team runs, 2+ wickets, 5+ runs saved from 18+ balls, or a match score of 8+.
3. **Match-winning**: the single best match score in the winning XI, at least 15.

Match score = runs above expected + runs saved + 10 × wickets above expected.

### Experimental indices 🧪
Batting, Bowling, Pressure and Winning Impact, Overall Impact and the Position Effectiveness Index are built like this:
* components are z-scored within gender
* small samples are shrunk toward average
* results are shown as 0–100 percentiles

Overall Impact uses the starting weights from the brief (batting 40 / bowling 35 / pressure 15), **renormalised over the components that apply to the player**. A batter who does not bowl has *no* bowling component; it is not scored as zero. Weights live in `config/settings.json`.

The indices were checked for **split-half reliability**: the same index was computed on two separate halves of the season and the rankings compared (`validation_report.md`). Spearman correlations are roughly 0.17–0.49, which is modest. Treat the indices as directional, experimental indicators, not definitive rankings. The dashboard labels them as experimental.

### Roles
Roles are inferred only from where and how a player actually batted or bowled, relative to comparable deliveries (rules and thresholds in `config/settings.json → roles`). A player can have several role tendencies. Primary role (Batter / Bowler / All-Rounder) comes from batting and bowling opportunity per match.

---

## 10. Known data limitations

The dashboard handles each of these honestly rather than inventing values:

| Not in the supplied data | Effect |
|---|---|
| Player IDs | Players are identified by name within each gender. Possible collisions (one name on both sides of a match) are flagged in the validation report. |
| Fielder names | Fielding impact is disabled. Caught dismissals display as “c ? b Bowler”. |
| Byes / leg-byes / penalty split | Shown combined as “b/lb/pen”. None are charged to the bowler, so bowling figures are unaffected. |
| Bowling type (spin / pace) | *Spin Attacker* and *Spin Pressure Specialist* roles are off. Fill `config/bowler_types.csv` (`gender,player,bowling_type` with `spin` or `pace`) and re-run to enable them. |
| Match stage (knockouts) | Knockout analysis is not available. |
| Toss, DLS targets | Rain-revised chases are flagged and excluded from required-rate pressure. |
| Competition strength | Baselines adjust for the competition's own average, not for how strong it is. A dominant performer in an associate-level event can rank highly. |
| Player photos / team logos | Initials avatars, national flags and team-initial badges are used instead. |

Coverage is exactly what the supplied files contain (17 men's and 6 women's competitions after grouping all internationals as *International T20Is*). The dashboard does not claim complete worldwide coverage.

---

## 11. Configuration

Edit `config/settings.json`, then run `python run.py` again:
* `eligibility.min_distinct_matches`: default 11
* `phases`: over ranges for powerplay, middle and death
* `pressure`: required-rate and collapse rules
* `impact.*_weights`, `position_effectiveness.weights`: index weights
* `competitions.short_names` / `franchise_patterns`: competition labels and types
* `roles`: every role threshold

Add national teams in `config/countries.json` if new associate nations appear. A match is an International T20I only when **both** teams are listed there.

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Install Python 3.10+ from python.org and tick **“Add Python to PATH”**. On macOS/Linux use `python3`. |
| `ModuleNotFoundError: pandas` | Activate the virtual environment (step 2), then `pip install -r requirements.txt`. |
| “Cricket data is not available yet” in the browser | Run `python run.py` first, then open the page through `python run.py serve` (not by double-clicking the HTML file). |
| Blank page or old numbers after an update | Hard-refresh the browser (`Ctrl+F5` / `Cmd+Shift+R`). |
| `Address already in use` | Another program is using port 8000: `python run.py serve --port 8080`. |
| `required column(s) not found` | A CSV has different headers. Run `python run.py inspect`, then either rename the column or add it as an alias in `python/cricketiq/ingestion/schema.py`. |
| Live Server shows a 404 for data | Live Server must serve the project **root** folder, not the `dashboard` folder. |
| PowerShell will not activate `.venv` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use Command Prompt with `.venv\Scripts\activate.bat`. |
| A validation check shows FAIL | Open `data/processed/validation_report.md`. It lists the check, the number of mismatches and example rows. |

## 13. Credits
Charts: [Chart.js](https://www.chartjs.org/) (MIT). Font: Inter via Fontsource (OFL). Flags: [flag-icons](https://github.com/lipis/flag-icons) (MIT).
