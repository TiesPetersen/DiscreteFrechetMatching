# AWS run, November 2026

One run, one machine, one job at a time, about 6 to 12 hours. It produces the numbers to show Wouter after the November audit and the lean DPP work. The job list is in `run_plan.py`, in blocks, most important first:

| block | what it shows | rough time |
|---|---|---|
| A | before and after the audit fixes, on the same machine: old code (08ca567) against new. Two NCA queries instead of three, removal from the back of the lists, and orientation (curves swapped) | 1 h |
| B | the main comparison with the final code, every synthetic dataset (including swapped and cheap first column), N = 2300, 6500, 11000, timing and operation counts | 2.3 h |
| C | the current DPP (vector lists) against the lean DPP at N = 11000, 18000, 30000: memory and time | 0.5 h |
| D | real-world datasets with the fixed projection (drifter, geolife, pigeons), and pigeons without repeated points | 3.9 h |
| E | the main comparison at N = 18000 and 30000, only for the algorithms that can get there | 1.6 h |

The times are rough guesses from Mac timings, easily off by a factor of 2. The run can be stopped at any time, and everything finished so far is kept. Running the same command again continues where it stopped.

## 1. Start the machine (AWS console)

1. Go to EC2 in the same region as last time: eu-central-1 (Frankfurt).
2. Click **Launch instance**.
   - **Name:** `frechet-nov-2026`.
   - **Image:** Amazon Linux 2023, 64-bit (x86).
   - **Instance type:** the same kind as last time: 4 vCPUs and about 128 GiB memory, memory optimised (for example `x2iedn.xlarge`). Check the hourly price shown in the picker before choosing. The lean DPP needs up to about 65 GB at N=30000, and the current DPP must be able to run out of memory cleanly, so less than 128 GiB will change block C.
   - **Key pair:** use last time's key, or create a new one and save the `.pem` file.
   - **Network:** allow SSH from **My IP** only.
   - **Storage:** 30 GiB, gp3. The repo with datasets is about 0.5 GB, and the default 8 GiB is tight once both builds and the results are there.
3. Launch it, wait until its state is **Running**, and copy its **Public IPv4 DNS**.

## 2. Connect

From the Mac (replace the key path and the address):

```bash
chmod 400 ~/Downloads/frechet.pem
ssh -i ~/Downloads/frechet.pem ec2-user@ec2-XX-XX-XX-XX.eu-central-1.compute.amazonaws.com
```

## 3. Install the tools and get the code

On the machine:

```bash
sudo dnf install -y git gcc-c++ make python3 tmux
git clone https://github.com/TiesPetersen/DiscreteFrechetMatching.git
cd DiscreteFrechetMatching
git checkout aws-run-2026-11
```

The repo is private, so git asks for a username and a token instead of a password. A fine-grained GitHub token for this one repo, with "Contents: read and write", also lets you push the results back in step 6.

## 4. Build both versions and check the plan

```bash
make -C experiment
git worktree add --detach old_code 08ca567
make -C old_code/experiment
python3 experiment/aws_2026_11/run_plan.py --dry-run
```

The dry run should end with `missing dataset files: 0`.

## 5. Run it inside tmux

tmux keeps the run going when the SSH connection drops.

```bash
tmux new -s frechet
ulimit -v $(( $(free -k | awk '/^Mem:/{print $2}') * 90 / 100 ))
mkdir -p results_aws_2026_11
{ date -u; hostname; uname -a; nproc; free -h; echo "ulimit -v (KB): $(ulimit -v)"; git log --oneline -1; } > results_aws_2026_11/run_metadata.txt
python3 experiment/aws_2026_11/run_plan.py
```

- Detach with `Ctrl-b` then `d`. Reattach with `tmux attach -t frechet`.
- Watch progress from a second SSH session with `tail -f ~/DiscreteFrechetMatching/results_aws_2026_11/run.log`.
- The memory cap (`ulimit -v`, 90 % of the memory) makes an algorithm that needs too much memory stop with "oom" instead of freezing the machine.
- If the run stops for any reason, run the same `ulimit` and `python3` lines again inside tmux. It skips everything already done.
- To run only some blocks, add for example `--blocks ABD`.

## 6. Bring the results back

Commit and push every few hours, not only at the end:

```bash
git add results_aws_2026_11
git commit -m "Add AWS run results (November 2026)"
git push origin aws-run-2026-11
```

Results files:
- `results_aws_2026_11/timing.csv`: time and memory per job.
- `results_aws_2026_11/counts.csv`: operation counts per job.
- `results_aws_2026_11/run.log`: what ran, and its outcome.

## 7. Stop paying

When the run is done and the results are pushed: EC2 → Instances → select the machine → **Instance state → Terminate**. A stopped machine still costs money for its disk; a terminated one costs nothing.
