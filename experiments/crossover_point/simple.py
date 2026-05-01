import time

from polyline_datasets.generate_polylines import generate_random_polylines

from src.BBMS_inter.main import BBMS_inter
from src.BBMS_dpp_instant.main import BBMS_dpp_instant
from src.DijkstraPrims.main import DijkstraPrims
from src.BBMS_dpp_instant_opt.main import BBMS_dpp_instant_opt

MULTIPLIER = 1.5
CSV_PATH = "experiments/crossover_point/results/results.csv"


def main():
    polyline_length = 1000

    with open(CSV_PATH, "w") as f:
        f.write("Length,DijkstraPrims,BBMS_inter,BBMS_dpp_instant,BBMS_dpp_instant_opt\n")

    while True:
        curves = generate_random_polylines(2, (polyline_length, polyline_length), (0, 10), (0, 10))

        start = time.perf_counter()
        DijkstraPrims(curves[0], curves[1])
        t_dp = time.perf_counter() - start

        start = time.perf_counter()
        BBMS_inter(curves[0], curves[1])
        t_inter = time.perf_counter() - start

        start = time.perf_counter()
        BBMS_dpp_instant(curves[0], curves[1])
        t_dpp = time.perf_counter() - start

        start = time.perf_counter()
        BBMS_dpp_instant_opt(curves[0], curves[1])
        t_dpp_opt = time.perf_counter() - start

        print(f"Length: {polyline_length}, DijkstraPrims: {t_dp:.4f}s, BBMS_inter: {t_inter:.4f}s, BBMS_dpp_instant: {t_dpp:.4f}s, BBMS_dpp_instant_opt: {t_dpp_opt:.4f}s")

        with open(CSV_PATH, "a") as f:
            f.write(f"{polyline_length},{t_dp:.4f},{t_inter:.4f},{t_dpp:.4f},{t_dpp_opt:.4f}\n")

        polyline_length = int(polyline_length * MULTIPLIER)


if __name__ == "__main__":
    main()
