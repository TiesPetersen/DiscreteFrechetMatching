from src.BBMS.main import BBMS
from src.BBMS_core.main import BBMS_core
from src.BBMS_inter.main import BBMS_inter
from src.DijkstraPrims.main import DijkstraPrims
from src.DynamicProgramming.main import DynamicProgramming

from polyline_datasets.load_polylines import load_polylines

import sys


ALGORITHMS = ['bbms', 'bbms_core', 'bbms_inter', 'dijkstraprims']


def compare_frechet_distance(filename, algorithm):
    # Load polylines from the specified file
    polylines = load_polylines(filename)

    mismatches = 0
    current_index = 1

    while current_index < len(polylines) - 1:
        # Run the specified algorithm
        try:
            if algorithm == 'bbms':
                _, frechet_distance = BBMS(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_core':
                _, frechet_distance = BBMS_core(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_inter':
                _, frechet_distance = BBMS_inter(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'dijkstraprims':
                _, frechet_distance = DijkstraPrims(polylines[current_index - 1], polylines[current_index])
            else:
                print(f"Unknown algorithm: {algorithm}")
                return
        except Exception as e:
            print(f"Error running {algorithm} on polylines {current_index - 1} and {current_index}: {e}")
            mismatches += 1
            current_index += 2
            continue

        # Compare to dynamic programming solution
        try:
            dp_frechet_distance = DynamicProgramming(polylines[current_index - 1], polylines[current_index])
        except Exception as e:
            print(f"Error running dynamic programming solution on polylines {current_index - 1} and {current_index}: {e}")
            mismatches += 1
            current_index += 2
            continue

        if frechet_distance != dp_frechet_distance:
            mismatches += 1
            print(f"Mismatch in Frechet distance for polylines {current_index - 1} and {current_index}:")
            print(f"{algorithm} Frechet distance: {frechet_distance}")
            print(f"Dynamic programming Frechet distance: {dp_frechet_distance}")
            print()

        # Move to the next pair of polylines (in order)
        current_index += 2

    if mismatches == 0:
        print(f"Success: All Frechet distances match between {algorithm} and dynamic programming solution")
    else:
        print(f"\n\nFail: {mismatches} mismatches found between {algorithm} and dynamic programming solution. See above for details.")


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
    compare_frechet_distance("polyline_datasets/" + filename, algorithm)


def usage():
    print("Usage: python -m tests.compare_frechet_distance <filename> <algorithm>      # filename of test data in polyline_datasets/")
    print("Available algorithms: " + ", ".join(ALGORITHMS))


if __name__ == "__main__":
    main()