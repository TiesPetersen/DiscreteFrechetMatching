"""
Reads a results_real_world/-style folder (experiment/real-world/main.py's output)
and writes a single self-contained interactive HTML report. Closely based on
analysis/app_synthetic.py's page shell (tabs, attribute list, axis controls),
but the data model underneath is genuinely different, because real-world curve
pairs have no shared "N" grid the way synthetic ones do:

  - Each dataset is a scatter of independent pairs, not a line across N. The
    x-axis is `cells` (m*n) instead of N -- the natural per-pair "size" measure
    -- log-scaled by default since real pair sizes span from a few thousand to
    several hundred million cells. Every point is one pair; there's no
    aggregation across "samples at the same N" because there is no such group.
  - Failed pairs (timeout/oom) are still shown -- as small marker-only traces
    along the bottom of the plot at their actual cells value, using the same
    hourglass/hexagon symbols as the synthetic report's wall markers -- rather
    than just vanishing, since with fair (unfiltered) sampling the failure
    *pattern* across pair sizes is itself one of the findings, not just a
    cutoff point.
  - The data table is a compact per-algorithm/dataset summary (ok/timeout/oom
    counts, mean/median/IQR of the attribute among ok pairs) rather than a
    per-N row breakdown, since with ~100-3000+ pairs per dataset there's no
    single grouping key worth turning into a table row.
  - Timing repeats (3 per pair) are still reduced via min-across-repeats before
    plotting, same rationale as analysis/app_synthetic.py's aggregate(): they
    measure the same pair repeatedly, so the minimum is the best estimate of
    true cost.

Usage:
    python analysis/app_real_world.py                     # reads <repo-root>/results_real_world
    python analysis/app_real_world.py results_foo          # reads a different folder
    python analysis/app_real_world.py results_foo -o out.html
"""

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict

import plotly.offline

KNOWN_ALGORITHM_ORDER = ["BBMSCore", "BBMSInter", "BBMSDppInstant", "BBMSDppStepwise", "DijkstraPrims"]

ALGORITHM_STYLE_PALETTE = [
    {"color": "#4E9BFF", "symbol": "circle"},
    {"color": "#FF8C42", "symbol": "square"},
    {"color": "#5FD068", "symbol": "diamond"},
    {"color": "#F25F5C", "symbol": "triangle-up"},
    {"color": "#70E0F0", "symbol": "triangle-down"},
    {"color": "#B4A0FF", "symbol": "x"},
]
DATASET_STYLE_PALETTE = [
    {"color": "#C77DFF", "symbol": "circle"},
    {"color": "#FFD23F", "symbol": "square"},
    {"color": "#3DD6D0", "symbol": "diamond"},
    {"color": "#FF6FA5", "symbol": "triangle-up"},
    {"color": "#8FE388", "symbol": "triangle-down"},
    {"color": "#FFB56B", "symbol": "x"},
]

NON_ATTRIBUTE_COLUMNS = {"algorithm", "pair_index", "m", "n", "cells", "repeat", "status"}

PASSES = [("Timing & Memory", "timing_memory.csv"), ("Operation Counts", "opcounts.csv")]

ATTRIBUTE_DESCRIPTIONS = {
    "runtime_s": "How long the algorithm took to run, in seconds.",
    "frechet_dist": "The computed distance between the two curves.",
    "maxrss_before_mb": "Memory used right before the algorithm started, in MB.",
    "maxrss_after_mb": "Memory used right after the algorithm finished, in MB.",
    "minor_faults": "Times memory was loaded without needing the disk.",
    "major_faults": "Times memory had to be loaded from disk.",
    "block_input_ops": "Number of disk read operations.",
    "block_output_ops": "Number of disk write operations.",
    "voluntary_ctx_switches": "Times the program paused itself, e.g. to wait for something.",
    "involuntary_ctx_switches": "Times the program was interrupted by the system.",
    "user_time_s": "Time spent actually running the algorithm's own code.",
    "sys_time_s": "Time spent on system-level tasks on the algorithm's behalf.",
    "blocked_time_s": "Time spent waiting instead of actively running.",
    "nca_regular_hops": "Steps taken walking up the tree one node at a time.",
    "nca_shortcut_hops": "Steps taken jumping up the tree using a shortcut.",
    "total_nca_steps": "Total steps taken walking up the tree (regular + shortcut).",
    "shortcuts_written": "Number of shortcuts created during the run.",
    "dead_paths_pruned": "Number of dead paths removed from the tree.",
    "shortcuts_extended": "Number of existing shortcuts redirected further up the tree.",
    "dead_path_walk_steps": "Steps taken walking up dead paths to remove shortcuts.",
    "heap_pushes": "Number of grid cells added to the algorithm's heap.",
    "heap_pops": "Number of grid cells taken off the heap to process.",
    "max_heap_size": "The largest the heap ever got during the run.",
    "avg_heap_size": "The heap's typical size while cells were being processed.",
    "cells_processed": "Number of grid cells the algorithm actually examined.",
    "pct_cells_explored": "Percentage of the whole grid the algorithm actually examined.",
}

STARRED_TIMING_ATTRIBUTES = {"runtime_s", "maxrss_after_mb"}

STATUS_MARKER_SYMBOLS = {"timeout": "hourglass", "oom": "hexagon", "error": "asterisk"}

ZERO_EPSILON = 1e-12


def discover_datasets(results_root):
    if not os.path.isdir(results_root):
        return []
    names = []
    for name in sorted(os.listdir(results_root)):
        path = os.path.join(results_root, name)
        if os.path.isdir(path) and any(os.path.exists(os.path.join(path, f)) for _, f in PASSES):
            names.append(name)
    return names


def load_rows(csv_path):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def attribute_columns(rows):
    if not rows:
        return []
    return [c for c in rows[0].keys() if c not in NON_ATTRIBUTE_COLUMNS]


def discover_algorithms(results_root, datasets):
    seen = []
    for dataset in datasets:
        for _, filename in PASSES:
            for row in load_rows(os.path.join(results_root, dataset, filename)):
                if row["algorithm"] not in seen:
                    seen.append(row["algorithm"])
    ordered = [a for a in KNOWN_ALGORITHM_ORDER if a in seen]
    ordered += [a for a in seen if a not in ordered]
    return ordered


def assign_styles(names, palette):
    return {name: palette[i % len(palette)] for i, name in enumerate(names)}


def status_counts(rows, algorithms):
    """{algorithm: {"ok": n, "timeout": n, "oom": n, "error": n}} across every
    row for that algorithm in this pass -- the completion-rate itself is a
    finding here, since fair (unfiltered) sampling means failures are expected
    at a real, reportable rate rather than being cut off at a single N."""
    counts = {a: defaultdict(int) for a in algorithms}
    for row in rows:
        counts[row["algorithm"]][row["status"]] += 1
    return counts


def aggregate_by_pair(rows, attribute):
    """[(cells, value), ...] sorted by cells, for every pair with an ok row --
    min across repeats first (repeats measure the same pair, see module
    docstring). Returns only successful pairs; failures are handled separately
    via status_counts + the marker traces in build_figure."""
    best = {}  # pair_index -> (cells, value)
    for row in rows:
        if row["status"] != "ok":
            continue
        try:
            value = float(row[attribute])
        except (KeyError, ValueError):
            continue
        if value == -1:
            continue
        pair_index = row["pair_index"]
        cells = int(row["cells"])
        if pair_index not in best or value < best[pair_index][1]:
            best[pair_index] = (cells, value)
    return sorted(best.values())


def failed_cells(rows, status):
    """cells values (one per pair, deduplicated) where this exact status
    occurred at least once for this algorithm -- used to plot the marker-only
    failure traces."""
    out = set()
    for row in rows:
        if row["status"] == status:
            out.add(int(row["cells"]))
    return sorted(out)


def is_structurally_absent(points):
    return all(abs(v) < ZERO_EPSILON for _, v in points)


def all_series_absent(series_by_trace):
    return all(is_structurally_absent(points) for points in series_by_trace.values())


PLOT_BG = "#0a0a0a"
PLOT_FG = "#f2f2f2"
PLOT_MUTED = "#888888"
PLOT_GRID = "#2e2e2e"
PLOT_FONT_FAMILY = "ui-monospace, 'SF Mono', 'Cascadia Code', Consolas, 'Roboto Mono', monospace"


def build_figure(attribute, points_by_trace, trace_order, style_map, rows_by_trace):
    """Scatter plot: one marker-only trace per algorithm/dataset with real (ok)
    data, x=cells (log by default), y=attribute value -- no lines, since pairs
    aren't ordered/comparable to each other the way N-grid points are. Failed
    pairs get their own small marker-only traces along y=0 in their own
    algorithm's color, using the same failure symbols as the synthetic
    report's wall markers, so the failure pattern across pair sizes is visible
    on the graph itself rather than just silently missing."""
    data = []
    any_points = False
    for name in trace_order:
        points = points_by_trace.get(name, [])
        if points and not is_structurally_absent(points):
            any_points = True
    y_floor = 0

    for name in trace_order:
        points = points_by_trace.get(name, [])
        style = style_map.get(name, ALGORITHM_STYLE_PALETTE[0])
        if points and not is_structurally_absent(points):
            xs = [c for c, _ in points]
            ys = [v for _, v in points]
            data.append({
                "x": xs, "y": ys, "mode": "markers", "name": name,
                "marker": {"symbol": style["symbol"], "color": style["color"], "size": 6, "opacity": 0.75},
            })

        rows = rows_by_trace.get(name, [])
        for status, symbol in STATUS_MARKER_SYMBOLS.items():
            fail_x = failed_cells(rows, status)
            if not fail_x:
                continue
            data.append({
                "x": fail_x, "y": [y_floor] * len(fail_x), "mode": "markers",
                "name": f"{name}: {status}", "showlegend": False,
                "hoverinfo": "name+x", "hoverlabel": {"namelength": -1},
                "marker": {"symbol": symbol, "color": style["color"], "size": 11, "line": {"width": 0}},
            })

    layout = {
        "title": {"text": attribute, "font": {"color": PLOT_FG}},
        "paper_bgcolor": PLOT_BG,
        "plot_bgcolor": PLOT_BG,
        "font": {"color": PLOT_FG, "family": PLOT_FONT_FAMILY},
        "xaxis": {"title": {"text": "cells (m × n)"}, "type": "log", "gridcolor": PLOT_GRID,
                  "zerolinecolor": PLOT_GRID, "linecolor": PLOT_MUTED, "tickfont": {"color": PLOT_MUTED}},
        "yaxis": {"title": {"text": attribute}, "type": "linear", "gridcolor": PLOT_GRID,
                  "zerolinecolor": PLOT_GRID, "linecolor": PLOT_MUTED, "tickfont": {"color": PLOT_MUTED}},
        "margin": {"t": 48, "r": 24, "b": 48, "l": 64},
        "legend": {"orientation": "h", "y": -0.2, "font": {"color": PLOT_FG}},
    }
    return {"data": data, "layout": layout}


def build_box_figure(attribute, points_by_trace, trace_order, style_map, group_label):
    """One box trace per algorithm/dataset, x-axis = trace name (categorical)
    instead of cells -- shows the same ok-pair values as build_figure's
    scatter, but grouped into a per-trace distribution (median + IQR box)
    with every individual point overlaid and jittered, so the spread across
    algorithms/datasets is comparable independent of pair size. Only ok pairs
    have a value to plot here at all; failures are already covered by the
    marker traces in build_figure, so this chart doesn't repeat them."""
    data = []
    for name in trace_order:
        points = points_by_trace.get(name, [])
        if not points or is_structurally_absent(points):
            continue
        style = style_map.get(name, ALGORITHM_STYLE_PALETTE[0])
        ys = [v for _, v in points]
        data.append({
            "type": "box", "y": ys, "name": name,
            "boxpoints": "all", "jitter": 0.4, "pointpos": 0,
            "marker": {"color": style["color"], "size": 4, "opacity": 0.6},
            "line": {"color": style["color"]},
            "fillcolor": "rgba(0,0,0,0)",
        })

    layout = {
        "title": {"text": f"{attribute} by {group_label}", "font": {"color": PLOT_FG}},
        "paper_bgcolor": PLOT_BG,
        "plot_bgcolor": PLOT_BG,
        "font": {"color": PLOT_FG, "family": PLOT_FONT_FAMILY},
        "showlegend": False,
        "xaxis": {"type": "category", "gridcolor": PLOT_GRID,
                  "zerolinecolor": PLOT_GRID, "linecolor": PLOT_MUTED, "tickfont": {"color": PLOT_MUTED}},
        "yaxis": {"title": {"text": attribute}, "type": "linear", "gridcolor": PLOT_GRID,
                  "zerolinecolor": PLOT_GRID, "linecolor": PLOT_MUTED, "tickfont": {"color": PLOT_MUTED}},
        "margin": {"t": 48, "r": 24, "b": 48, "l": 64},
    }
    return {"data": data, "layout": layout}


def fmt(value):
    return f"{value:.4g}"


def cell(value, note=None):
    return {"value": value, "note": note}


def build_table(points_by_trace, counts_by_trace, trace_order):
    """One column per trace (algorithm/dataset), rows = ok/timeout/oom/error
    counts followed by mean/median/IQR/min/max among the ok pairs -- a compact
    summary rather than a per-N breakdown, since there's no grouping key
    smaller than "every pair" to build rows from.

    Each cell is {value, note}: `max` gets a note when this trace also has
    timeouts or OOMs, since neither produces a value at all -- the true max
    (whatever that pair would have reached) is unknown and could be higher,
    so the displayed max is a lower bound on the real one, not the real one."""
    stat_rows = ["ok", "timeout", "oom", "error", "mean", "median", "IQR 25-75%", "min", "max"]
    table = {"stat": stat_rows}
    for name in trace_order:
        points = points_by_trace.get(name, [])
        counts = counts_by_trace.get(name, {})
        values = [v for _, v in points]
        n_timeout = counts.get("timeout", 0)
        n_oom = counts.get("oom", 0)
        col = [cell(str(counts.get("ok", 0))), cell(str(n_timeout)),
               cell(str(n_oom)), cell(str(counts.get("error", 0)))]
        if values:
            q1, q3 = (statistics.quantiles(values, n=4, method="inclusive")[0],
                      statistics.quantiles(values, n=4, method="inclusive")[2]) if len(values) >= 2 else (values[0], values[0])
            reasons = []
            if n_timeout > 0:
                reasons.append(f"{n_timeout} timed out")
            if n_oom > 0:
                reasons.append(f"{n_oom} ran out of memory")
            max_note = (f"not accurate: {', '.join(reasons)}, true max may be higher"
                        if reasons else None)
            col += [cell(fmt(sum(values) / len(values))), cell(fmt(statistics.median(values))),
                    cell(f"[{fmt(q1)}, {fmt(q3)}]"), cell(fmt(min(values))),
                    cell(fmt(max(values)), max_note)]
        else:
            col += [cell("—")] * 5
        table[name] = col
    return table


def build_report(results_root):
    datasets = discover_datasets(results_root)
    if not datasets:
        print(f"No dataset folders with timing_memory.csv/opcounts.csv found under "
              f"{results_root}", file=sys.stderr)
        sys.exit(1)
    algorithms = discover_algorithms(results_root, datasets)

    # raw_rows[pass_name][dataset] = rows ; raw_points[pass_name][attr][algo][dataset] = points
    raw_rows = defaultdict(lambda: defaultdict(list))
    raw_points = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    attrs_by_pass = defaultdict(list)

    for dataset in datasets:
        dataset_path = os.path.join(results_root, dataset)
        for pass_name, filename in PASSES:
            rows = load_rows(os.path.join(dataset_path, filename))
            raw_rows[pass_name][dataset] = rows
            attrs = attribute_columns(rows)
            seen = attrs_by_pass[pass_name]
            for a in attrs:
                if a not in seen:
                    seen.append(a)
            for attr in attrs:
                raw_points[pass_name][attr][dataset] = aggregate_by_pair(rows, attr)

    default_style_algo = assign_styles(algorithms, ALGORITHM_STYLE_PALETTE)
    default_style_ds = assign_styles(datasets, DATASET_STYLE_PALETTE)

    # --- By dataset: one point-set per algorithm, for a fixed dataset ---
    by_dataset = {}
    for dataset in datasets:
        by_dataset[dataset] = {}
        for pass_name, attrs in attrs_by_pass.items():
            rows = raw_rows[pass_name][dataset]
            rows_by_algo = defaultdict(list)
            for row in rows:
                rows_by_algo[row["algorithm"]].append(row)
            counts_by_algo = status_counts(rows, algorithms)

            figures, box_figures, tables, present_attrs = {}, {}, {}, []
            for attr in attrs:
                points_by_algo = {algo: aggregate_by_pair(rows_by_algo.get(algo, []), attr) for algo in algorithms}
                if all_series_absent(points_by_algo):
                    continue
                present_attrs.append(attr)
                figures[attr] = build_figure(attr, points_by_algo, algorithms, default_style_algo, rows_by_algo)
                box_figures[attr] = build_box_figure(attr, points_by_algo, algorithms, default_style_algo, "algorithm")
                tables[attr] = build_table(points_by_algo, counts_by_algo, algorithms)
            if present_attrs:
                by_dataset[dataset][pass_name] = {"attributes": present_attrs, "figures": figures,
                                                    "box_figures": box_figures, "tables": tables}

    # --- By algorithm: one point-set per dataset, for a fixed algorithm ---
    by_algorithm = {}
    for algo in algorithms:
        by_algorithm[algo] = {}
        for pass_name, attrs in attrs_by_pass.items():
            rows_by_dataset = {}
            for dataset in datasets:
                rows_by_dataset[dataset] = [r for r in raw_rows[pass_name][dataset] if r["algorithm"] == algo]
            counts_by_dataset = {ds: status_counts(rows, [algo])[algo] for ds, rows in rows_by_dataset.items()}

            figures, box_figures, tables, present_attrs = {}, {}, {}, []
            for attr in attrs:
                points_by_ds = {ds: aggregate_by_pair(rows_by_dataset[ds], attr) for ds in datasets}
                if all_series_absent(points_by_ds):
                    continue
                present_attrs.append(attr)
                figures[attr] = build_figure(attr, points_by_ds, datasets, default_style_ds, rows_by_dataset)
                box_figures[attr] = build_box_figure(attr, points_by_ds, datasets, default_style_ds, "dataset")
                tables[attr] = build_table(points_by_ds, counts_by_dataset, datasets)
            if present_attrs:
                by_algorithm[algo][pass_name] = {"attributes": present_attrs, "figures": figures,
                                                   "box_figures": box_figures, "tables": tables}

    return {"by_dataset": by_dataset, "by_algorithm": by_algorithm}, datasets, algorithms


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Real-World Experiment Results</title>
<style>
  :root {
    --bg: #0a0a0a; --bg-panel: #101010; --fg: #f2f2f2; --muted: #888888;
    --border: #2e2e2e; --border-strong: #555555;
    --row-hover: #161616; --row-active: #1c1c1c;
  }
  * { box-sizing: border-box; }
  body { margin: 0;
         font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, "Roboto Mono", monospace;
         background: var(--bg); color: var(--fg); }
  header { padding: 20px 24px; border-bottom: 1px solid var(--border); }
  header h1 { margin: 0; font-size: 1.1rem; font-weight: 700; }
  header .subtitle { color: var(--muted); font-size: 0.78rem; margin-top: 6px;
                      text-transform: uppercase; letter-spacing: 0.05em; }
  .tab-bar { display: flex; align-items: center; gap: 8px; padding: 16px 24px;
             border-bottom: 1px solid var(--border); flex-wrap: wrap; }
  .tab-group { display: flex; gap: 6px; align-items: center; }
  .tab-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
                color: var(--muted); margin-right: 6px; }
  .tab-sep { width: 1px; align-self: stretch; background: var(--border); margin: 0 16px; }
  .tab-bar button { padding: 6px 14px; border: 1px solid var(--border); background: transparent;
                     font-family: inherit; font-size: 0.85rem; cursor: pointer; color: var(--fg);
                     border-radius: 3px; }
  .tab-bar button:hover { border-color: var(--border-strong); }
  .tab-bar button.active { background: var(--fg); color: var(--bg); border-color: var(--fg);
                            font-weight: 700; }
  .layout { display: flex; gap: 24px; padding: 24px; align-items: flex-start; flex-wrap: wrap; }
  .tables { flex: 0 0 340px; display: flex; flex-direction: column; gap: 20px; min-width: 280px; }
  .table-block h2 { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
                     color: var(--muted); margin: 0 0 8px; font-weight: 700; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  td, th { padding: 7px 10px; border-bottom: 1px solid var(--border); text-align: left; }
  .attr-table { border: 1px solid var(--border); }
  .attr-table tbody tr { cursor: pointer; border-left: 2px solid transparent; }
  .attr-table tbody tr:hover { background: var(--row-hover); }
  .attr-table tbody tr.active { background: var(--row-active); font-weight: 700;
                                 border-left-color: var(--fg); }
  .attr-cell { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
  .attr-description { color: var(--muted); font-size: 0.72rem; font-weight: 400; margin-top: 2px; }
  .attr-star { color: #FFD23F; font-size: 0.9rem; flex: 0 0 auto; }
  .main-panel { flex: 1 1 560px; min-width: 360px; display: flex; flex-direction: column; gap: 16px; }
  .graph-panel { border: 1px solid var(--border); border-radius: 4px; padding: 12px;
                 overflow-x: auto; background: var(--bg-panel); }
  .axis-controls { display: flex; gap: 20px; padding: 0 4px 10px; font-size: 0.75rem;
                    color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .axis-controls label { display: flex; align-items: center; gap: 8px; }
  .axis-controls select { background: var(--bg); color: var(--fg); border: 1px solid var(--border);
                           font-family: inherit; font-size: 0.8rem; padding: 3px 6px; border-radius: 3px;
                           text-transform: none; letter-spacing: normal; }
  .status-legend { margin-left: auto; display: flex; align-items: center; gap: 14px;
                    text-transform: none; letter-spacing: normal; }
  .status-legend-note { color: var(--muted); }
  .status-legend-item { display: flex; align-items: center; gap: 5px; }
  .status-marker { font-size: 0.95rem; }
  .cell-note { color: var(--muted); font-size: 0.68rem; margin-top: 3px; white-space: normal; }
  #graph { width: 100%; height: 480px; }
  #graph-box { width: 100%; height: 420px; }
  .data-table-panel { border: 1px solid var(--border); border-radius: 4px; padding: 16px;
                       overflow-x: auto; background: var(--bg-panel); }
  .data-table-panel h3 { margin: 0 0 10px; font-size: 0.78rem; text-transform: uppercase;
                          letter-spacing: 0.05em; color: var(--muted); font-weight: 700; }
  .data-table-panel table { font-size: 0.78rem; white-space: nowrap; }
</style>
</head>
<body>
<header>
  <h1>Real-World Experiment Results</h1>
  <div class="subtitle">Source: __RESULTS_ROOT__ &middot; each point is one curve pair &middot; click any attribute to plot it</div>
</header>
<div class="tab-bar" id="tab-bar"></div>
<div class="layout">
  <div class="tables" id="tables"></div>
  <div class="main-panel">
    <div class="graph-panel">
      <div class="axis-controls">
        <label>X axis:
          <select id="xaxis-type">
            <option value="log" selected>log</option>
            <option value="linear">linear</option>
          </select>
        </label>
        <label>Y axis:
          <select id="yaxis-type">
            <option value="linear" selected>linear</option>
            <option value="log">log</option>
          </select>
        </label>
        <div class="status-legend">
          <span class="status-legend-note">Marker at bottom = that pair size caused a:</span>
          <span class="status-legend-item"><span class="status-marker">&#10710;</span> timeout</span>
          <span class="status-legend-item"><span class="status-marker">&#11041;</span> oom</span>
          <span class="status-legend-item"><span class="status-marker">*</span> error</span>
        </div>
      </div>
      <div id="graph"></div>
    </div>
    <div class="graph-panel">
      <div id="graph-box"></div>
    </div>
    <div class="data-table-panel">
      <h3 id="data-table-title"></h3>
      <div id="data-table"></div>
    </div>
  </div>
</div>

<script>__PLOTLY_JS__</script>
<script>
const REPORT = __REPORT_JSON__;
const ALGORITHMS = __ALGORITHMS_JSON__;
const DATASETS = __DATASETS_JSON__;
const ATTRIBUTE_DESCRIPTIONS = __ATTRIBUTE_DESCRIPTIONS_JSON__;
const STARRED_TIMING_ATTRIBUTES = new Set(__STARRED_TIMING_ATTRIBUTES_JSON__);

let currentView = null, currentKey = null, currentPass = null, currentAttribute = null;

function columnsFor(view) {
  return view === 'by_dataset' ? ALGORITHMS : DATASETS;
}

function renderTabBar() {
  const bar = document.getElementById('tab-bar');
  bar.innerHTML = '';

  const dsGroup = document.createElement('div');
  dsGroup.className = 'tab-group';
  const dsLabel = document.createElement('span');
  dsLabel.className = 'tab-label';
  dsLabel.textContent = 'By dataset';
  dsGroup.appendChild(dsLabel);
  DATASETS.forEach(name => dsGroup.appendChild(makeTabButton('by_dataset', name)));

  const algoGroup = document.createElement('div');
  algoGroup.className = 'tab-group';
  const algoLabel = document.createElement('span');
  algoLabel.className = 'tab-label';
  algoLabel.textContent = 'By algorithm';
  algoGroup.appendChild(algoLabel);
  ALGORITHMS.forEach(name => algoGroup.appendChild(makeTabButton('by_algorithm', name)));

  bar.appendChild(dsGroup);
  const sep = document.createElement('div');
  sep.className = 'tab-sep';
  bar.appendChild(sep);
  bar.appendChild(algoGroup);
}

function makeTabButton(view, key) {
  const btn = document.createElement('button');
  btn.textContent = key;
  btn.className = (view === currentView && key === currentKey) ? 'active' : '';
  btn.onclick = () => selectKey(view, key);
  return btn;
}

function selectKey(view, key) {
  currentView = view;
  currentKey = key;
  renderTabBar();
  renderTables();
  const passesData = REPORT[view][key];
  const passes = Object.keys(passesData);
  if (!passes.length) return;

  if (currentPass && passesData[currentPass] && passesData[currentPass].attributes.includes(currentAttribute)) {
    selectAttribute(currentPass, currentAttribute);
  } else {
    const firstPass = passes[0];
    selectAttribute(firstPass, passesData[firstPass].attributes[0]);
  }
}

function renderTables() {
  const tablesEl = document.getElementById('tables');
  tablesEl.innerHTML = '';
  const passesData = REPORT[currentView][currentKey];
  Object.keys(passesData).forEach(passName => {
    const block = document.createElement('div');
    block.className = 'table-block';
    const h2 = document.createElement('h2');
    h2.textContent = passName;
    block.appendChild(h2);

    const table = document.createElement('table');
    table.className = 'attr-table';
    const tbody = document.createElement('tbody');
    passesData[passName].attributes.forEach(attr => {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.className = 'attr-cell';

      const text = document.createElement('div');
      const name = document.createElement('div');
      name.className = 'attr-name';
      name.textContent = attr;
      text.appendChild(name);
      const desc = ATTRIBUTE_DESCRIPTIONS[attr];
      if (desc) {
        const description = document.createElement('div');
        description.className = 'attr-description';
        description.textContent = desc;
        text.appendChild(description);
      }
      td.appendChild(text);

      const starred = passName === 'Operation Counts'
        ? attr !== 'frechet_dist'
        : STARRED_TIMING_ATTRIBUTES.has(attr);
      if (starred) {
        const star = document.createElement('span');
        star.className = 'attr-star';
        star.textContent = '★';
        star.title = 'Key efficiency metric';
        td.appendChild(star);
      }

      tr.appendChild(td);
      tr.dataset.pass = passName;
      tr.dataset.attr = attr;
      tr.onclick = () => selectAttribute(passName, attr);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    block.appendChild(table);
    tablesEl.appendChild(block);
  });
  highlightActiveRow();
}

function highlightActiveRow() {
  document.querySelectorAll('#tables tbody tr').forEach(tr => {
    tr.classList.toggle('active', tr.dataset.pass === currentPass && tr.dataset.attr === currentAttribute);
  });
}

function currentAxisTypes() {
  return {
    x: document.getElementById('xaxis-type').value,
    y: document.getElementById('yaxis-type').value,
  };
}

function plotCurrent() {
  const passData = REPORT[currentView][currentKey][currentPass];
  const axes = currentAxisTypes();

  const fig = passData.figures[currentAttribute];
  const layout = JSON.parse(JSON.stringify(fig.layout));
  layout.xaxis.type = axes.x;
  layout.yaxis.type = axes.y;
  Plotly.newPlot('graph', fig.data, layout, {responsive: true});

  const boxFig = passData.box_figures[currentAttribute];
  const boxLayout = JSON.parse(JSON.stringify(boxFig.layout));
  boxLayout.yaxis.type = axes.y;
  Plotly.newPlot('graph-box', boxFig.data, boxLayout, {responsive: true});
}

function renderDataTable() {
  const info = REPORT[currentView][currentKey][currentPass].tables[currentAttribute];
  const fig = REPORT[currentView][currentKey][currentPass].figures[currentAttribute];
  const columns = columnsFor(currentView);
  document.getElementById('data-table-title').textContent =
    currentAttribute + ' - ' + currentKey + ' (' + currentPass + ')';

  const colorByColumn = {};
  fig.data.forEach(t => { if (!(t.name in colorByColumn)) colorByColumn[t.name] = t.marker.color; });

  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['stat', ...columns].forEach(h => {
    const th = document.createElement('th');
    th.textContent = h;
    if (colorByColumn[h]) th.style.color = colorByColumn[h];
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  info.stat.forEach((statName, i) => {
    const tr = document.createElement('tr');
    const tdStat = document.createElement('td');
    tdStat.textContent = statName;
    tr.appendChild(tdStat);
    columns.forEach(col => {
      const td = document.createElement('td');
      const c = info[col][i];
      const value = document.createElement('div');
      value.textContent = c.value;
      td.appendChild(value);
      if (c.note) {
        const note = document.createElement('div');
        note.className = 'cell-note';
        note.textContent = c.note;
        td.appendChild(note);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  const container = document.getElementById('data-table');
  container.innerHTML = '';
  container.appendChild(table);
}

function selectAttribute(passName, attr) {
  currentPass = passName;
  currentAttribute = attr;
  highlightActiveRow();
  plotCurrent();
  renderDataTable();
}

document.getElementById('xaxis-type').addEventListener('change', plotCurrent);
document.getElementById('yaxis-type').addEventListener('change', plotCurrent);

selectKey('by_dataset', DATASETS[0]);
</script>
</body>
</html>
"""


def render_html(report, datasets, algorithms, results_root):
    html = PAGE_TEMPLATE
    html = html.replace("__RESULTS_ROOT__", results_root)
    html = html.replace("__PLOTLY_JS__", plotly.offline.get_plotlyjs())
    html = html.replace("__REPORT_JSON__", json.dumps(report))
    html = html.replace("__ALGORITHMS_JSON__", json.dumps(algorithms))
    html = html.replace("__DATASETS_JSON__", json.dumps(datasets))
    html = html.replace("__ATTRIBUTE_DESCRIPTIONS_JSON__", json.dumps(ATTRIBUTE_DESCRIPTIONS))
    html = html.replace("__STARRED_TIMING_ATTRIBUTES_JSON__", json.dumps(sorted(STARRED_TIMING_ATTRIBUTES)))
    return html


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_folder", nargs="?", default=None,
                         help="path to a results_real_world-style folder "
                              "(relative paths are resolved from the repo root); "
                              "defaults to <repo-root>/results_real_world")
    parser.add_argument("-o", "--output", default=None,
                         help="output HTML path; defaults to analysis/output/report_real_world.html")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.results_folder:
        results_root = args.results_folder if os.path.isabs(args.results_folder) \
            else os.path.join(repo_root, args.results_folder)
    else:
        results_root = os.path.join(repo_root, "results_real_world")

    output_path = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "output", "report_real_world.html")

    report, datasets, algorithms = build_report(results_root)
    html = render_html(report, datasets, algorithms, os.path.relpath(results_root, repo_root))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
