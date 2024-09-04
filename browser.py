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
from css_parser import CSSParser, Selector

BG_DEFAULT_COLOR = "white"
DEFAULT_FILE = "file://test.html"
DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()
HOME_IMAGE = "img/home.png"

VIEW_SOURCE = "view-source:"
INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


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
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, bg=BG_DEFAULT_COLOR)
        self.canvas.pack()
        self.draw_url_bar()

    def load(self, input):
        is_view_source = False
        link = input
        if input.startswith(VIEW_SOURCE):
            is_view_source = True
            link = input[len(VIEW_SOURCE) :]

        request = url.URL(link)
        cache_response = self.request_from_cache(request)
        if cache_response:
            body, cache_time = cache_response
        else:
            body, cache_time = request.request()
            self.cache_request(request, body, cache_time)
        tree = (
            layout.Text(None, body)
            if is_view_source
            else html_parser.HTMLParser(body).parse()
        )
        links = [
            node.attributes["href"]
            for node in tree_to_list(tree, [])
            if isinstance(node, html_parser.Element)
            and node.tag == "link"
            and node.attributes.get("rel") == "stylesheet"
            and "href" in node.attributes
        ]
        rules = DEFAULT_STYLE_SHEET.copy()
        for link in links:
            style_url = request.resolve(link)
            try:
                cached_response = self.request_from_cache(style_url)
                if cached_response:
                    css, cache_time = cached_response
                else:
                    css, cache_time = style_url.request()
                self.cache_request(style_url, css, cache_time)
            except:
                continue
            new_rules = CSSParser(css).parse()
            print(new_rules)
            rules.extend(new_rules)
        style(tree, sorted(rules, key=cascade_priority))

        self.document = layout.DocumentLayout(tree, self.font_cache)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()
    
    def request_from_cache(self, url: url.URL) -> tuple[str, int]|None:
        if url in self.cache:
            content, store_time, max_age = self.cache[url]
            print(f"retrieving at {store_time} with {max_age} at {time.time()}")
            if store_time + max_age > time.time():
                return (content, 0)
            else:
                del self.cache[input]

    def cache_request(self, url: url.URL, body: str, cache_time: int):
        if cache_time > 0:
            print(f"storing at {time.time()} with {cache_time}")
            self.cache[url] = (body, time.time(), cache_time)

    def load_url(self, e=None):
        url_value = self.url_value.get()
        print(url_value)
        if url_value:
            self.load(url_value)

    def load_home_url(self):
        self.load(DEFAULT_FILE)

    def draw_url_bar(self):
        url_entry = tkinter.Entry(
            self.window, textvariable=self.url_value, font=("Garamond", 10, "normal")
        )
        url_entry.bind("<Return>", self.load_url)
        submit_button = tkinter.Button(self.window, text="Go", command=self.load_url)
        im = Image.open(HOME_IMAGE)
        im.thumbnail((HOME_BUTTON_WIDTH, URL_BAR_HEIGHT), Image.Resampling.LANCZOS)
        home_img = ImageTk.PhotoImage(im)
        home_button = tkinter.Button(
            self.window, image=home_img, command=self.load_home_url
        )
        # you must save a reference to tkinter image to avoid garbage collection
        home_button.image = home_img
        self.canvas.create_rectangle(
            0,
            0,
            WIDTH,
            2 * VSTEP + URL_BAR_HEIGHT,
            width=0,
            fill="#dedede",
        )
        self.canvas.create_window(
            HSTEP,
            VSTEP,
            window=home_button,
            anchor="nw",
            width=HOME_BUTTON_WIDTH,
            height=URL_BAR_HEIGHT,
        )
        self.canvas.create_window(
            HSTEP + HOME_BUTTON_WIDTH + HSTEP,
            VSTEP,
            window=url_entry,
            anchor="nw",
            height=URL_BAR_HEIGHT,
            width=URL_BAR_WIDTH,
        )
        self.canvas.create_window(
            HSTEP + HOME_BUTTON_WIDTH + HSTEP + URL_BAR_WIDTH + HSTEP,
            VSTEP,
            window=submit_button,
            anchor="nw",
            height=URL_BAR_HEIGHT,
        )

    def draw(self):
        content_tag = "content"
        self.canvas.delete(content_tag)
        for cmd in self.display_list:
            if cmd.top > self.scroll_offset + HEIGHT:
                continue
            if cmd.bottom < self.scroll_offset + URL_BAR_HEIGHT + 3 * VSTEP:
                continue
            cmd.execute(self.scroll_offset, self.canvas, tags=[content_tag])

    def scroll(self, offset, e):
        max_y = max(self.document.height + 3 * VSTEP + URL_BAR_HEIGHT - HEIGHT, 0)
        self.scroll_offset = min(max(0, self.scroll_offset + offset), max_y)
        self.draw()


def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)


def style(node: html_parser.Node, rules: list[tuple[Selector, dict[str, str]]]):
    # pass down inherited or default values
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value
    # apply rules from CSS stylesheets
    for selector, body in rules:
        if not selector.matches(node):
            continue
        for prop, val in body.items():
            node.style[prop] = val
    # apply rules from 'style' attribute
    if isinstance(node, html_parser.Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value
    # compute actual values for percentages
    node_font_size = node.style["font-size"]
    if node.parent:
        parent_font_size = node.parent.style["font-size"]
    else:
        parent_font_size = INHERITED_PROPERTIES["font-size"]
    if node_font_size.endswith("%"):
        node_pct = float(node_font_size[:-1]) / 100
        parent_px = float(parent_font_size[:-2])
        node.style["font-size"] = str(node_pct * parent_px) + "px"
    elif node_font_size == "inherit":
        node.style["font-size"] = parent_font_size

    # recursively style the rest of the tree
    for child in node.children:
        style(child, rules)


def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def cascade_priority(rule):
    selector, body = rule
    return selector.priority


if __name__ == "__main__":
    import sys

    if not len(sys.argv) > 1:
        arg = DEFAULT_FILE
    else:
        arg = sys.argv[1]
    b = Browser()
    b.load(arg)
    tkinter.mainloop()
