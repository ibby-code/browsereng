import time
import tkinter
import tkinter.font
import url
from dataclasses import dataclass
from functools import partial

DEFAULT_FILE = 'file://C:/Users/ibbya/Documents/recurse/browser/test.txt'

VIEW_SOURCE = 'view-source:'
END_CHARACTER_REF = ['<', '>', ' ', '\n']
CHARACTER_REF_MAP = {
    "amp": "&",	
    "lt": "<",	
    "gt": ">",	
    "quot": '"',	
    "apos": "'",	
    "nbsp": " ",
    "ndash": "–",	
    "mdash": "—",	
    "copy": "©",	
    "reg": "®",	
    "trade": "™",	
    "asymp": "≈",	
    "ne": "≠",	
    "pound": "£",	
    "euro": "€",	
    "deg": "°",	
}
WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

@dataclass
class Text:
    """Represent html text"""
    text: str

@dataclass
class Tag:
    """Represents a tag"""
    tag: str

class Browser:
    def __init__(self):
        self.cache = {}
        self.window = tkinter.Tk()
        self.window.bind("<Down>", partial(self.scroll, SCROLL_STEP))
        self.window.bind("<Up>", partial(self.scroll, -SCROLL_STEP))
        self.scroll_offset = 0
        self.display_list = []
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()
    
    def load(self, input):
        if input in self.cache:
            content, store_time, max_age = self.cache[input]
            print(f"retrieving at {store_time} with {max_age} at {time.time()}")
            if store_time + max_age > time.time():
                return content
            else:
                del self.cache[input]
        is_view_source = False
        link = input
        if input.startswith(VIEW_SOURCE):
            is_view_source = True
            link = input[len(VIEW_SOURCE):]

        request = url.URL(link)
        body, cache_time = request.request()
        content = body if is_view_source else lex(body)
        if cache_time > 0:
            print(f"storing at {time.time()} with {cache_time}")
            self.cache[input] = (content, time.time(), cache_time)
        self.display_list = layout(content)
        self.draw()
    
    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll_offset + HEIGHT: continue
            if y + VSTEP < self.scroll_offset: continue
            self.canvas.create_text(x, y - self.scroll_offset, text=c, anchor="nw")
    
    def scroll(self, offset, e):
        self.scroll_offset = max(0, self.scroll_offset + offset)
        self.draw()

def layout(text):
    font = tkinter.font.Font()
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for word in text.split():
        text_width = font.measure(word)
        if cursor_x + text_width > WIDTH - HSTEP:
            cursor_x = HSTEP
            cursor_y += font.metrics("linespace") * 1.25
        display_list.append((cursor_x, cursor_y, word))
        cursor_x += text_width + font.measure(" ") 
    return display_list

def lex(body):
    in_tag = False
    in_character_reference = False 
    saved_chars = ""
    display = ""
    for c in body:
        if in_character_reference and c in END_CHARACTER_REF:
            in_character_reference = False
            display += f"&{saved_chars}"
            saved_chars = ""
        if in_tag:
            if c == ">":
                in_tag = False
        elif in_character_reference:
            if c == ";":
                in_character_reference = False
                has_reference = saved_chars in CHARACTER_REF_MAP
                display += CHARACTER_REF_MAP[saved_chars] if has_reference else f"&{saved_chars};"
                saved_chars = ""
            else:
                saved_chars += c
        elif c == "<" :
            in_tag = True
        elif c == "&":
            in_character_reference = True 
        else:
            display += c
    if saved_chars:
        display += f"&{saved_chars}"
    return display

if __name__ == "__main__":
    import sys
    if not len(sys.argv) > 1:
        arg = DEFAULT_FILE
    else:
        arg = sys.argv[1]
    b = Browser()
    b.load(arg)
    tkinter.mainloop()
