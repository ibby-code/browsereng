import tkinter
from enum import Enum
from html_parser import Text
from display_constants import *

class VerticalAlign(Enum):
    CENTER  = 0
    TOP = 1
    BOTTOM = 2

class Layout:
    def __init__(self, tree, font_cache):
        self.display_list = []
        self.line = []
        self.cursor_x = HSTEP
        self.cursor_y = URL_BAR_HEIGHT + VSTEP * 2
        self.style = {"weight": "normal", "style" : "roman", "size": 12, "vertical-align": VerticalAlign.CENTER}
        self.ancestors = []
        self.font_cache = font_cache
        self.recurse(tree)
        self.flush_line()
    
    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def open_tag(self, tag):
        match tag:
            case "i":
                self.ancestors.append(self.style.copy())
                self.style['style'] = "italic"
            case "b":
                self.ancestors.append(self.style.copy())
                self.style['weight'] = "bold"
            case "small":
                self.ancestors.append(self.style.copy())
                self.style['size'] -= 2  
            case "big":
                self.ancestors.append(self.style.copy())
                self.style['size'] += 4  
            case "sup":
                self.ancestors.append(self.style.copy())
                self.style['vertical-align'] = VerticalAlign.TOP
                self.style['size'] -= 4  
            case "sub":
                self.ancestors.append(self.style.copy())
                self.style['vertical-align'] = VerticalAlign.BOTTOM
                self.style['size'] -= 4  
            case "br":
                self.flush_line()
            case "p":
                self.flush_line()
                # margin b4 paragraph. will prob move to css
                self.cursor_y += VSTEP

    def close_tag(self, tag):
        match tag:
           case "i" | "b" | "small" | "big" | "sup" | "sub":
                self.style = self.ancestors.pop()
           case "p":
                self.flush_line() 
                # margin after the paragraph
                self.cursor_y += VSTEP
    
    def get_font(self):
        key = (self.style['size'], self.style['weight'], self.style['style']) 
        if key not in self.font_cache:
            font = tkinter.font.Font(
                size=key[0],
                weight=key[1],
                slant=key[2],
            )
            label = tkinter.Label(font=font)
            self.font_cache[key] = (font, label)
        return self.font_cache[key][0]

    def word(self, word):
        font =  self.get_font()
        text_width = font.measure(word)
        # if there is no horizontal space, write current line
        if self.cursor_x + text_width > WIDTH - HSTEP:
            self.flush_line()
        self.line.append((self.cursor_x, word, font, self.style['vertical-align']))
        # shouldn't be adding a space if its followed by a tag
        self.cursor_x += text_width + font.measure(" ") 

    def flush_line(self):
        """Calculates baseline, adds all text objects in one line to display_list"""
        if not self.line: return
        font_metrics = [font.metrics() for x, word, font, align in self.line]
        max_ascent = max([metric["ascent"] for metric in font_metrics])
        max_descent = max([metric["descent"] for metric in font_metrics])
        baseline = self.cursor_y + LEADING_FACTOR * max_ascent
        for x, word, font, vAlign in self.line:
            match vAlign:
                case VerticalAlign.CENTER:
                    y = baseline - font.metrics("ascent")
                case VerticalAlign.TOP:
                    y = baseline - max_ascent 
                case VerticalAlign.BOTTOM:
                    y = (baseline + max_descent) - font.metrics("linespace")
            self.display_list.append((x, y, word, font))
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = HSTEP
        self.line = []

