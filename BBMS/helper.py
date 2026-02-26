from Point import Point

def computeDistanceMatrix(curve1: list[Point], curve2: list[Point]) -> list[list[float]]:
    matrix = [[0.0 for _ in range(len(curve1))] for _ in range(len(curve2))]
    for i in range(len(curve2)):
        for j in range(len(curve1)):
            matrix[i][j] = distance(curve1[j], curve2[i])
    return matrix


def printMatrix(matrix: list[list[float]]):
    # Print column headers
    print(" ", end="")
    for j in range(len(matrix[0])):
        print(f"{j:>7}", end="")
    print()
    
    # Print rows with row index
    for i, row in enumerate(matrix):
        print(f"{i:>3} ", end="")
        print(" ".join(f"{value:>6.2f}" for value in row))


def printMatrixConditional(inputMatrix: list[list[float]], outputMatrix: list[list[float]], threshold: float):
    # Print column headers
    print(" ", end="")
    for j in range(len(inputMatrix[0])):
        print(f"{j:>7}", end="")
    print()
    
    # Print rows with row index
    for i in range(len(inputMatrix)):
        print(f"{i:>3} ", end="")
        for j in range(len(inputMatrix[0])):
            if inputMatrix[i][j] <= threshold:
                print(f"{outputMatrix[i][j]:>6.2f}", end=" ")
            else:
                print("  .   ", end=" ")
        print()


def distance(p1: Point, p2: Point) -> float:
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5