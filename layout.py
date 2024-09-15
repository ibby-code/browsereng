import tkinter
from dataclasses import dataclass, field
from enum import Enum
from html_parser import Element, Text, create_anon_block
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
    BASELINE = 'baseline'
    SUB = 'sub'
    SUPER = 'super'

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
        child = BlockLayout(self.node, self, None, self.font_cache)
        self.children.append(child)
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = URL_BAR_HEIGHT + 2 * VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []

class BlockLayout:
    def __init__(self, node, parent, previous, font_cache):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
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
            for node in self.children:
                cmds.extend(node.paint())
        return cmds

    def layout_mode(self):
        if isinstance(self.node, Text):
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
                    anon_box = create_anon_block(self.node, self.node.style, block_nodes_buffer)
                    previous = BlockLayout(anon_box, self, previous, self.font_cache)
                    self.children.append(previous)
                    block_nodes_buffer = []
                    
                nxt = BlockLayout(child, self, previous, self.font_cache)
                self.children.append(nxt)
                previous = nxt
            if block_nodes_buffer:
                anon_box = create_anon_block(self.node, self.node.style, block_nodes_buffer)
                nxt = BlockLayout(anon_box, self, previous, self.font_cache)
                self.children.append(nxt)
        else:
            self.cursor_x = 0 
            self.new_line()
            self.recurse(self.node)
        for child in self.children:
            child.layout()
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

    def get_font(self, font_family, size, weight, font_style):
        key = (font_family, size, weight, font_style)
        if key not in self.font_cache:
            font = tkinter.font.Font(
                family=key[0],
                size=key[1],
                weight=key[2],
                slant=key[3],
            )
            label = tkinter.Label(font=font)
            self.font_cache[key] = (font, label)
        return self.font_cache[key][0]
   
    def word(self, node, word):
        weight = node.style["font-weight"]
        # only support family for now (not serif)
        font_family = node.style["font-family"].split(',')[0].strip('"' + "'")
        font_style = node.style["font-style"]
        if font_style == "normal": font_style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        font =  self.get_font(font_family, size, weight, font_style)
        text_width = font.measure(word)
 
       # if there is no horizontal space, write current line
        if self.cursor_x + text_width > self.width:
            self.new_line()

        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word, self.font_cache)
        line.children.append(text)
        self.cursor_x += text_width 
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
        for word in self.children:
            word.layout()

        font_metrics = [word.font.metrics() for word in self.children]
        max_ascent = max([metric["ascent"] for metric in font_metrics])
        max_descent = max([metric["descent"] for metric in font_metrics])
        baseline = self.y + LEADING_FACTOR * max_ascent
        for word in self.children:
            vertical_align = word.node.style.get("vertical-align", VerticalAlign.BASELINE)
            match vertical_align:
                case VerticalAlign.BASELINE:
                    word.y = baseline - word.font.metrics("ascent")
                case VerticalAlign.SUPER:
                    word.y = baseline - max_ascent 
                case VerticalAlign.SUB:
                    word.y = (baseline + max_descent) - word.font.metrics("linespace")
        self.height = 1.25 * (max_ascent + max_descent)

class TextLayout:
    def __init__(self, node, word, parent, previous, font_cache):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous
        self.font_cache = font_cache
    
    def paint(self):
        color = self.node.style["color"]
        return [DrawText(self.x, self.y, self.word, self.font, color)]
    
    def layout(self):
        weight = self.node.style["font-weight"]
        # only support family for now (not serif)
        font_family = self.node.style["font-family"].split(',')[0].strip('"' + "'")
        font_style = self.node.style["font-style"]
        # should prob use stylesheet for this
        if font_style == "normal": font_style = "roman"
        # assumes pixels
        size = int(float(self.node.style["font-size"][:-2]) * .75)
        self.font =  self.get_font(font_family, size, weight, font_style)
        self.width = self.font.measure(self.word)
 
        # calculate word position
        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x
        self.height = self.font.metrics("linespace")

    def get_font(self, font_family, size, weight, font_style):
        key = (font_family, size, weight, font_style)
        if key not in self.font_cache:
            font = tkinter.font.Font(
                family=key[0],
                size=key[1],
                weight=key[2],
                slant=key[3],
            )
            label = tkinter.Label(font=font)
            self.font_cache[key] = (font, label)
        return self.font_cache[key][0]

