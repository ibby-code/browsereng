import tkinter
import re
from enum import Enum
from html_parser import Node, Element, Text, create_anon_block
from display_constants import *
from draw_commands import DrawRect, Rect, DrawText


PIXEL_VALUE_REGEX = r"(\d+)px"

FONT_CACHE = {}


def get_font(font_family, size, weight, font_style):
    key = (font_family, size, weight, font_style)
    if key not in FONT_CACHE:
        font = tkinter.font.Font(
            family=key[0],
            size=key[1],
            weight=key[2],
            slant=key[3],
        )
        label = tkinter.Label(font=font)
        FONT_CACHE[key] = (font, label)
    return FONT_CACHE[key][0]


def is_inline_display(node: Node) -> bool:
    return isinstance(node, Text) or node.style["display"] == DisplayValue.INLINE.value


class VerticalAlign(Enum):
    BASELINE = "baseline"
    SUB = "sub"
    SUPER = "super"


class DisplayValue(Enum):
    BLOCK = "block"
    INLINE = "inline"


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []
        self.display_list = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = 0
        child.layout()
        self.height = child.height

    def paint(self):
        return []


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(Rect(self.x, self.y, x2, y2), bgcolor)
            cmds.append(rect)
        if self.layout_mode() == DisplayValue.INLINE:
            for node in self.children:
                cmds.extend(node.paint())
        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text):
            return DisplayValue.INLINE
        # default to block display if here are both
        elif any(
            [
                isinstance(child, Element)
                and child.style["display"] == DisplayValue.BLOCK.value
                for child in self.node.children
            ]
        ):
            return DisplayValue.BLOCK
        elif self.node.children:
            return DisplayValue.INLINE
        else:
            return DisplayValue.BLOCK

    def layout(self):
        self.x = self.parent.x
        match = re.search(PIXEL_VALUE_REGEX, self.node.style.get("width", ""))
        if match:
            self.width = int(match.group(1))
        else:
            self.width = self.parent.width
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        mode = self.layout_mode()
        if mode == DisplayValue.BLOCK:
            previous = None
            block_nodes_buffer = []
            for child in self.node.children:
                # hide the <head> tag
                if isinstance(child, Element) and child.tag == "head":
                    continue
                if is_inline_display(child):
                    block_nodes_buffer.append(child)
                    continue
                elif block_nodes_buffer:
                    anon_box = create_anon_block(
                        self.node, self.node.style, block_nodes_buffer
                    )
                    previous = BlockLayout(anon_box, self, previous)
                    self.children.append(previous)
                    block_nodes_buffer = []

                nxt = BlockLayout(child, self, previous)
                self.children.append(nxt)
                previous = nxt
            if block_nodes_buffer:
                anon_box = create_anon_block(
                    self.node, self.node.style, block_nodes_buffer
                )
                nxt = BlockLayout(anon_box, self, previous)
                self.children.append(nxt)
        else:
            self.new_line()
            self.recurse(self.node)
        for child in self.children:
            child.layout()

        match = re.search(PIXEL_VALUE_REGEX, self.node.style.get("height", ""))
        # override normal height with css
        if match:
            self.height = int(match.group(1))
        else:
            self.height = sum([child.height for child in self.children])

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(tree, word)
        else:
            if tree.tag == "br":
                self.new_line()
            for child in tree.children:
                self.recurse(child)

    def word(self, node, word):
        weight = node.style["font-weight"]
        # only support family for now (not serif)
        font_family = node.style["font-family"].split(",")[0].strip('"' + "'")
        font_style = node.style["font-style"]
        if font_style == "normal":
            font_style = "roman"
        size = int(float(node.style["font-size"][:-2]) * 0.75)
        font = get_font(font_family, size, weight, font_style)
        text_width = font.measure(word)

        # if there is no horizontal space, write current line
        if self.cursor_x + text_width > self.width:
            self.new_line()

        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)
        self.cursor_x += text_width
        # we should think about when to add a space
        if previous_word:
            self.cursor_x += font.measure(" ")

    def new_line(self):
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)


class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.height = 0
        self.children = []

    def paint(self):
        return []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        if not self.children:
            return
        for word in self.children:
            word.layout()

        font_metrics = [word.font.metrics() for word in self.children]
        max_ascent = max([metric["ascent"] for metric in font_metrics])
        max_descent = max([metric["descent"] for metric in font_metrics])
        baseline = self.y + LEADING_FACTOR * max_ascent
        for word in self.children:
            vertical_align = word.node.style.get(
                "vertical-align", VerticalAlign.BASELINE
            )
            match vertical_align:
                case VerticalAlign.BASELINE:
                    word.y = baseline - word.font.metrics("ascent")
                case VerticalAlign.SUPER:
                    word.y = baseline - max_ascent
                case VerticalAlign.SUB:
                    word.y = (baseline + max_descent) - word.font.metrics("linespace")
        self.height = 1.25 * (max_ascent + max_descent)


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous

    def paint(self):
        color = self.node.style["color"]
        tags = []
        cursor_style = self.node.style.get("cursor", None)
        if cursor_style and cursor_style == "pointer":
            tags.append(POINTER_HOVER_TAG)

        return [DrawText(self.x, self.y, self.word, self.font, color, tags=tags)]

    def layout(self):
        weight = self.node.style["font-weight"]
        # only support family for now (not serif)
        font_family = self.node.style["font-family"].split(",")[0].strip('"' + "'")
        font_style = self.node.style["font-style"]
        # should prob use stylesheet for this
        if font_style == "normal":
            font_style = "roman"
        # assumes pixels
        size = int(float(self.node.style["font-size"][:-2]) * 0.75)
        self.font = get_font(font_family, size, weight, font_style)
        self.width = self.font.measure(self.word)

        # calculate word position
        if self.previous:
            # we should think about when to add a space
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x
        self.height = self.font.metrics("linespace")
