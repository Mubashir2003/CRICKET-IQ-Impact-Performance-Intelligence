# CRICKET IQ - Validation Report

Generated: 2026-11-17T03:25:33

**Summary:** {'pass': 31, 'info': 3, 'warn': 1}

| Check | Status | Compared | Mismatches | Detail |
|---|---|---|---|---|
| Deliveries reference known matches | PASS | 361674 | 0 |  |
| Delivery teams match fixture teams | PASS | 3165 | 0 |  |
| Winner is one of the two teams | PASS | 1553 | 0 |  |
| Over numbers within 1-20 | PASS | 361674 | 0 |  |
| No over has more than 6 legal balls | WARN | 57634 | 13 |  |
| No innings has more than 10 wickets | PASS | 3165 | 0 |  |
| Delivery total = batter runs + extras | PASS | 361674 | 0 |  |
| Innings total = batter runs + extras | PASS | 3165 | 0 |  |
| Sum of batting scorecard = innings batter runs | PASS | 3165 | 0 |  |
| Bowler runs conceded = batter runs + wides + no-balls | PASS | 3165 | 0 |  |
| Batting dismissals = innings wickets | PASS | 3165 | 0 |  |
| Partnership runs sum to innings total | PASS | 3165 | 0 |  |
| Partnership = batter 1 + batter 2 + extras | PASS | 22510 | 0 |  |
| Batting scorecards: rows present in reconstruction | PASS | 14229 | 0 | Upstream rows with no reconstructed counterpart |
| Batting scorecards: runs | PASS | 14229 | 0 | upstream 'runs_up' vs reconstructed 'runs' |
| Batting scorecards: balls | PASS | 14229 | 0 | upstream 'balls_faced' vs reconstructed 'balls' |
| Batting scorecards: fours | PASS | 14229 | 0 | upstream 'fours_up' vs reconstructed 'fours' |
| Batting scorecards: sixes | PASS | 14229 | 0 | upstream 'sixes_up' vs reconstructed 'sixes' |
| Batting scorecards: dismissals | PASS | 14229 | 0 | 18 upstream rows count 'retired hurt / retired not out' as a dismissal; under the Laws these are not-out and the reconstruction treats them so |
| Batting scorecards: batting position | INFO | 14229 | 913 | Reconstruction orders batters by arrival at the crease (striker or non-striker), confirmed by partnership order. Upstream differs mainly where a new batter arrived at the non-striker's end. |
| Bowling scorecards: rows present in reconstruction | PASS | 10348 | 0 | Upstream rows with no reconstructed counterpart |
| Bowling scorecards: runs | PASS | 10348 | 0 | upstream 'runs_conceded' vs reconstructed 'runs' |
| Bowling scorecards: balls | PASS | 10348 | 0 | upstream 'legal_balls' vs reconstructed 'balls' |
| Bowling scorecards: wkts | PASS | 10348 | 0 | upstream 'wickets' vs reconstructed 'wkts' |
| Bowling scorecards: dots_strict | PASS | 10348 | 0 | upstream 'dot_balls' vs reconstructed 'dots_strict' |
| Bowling scorecards: fours | PASS | 10348 | 0 | upstream 'fours_conceded' vs reconstructed 'fours' |
| Bowling scorecards: sixes | PASS | 10348 | 0 | upstream 'sixes_conceded' vs reconstructed 'sixes' |
| Bowling dot-ball definition | INFO | 0 | 0 | Dashboard dot balls follow the bowler convention (legal ball, no runs charged to the bowler - byes/leg-byes count as dots). Upstream excludes byes/leg-byes; 'dots_strict' reproduces the upstream definition for this check. |
| Partnerships (by batting pair): rows present in reconstruction | PASS | 10045 | 0 | Upstream rows with no reconstructed counterpart |
| Partnerships (by batting pair): runs | PASS | 10045 | 0 | upstream 'runs_up' vs reconstructed 'runs' |
| Partnerships (by batting pair): balls | PASS | 10045 | 0 | upstream 'balls_up' vs reconstructed 'balls' |
| Partnership coverage | INFO | 22506 | 12461 | Reconstruction has 22506 batting-pair stands vs 10045 in the upstream file. Every upstream stand is matched above; the upstream file covers only a subset of stands, so partnership analytics use the full ball-by-ball reconstruction. |
| Player-match records (non-super-over): rows present in reconstruction | PASS | 18137 | 0 | Upstream rows with no reconstructed counterpart |
| Player-match records (non-super-over): bat_r | PASS | 18137 | 0 | upstream 'batting_runs' vs reconstructed 'bat_r' |
| Player-match records (non-super-over): bowl_w | PASS | 18137 | 0 | upstream 'bowling_wickets' vs reconstructed 'bowl_w' |

### Examples - No over has more than 6 legal balls
```
{'match_id': 'mens_1532658', 'innings_number': '2', 'over': '7', 'legal': '7'}
{'match_id': 'mens_1535415', 'innings_number': '1', 'over': '1', 'legal': '7'}
{'match_id': 'mens_1535415', 'innings_number': '1', 'over': '5', 'legal': '7'}
{'match_id': 'mens_1539472', 'innings_number': '2', 'over': '18', 'legal': '7'}
{'match_id': 'womens_1534066', 'innings_number': '1', 'over': '3', 'legal': '7'}
```

### Examples - Batting scorecards: batting position
```
{'match_id': 'mens_1496587', 'innings_number': '1', 'player': 'KTH Ratnayake', 'batting_position': '7', 'position': '8'}
{'match_id': 'mens_1496587', 'innings_number': '1', 'player': 'PWH de Silva', 'batting_position': '8', 'position': '7'}
{'match_id': 'mens_1496587', 'innings_number': '1', 'player': 'N Thushara', 'batting_position': '10', 'position': '11'}
{'match_id': 'mens_1496587', 'innings_number': '1', 'player': 'D Madushanka', 'batting_position': '11', 'position': '10'}
{'match_id': 'mens_1529792', 'innings_number': '2', 'player': 'KN Chaddha', 'batting_position': '2', 'position': '3'}
```

## Data-quality issues
```
[info] men/players: Eligible players (11+ matches): 712 of 2953 (0)
[info] women/players: Eligible players (11+ matches): 346 of 1430 (0)
```

## Index reliability (split-half Spearman)
```
{
  "impact_split_half": {
    "men/bat": {
      "players": 345,
      "spearman": 0.347
    },
    "men/bowl": {
      "players": 355,
      "spearman": 0.169
    },
    "men/pressure": {
      "players": 404,
      "spearman": 0.16
    },
    "men/winning": {
      "players": 598,
      "spearman": 0.171
    },
    "women/bat": {
      "players": 158,
      "spearman": 0.395
    },
    "women/bowl": {
      "players": 174,
      "spearman": 0.35
    },
    "women/pressure": {
      "players": 156,
      "spearman": 0.364
    },
    "women/winning": {
      "players": 286,
      "spearman": 0.3
    }
  },
  "position_effectiveness_split_half": {
    "men/lower": {
      "players": 27,
      "spearman": 0.292
    },
    "men/middle": {
      "players": 181,
      "spearman": 0.331
    },
    "men/top": {
      "players": 186,
      "spearman": 0.356
    },
    "women/middle": {
      "players": 82,
      "spearman": 0.437
    },
    "women/top": {
      "players": 92,
      "spearman": 0.486
    }
  }
}
```

## Eligibility
```
{
  "men": {
    "eligible": 712,
    "total": 2953
  },
  "women": {
    "eligible": 346,
    "total": 1430
  }
}
```
