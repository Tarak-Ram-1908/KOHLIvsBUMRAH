# 11 Kohlis vs 11 Bumrahs

Monte Carlo ODI simulation: a team of 11 Virat Kohlis bats first against a team of 11 Jasprit Bumrahs,
using ball-by-ball outcome probabilities from Cricsheet.

## Get the data
Ball-by-ball ODI data from [Cricsheet](https://cricsheet.org/downloads/) (not stored in this repo):

```powershell
mkdir data; curl.exe -L -o data/odis_json.zip https://cricsheet.org/downloads/odis_json.zip; Expand-Archive data/odis_json.zip data/odis_json
```

## Run
```powershell
python -I scripts/kohli_vs_bumrah.py data/odis_json 10000
```
It runs in about 2 minutes. Output from the last run is in [results.txt](results.txt).

## Method
- Each delivery is classified as 0, 1, 2, 3, 4, 5, 6, wicket, wide or no-ball (men's ODIs only).
- Every dismissal counts as a wicket (run-outs included, retirements excluded). Byes and leg-byes count as dots.
- Batter and bowler distributions are combined two ways: a **simple average** and **log5 / odds ratio**
  (league baseline = all men's ODIs from 2008).
- Wides and no-balls add 1 run and are re-bowled. Innings end at 300 legal balls or 10 wickets.

## Parsing check against ESPNcricinfo Statsguru (Nov 2026)
| | Cricsheet | Statsguru |
|---|---|---|
| Kohli matches | 314 | 322 |
| Kohli runs / avg / HS | 14,987 / 58.54 / 183 | 15,195 / 58.21 / 183 |
| Kohli bowling (balls, runs, wkts) | 662, 680, 5 | 662, 680, 5 |
| Bumrah matches | 89 | 91 |
| Bumrah wickets / economy | 145 / 4.60 | 151 / 4.58 |
| Bumrah batting avg / HS | 9.17 / 20 | 9.25 / 20* |

## Results (10,000 matches, Kohlis bat first)
| Blend | Kohlis win | Bumrahs win | Ties | Avg score K v B |
|---|---|---|---|---|
| Simple average | 7,250 | 2,680 | 70 | 248 v 200 |
| Log5 | 6,107 | 3,812 | 81 | 259 v 235 |

The chasing side's average stops once it passes the target. Moving Kohli's bowling by one wicket
shifts the log5 result between 5,549 and 6,552 Kohli wins, so his 5-wicket sample matters a lot.

Data: Cricsheet, licensed under ODC-BY.
