"""
Plots for the C++ adversarial crossover experiment.
Run from project root: python experiments/cpp_adversarial/plot.py
"""

import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = os.path.join("experiments", "cpp_adversarial", "results")
CSV_PATH    = os.path.join(RESULTS_DIR, "results.csv")

STYLES = {
    "DijkstraPrims":    ("tab:blue",   "o-"),
    "BBMSCore":         ("tab:red",    "s-"),
    "BBMSInter":        ("tab:green",  "^-"),
    "BBMSDppInstant":   ("tab:orange", "D-"),
    "BBMSDppStepwise":  ("tab:purple", "v-"),
}
LABELS = {
    "DijkstraPrims":    "DijkstraPrims (C++)",
    "BBMSCore":         "BBMSCore (C++)",
    "BBMSInter":        "BBMSInter (C++)",
    "BBMSDppInstant":   "BBMSDppInstant (C++)",
    "BBMSDppStepwise":  "BBMSDppStepwise (C++)",
}

# Theoretical memory wall: N_wall = sqrt(R_avail / bytes_per_cell).
# R_AVAIL_GB: available RAM on the test machine (16 GB total - ~7.5 GB idle with VS Code open).
R_AVAIL_GB = 8.5
R_AVAIL    = R_AVAIL_GB * 1024**3

# bytes_per_cell (practical): node array + pool estimate (~2 shortcuts/cell for DppInstant).
# DijkstraPrims wall (~47 000) is outside the experiment range and not shown.
MEMORY_WALL_BPC = {
    "BBMSCore":        16,
    "BBMSInter":       48,
    "BBMSDppInstant":  184,
    "BBMSDppStepwise": 184,
}

def _n_wall(bpc):
    return int((R_AVAIL / bpc) ** 0.5)

def _wall_groups(rows, x_max):
    """Group algorithms by shared N_wall; return sorted list of (nw, [alg, ...])."""
    by_nw = {}
    for alg, bpc in MEMORY_WALL_BPC.items():
        if alg not in rows:
            continue
        nw = _n_wall(bpc)
        if nw > x_max:
            continue
        by_nw.setdefault(nw, []).append(alg)
    return sorted(by_nw.items())

def _draw_wall_group(ax, x, algs):
    """Draw one wall line. Single alg → standard dashes; multiple → alternating colors.
    Each algorithm always gets its own legend entry with standard -- in its color."""
    if len(algs) == 1:
        color, _ = STYLES[algs[0]]
        ax.axvline(x, color=color, linestyle="--", linewidth=1.2, alpha=0.75,
                   label=f"{algs[0]} memory wall")
    else:
        seg = 5  # points per dash segment
        gap = seg * (len(algs) - 1)
        for i, alg in enumerate(algs):
            color, _ = STYLES[alg]
            # Actual line: alternating color dashes, no legend entry
            ax.axvline(x, color=color,
                       linestyle=(i * seg, (seg, gap)),
                       linewidth=1.5, alpha=0.85)
            # Proxy legend entry: standard -- in this algorithm's color
            ax.plot([], [], color=color, linestyle="--", linewidth=1.2, alpha=0.75,
                    label=f"{alg} memory wall")

def add_memory_walls(ax, rows, x_max):
    for nw, algs in _wall_groups(rows, x_max):
        _draw_wall_group(ax, nw, algs)


def load():
    rows = defaultdict(list)
    if not os.path.exists(CSV_PATH):
        print("No results CSV found.")
        return rows
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            if r["ok"] == "True":
                rows[r["algorithm"]].append((int(r["N"]), float(r["runtime_s"])))
    print(f"Loaded {sum(len(v) for v in rows.values())} completed runs.")
    return rows


def mean_by_N(runs):
    by_N = defaultdict(list)
    for N, t in runs:
        by_N[N].append(t)
    Ns    = sorted(by_N)
    means = [np.mean(by_N[N]) for N in Ns]
    stds  = [np.std(by_N[N])  for N in Ns]
    return Ns, means, stds


def save(fig, name):
    path = os.path.join(RESULTS_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved: {path}")
    plt.close(fig)


def plot_runtime(rows, log_scale, show_walls=False):
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    x_max = 0
    for alg, runs in rows.items():
        color, style = STYLES[alg]
        Ns, means, stds = mean_by_N(runs)
        x_max = max(x_max, max(Ns, default=0))
        ax.plot(Ns, means, style, color=color, label=LABELS[alg],
                linewidth=1.8, markersize=6)
        ax.fill_between(Ns,
                        [m - s for m, s in zip(means, stds)],
                        [m + s for m, s in zip(means, stds)],
                        color=color, alpha=0.15)
    if show_walls:
        add_memory_walls(ax, rows, x_max)
    ax.set_xlabel("Polyline length N")
    ax.set_ylabel("Mean runtime (seconds)")
    scale_label = "log scale" if log_scale else "linear scale"
    ax.set_title(f"Runtime vs N (mean ± 1 std, {scale_label}) (C++, adversarial input)")
    if log_scale:
        ax.set_yscale("log")
    ax.legend()
    ax.grid(True, which="both" if log_scale else "major", alpha=0.4)
    fig.tight_layout()
    scale_str = "log" if log_scale else "linear"
    walls_str = "_walls" if show_walls else ""
    save(fig, f"runtime_vs_N_{scale_str}{walls_str}.png")


def plot_speedup(rows, show_walls=False):
    dp_by_N  = dict(zip(*mean_by_N(rows.get("DijkstraPrims",    []))[:2]))
    bb_by_N  = dict(zip(*mean_by_N(rows.get("BBMSCore",         []))[:2]))
    bi_by_N  = dict(zip(*mean_by_N(rows.get("BBMSInter",        []))[:2]))
    dpp_by_N = dict(zip(*mean_by_N(rows.get("BBMSDppInstant",   []))[:2]))
    dps_by_N = dict(zip(*mean_by_N(rows.get("BBMSDppStepwise",  []))[:2]))
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    x_max = 0
    for alg_by_N, color, marker, label in [
        (bb_by_N,  "tab:red",    "s-", "BBMSCore / DijkstraPrims"),
        (bi_by_N,  "tab:green",  "^-", "BBMSInter / DijkstraPrims"),
        (dpp_by_N, "tab:orange", "D-", "BBMSDppInstant / DijkstraPrims"),
        (dps_by_N, "tab:purple", "v-", "BBMSDppStepwise / DijkstraPrims"),
    ]:
        common = sorted(set(dp_by_N) & set(alg_by_N))
        if len(common) < 2:
            continue
        x_max = max(x_max, max(common))
        ratios = [alg_by_N[N] / dp_by_N[N] for N in common]
        ax.plot(common, ratios, marker, color=color, linewidth=1.8, markersize=6, label=label)
    if show_walls:
        add_memory_walls(ax, rows, x_max)
    ax.axhline(1.0, color="tab:blue", linestyle=":", linewidth=1.2, label="Equal speed")
    ax.set_xlabel("Polyline length N")
    ax.set_ylabel("BBMS runtime / DijkstraPrims runtime")
    ax.set_title("How Many Times Slower is BBMS Than DijkstraPrims? (C++, adversarial input)")
    ax.legend()
    ax.grid(True, alpha=0.4)
    fig.tight_layout()
    walls_str = "_walls" if show_walls else ""
    save(fig, f"speedup_ratio{walls_str}.png")


def plot_loglog(rows, show_walls=False):
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    x_max = 0
    for alg, runs in rows.items():
        color, style = STYLES[alg]
        Ns, means, stds = mean_by_N(runs)
        if len(Ns) < 3:
            continue
        x_max   = max(x_max, max(Ns))
        log_Ns  = np.log(Ns)
        log_ms  = np.log(means)
        log_lo  = np.log(np.maximum(np.array(means) - np.array(stds), 1e-12))
        log_hi  = np.log(np.array(means) + np.array(stds))
        ax.plot(log_Ns, log_ms, style, color=color, label=LABELS[alg],
                linewidth=1.8, markersize=6)
        ax.fill_between(log_Ns, log_lo, log_hi, color=color, alpha=0.15)
    if show_walls:
        for nw, algs in _wall_groups(rows, x_max):
            _draw_wall_group(ax, np.log(nw), algs)
    ax.set_xlabel("log(N)")
    ax.set_ylabel("log(mean runtime)")
    ax.set_title("Runtime vs N (mean ± 1 std, log-log plot) (C++, adversarial input)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.4)
    fig.tight_layout()
    walls_str = "_walls" if show_walls else ""
    save(fig, f"loglog_scaling{walls_str}.png")


def plot_runtime_pre_wall(rows):
    """Linear runtime plot with x-axis capped at the first memory wall."""
    wall_Ns = [_n_wall(bpc) for alg, bpc in MEMORY_WALL_BPC.items() if alg in rows]
    if not wall_Ns:
        return
    x_cap = min(wall_Ns)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    y_max = 0
    for alg, runs in rows.items():
        if alg not in STYLES:
            continue
        color, style = STYLES[alg]
        Ns, means, stds = mean_by_N(runs)
        for N, m, s in zip(Ns, means, stds):
            if N <= x_cap:
                y_max = max(y_max, m + s)
        ax.plot(Ns, means, style, color=color, label=LABELS[alg],
                linewidth=1.8, markersize=6)
        ax.fill_between(Ns,
                        [m - s for m, s in zip(means, stds)],
                        [m + s for m, s in zip(means, stds)],
                        color=color, alpha=0.15)
    add_memory_walls(ax, rows, x_cap)
    ax.set_xlim(0, x_cap * 1.05)
    if y_max > 0:
        ax.set_ylim(0, y_max * 1.08)
    ax.set_xlabel("Polyline length N")
    ax.set_ylabel("Mean runtime (seconds)")
    ax.set_title("Runtime vs N — zoomed to first memory wall (linear scale) (C++, adversarial input)")
    ax.legend()
    ax.grid(True, alpha=0.4)
    fig.tight_layout()
    save(fig, "runtime_vs_N_pre_wall.png")


if __name__ == "__main__":
    rows = load()
    if not rows:
        print("No data to plot yet.")
    else:
        plot_runtime(rows, log_scale=True,  show_walls=False)
        plot_runtime(rows, log_scale=True,  show_walls=True)
        plot_runtime(rows, log_scale=False, show_walls=False)
        plot_runtime(rows, log_scale=False, show_walls=True)
        plot_speedup(rows, show_walls=False)
        plot_speedup(rows, show_walls=True)
        plot_loglog(rows, show_walls=False)
        plot_loglog(rows, show_walls=True)
        plot_runtime_pre_wall(rows)
