import time
import tkinter
import url

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

class Browser:
    def __init__(self):
        self.cache = {}
        self.window = tkinter.Tk()
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
        self.draw(content)
    
    def draw(self, content):
        cursor_x, cursor_y = HSTEP, VSTEP
        for c in content:
            self.canvas.create_text(cursor_x, cursor_y, text=c)
            cursor_x += HSTEP
            if cursor_x + HSTEP > WIDTH:
                cursor_x = HSTEP
                cursor_y += VSTEP

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
