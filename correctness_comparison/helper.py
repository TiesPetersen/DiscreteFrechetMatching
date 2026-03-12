from .Point import Point

def load_polylines(file_path):
    polylines = []
    current_polyline = []

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line == '':
                if current_polyline:
                    polylines.append(current_polyline)
                    current_polyline = []
            else:
                x, y = line.split()
                current_polyline.append(Point(float(x), float(y)))

    if current_polyline:
        polylines.append(current_polyline)

    return polylines