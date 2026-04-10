from src.BBMS_core.main import BBMS_core
from src.BBMS_inter.main import BBMS_inter
from src.BBMS.main import BBMS

from polyline_datasets.load_polylines import load_polylines

import sys

def compare_matching_bbms(filename):
    # Load polylines from the specified file
    polylines = load_polylines(filename)

    # Compare matching from BBMS_basic to BBMS on pairwise selection of polylines (in order)
    mismatches = 0
    current_index = 1

    while current_index < len(polylines) - 1:
        # Run BBMS_core
        try:
            BBMS_core_matching, BBMS_core_frechet_distance = BBMS_core(polylines[current_index - 1], polylines[current_index])
        except Exception as e:
            print(f"Error running BBMS_core on polylines {current_index - 1} and {current_index}: {e}")
            mismatches += 1
            current_index += 2
            continue

        # Run BBMS_inter
        try:
            BBMS_inter_matching, BBMS_inter_frechet_distance = BBMS_inter(polylines[current_index - 1], polylines[current_index])
        except Exception as e:
            print(f"Error running BBMS_inter on polylines {current_index - 1} and {current_index}: {e}")
            mismatches += 1
            current_index += 2
            continue

        # Run BBMS
        try:
            BBMS_matching, BBMS_frechet_distance = BBMS(polylines[current_index - 1], polylines[current_index])
        except Exception as e:
            print(f"Error running BBMS on polylines {current_index - 1} and {current_index}: {e}")
            mismatches += 1
            current_index += 2
            continue

        # Compare results
        BBMS_to_core = (BBMS_matching == BBMS_core_matching) and (BBMS_frechet_distance == BBMS_core_frechet_distance)
        BBMS_to_inter = (BBMS_matching == BBMS_inter_matching) and (BBMS_frechet_distance == BBMS_inter_frechet_distance)
        if not BBMS_to_core or not BBMS_to_inter:
            mismatches += 1
            print(f"Mismatch in matching for polylines {current_index - 1} and {current_index}:")
            print(f"Polyline 1: {polylines[current_index - 1]}")
            print(f"Polyline 2: {polylines[current_index]}")
            print(f"BBMS matching: {BBMS_matching}")
            print(f"BBMS_core matching: {BBMS_core_matching}")
            print(f"BBMS_inter matching: {BBMS_inter_matching}")
            print(f"BBMS frechet distance: {BBMS_frechet_distance}")
            print(f"BBMS_core frechet distance: {BBMS_core_frechet_distance}")
            print(f"BBMS_inter frechet distance: {BBMS_inter_frechet_distance}")
            print()

        # Move to the next pair of polylines (in order)
        current_index += 2

    if mismatches == 0:
        print("Success: All matchings and Frechet distances match between BBMS_core, BBMS_inter and BBMS")
    else:
        print(f"\n\nFail: {mismatches} mismatches found between BBMS_core, BBMS_inter and BBMS. See above for details.")

def main():
    # Check command line arguments
    if len(sys.argv) != 2:
        usage()
        sys.exit(1)

    filename = sys.argv[1]
    if not filename.endswith(".txt"):
        filename += ".txt"

    # Run the comparison
    compare_matching_bbms("polyline_datasets/" + filename)


def usage():
    print("Usage: python -m correctness_comparison.compare_matching <filename>      # filename of test data in polyline_datasets/")


if __name__ == "__main__":
    main()