import tkinter
from dataclasses import dataclass, field
from enum import Enum
from html_parser import Element, Text
from display_constants import *

BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]

TEXTLIKE_ELEMENTS = ['a', 'b', 'i', 'small', 'big', 'sub', 'sup']

@dataclass()
class DrawText:
    left: int
    top: int
    text: str
    font: 'tkinter.font.Font'
    color: str
    bottom: int =  field(init=False)

    def __post_init__(self):
        self.bottom = self.top + self.font.metrics("linespace")

    def execute(self, scroll, canvas, tags = []):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw",
            tags=tags
        )

@dataclass()
class DrawRect:
    left: int
    top: int
    right: int
    bottom: int
    color: str

    def execute(self, scroll, canvas, tags = []):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color,
            tags=tags
        )

class VerticalAlign(Enum):
    CENTER  = 0
    TOP = 1
    BOTTOM = 2

class DisplayValue(Enum):
    BLOCK = 'block'
    INLINE = 'inline'

class DocumentLayout:
    def __init__(self, node, font_cache):
        self.node = node
        self.parent = None
        self.children = []
        self.font_cache = font_cache
        self.display_list = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):
        child = BlockLayout([self.node], self, None, self.font_cache)
        self.children.append(child)
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = URL_BAR_HEIGHT + 2 * VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []

class BlockLayout:
    def __init__(self, nodes, parent, previous, font_cache):
        # anon block boxes
        self.nodes = nodes
        self.node = nodes[0]
        self.parent = parent
        self.previous = previous
        self.children = []
        self.display_list = []
        self.font_cache = font_cache
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            cmds.append(rect)
        if self.layout_mode() == DisplayValue.INLINE:
            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))
        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text) or len(self.nodes) > 1:
            return DisplayValue.INLINE
        # default to block display if here are both
        elif any([isinstance(child, Element) and \
                child.tag in BLOCK_ELEMENTS
                for child in self.node.children]):
            return DisplayValue.BLOCK
        elif self.node.children:
            return DisplayValue.INLINE
        else:
            return DisplayValue.BLOCK
    
    def is_textlike_node(self, node):
        return isinstance(node, Text) or node.tag in TEXTLIKE_ELEMENTS 
    
    def layout(self):
        self.x = self.parent.x
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
                if isinstance(child, Element) and child.tag == "head": continue
                if self.is_textlike_node(child):
                    block_nodes_buffer.append(child)
                    continue
                elif block_nodes_buffer:
                    previous = BlockLayout(block_nodes_buffer, self, previous, self.font_cache)
                    self.children.append(previous)
                    block_nodes_buffer = []
                    
                nxt = BlockLayout([child], self, previous, self.font_cache)
                self.children.append(nxt)
                previous = nxt
            if block_nodes_buffer:
                nxt = BlockLayout(block_nodes_buffer, self, previous, self.font_cache)
                self.children.append(nxt)
        else:
            self.cursor_x = 0 
            self.cursor_y = 0
            self.style = {
                "weight": "normal",
                "style" : "roman",
                "size": 12,
                "vertical-align": VerticalAlign.CENTER
            }
            self.ancestors = []

            self.line = []
            for node in self.nodes:
                self.recurse(node)
            self.flush_line()
        for child in self.children:
            child.layout()
        if mode == DisplayValue.BLOCK:
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y
    
    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(tree, word)
        else:
            if tree.tag == "br":
                self.flush()
            for child in tree.children:
                self.recurse(child)
   
    def get_font(self, size, weight, font_style):
        key = (size, weight, font_style)
        if key not in self.font_cache:
            font = tkinter.font.Font(
                size=key[0],
                weight=key[1],
                slant=key[2],
            )
            label = tkinter.Label(font=font)
            self.font_cache[key] = (font, label)
        return self.font_cache[key][0]

    def word(self, node, word):
        color = node.style["color"]
        weight = node.style["font-weight"]
        font_style = node.style["font-style"]
        if font_style == "normal": font_style = "roman"
        # assumes pixels
        size = int(float(node.style["font-size"][:-2]) * .75)
        font =  self.get_font(size, weight, font_style)
        text_width = font.measure(word)
        # if there is no horizontal space, write current line
        if self.cursor_x + text_width > self.width:
            self.flush_line()
        self.line.append((self.cursor_x, word, font, color, self.style['vertical-align']))
        # shouldn't be adding a space if its followed by a tag
        self.cursor_x += text_width + font.measure(" ") 

    def flush_line(self):
        """Calculates baseline, adds all text objects in one line to display_list"""
        if not self.line: return
        font_metrics = [font.metrics() for x, word, font, color, align in self.line]
        max_ascent = max([metric["ascent"] for metric in font_metrics])
        max_descent = max([metric["descent"] for metric in font_metrics])
        baseline = self.cursor_y + LEADING_FACTOR * max_ascent
        for rel_x, word, font, color, vAlign in self.line:
            x = self.x + rel_x
            match vAlign:
                case VerticalAlign.CENTER:
                    y = self.y + baseline - font.metrics("ascent")
                case VerticalAlign.TOP:
                    y = self.y + baseline - max_ascent 
                case VerticalAlign.BOTTOM:
                    y = self.y + (baseline + max_descent) - font.metrics("linespace")
            self.display_list.append((x, y, word, font, color))
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = 0 
        self.line = []

