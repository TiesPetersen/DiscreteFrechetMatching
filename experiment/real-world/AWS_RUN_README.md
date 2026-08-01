# Running the real-world experiment on an AWS machine

A full, fresh run of all four real-world datasets (`ov`, `geolife`, `pigeons`,
`drifter`) — 1,688 pairs total, sized to fit roughly a 24-hour run (estimated
~21.3h from real per-pair cost measured in a local pilot: Geolife ~4.8h,
Pigeons ~11.7h despite being by far the smallest pair count, Drifter ~4.8h, OV
negligible).

Unlike the synthetic experiment, `datasets/real-world/*/part_*.txt` are
pre-generated and checked into the repo — no raw data or `netCDF4` needed on
this machine, just `git clone`. The generator (`generate_real_world_datasets.py`)
only needs to be re-run if you want to resample; that script's own docstring
covers its `external_datasets/` raw-data requirements separately.

**Expect a lot of `timeout`/`oom` rows in the results, especially for
`BBMSCore`/`BBMSInter` on `pigeons`.** Sampling was deliberately fair and
unfiltered by curve length, so a meaningful fraction of pairs are expected to
fail outright — that's real data, not something to debug.

## 1. Install git (not present by default on Amazon Linux)

```bash
sudo dnf install -y git
```

## 2. Cache GitHub auth for 24h

```bash
git config --global credential.helper 'cache --timeout=86400'
```

This only sets the timeout; it doesn't cache anything until the next real
auth, so do one push/pull right after cloning to populate it. If
`credential.helper cache` was ever set before without `--timeout=86400`, the
default is 900 seconds — rerun the command above to fix it.

## 3. Get the repo + branch

```bash
git clone https://github.com/TiesPetersen/DiscreteFrechetMatching.git
cd DiscreteFrechetMatching
git checkout <your-branch>
```

## 4. Build tools + runner binaries

```bash
sudo dnf install -y gcc-c++ make python3 tmux
cd experiment && make && cd ..
```

`runner.cpp`/`Makefile` live at `experiment/` (shared with the synthetic
orchestrator) — same build regardless of which experiment you're running.

## 5. Run it in tmux (survives an SSH disconnect)

```bash
tmux new -s frechet
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))
mkdir -p results_real_world
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname: $(hostname)"
  echo "uname: $(uname -a)"
  echo "nproc: $(nproc)"
  free -h
  echo "ulimit -v (KB): $(ulimit -v)"
} > results_real_world/run_metadata.txt
python3 -c "
import sys; sys.path.insert(0, 'experiment/real-world')
import main as m
m.main()
"
```

`RESULTS_DIR` (`results_real_world`) and `TIMEOUT` (300s, timing pass only)
already default correctly in `experiment/real-world/main.py`, so there's
nothing to override before calling `m.main()` the way the synthetic README
overrides `RESULTS_DIR`/`TIMEOUT` explicitly. The op-count pass is uncapped,
same as the synthetic experiment, but only ever attempted for an
(algorithm, pair) that already succeeded on every timing repeat — a timing
failure means op-count is skipped for that pair/algorithm entirely, since
it's already known to be too expensive.

Detach with `Ctrl-b d`, reattach with `tmux attach -t frechet`. Resumable:
Ctrl-C or a dropped connection is safe, just rerun the same command to
continue — it skips whatever's already in `results_real_world/`.

```bash
tail -f results_real_world/experiment.log   # watch progress
```

Datasets run in alphabetical order (`drifter`, `geolife`, `ov`, `pigeons`) —
`pigeons` runs last and is the single biggest time sink (~11.7h of the ~21.3h
total) despite having the fewest pairs (21), so most of the wall-clock budget
is actually spent at the very end, not spread evenly across the run.

## 6. Push results back

```bash
git add results_real_world/
git commit -m "describe what this run covers"
git push origin <your-branch>
```

Commit periodically as datasets finish, not just once at the end.
