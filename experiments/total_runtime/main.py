from src.BBMS_core.main import BBMS_core
from src.BBMS_inter.main import BBMS_inter
from src.BBMS_inter_opt.main import BBMS_inter_opt
from src.BBMS_dpp_instant.main import BBMS_dpp_instant
from src.BBMS_dpp_stepwise.main import BBMS_dpp_stepwise
from src.DijkstraPrims.main import DijkstraPrims

from polyline_datasets.load_polylines import load_polylines

import sys
import time


ALGORITHMS = ['bbms_core', 'bbms_inter', 'bbms_inter_opt', 'bbms_dpp_instant', 'bbms_dpp_stepwise', 'dijkstraprims']


def run_benchmark(filename, algorithm):
    """ Runs the specified algorithm on all pairs of consecutive polylines in the specified file while keeping track of the total runtime. """

    # Load polylines from the specified file
    polylines = load_polylines(filename)

    start = time.perf_counter()
    current_index = 1

    while current_index < len(polylines) - 1:
        if current_index % (len(polylines) // 10) == 1:
            print(f"Progress: {(current_index) / len(polylines) * 100:.2f}%")
        # Run the specified algorithm
        try:
            if algorithm == 'bbms_core':
                BBMS_core(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_inter':
                BBMS_inter(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_inter_opt':
                BBMS_inter_opt(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_dpp_instant':
                BBMS_dpp_instant(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_dpp_stepwise':
                BBMS_dpp_stepwise(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'dijkstraprims':
                DijkstraPrims(polylines[current_index - 1], polylines[current_index])
            else:
                print(f"Unknown algorithm: {algorithm}")
                return
        except Exception as e:
            print(f"Error running {algorithm} on polylines {current_index - 1} and {current_index}: {e}")
            current_index += 2
            continue

        # Move to the next pair of polylines (in order)
        current_index += 2

    end = time.perf_counter()
    total_time = end - start

    print(f"Total runtime for {algorithm} on {filename}: {total_time:.4f} seconds")


def main():
    # Check command line arguments
    if len(sys.argv) != 3:
        usage()
        sys.exit(1)

    filename = sys.argv[1]
    if not filename.endswith(".txt"):
        filename += ".txt"
        
    algorithm = sys.argv[2]
    if algorithm not in ALGORITHMS:
        usage()
        sys.exit(1)

    # Run the comparison
    run_benchmark("polyline_datasets/" + filename, algorithm)


def usage():
    print("Usage: python -m performance_comparison.run_benchmark <filename> <algorithm>      # filename of test data in polyline_datasets/")
    print("Available algorithms: " + ", ".join(ALGORITHMS))


if __name__ == "__main__":
    main()