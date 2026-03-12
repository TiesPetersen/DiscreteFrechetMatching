from BBMS.main import BBMS
from .helper import load_polylines
import sys

def compare_matching_bbms_basic_to_bbms(filename):
    # Load polylines from the specified file
    polylines = load_polylines(filename)

    matching, frechet_distance = BBMS(polylines[0], polylines[1])

    print(f"Matching from BBMS: {matching}")
    print(f"Frechet distance from BBMS: {frechet_distance}")


def main():
    # Check command line arguments
    if len(sys.argv) != 2:
        usage()
        sys.exit(1)

    filename = sys.argv[1]
    if not filename.endswith(".txt"):
        filename += ".txt"

    # Run the comparison

    print(f"Comparing matching from BBMS_basic to BBMS for correctness...")

    compare_matching_bbms_basic_to_bbms("correctness_comparison/test_data/" + filename)


def usage():
    print("Usage: python -m correctness_comparison.compare_matching <filename>      # filename of test data in /test_data/")


if __name__ == "__main__":
    main()