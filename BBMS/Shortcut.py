from .Node import Node

class Shortcut:
    target : Node
    value : float

    def __init__(self, target : Node, value : float):
        self.target = target
        self.value = value