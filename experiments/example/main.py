from src.BBMS.main import BBMS
from src.BBMS_basic.main import BBMS_basic
from src.DijkstraPrims.main import DijkstraPrims
from src.DynamicProgramming.main import DynamicProgramming

from src.Point import Point


def main():
    # Example usage of the BBMS algorithm

    curve1 = [Point(0, 0), Point(1, 1), Point(2, 2)]
    curve2 = [Point(0, 0), Point(1, 0), Point(2, 0)]


    print("BBMS:")
    matching, distance = BBMS(curve1, curve2)
    print(f"Discrete Fréchet distance: {distance}")
    print("Matching:" + str(matching))

    print()

    print("BBMS_basic:")
    matching, distance = BBMS_basic(curve1, curve2)
    print(f"Discrete Fréchet distance: {distance}")
    print("Matching:" + str(matching))

    print()

    print("DijkstraPrims:")
    matching, distance = DijkstraPrims(curve1, curve2)
    print(f"Discrete Fréchet distance: {distance}")
    print("Matching:" + str(matching))

    print()

    print("Dynamic Programming:")
    distance = DynamicProgramming(curve1, curve2)
    print(f"Discrete Fréchet distance: {distance}")


if __name__ == "__main__":
    main()