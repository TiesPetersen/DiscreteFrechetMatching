from Point import Point

def computeDiscreteFrechetDistance(curve1: list[Point], curve2: list[Point]) -> float:



    pass


def main():
    curve1 = [Point(1, 0), Point(1, 1), Point(0, 2), Point(2,3), Point(1, 4), Point(2, 4), Point(0, 5)]
    curve2 = [Point(3, 0), Point(3, 1), Point(1, 2), Point(2, 2), Point(1, 3), Point(3, 4), Point(3, 4), Point(3, 3), Point(4, 4), Point(4, 5)]

    distance = computeDiscreteFrechetDistance(curve1, curve2)
    print(f"Discrete Fréchet Distance: {distance}")

if __name__ == "__main__":
    main()