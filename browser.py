import layout
import html_parser
import time
import tkinter
import tkinter.font
import url
from dataclasses import dataclass
from display_constants import *
from functools import partial
from PIL import ImageTk, Image

DEFAULT_FILE = 'file://test.txt'
HOME_IMAGE = 'img/home.png'

VIEW_SOURCE = 'view-source:'

class Browser:
    def __init__(self):
        self.cache = {}
        self.font_cache = {}
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
        tree = layout.Text(None, body) if is_view_source else html_parser.HTMLParser(body).parse()
        if cache_time > 0:
            print(f"storing at {time.time()} with {cache_time}")
            self.cache[input] = (tree, time.time(), cache_time)
        self.document = layout.DocumentLayout(tree, self.font_cache)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
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
        self.canvas.create_rectangle(
            0, 0,
            WIDTH, 2 * VSTEP + URL_BAR_HEIGHT,
            width=0,
            fill="#dedede",
        )
        self.canvas.create_window(HSTEP, VSTEP, window=home_button, anchor="nw", width=HOME_BUTTON_WIDTH, height=URL_BAR_HEIGHT)
        self.canvas.create_window(HSTEP + HOME_BUTTON_WIDTH + HSTEP, VSTEP, window=url_entry, anchor="nw", height=URL_BAR_HEIGHT, width=URL_BAR_WIDTH)
        self.canvas.create_window(HSTEP + HOME_BUTTON_WIDTH + HSTEP + URL_BAR_WIDTH + HSTEP, VSTEP, window=submit_button, anchor="nw", height=URL_BAR_HEIGHT)
    
    def draw(self):
        content_tag = "content"
        self.canvas.delete(content_tag)
        for cmd in self.display_list:
            if cmd.top > self.scroll_offset + HEIGHT: continue
            if cmd.bottom < self.scroll_offset + URL_BAR_HEIGHT + 3 * VSTEP: continue
            cmd.execute(self.scroll_offset, self.canvas, tags=[content_tag])
    
    def scroll(self, offset, e):
        max_y = max(self.document.height + 3 * VSTEP + URL_BAR_HEIGHT - HEIGHT, 0)
        self.scroll_offset = min(max(0, self.scroll_offset + offset), max_y)
        self.draw()

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

if __name__ == "__main__":
    import sys
    if not len(sys.argv) > 1:
        arg = DEFAULT_FILE
    else:
        arg = sys.argv[1]
    b = Browser()
    b.load(arg)
    tkinter.mainloop()
