import re
import skia
from enum import Enum
from html_parser import Node, Element, Text, create_anon_block
from display_constants import DEFAULT_FONT_SIZE_PX, HSTEP, INPUT_WIDTH_PX, LEADING_FACTOR, POINTER_HOVER_TAG, WIDTH 
from draw_commands import DrawRect, DrawRRect, DrawText, DrawObject, DrawOutline, DrawLine, get_font_linespace, parse_color


PIXEL_VALUE_REGEX = r"(\d+)px"

FONT_CACHE = {}

def get_node_font(node: Node) -> skia.Font:
    weight = node.style["font-weight"]
    # only support family for now (not serif)
    font_family = node.style["font-family"].split(",")[0].strip('"' + "'")
    font_style = node.style["font-style"]
    # baked in euro-centrism :-)
    if font_style == "normal":
        font_style = "roman"
    # assumes pixels
    try:
        size = int(float(node.style["font-size"][:-2]) * 0.75)
    except ValueError:
        print("Unable to parse font size", node.style["font-size"])
        size = DEFAULT_FONT_SIZE_PX 

    return get_font(font_family, size, weight, font_style)
 

def get_font(font_family: str, size: int, weight: str, font_style: str) -> skia.Font:
    key = (font_family, size, weight, font_style)
    if key not in FONT_CACHE:
        if weight == "bold":
            skia_weight = skia.FontStyle.kBold_Weight
        else:
            skia_weight = skia.FontStyle.kNormal_Weight
        if font_style == "italic":
            skia_style = skia.FontStyle.kItalic_Slant
        else:
            skia_style = skia.FontStyle.kUpright_Slant
        skia_width = skia.FontStyle.kNormal_Width
        style_info = \
            skia.FontStyle(skia_weight, skia_width, skia_style)
        font = skia.Typeface(font_family, style_info)
        FONT_CACHE[key] = font
    return skia.Font(FONT_CACHE[key], size)


def is_inline_display(node: Node) -> bool:
    return isinstance(node, Text) or node.style["display"] == DisplayValue.INLINE.value


def draw_node_background(node: Node, x: int, width: int, y: int, height: int) -> list[DrawObject]:
    cmds = []
    background = node.style.get("background", None)
    bgcolor = ""
    if background:
        # background-color should be in the final layer
        color_values = [ value
                    for value in background.split(",")[-1].split(" ")
                    if parse_color(value, None)
                  ]
        bgcolor = color_values[-1] if len(color_values) else ""
    if "background-color" in node.style:
        bgcolor = node.style.get("background-color")
    if bgcolor:
        x2, y2 = x + width, y + height
        try:
            radius = float(node.style.get("border-radius", "0px")[:-2])
        except ValueError:
            radius = 0.0
        rect = DrawRRect(bgcolor, radius, x1=x, y1=y, x2=x2, y2=y2)
        cmds.append(rect)
    return cmds


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

    def should_paint(self):
        return True

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
    
    def should_paint(self):
        return isinstance(self.node, Text) or \
            (self.node.tag != "input" and self.node.tag != "button")

    def paint(self):
        cmds = []
        cmds.extend(draw_node_background(
            self.node, self.x, self.width, self.y, self.height))
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
        elif self.node.children or self.node.tag == "input":
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
                if isinstance(child, Element) and (
                    child.tag == "head"
                    or (
                        child.tag == "input"
                        and child.attributes.get("type", "") == "hidden"
                    )
                    or child.attributes.get("hidden", None) != None
                ):

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
            elif tree.tag  in ["input", "button"]:
                self.input(tree)
            else:
                for child in tree.children:
                    self.recurse(child)

    def word(self, node, word):
        font = get_node_font(node)
        text_width = font.measureText(word)

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
            self.cursor_x += font.measureText(" ")
    
    def input(self, node):
        w = INPUT_WIDTH_PX
        if self.cursor_x + w > self.width:
            self.new_line()

        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        input = InputLayout(node, line, previous_word)
        line.children.append(input)
 
        font = get_node_font(node)
        self.cursor_x += w + font.measureText(" ")

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
        self.x = None
        self.y = None

    def should_paint(self):
        return True

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

        font_metrics = [word.font.getMetrics() for word in self.children]
        max_ascent = max([-metric.fAscent for metric in font_metrics])
        max_descent = max([metric.fDescent for metric in font_metrics])
        baseline = self.y + LEADING_FACTOR * max_ascent
        for word in self.children:
            vertical_align = word.node.style.get(
                "vertical-align", VerticalAlign.BASELINE
            )
            match vertical_align:
                case VerticalAlign.BASELINE:
                    word.y = baseline + word.font.getMetrics().fAscent
                case VerticalAlign.SUPER:
                    word.y = baseline - max_ascent
                case VerticalAlign.SUB:
                    word.y = (baseline + max_descent) - get_font_linespace(word.font)
        self.height = 1.25 * (max_ascent + max_descent)


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous
        self.x = None
        self.y = None

    def should_paint(self):
        return True

    def paint(self):
        color = self.node.style["color"]
        tags = []
        cursor_style = self.node.style.get("cursor", None)
        if cursor_style and cursor_style == "pointer":
            tags.append(POINTER_HOVER_TAG)

        return [DrawText(self.word, self.font, color, x1=self.x, y1=self.y)]

    def layout(self):
        self.font = get_node_font(self.node)
        self.width = self.font.measureText(self.word)

        # calculate word position
        if self.previous:
            # we should think about when to add a space
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x
        self.height = get_font_linespace(self.font)

class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.children = []
        self.parent = parent
        self.previous = previous
        self.x = None
        self.y = None

    def should_paint(self):
        return True

    def paint(self):
        cmds = []
        # cursor_style = self.node.style.get("cursor", None)
        # if cursor_style and cursor_style == "pointer":
        cmds.extend(draw_node_background(
            self.node, self.x, self.width, self.y, self.height))
        if self.node.tag == "input":
            text = self.node.attributes.get("value", "")
            type = self.node.attributes.get("type", "")
            if type == "password":
                text = "*" * len(text)
        elif self.node.tag == "button":
            if len(self.node.children) == 1 and \
               isinstance(self.node.children[0], Text):
                text = self.node.children[0].text
            else:
                print("Ignoring HTML contents inside button")
                text = ""
        # support border style and use it by default for inputs
        if self.node.is_focused and self.node.tag == "input":
            cx = self.x + self.font.measureText(text)
            cmds.append(DrawLine(
                 "black", 1, x1=cx, y1=self.y, x2=cx, y2=self.y + self.height ))
        color = self.node.style["color"]
        cmds.append(DrawText(text, self.font, color, x1=self.x, y1=self.y))
        return cmds

    def layout(self):
        self.font = get_node_font(self.node)
        self.width = INPUT_WIDTH_PX

        # calculate word position
        if self.previous:
            # we should think about when to add a space
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x
        self.height = get_font_linespace(self.font)
