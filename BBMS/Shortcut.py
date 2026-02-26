# Shortcut:
#   sink     : Node    // NCA of the face adjacent to this node
#   path_max : float   // max G-value on tree path from owner to sink,
#                      // EXCLUDING sink's own value


class Shortcut:
    def __init__(self, sink, path_max_distance):
        self.sink = sink
        self.path_max_distance = path_max_distance