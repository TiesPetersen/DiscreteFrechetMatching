from Point import Point
import heapq


def dijkstraPrims(curve1: list[Point], curve2: list[Point]) -> tuple[float, list[tuple[int, int]]]:
    assert(len(curve1) > 0 and len(curve2) > 0)

    d = distance(curve1[0], curve2[0])
    priority_queue = [(d, 0, 0)]

    longest_dist = d
    prev = {(0, 0): (-1, -1)}

    # possible neighbor offsets
    neighbors = [(1, 0), (1, 1), (0, 1)]

    while priority_queue:
        # pop the pair of indices with the smallest distance from the priority queue
        current_dist, i, j = heapq.heappop(priority_queue)

        # update the longest distance if the current distance is greater
        longest_dist = max(longest_dist, current_dist)

        # we have reached the end of both curves, so break
        if (i, j) == (len(curve1) - 1, len(curve2) - 1):
            break

        # iterate through the neighboring pairs of indices
        for di, dj in neighbors:
            # calculate the new indices for the neighboring pair of points
            new_i, new_j = i + di, j + dj

            # check if the new indices are within bounds of the curves
            if not (0 <= new_i < len(curve1) and 0 <= new_j < len(curve2)):
                continue

            # check if we have already visited this pair of indices
            if (new_i, new_j) in prev:
                continue

            # calculate the distance for the new pair of indices and add it to the priority queue
            d = distance(curve1[new_i], curve2[new_j])
            heapq.heappush(priority_queue, (d, new_i, new_j))
            prev[(new_i, new_j)] = (i, j)

    # reconstruct the matching from the prev dictionary
    curr = (len(curve1) - 1, len(curve2) - 1)
    matching = [curr]
    while curr != (0, 0):
        curr = prev[curr]
        matching.append(curr)

    matching.reverse()

    return longest_dist, matching



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


def main():
    curve1 = [Point(1, 0), Point(1, 1), Point(0, 2), Point(2,3), Point(1, 4), Point(2, 4), Point(0, 5)]
    curve2 = [Point(3, 0), Point(3, 1), Point(1, 2), Point(2, 2), Point(1, 3), Point(3, 4), Point(3, 4), Point(3, 3), Point(4, 4), Point(1, 5)]

    # curve1 = [Point(0, 0), Point(1, 1), Point(0, 2), Point(1, 3)]
    # curve2 = [Point(1, 0), Point(0, 1), Point(1, 2), Point(0, 3)]

    frechet_distance, matching = dijkstraPrims(curve1, curve2)
    print(f"Discrete Fréchet Distance: {frechet_distance}")
    print(f"Matching: {matching}")

    print("Distance Matrix:")
    distance_matrix = computeDistanceMatrix(curve1, curve2)
    printMatrix(distance_matrix)


if __name__ == "__main__":
    main()