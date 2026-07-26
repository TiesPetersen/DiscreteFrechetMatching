"""
Reads a results folder (as produced by experiment/main.py or
experiment/calibration/calibrate.py -- i.e. results/<dataset>/{timing_memory,
opcounts}.csv) and writes a single self-contained interactive HTML report.

Two ways to slice the data, selected via tabs at the top:
  - By dataset: pick a dataset, click an attribute, see that attribute vs N
    with one line per algorithm.
  - By algorithm: pick an algorithm, click an attribute, see that attribute
    vs N with one line per dataset (only attributes that algorithm actually
    produces non-zero data for anywhere are listed -- e.g. DijkstraPrims has
    nothing to show under total_nca_steps, so it isn't offered).

Every line has an IQR error bar per point (25th/75th percentile across
samples, after first taking the min across repeats within each sample -- see
aggregate()) and stops at the largest N it actually completed at -- i.e.
exactly where its wall was hit. Each graph has independent linear/log axis
dropdowns and a data table underneath: mean (n=sample count) per N, with the
IQR (explicitly labeled, not just a bare bracketed pair) and the individual
per-sample values themselves shown in small grey text below each mean, plus
a final row giving the stop reason/status for each line.

Usage:
    python analysis/app.py                        # reads <repo-root>/results
    python analysis/app.py results_calibration     # reads a different folder
    python analysis/app.py results -o out.html     # custom output path

The output HTML embeds Plotly.js directly (no CDN, no server) so it works
fully offline -- just open it in a browser.
"""

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict

import plotly.offline

# Preferred ordering for algorithms we already know about, so existing runs
# keep stable legend order/colors -- but this is a tie-breaker, not a filter:
# discover_algorithms() below picks up whatever algorithm names actually
# appear in the data, known or not, so adding a new algorithm to the
# experiment (or removing one) needs no code change here.
KNOWN_ALGORITHM_ORDER = ["BBMSCore", "BBMSInter", "DijkstraPrims"]

# Distinct hues (chosen for contrast against the dark plot background),
# solid lines -- color is the primary way to tell traces apart. Marker shape
# still varies too, as a free secondary cue (helps colorblind readers, no
# cost to anyone else).
#
# Two entirely separate palettes for algorithms vs. datasets: the "by
# dataset" view colors its lines by algorithm, and the "by algorithm" view
# colors its lines by dataset -- if both drew from the same palette, the
# same color would mean two different things depending on which tab you're
# on (e.g. blue = BBMSCore in one view, blue = some dataset in the other),
# which is exactly the confusing case to avoid.
ALGORITHM_STYLE_PALETTE = [
    {"color": "#4E9BFF", "dash": "solid", "symbol": "circle"},
    {"color": "#FF8C42", "dash": "solid", "symbol": "square"},
    {"color": "#5FD068", "dash": "solid", "symbol": "diamond"},
    {"color": "#F25F5C", "dash": "solid", "symbol": "triangle-up"},
    {"color": "#70E0F0", "dash": "solid", "symbol": "triangle-down"},
    {"color": "#B4A0FF", "dash": "solid", "symbol": "x"},
]
DATASET_STYLE_PALETTE = [
    {"color": "#C77DFF", "dash": "solid", "symbol": "circle"},
    {"color": "#FFD23F", "dash": "solid", "symbol": "square"},
    {"color": "#3DD6D0", "dash": "solid", "symbol": "diamond"},
    {"color": "#FF6FA5", "dash": "solid", "symbol": "triangle-up"},
    {"color": "#8FE388", "dash": "solid", "symbol": "triangle-down"},
    {"color": "#FFB56B", "dash": "solid", "symbol": "x"},
]

# Identifier/grouping columns -- not something you'd plot on the y-axis.
# `status` is used to filter to successful runs / find stop reasons, not
# plotted itself.
NON_ATTRIBUTE_COLUMNS = {"algorithm", "N", "sample", "repeat", "status"}

PASSES = [("Timing & Memory", "timing_memory.csv"), ("Operation Counts", "opcounts.csv")]

ZERO_EPSILON = 1e-12  # below this, a value counts as "structurally zero"


def discover_datasets(results_root):
    """Sorted dataset names (subfolders of results_root containing at least
    one of the two expected CSVs)."""
    if not os.path.isdir(results_root):
        return []
    datasets = []
    for name in sorted(os.listdir(results_root)):
        path = os.path.join(results_root, name)
        if not os.path.isdir(path):
            continue
        if any(os.path.exists(os.path.join(path, filename)) for _, filename in PASSES):
            datasets.append(name)
    return datasets


def load_rows(csv_path):
    """All rows in a results CSV, ok and failed alike."""
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def attribute_columns(rows):
    """Numeric attribute columns present in this CSV, in file order."""
    if not rows:
        return []
    return [c for c in rows[0].keys() if c not in NON_ATTRIBUTE_COLUMNS]


def discover_algorithms(results_root, datasets):
    """Every distinct `algorithm` value seen across every dataset's CSVs --
    not a hardcoded list, so adding a new algorithm to the experiment (or
    dropping one) just works without touching this script. Known algorithms
    come first (stable ordering/coloring for existing runs); anything new
    is appended alphabetically."""
    found = set()
    for dataset in datasets:
        dataset_path = os.path.join(results_root, dataset)
        for _, filename in PASSES:
            for row in load_rows(os.path.join(dataset_path, filename)):
                found.add(row["algorithm"])
    known = [a for a in KNOWN_ALGORITHM_ORDER if a in found]
    return known + sorted(found - set(known))


def assign_styles(names, palette):
    return {name: palette[i % len(palette)] for i, name in enumerate(names)}


def compute_stop_status(rows, algorithms):
    """For each algorithm: how far it got and why it stopped, if it did.
    A well-behaved run has at most one non-ok row per algorithm (main.py's
    wall-skipping means everything past the first failure is never
    attempted, not recorded as another failure) -- but this takes the
    smallest failing N defensively in case that's ever not true."""
    status = {}
    by_algorithm = defaultdict(list)
    for row in rows:
        by_algorithm[row["algorithm"]].append(row)

    for algo in algorithms:
        algo_rows = by_algorithm.get(algo, [])
        if not algo_rows:
            status[algo] = {"state": "no data", "at_n": None}
            continue
        failures = [r for r in algo_rows if r["status"] != "ok"]
        if failures:
            worst = min(failures, key=lambda r: int(r["N"]))
            status[algo] = {"state": worst["status"], "at_n": int(worst["N"])}
        else:
            status[algo] = {"state": "completed", "at_n": None}
    return status


def quartiles(values):
    """(q1, q3) via linear interpolation. Needs >=2 points; with fewer, both
    collapse to the single value (a zero-width error bar) rather than
    raising -- statistics.quantiles requires at least 2 data points."""
    if len(values) < 2:
        v = values[0] if values else 0.0
        return v, v
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q3


def aggregate(rows, attribute):
    """Per (algorithm, N): mean/q1/q3/count of `attribute` across samples --
    after first taking the min across repeats within each (algorithm, N,
    sample). Repeats and samples are two different things (PLAN.md 5.1):
    repeats measure the *same* instance multiple times (pure measurement
    noise, one-directional, so min is the best estimate of the true cost),
    while different samples are genuinely different instances (characterized
    with mean/IQR -- taking their min would just cherry-pick the easiest
    instance rather than describe typical behavior). Rows with no `repeat`
    column (opcounts.csv, which is deterministic and only ever runs once per
    sample) pass straight through the per-sample min as a no-op -- there's
    nothing to denoise there.

    Returns {algorithm: {N: {mean, q1, q3, count, values}}}; `count` is the
    number of samples behind each point, not the number of raw rows; `values`
    is the sorted list of those per-sample values themselves (each already
    reduced across its own repeats), for display alongside the summary stats
    so a reader can see the actual spread behind the mean, not just trust it."""
    per_sample_values = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in rows:
        if row["status"] != "ok":
            continue
        try:
            value = float(row[attribute])
        except (KeyError, ValueError):
            continue
        algo, n, sample = row["algorithm"], int(row["N"]), int(row["sample"])
        per_sample_values[algo][n][sample].append(value)

    values_by_group = defaultdict(lambda: defaultdict(list))
    for algo, by_n in per_sample_values.items():
        for n, by_sample in by_n.items():
            for sample_values in by_sample.values():
                values_by_group[algo][n].append(min(sample_values))

    result = {}
    for algo, by_n in values_by_group.items():
        result[algo] = {}
        for n, values in by_n.items():
            q1, q3 = quartiles(values)
            result[algo][n] = {
                "mean": sum(values) / len(values),
                "q1": q1, "q3": q3, "count": len(values),
                "values": sorted(values),
            }
    return result


def is_structurally_absent(points_by_n):
    """True if every value in this {n: point} series is ~0 -- i.e. nothing
    to do for this metric (e.g. DijkstraPrims on total_nca_steps, or
    BBMSCore -- no shortcuts -- on shortcuts_written)."""
    return all(abs(p["mean"]) < ZERO_EPSILON for p in points_by_n.values())


def all_series_absent(series_by_trace):
    """Same idea as is_structurally_absent, but across every trace (e.g.
    every dataset) at once -- used to decide whether an attribute is worth
    listing at all for a given algorithm."""
    return all(is_structurally_absent(points) for points in series_by_trace.values())


# Plotly needs explicit dark-theme colors -- its own defaults are a white
# plot area, which would clash badly floating inside the rest of the page.
PLOT_BG = "#0a0a0a"
PLOT_FG = "#f2f2f2"
PLOT_MUTED = "#888888"
PLOT_GRID = "#2e2e2e"
PLOT_FONT_FAMILY = "ui-monospace, 'SF Mono', 'Cascadia Code', Consolas, 'Roboto Mono', monospace"


def build_figure(attribute, series_by_trace, trace_order, style_map):
    """Plotly figure spec (JSON-serializable dict): one line per trace
    (algorithm or dataset, depending on which view this is for) that
    actually has nonzero data for this attribute, x=N, with an asymmetric
    IQR error bar per point. Default x=log, y=linear -- the page's axis
    dropdowns can override either at render time. Each trace gets a distinct
    color and marker shape."""
    data = []
    for name in trace_order:
        points = series_by_trace.get(name)
        if not points or is_structurally_absent(points):
            continue
        ns = sorted(points)
        style = style_map.get(name, ALGORITHM_STYLE_PALETTE[0])
        data.append({
            "x": ns,
            "y": [points[n]["mean"] for n in ns],
            "mode": "lines+markers",
            "name": name,
            "line": {"color": style["color"], "dash": style["dash"]},
            "marker": {"symbol": style["symbol"], "color": style["color"], "size": 7},
            "error_y": {
                "type": "data",
                "symmetric": False,
                "color": style["color"],
                # clamped at 0: error_y expects non-negative magnitudes, but
                # mean and quartiles aren't guaranteed nested -- a skewed
                # small sample can have the mean fall outside [q1, q3].
                "array": [max(0.0, points[n]["q3"] - points[n]["mean"]) for n in ns],
                "arrayminus": [max(0.0, points[n]["mean"] - points[n]["q1"]) for n in ns],
            },
        })
    layout = {
        "title": {"text": attribute, "font": {"color": PLOT_FG}},
        "paper_bgcolor": PLOT_BG,
        "plot_bgcolor": PLOT_BG,
        "font": {"color": PLOT_FG, "family": PLOT_FONT_FAMILY},
        "xaxis": {"title": {"text": "N"}, "type": "log", "gridcolor": PLOT_GRID,
                  "zerolinecolor": PLOT_GRID, "linecolor": PLOT_MUTED, "tickfont": {"color": PLOT_MUTED}},
        "yaxis": {"title": {"text": attribute}, "type": "linear", "gridcolor": PLOT_GRID,
                  "zerolinecolor": PLOT_GRID, "linecolor": PLOT_MUTED, "tickfont": {"color": PLOT_MUTED}},
        "margin": {"t": 48, "r": 24, "b": 48, "l": 64},
        "legend": {"orientation": "h", "y": -0.2, "font": {"color": PLOT_FG}},
    }
    return {"data": data, "layout": layout}


def fmt(value):
    return f"{value:.4g}"


def build_table(series_by_trace, stop_status_by_trace, trace_order):
    """Rows = every N with at least one trace's data, columns = trace_order
    (algorithms or datasets), plus a final row giving each trace's stop
    reason -- shown regardless of whether it was structurally absent from
    the graph, since that's independent of this one attribute.

    Each data cell is {summary, detail}: `summary` is the mean and how many
    samples it's from; `detail` is small-grey-font supporting text -- the IQR
    labeled explicitly (not just a bare bracketed pair, which reads as
    "some range" without saying what kind), plus the individual per-sample
    values themselves, so a reader can see the actual data behind the mean
    rather than only a pre-digested summary of it."""
    all_ns = sorted({n for points in series_by_trace.values() for n in points})
    rows = []
    for n in all_ns:
        cell = {"N": n}
        for name in trace_order:
            point = series_by_trace.get(name, {}).get(n)
            if point:
                values_str = ", ".join(fmt(v) for v in point["values"])
                cell[name] = {
                    "summary": f"{fmt(point['mean'])}  (n={point['count']})",
                    "detail": (f"IQR 25–75%: [{fmt(point['q1'])}, {fmt(point['q3'])}]"
                               f"  ·  per-sample: {values_str}"),
                }
            else:
                cell[name] = {"summary": "—", "detail": ""}
        rows.append(cell)

    stop_row = {"N": "stopped at"}
    for name in trace_order:
        s = stop_status_by_trace.get(name, {"state": "no data", "at_n": None})
        if s["state"] == "completed":
            stop_row[name] = "completed configured grid"
        elif s["state"] == "no data":
            stop_row[name] = "no data"
        else:
            stop_row[name] = f"{s['state']} @ N={s['at_n']}"

    return {"rows": rows, "stop_row": stop_row}


def build_report(results_root):
    datasets = discover_datasets(results_root)
    if not datasets:
        print(f"No dataset folders with timing_memory.csv/opcounts.csv found under "
              f"{results_root}", file=sys.stderr)
        sys.exit(1)
    algorithms = discover_algorithms(results_root, datasets)

    # raw[pass_name][attribute][algorithm][dataset] = {n: point}
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    # stop[pass_name][algorithm][dataset] = {state, at_n}
    stop = defaultdict(lambda: defaultdict(dict))
    # attrs_by_pass[pass_name] = attribute names, unioned across every dataset
    # (order-preserving) -- not just the first dataset seen, so an attribute
    # introduced by a later dataset/algorithm still gets picked up.
    attrs_by_pass = defaultdict(list)

    for dataset in datasets:
        dataset_path = os.path.join(results_root, dataset)
        for pass_name, filename in PASSES:
            rows = load_rows(os.path.join(dataset_path, filename))
            attrs = attribute_columns(rows)
            if not attrs:
                continue
            seen = attrs_by_pass[pass_name]
            for a in attrs:
                if a not in seen:
                    seen.append(a)

            stop_status = compute_stop_status(rows, algorithms)
            for algo in algorithms:
                stop[pass_name][algo][dataset] = stop_status.get(algo, {"state": "no data", "at_n": None})

            for attr in attrs:
                series = aggregate(rows, attr)
                for algo, points in series.items():
                    raw[pass_name][attr][algo][dataset] = points

    default_stop = {"state": "no data", "at_n": None}
    algorithm_styles = assign_styles(algorithms, ALGORITHM_STYLE_PALETTE)
    dataset_styles = assign_styles(datasets, DATASET_STYLE_PALETTE)

    # --- By dataset: for a fixed dataset, one line per algorithm ---
    by_dataset = {}
    for dataset in datasets:
        by_dataset[dataset] = {}
        for pass_name, attrs in attrs_by_pass.items():
            figures, tables, present_attrs = {}, {}, []
            for attr in attrs:
                series_by_algo = {
                    algo: raw[pass_name][attr][algo][dataset]
                    for algo in algorithms
                    if dataset in raw[pass_name][attr].get(algo, {})
                }
                if not series_by_algo:
                    continue
                present_attrs.append(attr)
                figures[attr] = build_figure(attr, series_by_algo, algorithms, algorithm_styles)
                stop_for_dataset = {algo: stop[pass_name][algo].get(dataset, default_stop) for algo in algorithms}
                tables[attr] = build_table(series_by_algo, stop_for_dataset, algorithms)
            if present_attrs:
                by_dataset[dataset][pass_name] = {"attributes": present_attrs, "figures": figures, "tables": tables}

    # --- By algorithm: for a fixed algorithm, one line per dataset ---
    by_algorithm = {}
    for algo in algorithms:
        by_algorithm[algo] = {}
        for pass_name, attrs in attrs_by_pass.items():
            figures, tables, present_attrs = {}, {}, []
            for attr in attrs:
                series_by_dataset = raw[pass_name][attr].get(algo, {})
                if not series_by_dataset or all_series_absent(series_by_dataset):
                    continue
                present_attrs.append(attr)
                figures[attr] = build_figure(attr, series_by_dataset, datasets, dataset_styles)
                stop_for_algo = {ds: stop[pass_name][algo].get(ds, default_stop) for ds in datasets}
                tables[attr] = build_table(series_by_dataset, stop_for_algo, datasets)
            if present_attrs:
                by_algorithm[algo][pass_name] = {"attributes": present_attrs, "figures": figures, "tables": tables}

    return {"by_dataset": by_dataset, "by_algorithm": by_algorithm}, datasets, algorithms


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Discrete Frechet Matching -- Experiment Results</title>
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
  .main-panel { flex: 1 1 560px; min-width: 360px; display: flex; flex-direction: column; gap: 16px; }
  .graph-panel { border: 1px solid var(--border); border-radius: 4px; padding: 12px;
                 overflow-x: auto; background: var(--bg-panel); }
  .axis-controls { display: flex; gap: 20px; padding: 0 4px 10px; font-size: 0.75rem;
                    color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .axis-controls label { display: flex; align-items: center; gap: 8px; }
  .axis-controls select { background: var(--bg); color: var(--fg); border: 1px solid var(--border);
                           font-family: inherit; font-size: 0.8rem; padding: 3px 6px; border-radius: 3px;
                           text-transform: none; letter-spacing: normal; }
  #graph { width: 100%; height: 480px; }
  .data-table-panel { border: 1px solid var(--border); border-radius: 4px; padding: 16px;
                       overflow-x: auto; background: var(--bg-panel); }
  .data-table-panel h3 { margin: 0 0 10px; font-size: 0.78rem; text-transform: uppercase;
                          letter-spacing: 0.05em; color: var(--muted); font-weight: 700; }
  .data-table-panel table { font-size: 0.78rem; white-space: nowrap; }
  .cell-detail { color: var(--muted); font-size: 0.68rem; margin-top: 3px;
                  white-space: normal; max-width: 260px; }
  .data-table-panel tr.stop-row td { border-top: 1px solid var(--border-strong); font-style: italic;
                                      color: var(--muted); }
</style>
</head>
<body>
<header>
  <h1>Discrete Frechet Matching &mdash; Experiment Results</h1>
  <div class="subtitle">Source: __RESULTS_ROOT__ &middot; click any attribute to plot it</div>
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
      </div>
      <div id="graph"></div>
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
  const passes = Object.keys(REPORT[view][key]);
  if (passes.length) {
    const firstPass = passes[0];
    selectAttribute(firstPass, REPORT[view][key][firstPass].attributes[0]);
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
      td.textContent = attr;
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
  const fig = REPORT[currentView][currentKey][currentPass].figures[currentAttribute];
  const axes = currentAxisTypes();
  const layout = JSON.parse(JSON.stringify(fig.layout));
  layout.xaxis.type = axes.x;
  layout.yaxis.type = axes.y;
  Plotly.newPlot('graph', fig.data, layout, {responsive: true});
}

function renderDataTable() {
  const info = REPORT[currentView][currentKey][currentPass].tables[currentAttribute];
  const fig = REPORT[currentView][currentKey][currentPass].figures[currentAttribute];
  const columns = columnsFor(currentView);
  document.getElementById('data-table-title').textContent =
    currentAttribute + ' -- ' + currentKey + ' (' + currentPass + ')';

  // Colors come straight from this attribute's own plotted traces, not a
  // fixed per-name mapping -- a column whose trace was left off the graph
  // (nothing to do for this attribute) falls back to the muted grey rather
  // than implying it's plotted when it isn't.
  const colorByColumn = {};
  fig.data.forEach(t => { colorByColumn[t.name] = t.line.color; });

  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['N', ...columns].forEach(h => {
    const th = document.createElement('th');
    th.textContent = h;
    if (colorByColumn[h]) th.style.color = colorByColumn[h];
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  info.rows.forEach(row => {
    const tr = document.createElement('tr');

    const tdN = document.createElement('td');
    tdN.textContent = row['N'];
    tr.appendChild(tdN);

    // Each data cell is {summary, detail}: summary at normal size/weight,
    // detail (the IQR label + individual per-sample values) below it in
    // small grey text -- supporting evidence for the mean, not competing
    // with it for attention.
    columns.forEach(col => {
      const td = document.createElement('td');
      const cell = row[col];
      const summary = document.createElement('div');
      summary.textContent = cell.summary;
      td.appendChild(summary);
      if (cell.detail) {
        const detail = document.createElement('div');
        detail.className = 'cell-detail';
        detail.textContent = cell.detail;
        td.appendChild(detail);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  const stopTr = document.createElement('tr');
  stopTr.className = 'stop-row';
  ['N', ...columns].forEach(col => {
    const td = document.createElement('td');
    td.textContent = info.stop_row[col];
    stopTr.appendChild(td);
  });
  tbody.appendChild(stopTr);

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
    return html


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_folder", nargs="?", default=None,
                         help="path to a results folder, e.g. results or results_calibration "
                              "(relative paths are resolved from the repo root); "
                              "defaults to <repo-root>/results")
    parser.add_argument("-o", "--output", default=None,
                         help="output HTML path; defaults to analysis/output/report.html")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.results_folder:
        results_root = args.results_folder if os.path.isabs(args.results_folder) \
            else os.path.join(repo_root, args.results_folder)
    else:
        results_root = os.path.join(repo_root, "results")

    output_path = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "output", "report.html")

    report, datasets, algorithms = build_report(results_root)
    html = render_html(report, datasets, algorithms, os.path.relpath(results_root, repo_root))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
