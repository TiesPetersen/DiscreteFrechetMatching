"""
Log-log scaling plot for DijkstraPrims / BBMSCore / BBMSInter.
Run from project root: python experiments/loglog_scaling/plot.py

For each algorithm: takes the minimum runtime per N across samples (system
noise only ever slows a run down, so the min estimates the noise-free cost),
then fits a line in log-log space (runtime ~ C * N^k) and reports the
empirical exponent k.

Since these curves are both length N (nm = N^2), the theoretical baselines are:
  - BBMSCore / BBMSInter: claimed O(nm)          = O(N^2)
  - DijkstraPrims:        claimed O(nm log(nm))  = O(N^2 log N)
DijkstraPrims' reference is NOT a pure power law — it's a genuinely different
curve (a quadratic times a slowly-growing log factor), not "the same
quadratic with a worse constant." Its fitted power-law exponent is expected
to come out slightly above 2.0, drifting down toward 2.0 as N grows, which is
the log factor's signature — not evidence against the O(N^2 log N) claim.
"""

import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = os.path.join("experiments", "loglog_scaling", "results")
CSV_PATH    = os.path.join(RESULTS_DIR, "results.csv")
FIT_PATH    = os.path.join(RESULTS_DIR, "fit_summary.csv")

# Categorical slots 1-3 (blue, aqua, yellow) from the project's validated palette,
# assigned in fixed order — never cycled or reassigned if a series is filtered out.
STYLES = {
    "DijkstraPrims": "#2a78d6",
    "BBMSCore":      "#1baf7a",
    "BBMSInter":     "#eda100",
}
MARKERS = {
    "DijkstraPrims": "o",
    "BBMSCore":      "s",
    "BBMSInter":     "^",
}
GRIDLINE = "#e1e0d9"
MUTED    = "#898781"


def load_min_by_N():
    """(algorithm, N) -> minimum runtime_s across samples, for ok==True rows only."""
    raw = defaultdict(lambda: defaultdict(list))
    if not os.path.exists(CSV_PATH):
        print("No results CSV found.")
        return {}
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            if r["ok"] == "True":
                raw[r["algorithm"]][int(r["N"])].append(float(r["runtime_s"]))

    mins = {}
    for alg, by_N in raw.items():
        Ns = sorted(by_N)
        mins[alg] = (Ns, [min(by_N[N]) for N in Ns])
    return mins


def fit_power_law(Ns, runtimes):
    """Least-squares fit of log(runtime) = k*log(N) + log(C). Returns (k, C, r_squared)."""
    log_N = np.log(Ns)
    log_t = np.log(runtimes)
    k, log_C = np.polyfit(log_N, log_t, 1)
    residuals = log_t - (k * log_N + log_C)
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((log_t - np.mean(log_t)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return k, np.exp(log_C), r_squared


def add_theoretical_reference(ax, Ns_ref, anchor_N, anchor_t, exponent, log_factor, label, linestyle):
    """Draw a reference curve C*N^exponent[*log(N)], anchored through one observed point."""
    Ns_ref = np.asarray(Ns_ref, dtype=float)
    if log_factor:
        C  = anchor_t / (anchor_N ** exponent * np.log(anchor_N))
        ts = C * Ns_ref ** exponent * np.log(Ns_ref)
    else:
        C  = anchor_t / (anchor_N ** exponent)
        ts = C * Ns_ref ** exponent
    ax.plot(Ns_ref, ts, linestyle=linestyle, color=MUTED, linewidth=1.4, label=label, zorder=1)


def main():
    data = load_min_by_N()
    if not data:
        print("No data to plot yet.")
        return

    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    fits = []

    for alg in ["DijkstraPrims", "BBMSCore", "BBMSInter"]:
        if alg not in data:
            continue
        Ns, runtimes = data[alg]
        if len(Ns) < 3:
            print(f"  [SKIP] {alg}: only {len(Ns)} distinct N values, need >= 3 to fit")
            continue

        color = STYLES[alg]
        k, C, r2 = fit_power_law(Ns, runtimes)
        fits.append((alg, k, C, r2, len(Ns)))

        # Data points: marker + thin connecting line, white ring on markers so
        # they stay legible where the fitted line crosses them.
        ax.plot(Ns, runtimes, marker=MARKERS[alg], color=color, linewidth=1.6,
                 markersize=7, markeredgecolor="white", markeredgewidth=1.2,
                 label=f"{alg}  (fit: N^{k:.2f}, R²={r2:.3f})", zorder=3)

        # Fitted line across the observed range, subtler than the data itself.
        fit_Ns = np.array([min(Ns), max(Ns)], dtype=float)
        fit_ts = C * fit_Ns ** k
        ax.plot(fit_Ns, fit_ts, linestyle="--", color=color, linewidth=1.2,
                 alpha=0.55, zorder=2)

    if not fits:
        print("Not enough data to fit any algorithm yet (need >= 3 distinct N per algorithm).")
        plt.close(fig)
        return

    # Two separate theoretical references, not one shared O(N^2) line:
    # BBMSCore/BBMSInter are claimed O(nm) = O(N^2); DijkstraPrims is claimed
    # O(nm log nm) = O(N^2 log N), a genuinely different (non-power-law) curve.
    bbms_algs = [alg for alg in ("BBMSCore", "BBMSInter") if alg in data]
    if bbms_algs:
        anchor_alg = bbms_algs[0]
        anchor_Ns, anchor_ts = data[anchor_alg]
        bbms_Ns = sorted({N for alg in bbms_algs for N in data[alg][0]})
        add_theoretical_reference(
            ax, [min(bbms_Ns), max(bbms_Ns)], anchor_Ns[0], anchor_ts[0],
            exponent=2, log_factor=False,
            label="O(nm) reference (BBMS)", linestyle=":",
        )
    if "DijkstraPrims" in data:
        dp_Ns, dp_ts = data["DijkstraPrims"]
        add_theoretical_reference(
            ax, [min(dp_Ns), max(dp_Ns)], dp_Ns[0], dp_ts[0],
            exponent=2, log_factor=True,
            label="O(nm log nm) reference (DijkstraPrims)", linestyle="-.",
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Polyline length N")
    ax.set_ylabel("Minimum runtime (seconds)")
    ax.set_title("Runtime scaling (log-log, adversarial input, min over samples)")
    ax.grid(True, which="both", color=GRIDLINE, linewidth=0.8, alpha=0.8)
    ax.legend(fontsize=9)
    fig.tight_layout()

    out_path = os.path.join(RESULTS_DIR, "loglog_fit.png")
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")

    with open(FIT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "exponent_k", "coefficient_C", "r_squared", "n_points"])
        for alg, k, C, r2, npts in fits:
            w.writerow([alg, f"{k:.4f}", f"{C:.6g}", f"{r2:.4f}", npts])
    print(f"Saved: {FIT_PATH}")

    print("\nFitted power-law exponents:")
    for alg, k, C, r2, npts in fits:
        expected = "~2.0 (O(nm))" if alg != "DijkstraPrims" else "slightly > 2.0, drifting down (O(nm log nm) is not a pure power law)"
        print(f"  {alg:15s} N^{k:.2f}   R²={r2:.3f}   ({npts} points)   expected: {expected}")


if __name__ == "__main__":
    main()
