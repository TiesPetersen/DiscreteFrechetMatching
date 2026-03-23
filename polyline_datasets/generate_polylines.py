from src.Point import Point

import random


def generate_random_polylines(num_polylines, length_range, x_range, y_range):
    """ Generates a list of random polylines. Each polyline is a list of Points. """

    polylines = []
    for _ in range(num_polylines):
        length = random.randint(*length_range)
        polyline = []
        for _ in range(length):
            x = random.uniform(*x_range)
            y = random.uniform(*y_range)
            polyline.append(Point(x, y))
        polylines.append(polyline)

    return polylines


def save_polylines(polylines, file_path):
    """ Saves a list of polylines to a text file. Each polyline is separated by a blank line. Each point is saved as 'x y' on its own line. """
    with open(file_path, 'w') as f:
        for polyline in polylines:
            for point in polyline:
                f.write(f"{point.x} {point.y}\n")
            f.write("\n")


def main():
    random_lines = generate_random_polylines(num_polylines=100, length_range=(2, 1000), x_range=(0, 1000), y_range=(0, 1000))

    save_polylines(random_lines, "experiments/data/new_polylines.txt")


if __name__ == "__main__":
    main()