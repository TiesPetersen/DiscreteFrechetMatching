from Point import Point
from helper import computeDistanceMatrix, printMatrix, printMatrixConditional

def BBMS(curve1: list[Point], curve2: list[Point]) -> tuple[float, list[list[float]]]:
    m = len(curve1)
    n = len(curve2)
    assert(m > 0 and n > 0)

    # construct grid G for curve1 and curve2
    distance_matrix = computeDistanceMatrix(curve1, curve2)

    # tree with root (0, 0)

    # for i <- 1 to m do: Add G[i, 0] to T

    # for j <- 1 to n do: Add G[0, j] to T

    # for i <- 1 to m do
    #     for j <- 1 to n do
    #         AddToTree(T, G, i, j)

    # return path in T between G[0, 0] and G[m, n]


def addToTree(T, G, i, j):
    # parent(G[i, j]) <- candidate parent with lowest maximum distance to Nearest Common Ancestor in T

    # if G[i - 1, j - 1] is dead then
    #     Remove the dead path ending at G[i - 1, j - 1] from T and extend shortcuts

    # Make shortcuts for G[i - 1, j], G[i, j - 1], and G[i, j] where necessary

    pass


def main():
    # curve1 = [Point(1, 0), Point(1, 1), Point(0, 2), Point(2,3), Point(1, 4), Point(2, 4), Point(0, 5)]
    # curve2 = [Point(3, 0), Point(3, 1), Point(1, 2), Point(2, 2), Point(1, 3), Point(3, 4), Point(3, 4), Point(3, 3), Point(4, 4), Point(1, 5)]

    curve1 = [Point(0, 0), Point(1, 1), Point(0, 2), Point(1, 3)]
    curve2 = [Point(1, 0), Point(0, 1), Point(1, 2), Point(0, 3)]

    frechet_distance, matching = dijkstraPrims(curve1, curve2)
    print(f"Discrete Fréchet Distance: {frechet_distance}")
    print(f"Matching: {matching}")

    print("Distance Matrix:")
    distance_matrix = BBMS(curve1, curve2)
    printMatrix(distance_matrix)


if __name__ == "__main__":
    main()