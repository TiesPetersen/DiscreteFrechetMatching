from .Node import Node

class Shortcut:
    target : Node
    value : float

    def __init__(self, target : Node, value : float):
        print(f"Creating shortcut to node ({target.i}, {target.j}) with value {value}")
        self.target = target
        self.value = value