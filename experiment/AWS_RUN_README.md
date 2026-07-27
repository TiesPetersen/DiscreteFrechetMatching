# Running the calibration pass on the AWS machine

Push results back to this same branch (`aws-experiment-run-2`) when done.

## 1. Install git (not present by default on Amazon Linux)

```bash
sudo dnf install -y git || sudo yum install -y git
```

## 2. Get the repo + branch

```bash
git clone https://github.com/TiesPetersen/DiscreteFrechetMatching.git
cd DiscreteFrechetMatching
git checkout aws-experiment-run-2
```

## 3. Build tools + runner binaries

```bash
sudo dnf install -y gcc-c++ make python3 || sudo yum install -y gcc-c++ make python3
cd experiment && make && cd ..
```

## 4. Memory safety net (redo this in every new shell)

```bash
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))
```

## 5. Run it in tmux (survives an SSH disconnect)

```bash
tmux new -s frechet
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))   # new shell = redo this
python3 -c "
import sys; sys.path.insert(0, 'experiment')
import main as m
m.RESULTS_DIR = 'results_calibration_180'
m.LOG_PATH = 'results_calibration_180/experiment.log'
m.TIMEOUT = 180
m.main()
"
```

Detach with `Ctrl-b d`, reattach with `tmux attach -t frechet`. Resumable: Ctrl-C
or a dropped connection is safe, just rerun the same command to continue.

```bash
tail -f results_calibration_180/experiment.log   # watch progress
```

## 6. Push results back

```bash
git add results_calibration_180/
git commit -m "describe what this run covers"
git push origin aws-experiment-run-2
```

Commit periodically as datasets finish, not just once at the end.
