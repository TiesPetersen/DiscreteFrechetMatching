from BBMS.main import BBMS
from .helper import load_polylines
import sys


ALGORITHMS = ['bbms', 'bbms_basic', 'dijkstraprims']


def compare_frechet_distance(filename, algorithm):
    # Load polylines from the specified file
    # polylines = load_polylines(filename)

    # matching, frechet_distance = BBMS(polylines[0], polylines[1])

    # print(f"Matching from BBMS: {matching}")
    # print(f"Frechet distance from BBMS: {frechet_distance}")

    pass


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

    print(f"Comparing frechet distance from {algorithm} to dynamic programming solution for correctness...")

    compare_frechet_distance("correctness_comparison/test_data/" + filename, algorithm)


def usage():
    print("Usage: python -m correctness_comparison.compare_frechet_distance <filename> <algorithm>      # filename of test data in /test_data/")
    print("Available algorithms: " + ", ".join(ALGORITHMS))


if __name__ == "__main__":
    main()