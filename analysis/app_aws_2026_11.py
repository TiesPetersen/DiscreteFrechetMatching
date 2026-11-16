"""
Overview report for the November 2026 AWS run (experiment/aws_2026_11).

Where app_synthetic.py and app_real_world.py let a reader explore every
attribute, this page shows only the headline results, block by block, each
with one or two charts and a short table:

  A  old code (08ca567) against new code on the same machine
  C  the current DPP (vector lists) against the lean DPP: memory and time
  B+E  the final code on every synthetic dataset, N = 2300 to 30000
  D  real-world datasets, and pigeons with and without repeated points

Synthetic timings are single runs on each pair; the numbers are means over the
pairs of one dataset file (1 to 3 pairs).

Usage:
    python analysis/app_aws_2026_11.py results_aws_2026_11 -o analysis/output/aws_2026_11/overview.html
"""

import argparse
import html
import json
import os

import pandas as pd
import plotly.graph_objects as go
import plotly.offline
from plotly.subplots import make_subplots

import algorithm_styles

BG, PANEL, FG, MUTED, GRID = "#0a0a0a", "#101010", "#f2f2f2", "#888888", "#2e2e2e"
FONT = "ui-monospace, 'SF Mono', 'Cascadia Code', Consolas, 'Roboto Mono', monospace"

DATASET_ORDER = ["random", "identical", "outlier", "outlier_swapped", "alternating",
                 "alternating_swapped", "alternating_cheap_column"]
DATASET_COLORS = {"drifter": "#C77DFF", "geolife": "#FFD23F", "pigeons": "#3DD6D0", "pigeons_dedup": "#FF6FA5"}


def short(name):
    """Algorithm name without the BBMS prefixes, for tight table headers."""
    return name.replace("BBMSDpp", "").replace("BBMS", "").replace("DijkstraPrims", "Dijkstra")


def style_figure(fig, height):
    fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, height=height,
                      font={"color": FG, "family": FONT, "size": 12},
                      margin={"t": 40, "r": 20, "b": 50, "l": 60},
                      legend={"orientation": "h", "y": -0.18, "font": {"color": FG}})
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=MUTED, tickfont={"color": MUTED})
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=MUTED, tickfont={"color": MUTED})
    fig.update_annotations(font={"color": FG})
    return fig


def table(frame, caption=""):
    """A pandas frame as a plain HTML table (index included)."""
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in [frame.index.name or ""] + list(frame.columns))
    rows = []
    for index, row in frame.iterrows():
        cells = "".join(f"<td>{html.escape(str(v))}</td>" for v in row)
        rows.append(f"<tr><th>{html.escape(str(index))}</th>{cells}</tr>")
    cap = f"<div class='caption'>{caption}</div>" if caption else ""
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>{cap}</div>"


def seconds(value):
    if pd.isna(value):
        return "-"
    return f"{value:.2f}" if value < 10 else f"{value:.0f}" if value >= 100 else f"{value:.1f}"


# ---------------------------------------------------------------- block A

def block_a(timing, counts):
    ok = timing[(timing.block == "A") & (timing.outcome == "ok")]
    mean = ok.groupby(["dataset", "m", "algorithm", "code"]).runtime_s.mean().unstack("code").dropna()
    mean["speedup"] = mean.old / mean.new
    mean = mean.reset_index()
    mean["case"] = mean.dataset + " " + mean.m.astype(str)
    cases = [c for d in ["random", "outlier", "alternating", "alternating_swapped"]
             for c in sorted(mean[mean.dataset == d].case.unique(), key=lambda c: int(c.split()[-1]))]

    algorithms = sorted(mean.algorithm.unique(), key=algorithm_styles.sort_key)
    styles = algorithm_styles.styles(algorithms)
    fig = go.Figure()
    for algorithm in algorithms:
        part = mean[mean.algorithm == algorithm].set_index("case").reindex(cases)
        fig.add_bar(name=algorithm, x=cases, y=part.speedup, marker_color=styles[algorithm]["color"],
                    hovertemplate="%{x}<br>" + algorithm + ": %{y:.2f}× faster<extra></extra>")
    fig.add_hline(y=1, line_color=MUTED, line_dash="dot")
    fig.update_yaxes(type="log", tickvals=[1, 1.25, 1.5, 2, 3, 5, 10], ticktext=["1×", "1.25×", "1.5×", "2×", "3×", "5×", "10×"],
                     range=[-0.05, 1.05])
    fig.update_layout(barmode="group", yaxis_title="old time / new time (higher = faster now)",
                      title="Speed-up from the audit fixes, same machine, same pairs")
    style_figure(fig, 460)

    # Table: seconds old -> new, and NCA steps old / new
    steps = counts[(counts.block == "A") & (counts.outcome == "ok")]
    steps = steps.groupby(["dataset", "m", "algorithm", "code"]).total_nca_steps.mean().unstack("code")
    rows = {}
    for (dataset, m, algorithm), row in mean.set_index(["dataset", "m", "algorithm"]).iterrows():
        text = f"{seconds(row.old)} → {seconds(row.new)} s"
        if (dataset, m, algorithm) in steps.index:
            s = steps.loc[(dataset, m, algorithm)]
            if s.old > 0:
                text += f" · steps ÷{s.old / s.new:.2f}"
        rows.setdefault(f"{dataset} {m}", {})[short(algorithm)] = text
    frame = pd.DataFrame(rows).T.reindex(cases)
    frame = frame[[short(a) for a in algorithms if short(a) in frame.columns]].fillna("-")
    frame.index.name = "dataset, N"
    return fig, table(frame, "Seconds old → new code; “steps ÷x” is old NCA steps divided by new. "
                             "Dijkstra has no NCA steps. Core and Inter were only run where they finish quickly.")


# ---------------------------------------------------------------- block C

def block_c(timing):
    ok = timing[timing.outcome == "ok"]
    current = timing[timing.block == "C"].copy()
    current["algorithm"] += " (current)"
    final = ok[ok.block.isin(["B", "E"]) & ok.algorithm.isin(["BBMSDppStepwiseLean", "BBMSDppInstantLean", "DijkstraPrims", "BBMSCore"])]
    data = pd.concat([current, final])
    data = data[data.dataset.isin(["random", "alternating"]) & data.m.isin([11000, 18000, 30000])]

    algorithms = sorted(data.algorithm.unique(), key=algorithm_styles.sort_key)
    styles = algorithm_styles.styles(algorithms)
    fig = make_subplots(rows=2, cols=2, shared_xaxes=True, vertical_spacing=0.12, horizontal_spacing=0.08,
                        subplot_titles=["random: peak memory (GB)", "alternating: peak memory (GB)",
                                        "random: time (s)", "alternating: time (s)"])
    sizes = ["11000", "18000", "30000"]
    for col, dataset in enumerate(["random", "alternating"], start=1):
        part = data[data.dataset == dataset]
        for algorithm in algorithms:
            rows = part[part.algorithm == algorithm]
            okrows = rows[rows.outcome == "ok"].groupby("m").agg(mem=("maxrss_after_mb", "mean"), rt=("runtime_s", "mean"))
            failed = set(rows[rows.outcome != "ok"].m)
            okrows = okrows.reindex([int(s) for s in sizes])
            mem = okrows.mem / 1024
            labels = ["out of memory" if int(s) in failed else "" for s in sizes]
            style = styles[algorithm]
            pattern = {"shape": "/" if "(current)" in algorithm else ""}
            fig.add_bar(row=1, col=col, x=sizes, y=mem, name=algorithm, legendgroup=algorithm, showlegend=col == 1,
                        marker={"color": style["color"], "pattern": pattern},
                        text=[l or (f"{v:.0f}" if pd.notna(v) else "") for l, v in zip(labels, mem)],
                        textposition="outside", cliponaxis=False,
                        hovertemplate=algorithm + "<br>N=%{x}: %{y:.1f} GB<extra></extra>")
            fig.add_bar(row=2, col=col, x=sizes, y=okrows.rt, name=algorithm, legendgroup=algorithm, showlegend=False,
                        marker={"color": style["color"], "pattern": pattern},
                        hovertemplate=algorithm + "<br>N=%{x}: %{y:.1f} s<extra></extra>")
        failed_sizes = sorted({str(m) for m in part[part.outcome != "ok"].m})
        if failed_sizes:
            fig.add_scatter(row=1, col=col, x=failed_sizes, y=[105] * len(failed_sizes), mode="markers+text",
                            marker={"symbol": "hexagon", "color": "#F25F5C", "size": 12}, showlegend=False,
                            text=["current DPP:<br>out of memory"] * len(failed_sizes), textposition="bottom center",
                            textfont={"color": FG, "size": 11}, hoverinfo="skip")
    fig.add_hline(y=124, row=1, col="all", line_color="#F25F5C", line_dash="dot",
                  annotation_text="machine: 124 GB", annotation_font_color=MUTED)
    fig.update_layout(barmode="group", title="Current DPP against lean DPP (hatched = current)")
    fig.update_xaxes(title_text="N", row=2)
    style_figure(fig, 700)
    fig.update_layout(margin={"t": 90})

    # Table: GB and seconds per algorithm and N
    rows = {}
    for (dataset, m, algorithm), g in data.groupby(["dataset", "m", "algorithm"]):
        okg = g[g.outcome == "ok"]
        rows.setdefault(f"{dataset} {m}", {})[short(algorithm)] = (
            "out of memory" if okg.empty else f"{okg.maxrss_after_mb.mean() / 1024:.1f} GB, {seconds(okg.runtime_s.mean())} s")
    frame = pd.DataFrame(rows).T
    frame = frame[[short(a) for a in algorithms if short(a) in frame.columns]].fillna("-")
    frame.index.name = "dataset, N"
    return fig, table(frame, "Peak memory of the process and time, the mean over the 1 to 3 pairs of one size. "
                             "“-” means not run: InstantLean was left out at N = 30000 to save time.")


# ---------------------------------------------------------------- blocks B and E

def block_be(timing):
    ok = timing[timing.block.isin(["B", "E"]) & (timing.outcome == "ok")]
    mean = ok.groupby(["dataset", "m", "algorithm"]).runtime_s.mean().reset_index()
    algorithms = sorted(mean.algorithm.unique(), key=algorithm_styles.sort_key)
    styles = algorithm_styles.styles(algorithms)
    datasets = [d for d in DATASET_ORDER if d in set(mean.dataset)]

    fig = make_subplots(rows=4, cols=2, subplot_titles=datasets, vertical_spacing=0.07, horizontal_spacing=0.08)
    for i, dataset in enumerate(datasets):
        r, c = i // 2 + 1, i % 2 + 1
        for algorithm in algorithms:
            part = mean[(mean.dataset == dataset) & (mean.algorithm == algorithm) & (mean.runtime_s > 0)].sort_values("m")
            if part.empty:
                continue
            style = styles[algorithm]
            fig.add_scatter(row=r, col=c, x=part.m, y=part.runtime_s, mode="lines+markers", name=algorithm,
                            legendgroup=algorithm, showlegend=i == 0,
                            line={"color": style["color"], "dash": style["dash"]},
                            marker={"symbol": style["symbol"], "color": style["color"], "size": 7},
                            hovertemplate=algorithm + "<br>N=%{x}: %{y:.2f} s<extra></extra>")
    fig.update_xaxes(type="log", tickvals=[2300, 6500, 11000, 18000, 30000], ticktext=["2300", "6500", "11k", "18k", "30k"])
    fig.update_yaxes(type="log", title_text="s", dtick=1)
    fig.update_layout(title="Time against N, final code (log-log). Lines end where the plan stopped them, not at a failure")
    style_figure(fig, 1150)
    fig.update_layout(legend={"y": -0.05}, margin={"t": 90})

    # Ratio chart: Dijkstra time / StepwiseLean time
    wide = mean.pivot_table(index=["dataset", "m"], columns="algorithm", values="runtime_s")
    ratio = (wide.DijkstraPrims / wide.BBMSDppStepwiseLean).dropna().reset_index(name="ratio")
    ratio = ratio[ratio.dataset != "identical"]
    # One colour per source set; the swapped and cheap-column variants are dashed and dotted
    looks = {"random": ("#C77DFF", "solid"), "outlier": ("#FFD23F", "solid"), "outlier_swapped": ("#FFD23F", "dash"),
             "alternating": ("#3DD6D0", "solid"), "alternating_swapped": ("#3DD6D0", "dash"),
             "alternating_cheap_column": ("#3DD6D0", "dot")}
    fig2 = go.Figure()
    for dataset in [d for d in DATASET_ORDER if d in set(ratio.dataset)]:
        part = ratio[ratio.dataset == dataset].sort_values("m")
        color, dash = looks.get(dataset, ("#FF6FA5", "solid"))
        fig2.add_scatter(x=part.m, y=part.ratio, mode="lines+markers", name=dataset,
                         line={"color": color, "dash": dash}, marker={"size": 8},
                         hovertemplate=dataset + "<br>N=%{x}: Dijkstra takes %{y:.2f}× as long<extra></extra>")
    fig2.add_hline(y=1, line_color=MUTED, line_dash="dot", annotation_text="equal", annotation_font_color=MUTED)
    fig2.update_xaxes(type="log", tickvals=[2300, 6500, 11000, 18000, 30000], ticktext=["2300", "6500", "11k", "18k", "30k"], title_text="N")
    fig2.update_yaxes(type="log", title_text="Dijkstra time / StepwiseLean time", tickvals=[1, 2, 3, 5, 7, 10])
    fig2.update_layout(title="How many times longer DijkstraPrims takes than StepwiseLean (above 1 = StepwiseLean wins)")
    style_figure(fig2, 440)

    # Table at N = 11000 (largest N every dataset has)
    at = mean[mean.m == 11000].pivot_table(index="dataset", columns="algorithm", values="runtime_s")
    at = at.reindex([d for d in DATASET_ORDER if d in at.index])
    at = at[[a for a in algorithms if a in at.columns]]
    frame = at.map(seconds)
    frame.columns = [short(a) for a in at.columns]
    frame["Dijkstra ÷ StepwiseLean"] = (at.DijkstraPrims / at.BBMSDppStepwiseLean).map(lambda v: f"{v:.1f}×" if v > 0.01 else "-")
    frame.index.name = "N = 11000"
    mem = ok[ok.m == 11000].groupby("algorithm").maxrss_after_mb.max() / 1024
    caption = ("Seconds at N = 11000. “-”: not run at this size (Core only up to 6500, Inter not on the alternating sets "
               "above 2300). On identical, Dijkstra finishes instantly because the diagonal is free, so the ratio is left out. "
               "Peak memory at this size: " + ", ".join(f"{short(a)} {mem[a]:.1f} GB" for a in algorithms if a in mem.index) + ".")
    return fig, fig2, table(frame, caption)


# ---------------------------------------------------------------- block D

def block_d(timing):
    data = timing[timing.block == "D"].copy()
    data["algorithm"] = data.algorithm.replace({"BBMSDppStepwise": "BBMSDppStepwise (current)"})
    ok = data[data.outcome == "ok"]
    datasets = ["drifter", "geolife", "pigeons", "pigeons_dedup"]

    # Scatter: per pair, Dijkstra time / StepwiseLean time against cells
    wide = ok.pivot_table(index=["dataset", "file", "pair", "cells"], columns="algorithm", values="runtime_s").reset_index()
    wide["ratio"] = wide.DijkstraPrims / wide.BBMSDppStepwiseLean
    fig = go.Figure()
    for dataset in datasets:
        part = wide[wide.dataset == dataset]
        fig.add_scatter(x=part.cells, y=part.ratio, mode="markers", name=f"{dataset} ({len(part)} pairs)",
                        marker={"color": DATASET_COLORS[dataset], "size": 7, "opacity": 0.75},
                        hovertemplate=dataset + "<br>%{x:.3s} cells<br>Dijkstra takes %{y:.2f}× as long<extra></extra>")
    fig.add_hline(y=1, line_color=MUTED, line_dash="dot", annotation_text="equal", annotation_font_color=MUTED)
    fig.update_xaxes(type="log", title_text="cells (m × n)")
    fig.update_yaxes(type="log", title_text="Dijkstra time / StepwiseLean time", dtick=1)
    fig.update_layout(title="Real-world pairs: above 1 StepwiseLean wins, below 1 DijkstraPrims wins")
    style_figure(fig, 480)

    # Summary table per dataset and algorithm
    algorithms = sorted(data.algorithm.unique(), key=algorithm_styles.sort_key)
    rows = {}
    for dataset in datasets:
        part = data[data.dataset == dataset]
        pivot = ok[ok.dataset == dataset].pivot_table(index=["file", "pair"], columns="algorithm", values="runtime_s")
        for algorithm in algorithms:
            runs = part[part.algorithm == algorithm]
            if runs.empty:
                continue
            outcome = runs.outcome.value_counts()
            failed = ", ".join(f"{n} {k}" for k, n in outcome.items() if k != "ok")
            text = f"{outcome.get('ok', 0)} ok" + (f", {failed}" if failed else "")
            if algorithm != "DijkstraPrims" and algorithm in pivot:
                common = pivot[[algorithm, "DijkstraPrims"]].dropna()
                text += f" · {common[algorithm].sum():.0f} s vs Dijkstra {common.DijkstraPrims.sum():.0f} s"
            else:
                text += f" · {runs.runtime_s.sum():.0f} s"
            rows.setdefault(dataset, {})[short(algorithm)] = text
    frame = pd.DataFrame(rows).T
    frame = frame[[short(a) for a in algorithms if short(a) in frame.columns]].fillna("not run")
    frame.index.name = "dataset"
    caption = ("Per algorithm: pairs that finished, failed ones, and total time against DijkstraPrims on the same pairs. "
               "Limit 300 s per run. On pigeons, Inter, InstantLean and the current Stepwise were only run on the pairs "
               "below 100 million cells (plus the largest pair for the current Stepwise); Core was not run there.")

    # Pigeons: current Stepwise against lean, per pair
    pig = data[(data.dataset == "pigeons") & data.algorithm.isin(["BBMSDppStepwise (current)", "BBMSDppStepwiseLean", "DijkstraPrims"])]
    pw = pig.pivot_table(index=["file", "pair", "cells"], columns="algorithm", values=["runtime_s", "maxrss_after_mb"], aggfunc="first")
    pw = pw[pw[("runtime_s", "BBMSDppStepwise (current)")].notna()]
    lines = []
    for (file, pair, cells), row in pw.sort_index(level="cells").iterrows():
        cur_t = row[("runtime_s", "BBMSDppStepwise (current)")]
        cur_m = row[("maxrss_after_mb", "BBMSDppStepwise (current)")]
        if pd.isna(cur_t):
            continue
        failed = (pig[(pig.pair == pair) & (pig.file == file) & (pig.algorithm == "BBMSDppStepwise (current)")].outcome != "ok").any()
        lines.append({"cells": f"{cells / 1e6:.0f} M",
                      "current Stepwise": "out of memory" if failed else f"{seconds(cur_t)} s, {cur_m / 1024:.1f} GB",
                      "StepwiseLean": f"{seconds(row[('runtime_s', 'BBMSDppStepwiseLean')])} s, {row[('maxrss_after_mb', 'BBMSDppStepwiseLean')] / 1024:.1f} GB",
                      "Dijkstra": f"{seconds(row[('runtime_s', 'DijkstraPrims')])} s, {row[('maxrss_after_mb', 'DijkstraPrims')] / 1024:.1f} GB"})
    pig_frame = pd.DataFrame(lines).set_index("cells")
    pig_table = table(pig_frame, "Pigeon pairs where the current Stepwise ran, smallest first: time and peak memory. "
                                 "On the largest pair (678 million cells) the current version runs out of the 124 GB, "
                                 "the lean one finishes with 34 GB.")

    # Pigeons with and without repeated points
    both = ok[ok.dataset.isin(["pigeons", "pigeons_dedup"]) & ok.algorithm.isin(["BBMSDppStepwiseLean", "DijkstraPrims"])]
    totals = both.groupby(["dataset", "algorithm"]).runtime_s.sum().unstack("dataset")
    pairs = data[data.dataset.isin(["pigeons", "pigeons_dedup"])].drop_duplicates(["dataset", "file", "pair"])
    cells = pairs.groupby("dataset").cells.median()
    fig2 = go.Figure()
    styles = algorithm_styles.styles(list(totals.index))
    for algorithm in totals.index:
        fig2.add_bar(name=algorithm, x=["pigeons (raw)", "pigeons_dedup (repeats removed)"],
                     y=[totals.loc[algorithm, "pigeons"], totals.loc[algorithm, "pigeons_dedup"]],
                     marker_color=styles[algorithm]["color"], texttemplate="%{y:.0f} s", textposition="outside",
                     cliponaxis=False)
    fig2.update_layout(barmode="group", yaxis_title="total seconds over the 36 pairs",
                       title=f"Removing repeated points: median pair shrinks from {cells['pigeons'] / 1e6:.0f} M to "
                             f"{cells['pigeons_dedup'] / 1e6:.1f} M cells")
    style_figure(fig2, 420)
    return fig, table(frame, caption), pig_table, fig2


# ---------------------------------------------------------------- page

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWS run, November 2026</title>
<style>
  :root { --bg: #0a0a0a; --panel: #101010; --fg: #f2f2f2; --muted: #888; --border: #2e2e2e; }
  body { margin: 0; background: var(--bg); color: var(--fg);
         font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace; }
  main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 64px; }
  h1 { font-size: 1.3rem; margin: 0 0 6px; }
  h2 { font-size: 1.05rem; margin: 48px 0 8px; padding-top: 16px; border-top: 1px solid var(--border); }
  p, li { color: #d0d0d0; line-height: 1.55; font-size: 0.88rem; max-width: 900px; }
  .sub { color: var(--muted); font-size: 0.8rem; }
  .chart { border: 1px solid var(--border); border-radius: 4px; background: var(--panel); margin: 12px 0; }
  .table-wrap { overflow-x: auto; margin: 12px 0; }
  table { border-collapse: collapse; font-size: 0.78rem; white-space: nowrap; }
  th, td { border-bottom: 1px solid var(--border); padding: 6px 10px; text-align: left; }
  thead th { color: var(--muted); font-weight: 700; }
  tbody th { font-weight: 400; color: var(--muted); }
  .caption { color: var(--muted); font-size: 0.75rem; margin-top: 8px; white-space: normal; max-width: 900px; line-height: 1.5; }
  nav a { color: var(--fg); margin-right: 14px; font-size: 0.82rem; }
</style></head><body><main>
<h1>AWS run, November 2026</h1>
<div class="sub">__META__</div>
<p>__INTRO__</p>
<nav><a href="#a">A · before and after</a><a href="#c">C · lean DPP memory</a><a href="#be">B+E · synthetic</a><a href="#d">D · real-world</a></nav>
__BODY__
</main>
<script>__PLOTLY__</script>
<script>
const FIGURES = __FIGURES__;
for (const [id, fig] of Object.entries(FIGURES)) {
  Plotly.newPlot(id, fig.data, fig.layout, {responsive: true, displaylogo: false});
}
</script></body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_folder")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    timing = pd.read_csv(os.path.join(args.results_folder, "timing.csv"))
    counts = pd.read_csv(os.path.join(args.results_folder, "counts.csv"))

    # Correctness: every algorithm on one code version must report the same distance for a pair
    ok = pd.concat([timing, counts])
    ok = ok[ok.outcome == "ok"]
    spread = ok.groupby(["code", "dataset", "file", "pair"]).frechet_dist.agg(lambda s: s.max() - s.min())
    pairs = ok.drop_duplicates(["dataset", "file", "pair"]).shape[0]
    outcomes = timing.outcome.value_counts().to_dict()

    figures, body = {}, []

    def chart(name, fig):
        figures[name] = json.loads(fig.to_json())
        return f"<div class='chart' id='{name}'></div>"

    fig_a, table_a = block_a(timing, counts)
    body.append("<h2 id='a'>A · Before and after the audit fixes</h2>"
                "<p>The old code (commit 08ca567, before the audit) and the new code ran on the same pairs on this machine. "
                "The fixes: two NCA queries per cell instead of three, removal of shortcuts from the back of the lists "
                "instead of the front, squared distances, and one hash lookup per neighbour in DijkstraPrims. "
                "The DPP variants gain most, up to almost 10× on alternating at N = 11000. DijkstraPrims stays the same, "
                "as expected, so the gap between the two families changed because of BBMS, not because of the machine.</p>"
                + chart("fig_a", fig_a) + table_a)

    fig_c, table_c = block_c(timing)
    body.append("<h2 id='c'>C · Current DPP against lean DPP</h2>"
                "<p>The lean DPP variants keep the exact same algorithm (same parent choices, matchings and operation counts, "
                "checked by a test) but store it in about a quarter of the memory: linked lists through the shortcuts "
                "instead of a vector per cell, reuse of dead shortcuts, and 32-bit positions instead of pointers. "
                "The current DPP needs 69 GB at N = 18000 and runs out of the 124 GB at N = 30000. StepwiseLean needs "
                "15 to 22 GB at N = 18000 and finishes N = 30000 with 40 to 60 GB. The lean versions are also faster: StepwiseLean 1.9 to 3.6×, InstantLean 1.3 to 3.8×.</p>"
                + chart("fig_c", fig_c) + table_c)

    fig_be, fig_ratio, table_be = block_be(timing)
    body.append("<h2 id='be'>B + E · All synthetic datasets with the final code</h2>"
                "<p>Every synthetic dataset, N = 2300 to 30000. The swapped sets are the same pairs with the two curves "
                "exchanged; the cheap-column set is alternating with a cheap first column, which makes DijkstraPrims visit "
                "cells in a jumbled order. StepwiseLean is faster than DijkstraPrims on every pair of the alternating sets "
                "(about 5 to 10×) and the outlier sets (about 3×). On all of these DijkstraPrims visits every cell, so they "
                "are worst cases for it. On random the winner depends on the pair: DijkstraPrims is faster on 5 of the 13 "
                "random pairs, and the means below (1.0 to 2.1×) hide that. On identical DijkstraPrims wins easily. "
                "DijkstraPrims still uses a hash map here; see SUMMARY.md section 6 on fairness.</p>"
                + chart("fig_ratio", fig_ratio) + table_be + chart("fig_be", fig_be))

    fig_d, table_d, table_pig, fig_dedup = block_d(timing)
    body.append("<h2 id='d'>D · Real-world datasets</h2>"
                "<p>The real-world sets after the generator fixes: one shared projection per pair, longitudes continuous "
                "across the date line, drifter pairs from one region, and pigeons_dedup, the pigeon pairs with "
                "repeated points removed. Here the picture is mixed. On drifter StepwiseLean wins on 3 of 4 pairs; "
                "on geolife the two are about equal in total, DijkstraPrims slightly ahead; on raw pigeons DijkstraPrims "
                "is about 6× faster. Every BBMS variant visits every cell, while DijkstraPrims stops at the end cell, after "
                "a median 24 % of the cells on pigeons. StepwiseLean also spends about 3× longer per cell on raw pigeons "
                "(334 ns) than without the repeats (107 ns), with the same NCA steps per cell; that is not explained yet. "
                "Removing the repeats makes the grids 23× smaller in total: StepwiseLean's total drops from about 2500 s "
                "to 35 s (72×), DijkstraPrims's from 410 s to 30 s (14×).</p>"
                + chart("fig_d", fig_d) + table_d + chart("fig_dedup", fig_dedup)
                + "<p>The current Stepwise against the lean one on the same pigeon pairs: the lean one is about 2× faster "
                  "on the smaller pairs and about as fast (within 15 %) on the larger ones, uses 2.4 to 4× less memory, "
                  "and only the lean one finishes the largest pair.</p>" + table_pig)

    meta = (f"Amazon EC2, 4 vCPU, 124 GB, eu-central-1 · 14 Nov 2026, 00:24 - 11:09 UTC · "
            f"{len(timing)} timing runs and {len(counts)} counting runs · outcomes: "
            + ", ".join(f"{n} {k}" for k, n in outcomes.items()))
    intro = (f"One job at a time, limit 300 s per real-world run, memory capped at 90 % of the machine. "
             f"Correctness: on each of the {pairs} pairs, every algorithm of one code version that finished reports the same "
             f"Fréchet distance ({int((spread > 1e-9).sum())} differences). Synthetic times are single runs, averaged over the "
             f"1 to 3 pairs of a dataset file.")
    page = (PAGE.replace("__META__", html.escape(meta)).replace("__INTRO__", intro)
            .replace("__BODY__", "\n".join(body)).replace("__PLOTLY__", plotly.offline.get_plotlyjs())
            .replace("__FIGURES__", json.dumps(figures)))
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
