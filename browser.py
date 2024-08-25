import math
import time
import tkinter
import tkinter.font
import url
from dataclasses import dataclass
from functools import partial
from PIL import ImageTk, Image

DEFAULT_FILE = 'file://test.txt'
HOME_IMAGE = 'img/home.png'

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
URL_BAR_HEIGHT = 20
URL_BAR_WIDTH = 600
HOME_BUTTON_WIDTH = 30 

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
        self.window.title("CanYouBrowseIt")
        self.window.bind("<Down>", partial(self.scroll, SCROLL_STEP))
        self.window.bind("<Up>", partial(self.scroll, -SCROLL_STEP))
        self.scroll_offset = 0
        self.url_value = tkinter.StringVar()
        self.display_list = []
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()
        self.draw_url_bar()
    
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
        tokens = [Text(body)] if is_view_source else lex(body)
        if cache_time > 0:
            print(f"storing at {time.time()} with {cache_time}")
            self.cache[input] = (tokens, time.time(), cache_time)
        self.display_list = Layout(tokens).display_list
        self.draw()
    
    def load_url(self, e = None):
        url_value = self.url_value.get() 
        print(url_value)
        if url_value:
            self.load(url_value)

    def load_home_url(self):
        self.load(DEFAULT_FILE)
    
    def draw_url_bar(self):
        url_entry = tkinter.Entry(self.window, textvariable=self.url_value, font=('Garamond', 10, 'normal'))
        url_entry.bind("<Return>", self.load_url)
        submit_button = tkinter.Button(self.window, text="Go", command=self.load_url)
        im = Image.open(HOME_IMAGE)
        im.thumbnail((HOME_BUTTON_WIDTH, URL_BAR_HEIGHT), Image.Resampling.LANCZOS)
        home_img = ImageTk.PhotoImage(im)
        home_button = tkinter.Button(self.window, image=home_img, command=self.load_home_url)
        # you must save a reference to tkinter image to avoid garbage collection
        home_button.image = home_img
        self.canvas.create_window(HSTEP, VSTEP, window=home_button, anchor="nw", width=HOME_BUTTON_WIDTH, height=URL_BAR_HEIGHT)
        self.canvas.create_window(HSTEP + HOME_BUTTON_WIDTH + HSTEP, VSTEP, window=url_entry, anchor="nw", height=URL_BAR_HEIGHT, width=URL_BAR_WIDTH)
        self.canvas.create_window(HSTEP + HOME_BUTTON_WIDTH + HSTEP + URL_BAR_WIDTH + HSTEP, VSTEP, window=submit_button, anchor="nw", height=URL_BAR_HEIGHT)
    
    def draw(self):
        self.canvas.delete("body")
        for x, y, c, f in self.display_list:
            if y > self.scroll_offset + HEIGHT: continue
            if y + VSTEP < self.scroll_offset: continue
            self.canvas.create_text(x, y - self.scroll_offset, text=c, font=f, anchor="nw", tags='body')
    
    def scroll(self, offset, e):
        self.scroll_offset = max(0, self.scroll_offset + offset)
        self.draw()

class Layout:
    def __init__(self, tokens):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = URL_BAR_HEIGHT + VSTEP * 2
        self.style = {"weight": "normal", "style" : "roman", "size": 12}
        self.ancestors = []
        for tok in tokens:
            self.token(tok)
    
    def token(self, token):
        if isinstance(token, Text):
            for word in token.text.split():
                self.word(word)
        else:
            match token.tag:
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
                case "/i" | "/b" | "/small" | "/big":
                    self.style = self.ancestors.pop()

    def word(self, word):
        font = tkinter.font.Font(
            size=self.style['size'],
            weight=self.style['weight'],
            slant=self.style['style'],
        )
        text_width = font.measure(word)
        if self.cursor_x + text_width > WIDTH - HSTEP:
            self.cursor_x = HSTEP
            self.cursor_y += font.metrics("linespace") * 1.25
        self.display_list.append((self.cursor_x, self.cursor_y, word, font))
        self.cursor_x += text_width + font.measure(" ") 


def lex(body):
    in_tag = False
    in_character_reference = False 
    saved_chars = ""
    display = [] 
    for c in body:
        if in_character_reference and c in END_CHARACTER_REF:
            in_character_reference = False
            display.append(Text(f"&{saved_chars}"))
            saved_chars = ""
        if in_tag:
            if c == ">":
                in_tag = False
                display.append(Tag(saved_chars))
                saved_chars = ""
            else:
                saved_chars += c
        elif in_character_reference:
            if c == ";":
                in_character_reference = False
                has_reference = saved_chars in CHARACTER_REF_MAP
                display.append(Text(CHARACTER_REF_MAP[saved_chars] if has_reference else f"&{saved_chars};"))
                saved_chars = ""
            else:
                saved_chars += c
        elif c == "<" :
            in_tag = True
            display.append(Text(saved_chars))
            saved_chars = ""
        elif c == "&":
            in_character_reference = True 
            display.append(Text(saved_chars))
            saved_chars = ""
        else:
            saved_chars += c
    if saved_chars:
        display.append(Text(f"&{saved_chars}"))
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
