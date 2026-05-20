"""
Standalone plot script for the adversarial_crossover experiment.

Run at any time — reads whatever results are in the CSV so far and
generates/overwrites the PNG files in the same results directory.

Usage:
    python experiments/adversarial_crossover/plot.py
"""

import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = "experiments/adversarial_crossover/results"
CSV_PATH = os.path.join(RESULTS_DIR, "results.csv")


def load_results():
    rows = []
    if not os.path.exists(CSV_PATH):
        print("No results CSV found.")
        return rows
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            if r["ok"] == "True":
                r["N"] = int(r["N"])
                r["runtime_s"] = float(r["runtime_s"])
                rows.append(r)
    print(f"Loaded {len(rows)} completed runs.")
    return rows


def mean_by_N(rows, algorithm):
    by_N = defaultdict(list)
    for r in rows:
        if r["algorithm"] == algorithm:
            by_N[r["N"]].append(r["runtime_s"])
    Ns = sorted(by_N)
    means = [np.mean(by_N[N]) for N in Ns]
    stds  = [np.std(by_N[N])  for N in Ns]
    return Ns, means, stds


def make_plots(rows):
    if not rows:
        return

    STYLES = {
        "DijkstraPrims":    ("tab:blue",   "o-"),
        "BBMS_inter":       ("tab:green",  "s-"),
        "BBMS_dpp_instant": ("tab:orange", "^-"),
    }

    # --- Plot 1: absolute runtime ---
    plt.figure(figsize=(10, 6), dpi=150)
    for alg, (color, style) in STYLES.items():
        Ns, means, stds = mean_by_N(rows, alg)
        if not Ns:
            continue
        plt.plot(Ns, means, style, color=color, label=alg, linewidth=1.8, markersize=6)
        plt.fill_between(Ns,
                         [m - s for m, s in zip(means, stds)],
                         [m + s for m, s in zip(means, stds)],
                         color=color, alpha=0.15)

    plt.xlabel("Polyline length N")
    plt.ylabel("Mean runtime (seconds)")
    plt.title("Adversarial inputs — Runtime vs N (mean ± 1 std, log scale)")
    plt.yscale("log")
    plt.legend()
    plt.grid(True, which="both", alpha=0.4)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "runtime_vs_N.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # --- Plot 1b: same but linear y scale ---
    plt.figure(figsize=(10, 6), dpi=150)
    for alg, (color, style) in STYLES.items():
        Ns, means, stds = mean_by_N(rows, alg)
        if not Ns:
            continue
        plt.plot(Ns, means, style, color=color, label=alg, linewidth=1.8, markersize=6)
        plt.fill_between(Ns,
                         [m - s for m, s in zip(means, stds)],
                         [m + s for m, s in zip(means, stds)],
                         color=color, alpha=0.15)

    plt.xlabel("Polyline length N")
    plt.ylabel("Mean runtime (seconds)")
    plt.title("Adversarial inputs — Runtime vs N (mean ± 1 std, linear scale)")
    plt.legend()
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "runtime_vs_N_linear.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # --- Plot 2: BBMS_inter vs BBMS_dpp_instant (zoom in on crossover region) ---
    plt.figure(figsize=(9, 5), dpi=150)
    for alg, (color, style) in [
        ("BBMS_inter",       ("tab:green",  "s-")),
        ("BBMS_dpp_instant", ("tab:orange", "^-")),
    ]:
        Ns, means, stds = mean_by_N(rows, alg)
        if not Ns:
            continue
        plt.plot(Ns, means, style, color=color, label=alg, linewidth=1.8, markersize=6)
        plt.fill_between(Ns,
                         [m - s for m, s in zip(means, stds)],
                         [m + s for m, s in zip(means, stds)],
                         color=color, alpha=0.2)

    plt.xlabel("Polyline length N")
    plt.ylabel("Mean runtime (seconds)")
    plt.title("BBMS_inter vs BBMS_dpp_instant — Adversarial inputs")
    plt.legend()
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "bbms_crossover.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # --- Plot 3: speedup ratio (BBMS / DP) ---
    dp_Ns, dp_means, _ = mean_by_N(rows, "DijkstraPrims")
    dp_dict = dict(zip(dp_Ns, dp_means))

    plt.figure(figsize=(9, 5), dpi=150)
    for alg, color, label in [
        ("BBMS_inter",       "tab:green",  "BBMS_inter / DijkstraPrims"),
        ("BBMS_dpp_instant", "tab:orange", "BBMS_dpp_instant / DijkstraPrims"),
    ]:
        Ns, means, _ = mean_by_N(rows, alg)
        common = [(N, m) for N, m in zip(Ns, means) if N in dp_dict]
        if not common:
            continue
        Ns_c, bbms_c = zip(*common)
        dp_c = [dp_dict[N] for N in Ns_c]
        ratios = [b / d for b, d in zip(bbms_c, dp_c)]
        plt.plot(Ns_c, ratios, "o-", color=color, label=label, linewidth=1.8)

    plt.axhline(1.0, color="black", linestyle=":", linewidth=1.2, label="Equal speed")
    plt.xlabel("Polyline length N")
    plt.ylabel("BBMS runtime / DijkstraPrims runtime")
    plt.title("How Many Times Slower is BBMS Than DijkstraPrims? (Adversarial)")
    plt.legend()
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "speedup_ratio.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # --- Plot 4: log-log for empirical exponent estimation ---
    plt.figure(figsize=(10, 6), dpi=150)
    for alg, (color, style) in STYLES.items():
        Ns, means, _ = mean_by_N(rows, alg)
        if len(Ns) < 2:
            continue
        plt.plot(np.log(Ns), np.log(means), style, color=color, label=alg,
                 linewidth=1.8, markersize=6)
        # Fit line
        log_Ns = np.log(Ns)
        log_ms = np.log(means)
        k, b = np.polyfit(log_Ns, log_ms, 1)
        fit_y = k * log_Ns + b
        plt.plot(log_Ns, fit_y, "--", color=color, alpha=0.5,
                 label=f"{alg} fit k={k:.2f}")

    plt.xlabel("log(N)")
    plt.ylabel("log(mean runtime)")
    plt.title("Log-log plot — empirical scaling exponents")
    plt.legend(fontsize=7)
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "loglog_scaling.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


if __name__ == "__main__":
    rows = load_results()
    make_plots(rows)
