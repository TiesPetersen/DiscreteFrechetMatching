from src.BBMS.main import BBMS
from src.BBMS_basic.main import BBMS_basic
from src.DijkstraPrims.main import DijkstraPrims
from src.DynamicProgramming.main import DynamicProgramming

from src.Point import Point


def main():
    # Example usage of the BBMS algorithm

    curve1 = [Point(17, 9), Point(9, 0), Point(15, 1), Point(8, 3), Point(17, 8)]
    curve2 = [Point(18, 17), Point(6, 9), Point(19, 17), Point(3, 2), Point(5, 8), Point(4, 5), Point(2, 4), Point(8, 15)]

    print("BBMS:")
    matching, distance = BBMS(curve1, curve2)
    print(f"Discrete Fréchet distance: {distance}")
    print("Matching:" + str(matching))





    # print()

    # print("BBMS_basic:")
    # matching, distance = BBMS_basic(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")
    # print("Matching:" + str(matching))

    # print()

    # print("DijkstraPrims:")
    # matching, distance = DijkstraPrims(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")
    # print("Matching:" + str(matching))

    # print()

    # print("Dynamic Programming:")
    # distance = DynamicProgramming(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")


if __name__ == "__main__":
    main()