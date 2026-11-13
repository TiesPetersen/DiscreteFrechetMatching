"""
Samples curve pairs from the raw external datasets (Geolife, Pigeons, Drifter, plus
Pigeons with repeated points removed)
into the plain-text curve-pair format experiment/runner.cpp reads -- one file per
dataset, containing every sampled pair (see write_pairs() for the exact format).

Unlike datasets/synthetic (one file per (dataset, N) on a shared grid), real-world
curves have independent, unequal lengths (m need not equal n) with no natural
"N" -- runner.cpp already supports this (it never assumes m == n internally,
only its own reporting of a single N field does, which experiment/real-world/main.py
works around by tracking m/n itself). So there's just one file per dataset here,
containing however many pairs were sampled for it.

Sampling is deliberately *not* filtered or biased by curve length -- every curve
in a dataset has an equal chance of being picked, long ones included. Some
resulting pairs are large enough that an algorithm will time out or run out of
memory on them; that's an expected, reportable outcome, not something to avoid
(see external_datasets/PILOT_FINDINGS -- ../../external_datasets/pilot.py's run
that established the sample sizes below).

Sample sizes (curves per dataset) were
rebalanced after a first AWS run showed Drifter (cheap, zero timeouts, 1,326
pairs) was oversized well past the point of adding confidence -- a few hundred
pairs tells the same story -- while Pigeons (21 pairs) was undersized for its
failure rate specifically to be trustworthy, being the one dataset where
real animal-movement curves reproduce the same BBMSCore/BBMSInter blowup the
synthetic `alternating` dataset was hand-engineered to cause. Pigeons pairs
are also ~100x more expensive per typical pair (median length 7,464) than
Drifter (716) or Geolife (506) and already produced genuine 120s timeouts on
pairs a fraction of that median size, so growing it further costs steeply:
each extra curve adds a full new row of expensive pairs, not just one pair.
Drifter was cut to 300 pairs (~0.8h) to free up time, letting Pigeons grow to
36 pairs (~16.7h, up from 21) while keeping total runtime roughly where it
was (~22h).

Expects the raw downloads to already exist under external_datasets/ at the repo
root (see the conversation this was built from / README for download sources --
Geolife via Microsoft's download page, Pigeons via Movebank, Drifter via NOAA's
GDP six-hourly interpolated dataset).

Run from the project root:
    python3 datasets/real-world/generate_real_world_datasets.py
"""
import csv
import math
import os
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTERNAL_DIR = os.path.join(PROJECT_ROOT, "external_datasets")
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

SEED = 42069  # same convention as datasets/synthetic/generate_datasets.py

# Curves to sample per dataset; all C(K, 2) pairs among them are used.
SAMPLE_SIZES = {
    "drifter": 25,
    "geolife": 22,
    "pigeons": 9,
}

METERS_PER_DEG = 111_320.0


def unwrap(points):
    """points: list of (lon, lat). Makes longitudes continuous: a step across the
    date line (for example 179.9 to -179.9) becomes a small step instead of a jump
    of almost 360 degrees."""
    out = []
    for lon, lat in points:
        if out:
            previous = out[-1][0]
            lon += 360.0 * round((previous - lon) / 360.0)
        out.append((lon, lat))
    return out


def project_pair(p, q):
    """p, q: lists of (lon, lat), already unwrapped. Returns both curves in metres,
    in one shared flat (equirectangular) projection centred on the mean of all
    points of the pair.

    Both curves must use the same reference. Projecting each curve with its own
    reference latitude shifts the two curves against each other, which changes
    the distance values, and so the algorithms' cost (13 Nov 2026 audit)."""
    # Move q by whole turns of 360 degrees so it sits next to p, not across the date line
    mean_lon_p = sum(lon for lon, _ in p) / len(p)
    mean_lon_q = sum(lon for lon, _ in q) / len(q)
    shift = 360.0 * round((mean_lon_p - mean_lon_q) / 360.0)
    q = [(lon + shift, lat) for lon, lat in q]

    # One reference point and one longitude scale for both curves
    both = p + q
    ref_lon = sum(lon for lon, _ in both) / len(both)
    ref_lat = sum(lat for _, lat in both) / len(both)
    scale_lon = METERS_PER_DEG * math.cos(math.radians(ref_lat))

    def project(points):
        return [((lon - ref_lon) * scale_lon, (lat - ref_lat) * METERS_PER_DEG) for lon, lat in points]

    return project(p), project(q)


def drop_repeated_points(points):
    """Removes each point that is identical to the point before it."""
    return [point for k, point in enumerate(points) if k == 0 or point != points[k - 1]]


# GitHub hard-rejects any single file over 100MB. Long real-world curves (unlike
# the small, uniform synthetic ones) can make even a modest pair count balloon
# past that in one file (drifter/pigeons both did, at ~120-200MB single-file).
# Split into part_NNN.txt chunks instead, each kept comfortably under this.
MAX_PART_BYTES = 40 * 1024 * 1024


def format_pair(p, q):
    return (f"{len(p)}\n" + " ".join(f"{x} {y}" for x, y in p) + "\n"
            f"{len(q)}\n" + " ".join(f"{x} {y}" for x, y in q) + "\n")


def write_pairs(out_dir, pairs):
    """pairs: list of (p_points, q_points), each a list of (x, y). Writes one or
    more part_NNN.txt files matching experiment/runner.cpp's load_sample()
    format per part: <count>, then per pair <m> then m "x y" points, <n> then n
    "x y" points -- split across parts so no single file exceeds MAX_PART_BYTES."""
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old.startswith("part_") and old.endswith(".txt"):
            os.remove(os.path.join(out_dir, old))

    formatted = [format_pair(p, q) for p, q in pairs]
    parts = []
    current, current_size = [], 0
    for text in formatted:
        if current and current_size + len(text) > MAX_PART_BYTES:
            parts.append(current)
            current, current_size = [], 0
        current.append(text)
        current_size += len(text)
    if current:
        parts.append(current)

    for i, part in enumerate(parts):
        with open(f"{out_dir}/part_{i:03d}.txt", "w") as f:
            f.write(f"{len(part)}\n")
            f.writelines(part)
    return len(parts)


# --- Geolife: .plt files, 6-line header, "lat,lon,alt,_,days,date,time" ---

def load_geolife_curve(path):
    pts = []
    with open(path) as f:
        for _ in range(6):
            next(f)
        for line in f:
            parts = line.split(",")
            lat, lon = float(parts[0]), float(parts[1])
            pts.append((lon, lat))
    return unwrap(pts)


def geolife_curve_paths():
    data_dir = f"{EXTERNAL_DIR}/geolife/Data"
    paths = []
    for user in sorted(os.listdir(data_dir)):
        traj_dir = f"{data_dir}/{user}/Trajectory"
        if not os.path.isdir(traj_dir):
            continue
        for fn in sorted(os.listdir(traj_dir)):
            if fn.endswith(".plt"):
                paths.append(f"{traj_dir}/{fn}")
    return paths


# --- Pigeons: one CSV, curves grouped by the "comments" column ---

def load_pigeon_curves():
    path = (f"{EXTERNAL_DIR}/pigeons/Right hemisphere advantage in route fidelity "
            f"in homing pigeons (data from Pollonara et al. 2017).csv")
    groups = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            key = row["comments"]
            groups.setdefault(key, []).append(
                (float(row["location-long"]), float(row["location-lat"])))
    return groups


# --- Drifter: NetCDF, one file per buoy ---

def load_drifter_curve(path):
    import netCDF4 as nc
    ds = nc.Dataset(path)
    lons = ds.variables["longitude"][0, :]
    lats = ds.variables["latitude"][0, :]
    ds.close()
    return unwrap(list(zip(lons.tolist(), lats.tolist())))


def drifter_curve_paths():
    paths = []
    for year in ("2022", "2023", "2024"):
        year_dir = f"{EXTERNAL_DIR}/drifter/{year}"
        for fn in sorted(os.listdir(year_dir)):
            if fn.endswith(".nc"):
                paths.append(f"{year_dir}/{fn}")
    return paths


def median_cell(points, size=10):
    """The size x size degree cell that holds the curve's median position."""
    lons = sorted(lon for lon, _ in points)
    lats = sorted(lat for _, lat in points)
    median_lon, median_lat = lons[len(lons) // 2], lats[len(lats) // 2]
    median_lon = (median_lon + 180.0) % 360.0 - 180.0
    return (math.floor(median_lat / size) * size, math.floor(median_lon / size) * size)


def densest_region(paths):
    """Keeps only the drifter curves whose median position lies in the 10 x 10
    degree cell that holds the most curves. Random buoys from the whole world
    are mostly in different oceans (median Frechet distance about 11,000 km in
    the first run), so a pair says little about matching two related curves.
    Buoys in one region overlap and drift through the same currents."""
    cells = {path: median_cell(load_drifter_curve(path)) for path in paths}
    counts = {}
    for cell in cells.values():
        counts[cell] = counts.get(cell, 0) + 1
    best = max(sorted(counts), key=lambda cell: counts[cell])
    return best, [path for path in paths if cells[path] == best]


def sample_and_pair(curve_loaders, k, seed):
    """curve_loaders: list of zero-arg callables, one per available curve.
    Samples k of them uniformly at random (no length filtering -- "fair" means
    every curve has an equal chance regardless of how long it is), loads them,
    and returns every pair among them."""
    rng = random.Random(seed)
    chosen = rng.sample(curve_loaders, min(k, len(curve_loaders)))
    loaded = [load() for load in chosen]
    pairs = []
    for i in range(len(loaded)):
        for j in range(i + 1, len(loaded)):
            pairs.append((loaded[i], loaded[j]))
    return len(loaded), pairs


def project_pairs(pairs):
    """Projects every (p, q) pair of lon/lat curves into one shared frame per pair."""
    return [project_pair(p, q) for p, q in pairs]


def main():
    report = {}

    # Geolife
    paths = geolife_curve_paths()
    loaders = [(lambda p=p: load_geolife_curve(p)) for p in paths]
    k, pairs = sample_and_pair(loaders, SAMPLE_SIZES["geolife"], SEED)
    n_parts = write_pairs(f"{OUTPUT_DIR}/geolife", project_pairs(pairs))
    report["geolife"] = (k, len(pairs), n_parts)

    # Pigeons
    groups = load_pigeon_curves()
    loaders = [(lambda pts=pts: unwrap(pts)) for pts in groups.values()]
    k, pairs = sample_and_pair(loaders, SAMPLE_SIZES["pigeons"], SEED)
    n_parts = write_pairs(f"{OUTPUT_DIR}/pigeons", project_pairs(pairs))
    report["pigeons"] = (k, len(pairs), n_parts)

    # Pigeons without repeated points: the same pairs, with every point that equals
    # the point before it removed. Most pigeon points are repeats (61 to 91 % in
    # most curves), which creates many exact ties; this control shows their effect.
    deduplicated = [(drop_repeated_points(p), drop_repeated_points(q)) for p, q in pairs]
    n_parts = write_pairs(f"{OUTPUT_DIR}/pigeons_dedup", project_pairs(deduplicated))
    report["pigeons_dedup"] = (k, len(deduplicated), n_parts)

    # Drifter: curves from one region only
    region, paths = densest_region(drifter_curve_paths())
    print(f"drifter region: lat {region[0]} to {region[0] + 10}, lon {region[1]} to {region[1] + 10}, {len(paths)} curves")
    loaders = [(lambda p=p: load_drifter_curve(p)) for p in paths]
    k, pairs = sample_and_pair(loaders, SAMPLE_SIZES["drifter"], SEED)
    n_parts = write_pairs(f"{OUTPUT_DIR}/drifter", project_pairs(pairs))
    report["drifter"] = (k, len(pairs), n_parts)

    print("dataset    curves sampled   pairs written   part files")
    for name, (k, n_pairs, n_parts) in report.items():
        print(f"{name:13s} {k:11d}   {n_pairs:13d}   {n_parts:10d}")


if __name__ == "__main__":
    main()
