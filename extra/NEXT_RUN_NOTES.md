# Notes for a future re-run of the main experiment

Written after watching the live AWS `worst-case` run get through N=18000 and
partway into N=28000. These are changes worth making *if the whole experiment
were being restarted from scratch on a fresh machine*, not changes to make
mid-run on the current data (which stays as-is and is still usable).

## 1. Dataset order: cheap to expensive

`DATASETS = ["worst-case", "best-case", "random"]` in `experiment/main.py`
runs the most expensive dataset first. Everything observed so far suggests
`worst-case` is uniquely expensive because of its adversarial shortcut
structure forcing pathological NCA walks in `BBMSCore` -- `best-case`
(near-diagonal curves) and probably `random` are likely dramatically
cheaper. Running the cheap ones first means a stopped/cut-short run still
has full data for two of the three datasets, instead of a half-finished
expensive one and nothing else.

Recommendation: `DATASETS = ["best-case", "random", "worst-case"]`.

## 2. Denser, more evenly log-spaced N grid, with extra points near the wall

Current grid: `[500, 1000, 2000, 4000, 7000, 11000, 18000, 28000, 40000, 50000]`.
The ratios shrink at the top end (2x near the bottom, down to 1.25x at the
very top), which works against the original goal of evenly-weighted
log-log regression fits.

A cleaner geometric progression from 500 to 50000 over 9 steps uses a
constant ratio of about 1.67x throughout.

More importantly: this run showed `BBMSCore`'s timeout wall sits somewhere
between N=28000 and N=40000. A future run should add one or two extra grid
points specifically in that gap (e.g. ~32000, ~35000) to actually
characterize the transition instead of relying on wherever the pre-committed
grid happens to land.

## 3. Reconsider instance type

`x2iedn.xlarge` is memory-optimized (128GB RAM, 4 vCPUs, Cascade Lake at a
moderate clock) -- a reasonable choice given `BBMSInter`/`DijkstraPrims`
were expected to need close to the full 128GB by N=50000. But `BBMSCore`
hits its wall from raw single-thread time long before it comes close to a
memory ceiling, so for that algorithm the memory capacity is wasted while
clock speed is the actual constraint.

A family like AWS `z1d` (still Cascade Lake, but tuned for high sustained
all-core clock, ~4.0GHz) with still-substantial memory would likely serve
this mixed compute-bound/memory-bound workload better. Check current z1d
memory ceilings against the ~130GB / ~52GB estimates for
`BBMSInter`/`DijkstraPrims` at N=50000 before committing -- that's the one
hard constraint not worth trading away.

## 4. What NOT to change

`K=5` samples, `R=3` timing repeats, and `TIMEOUT_S=7200` (2h) were the more
speculative choices going in, and the real run has validated all three:
repeat-to-repeat noise stayed tight even at N=18000/28000 (DijkstraPrims
varied by only a couple seconds across all 15 runs at N=18000), and the one
anomalous sample-to-sample spread seen early on (around N=11000) didn't
recur at larger N -- it looks like transient system noise rather than a
real property of the algorithm/instance. The 2h timeout has had genuine
headroom the whole way through.

If the time budget for a future run is generous, bumping `K` to 7-8 would
tighten IQR estimates, but this is a nice-to-have, not a correction.

Explicitly avoid tuning the timeout down to deliberately force `BBMSCore` to
wall sooner at a specific N -- choosing a failure threshold based on which
way it makes one algorithm fail is post-hoc and biases the comparison. The
timeout should stay a value set independently of any specific algorithm's
outcome.
