from ..helper import distance


def DynamicProgramming(curve1, curve2):
    assert(len(curve1) > 0 and len(curve2) > 0)

    distance_matrix = computeDistanceMatrix(curve1, curve2)

    dp_table = [[0.0 for _ in range(len(curve1))] for _ in range(len(curve2))]
    dp_table[0][0] = distance_matrix[0][0]

    for i in range(1, len(curve2)):
        dp_table[i][0] = max(dp_table[i-1][0], distance_matrix[i][0])

    for j in range(1, len(curve1)):
        dp_table[0][j] = max(dp_table[0][j-1], distance_matrix[0][j])

    for i in range(1, len(curve2)):
        for j in range(1, len(curve1)):
            dp_table[i][j] = max(
                min(dp_table[i-1][j], dp_table[i][j-1], dp_table[i-1][j-1]),
                distance_matrix[i][j]
            )

    return dp_table[-1][-1]


def computeDistanceMatrix(curve1, curve2):
    matrix = [[0.0 for _ in range(len(curve1))] for _ in range(len(curve2))]
    for i in range(len(curve2)):
        for j in range(len(curve1)):
            matrix[i][j] = distance(curve1[j], curve2[i])
    return matrix
