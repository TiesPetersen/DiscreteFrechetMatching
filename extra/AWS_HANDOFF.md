# AWS calibration + full run: step-by-step

Written 2026-07-22, for whoever is at the keyboard on the rented AWS machine --
**no Claude Code access assumed there.** Every command below is meant to be
copy-pasted as-is. Background: `../HANDOFF.md` (project status) and `../PLAN.md`
(full experimental design/reasoning). This file only covers the AWS-specific
steps: calibrate first, then commit to the real multi-hour/day sweep.

The calibration script referenced here (`calibrate.py`) already exists in this
repo and has been tested end-to-end (built, run, resumed, forced-timeout path
all verified working, on WSL) -- you should not need to write or debug any code
to use it, just run the commands below.

## 0. Why calibrate at all before the real run

`experiment/main.py` currently has two placeholder values that were extrapolated
from an M1 Mac mini, not measured on real hardware: `TIMEOUT_S = 2700` (45 min)
and the top of `GRID` (up to N=50000). A local rehearsal on a Windows/WSL laptop
(not the real testbed, but instructive) already showed:

- `BBMSCore`'s runtime on the `worst-case` (adversarial) dataset scales much
  worse than the ~4x-per-N-doubling you'd expect from cell count alone -- more
  like 6-8x. It was already brushing a 20s timeout at N=4000, the 4th of 10 grid
  points.
- Memory scales close to the expected ~4x/doubling for all three algorithms, but
  extrapolating from N=4000 (BBMSInter: 858MB) to N=50000 implies multi-hundred-GB
  memory needs -- almost certainly unreachable on whatever instance is rented.

Neither of these numbers transfers directly to AWS (different CPU, no WSL
virtualization overhead there), but the qualitative shape -- BBMSCore walling
out earlier than the others, memory becoming the binding constraint well before
N=50000 -- is worth checking for real before committing to a run that might take
days.

## 1. Get the repo onto the machine

```bash
git clone https://github.com/TiesPetersen/DiscreteFrechetMatching.git
cd DiscreteFrechetMatching
git checkout main-experiment
```

If the machine already has a clone, just `git pull` on `main-experiment` instead.

Confirm build tools exist (Ubuntu AMIs usually have these; if not, `sudo apt-get
install -y build-essential python3`):

```bash
g++ --version && make --version && python3 --version
```

## 2. Build the runner binaries

```bash
cd experiment
make
cd ..
```

This should produce `experiment/runner.exe` and `experiment/runner_counted.exe`
with no errors. If `make` fails, stop here -- nothing past this point will work
until the build is fixed.

## 3. Set a memory safety net (recommended, not optional if you're not watching the terminal)

A real OOM on this machine is a kernel event -- if it picks the wrong victim
process, it can take down your SSH session or other things sharing the box, not
just the runner. Cap this shell's processes to a safe fraction of total RAM so
an over-budget allocation fails cleanly inside the runner (`status=oom`) instead
of triggering the kernel OOM-killer:

```bash
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))
```

Run this once per shell session, before step 4 and before step 6. It only
affects processes started from that shell afterward.

This is scientific research, not just an ops safety measure — this cap changes
what `status=oom` *means* in the results (a process hit 90% of RAM, not
necessarily "the physical machine ran out of memory"). Log the resolved value
and machine specs alongside the results it applies to:

```bash
mkdir -p results_calibration
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname: $(hostname)"
  echo "uname: $(uname -a)"
  echo "nproc: $(nproc)"
  free -h
  echo "ulimit -v (KB): $(ulimit -v)"
} > results_calibration/run_metadata.txt
```

(`ulimit -v` with no argument prints the currently active limit, so this
confirms exactly what got applied, not just the formula used to compute it.)

## 4. Run the calibration script

From the repo root:

```bash
python3 experiment/calibration/calibrate.py --timeout 120
```

This defaults to the `worst-case` dataset (the one most likely to reveal an
early wall), the *full* production `GRID` from `main.py` (not just the top few
N -- deliberately broader than `PLAN.md`'s original "top 2-3 values" suggestion,
given what the laptop rehearsal showed about BBMSCore), 1 sample, 1 repeat, and
a 120s per-run timeout. Wall-skipping means a broader grid costs almost nothing
extra once an algorithm starts failing -- it just stops attempting larger N for
that algorithm.

It writes to `results_calibration/`, never `results/`, so it can't be confused
with or clobber real run data later. It's resumable exactly like `main.py`: if
it's interrupted (Ctrl-C, SSH drop), just rerun the same command and it picks up
where it left off. To start over clean: `rm -rf results_calibration`.

It prints a summary at the end: average runtime/memory per (algorithm, N), any
non-ok rows (which mark exactly where each algorithm's wall is), and a
cross-algorithm `frechet_distance` agreement check.

If you have time/budget, also run it against the other two datasets:

```bash
python3 experiment/calibration/calibrate.py --timeout 120 --dataset best-case
python3 experiment/calibration/calibrate.py --timeout 120 --dataset random
```

(or `--dataset all` to do all three in one invocation). `best-case`/`random`
are expected to scale better than `worst-case` -- confirming that shifts your
estimate of the *real* run's total wall-clock time, since most of the sweep's
cost will come from whichever dataset survives to the largest N.

## 5. Read the results, decide on real values

Look at the printed summary (or `results_calibration/<dataset>/timing_memory.csv`
directly). Two decisions to make before the real run:

- **`TIMEOUT_S`**: pick something comfortably above the largest *successful*
  runtime you observed (3-5x margin is reasonable) so the real sweep doesn't
  falsely wall out a run that would've finished. If nothing timed out at all
  across the whole grid, the current `2700` placeholder is probably fine as an
  upper bound -- but consider lowering it substantially if the largest surviving
  runs finished in seconds, since 45 minutes of dead waiting on a genuinely stuck
  run is expensive multiplied over the full sweep.
- **`GRID`**: if every algorithm walls out (timeout or OOM) around the same N,
  the grid points above that are pure dead weight -- consider trimming them.
  If only *some* algorithms wall early, leave the grid alone; wall-skipping
  already handles that per-algorithm for free.

Edit `experiment/main.py` directly (lines ~26 and ~31, `GRID` and `TIMEOUT_S`)
with the chosen values. This is the one file you should expect to hand-edit on
the AWS machine -- everything else in this repo should already be correct.

## 6. Kick off the real full run

This can plausibly take hours to days depending on what step 5 revealed. Run it
somewhere that survives an SSH disconnect -- `tmux` or `screen`, not a bare
foreground shell:

```bash
tmux new -s frechet
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))   # same safety net as step 3, new shell = must redo
mkdir -p results
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname: $(hostname)"
  echo "uname: $(uname -a)"
  echo "nproc: $(nproc)"
  free -h
  echo "ulimit -v (KB): $(ulimit -v)"
} > results/run_metadata.txt
python3 experiment/main.py
```

`results/run_metadata.txt` is the one that matters most — it travels with the
real data pulled down in step 7, and is what documents, for the paper, exactly
what "OOM" was measured against on this specific instance.

Detach with `Ctrl-b d` (tmux) and reattach later with `tmux attach -t frechet`.
`main.py` is resumable by design: an interrupted run (Ctrl-C, reboot, session
loss) picks up exactly where it left off on rerun -- do not delete `results/` to
"start clean" unless you actually intend to discard progress.

To check on it without attaching:

```bash
tail -f results/worst-case/timing_memory.csv   # watch rows land in real time
ps aux | grep main.py                           # confirm it's still alive
```

It prints `All runs complete.` when every dataset's timing and op-count passes
have finished (or walled out) for every configured N/sample/repeat/algorithm.

## 7. After it finishes

Pull `results/` back down to wherever the paper analysis happens (`scp`/`rsync`
the whole directory). Those CSVs are the real data -- nothing else on the AWS
machine needs to survive past this point except in case something needs
re-running.

## Troubleshooting

- **Machine feels unresponsive / very slow**: probably genuine memory pressure
  (swapping). Check `free -h`. If you set the `ulimit -v` safety net in steps 3
  and 6, a single over-budget run fails cleanly instead of thrashing the whole
  machine -- if you skipped that step, this is why to go back and set it.
- **Not sure if a tmux-detached run is still going**: `tmux attach -t frechet`,
  or `ps aux | grep main.py` plus watching whether CSV row counts are still
  growing (`wc -l results/*/*.csv`, checked twice a minute or so apart).
- **Want to abort and reconsider the grid/timeout mid-run**: Ctrl-C is safe
  (resumable). Edit `main.py`, then just rerun `python3 experiment/main.py` --
  already-completed rows are skipped, already-discovered walls are respected.
