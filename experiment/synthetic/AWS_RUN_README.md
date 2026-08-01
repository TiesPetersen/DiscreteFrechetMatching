# Running the synthetic experiment on an AWS machine

A full, fresh run of all four synthetic datasets (`identical`, `random`,
`outlier`, `alternating`) across the whole N grid (500 to 50,000), both passes,
from scratch. For reference, the last full fresh run of just three of these
datasets (no `alternating`) took ~25 hours at a 180s timeout; expect a full
run of all four to take longer than that, likely multi-day — this isn't a
single-session thing, budget for it accordingly.

## 1. Install git (not present by default on Amazon Linux)

```bash
sudo dnf install -y git
```

## 2. Cache GitHub auth for 24h

Avoids re-entering credentials on every push during a long run.

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

`runner.cpp`/`Makefile` live at `experiment/` (shared with the real-world
orchestrator), not under `experiment/synthetic/` — this build step doesn't
change regardless of which experiment you're about to run.

## 5. Run it in tmux (survives an SSH disconnect)

```bash
tmux new -s frechet
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))
mkdir -p results_synthetic
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname: $(hostname)"
  echo "uname: $(uname -a)"
  echo "nproc: $(nproc)"
  free -h
  echo "ulimit -v (KB): $(ulimit -v)"
} > results_synthetic/run_metadata.txt
python3 -c "
import sys; sys.path.insert(0, 'experiment/synthetic')
import main as m
m.RESULTS_DIR = 'results_synthetic'
m.LOG_PATH = 'results_synthetic/experiment.log'
m.TIMEOUT = 300
m.main()
"
```

Detach with `Ctrl-b d`, reattach with `tmux attach -t frechet`. Resumable:
Ctrl-C or a dropped connection is safe, just rerun the same command to
continue — `main.py` skips whatever's already in `results_synthetic/`.

```bash
tail -f results_synthetic/experiment.log   # watch progress
```

Note: the op-count pass has no timeout in the synthetic orchestrator (op
counts are deterministic and BBMS work is always exactly m*n regardless of
input, so this has never been an issue here) — if that changes, watch
`alternating` in particular, since its queue can hold millions of entries and
the per-push/pop instrumentation adds a little overhead specifically for
`DijkstraPrims`.

## 6. Push results back

```bash
git add results_synthetic/
git commit -m "describe what this run covers"
git push origin <your-branch>
```

Commit periodically as datasets finish, not just once at the end.
