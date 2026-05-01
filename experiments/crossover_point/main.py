import time
import signal
import multiprocessing

from polyline_datasets.generate_polylines import generate_random_polylines

from src.BBMS_inter.main import BBMS_inter
from src.BBMS_dpp_instant.main import BBMS_dpp_instant
from src.DijkstraPrims.main import DijkstraPrims

MULTIPLIER = 1.5
BATCH_SIZE = 1  # 6 lengths × 3 algorithms = 18 jobs across 20 processors
CSV_PATH = "experiments/crossover_point/results/results.csv"


def _timed(fn, a, b):
    start = time.perf_counter()
    fn(a, b)
    return time.perf_counter() - start


def _init_worker():
    # workers ignore Ctrl+C; main process handles shutdown via pool.terminate()
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _collect_batch(batch_futures):
    """Poll futures and write each row to CSV as soon as all 3 algorithms for it complete."""
    done = set()
    while len(done) < len(batch_futures):
        for i, (length, f1, f2, f3) in enumerate(batch_futures):
            if i in done:
                continue
            if f1.ready() and f2.ready() and f3.ready():
                try:
                    t_dp = f1.get(timeout=0)
                    t_inter = f2.get(timeout=0)
                    t_dpp = f3.get(timeout=0)
                    print(f"Length: {length}, DijkstraPrims: {t_dp:.4f}s, BBMS_inter: {t_inter:.4f}s, BBMS_dpp_instant: {t_dpp:.4f}s")
                    with open(CSV_PATH, "a") as f:
                        f.write(f"{length},{t_dp:.4f},{t_inter:.4f},{t_dpp:.4f}\n")
                except Exception:
                    pass
                done.add(i)
        time.sleep(1)


def main():
    polyline_length = 5062

    with open(CSV_PATH, "w") as f:
        f.write("Length,DijkstraPrims,BBMS_inter,BBMS_dpp_instant\n")

    pool = multiprocessing.Pool(processes=20, initializer=_init_worker)
    batch_futures = []

    try:
        while True:
            batch_lengths = [int(polyline_length * MULTIPLIER**i) for i in range(BATCH_SIZE)]

            batch_futures = []
            for length in batch_lengths:
                curves = generate_random_polylines(2, (length, length), (0, 10), (0, 10))
                f1 = pool.apply_async(_timed, (DijkstraPrims, curves[0], curves[1]))
                f2 = pool.apply_async(_timed, (BBMS_inter, curves[0], curves[1]))
                f3 = pool.apply_async(_timed, (BBMS_dpp_instant, curves[0], curves[1]))
                batch_futures.append((length, f1, f2, f3))

            _collect_batch(batch_futures)
            polyline_length = int(batch_lengths[-1] * MULTIPLIER)

    except KeyboardInterrupt:
        print("\nCtrl+C received — terminating all worker processes...")
        pool.terminate()
        pool.join()
        print("Done. All completed rows have been saved to CSV.")


if __name__ == "__main__":
    main()
