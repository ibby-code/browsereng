from enum import Enum

class Focusable(Enum):
    ADDRESS_BAR = "address bar"
    CONTENT = "content"


class Event(Enum):
    KEY = "<KEY>"
    ENTER = "<RETURN>"
    BACKSPACE = "backspace"
    LEFT_ARROW = "left_arrow"
    RIGHT_ARROW = "right_arrow"
    ESCAPE = "escape"

