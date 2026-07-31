# Running the op-count redo on the AWS machine

This run reuses the existing `results_calibration_180` timing data for
`identical`/`random`/`outlier` (nothing about timing/memory measurement
changed) and only redoes their op-count pass, to pick up the new
`max_heap_size`/`avg_heap_size` counters. `alternating` is brand new and runs
both passes fully. Push results back to this same branch
(`aws-experiment-run-3`) when done.

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
git checkout aws-experiment-run-3
```

## 4. Build tools + runner binaries

```bash
sudo dnf install -y gcc-c++ make python3 tmux
cd experiment && make && cd ..
```

`results_calibration_300/{identical,random,outlier}/timing_memory.csv` are
already checked into this branch (copied from `results_calibration_180`, no
`opcounts.csv` — that's the pass being redone). `alternating` gets nothing
pre-seeded, so it runs completely fresh.

## 5. Run it in tmux (survives an SSH disconnect)

```bash
tmux new -s frechet
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname: $(hostname)"
  echo "uname: $(uname -a)"
  echo "nproc: $(nproc)"
  free -h
  echo "ulimit -v (KB): $(ulimit -v)"
} > results_calibration_300/run_metadata.txt
python3 -c "
import sys; sys.path.insert(0, 'experiment')
import main as m
m.RESULTS_DIR = 'results_calibration_300'
m.LOG_PATH = 'results_calibration_300/experiment.log'
m.TIMEOUT = 300
m.main()
"
```

Detach with `Ctrl-b d`, reattach with `tmux attach -t frechet`. Resumable:
Ctrl-C or a dropped connection is safe, just rerun the same command to
continue.

```bash
tail -f results_calibration_300/experiment.log   # watch progress
```

Note: the op-count pass has no timeout, and the new per-push/pop
instrumentation adds a little overhead specifically for DijkstraPrims —
worth watching for `alternating`, given its queue can hold millions of
entries.

## 6. Push results back

```bash
git add results_calibration_300/
git commit -m "describe what this run covers"
git push origin aws-experiment-run-3
```

Commit periodically as datasets finish, not just once at the end.
