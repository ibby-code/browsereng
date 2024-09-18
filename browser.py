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
    "font-family": "Times",
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
    "cursor": "auto",
}

CLEARABLE_CONTENT_TAG = "clearable"

class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = layout.get_font("Arisl", 20, "normal", "roman")
        self.font_height = self.font.metrics("linespace")
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2 * self.padding
        self.bottom = self.urlbar_bottom

        plus_width = self.font.measure("+") + 2 * self.padding
        self.newtab_rect = layout.Rect(self.padding, self.padding, self.padding + plus_width, self.padding + self.font_height)

        back_width = self.font.measure("<") + 2 * self.padding
        self.back_rect = layout.Rect(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding
        )
 
        home_width = self.font.measure("H") + 2 * self.padding
        self.home_rect = layout.Rect(
            self.padding + self.back_rect.right,
            self.urlbar_top + self.padding,
            self.padding + home_width + self.back_rect.right,
            self.urlbar_bottom - self.padding
        )

        self.address_rect = layout.Rect(
            self.padding + self.home_rect.right,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding
        )
    
    def click(self, x, y):
        if self.newtab_rect.containsPoint(x, y):
            self.browser.new_tab(DEFAULT_FILE)
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).containsPoint(x, y):
                    self.browser.active_tab = tab
                    break
    
    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width = self.font.measure("Tab X") + 2*self.padding
        return layout.Rect(
            tabs_start + tab_width * i, self.tabbar_top,
            tabs_start + tab_width * (i + 1), self.tabbar_bottom)
    
    def paint(self):
        cmds = []
        # add background for chrome
        cmds.append(layout.DrawRect(
            layout.Rect(0, 0, WIDTH, self.bottom),
            "white"))
        cmds.append(layout.DrawLine(
            layout.Rect(0, self.bottom, WIDTH,
            self.bottom), "black", 1))
        # add new tab button
        cmds.append(layout.DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(layout.DrawText(
            self.newtab_rect.left + self.padding,
            self.newtab_rect.top,
            "+", self.font, "black"))
        # draw tabs
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(layout.DrawLine(layout.Rect(bounds.left, 0, bounds.left, bounds.bottom),
                "black", 1))
            cmds.append(layout.DrawLine(layout.Rect(
                bounds.right, 0, bounds.right, bounds.bottom),
                "black", 1))
            cmds.append(layout.DrawText(
                bounds.left + self.padding, bounds.top + self.padding,
                "Tab {}".format(i), self.font, "black"))
            if tab == self.browser.active_tab:
                cmds.append(layout.DrawLine(layout.Rect(
                    0, bounds.bottom, bounds.left, bounds.bottom),
                    "black", 1))
                cmds.append(layout.DrawLine(layout.Rect(
                    bounds.right, bounds.bottom, WIDTH, bounds.bottom),
                    "black", 1))
        # draw back button
        cmds.append(layout.DrawOutline(self.back_rect, "black", 1))
        cmds.append(layout.DrawText(
            self.back_rect.left + self.padding,
            self.back_rect.top,
            "<", self.font, "black"))
        # draw home button
        cmds.append(layout.DrawOutline(self.home_rect, "black", 1))
        cmds.append(layout.DrawText(
            self.home_rect.left + self.padding,
            self.home_rect.top,
            "H", self.font, "black"))
        # draw address bar
        cmds.append(layout.DrawOutline(self.address_rect, "black", 1))
        url = str(self.browser.active_tab.url)
        cmds.append(layout.DrawText(
            self.address_rect.left + self.padding,
            self.address_rect.top,
            url, self.font, "black"))
        return cmds

class Browser:
    def __init__(self):
        self.tabs: list[Tab] = []
        self.active_tab: Tab|None = None
        self.window = tkinter.Tk()
        self.window.title("CanYouBrowseIt")
        self.window.bind("<Button-1>", self.click)
        self.window.bind("<Down>", partial(self.scroll, SCROLL_STEP))
        self.window.bind("<Up>", partial(self.scroll, -SCROLL_STEP))
        self.window.bind("<MouseWheel>", self.scroll_mouse)
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, bg=BG_DEFAULT_COLOR)
        self.canvas.tag_bind(POINTER_HOVER_TAG, "<Enter>", partial(self.set_cursor, "hand1"))
        self.canvas.tag_bind(POINTER_HOVER_TAG, "<Leave>", partial(self.set_cursor, ""))
        self.chrome = Chrome(self)
        self.canvas.pack()

    def scroll_mouse(self, e):
        delta = e.delta
        if delta % 120 == 0:
            # windows uses multiples of 120
            offset = SCROLL_STEP * (delta // 120)
        else:
            # mac uses multiples of 1
            offset = SCROLL_STEP * delta
        self.scroll(offset, e)
    
    def scroll(self, increment, e):
        self.active_tab.scroll(increment)
        self.draw()
    
    def click(self, e):
        # being called for clicks on home button / entry bar
        if e.y < self.chrome.bottom:
            print("chrome click")
            self.chrome.click(e.x, e.y)
        else:
            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
        self.draw()

    def set_cursor(self, cursor, e):
        # print("set cursor", cursor)
        self.canvas.config(cursor=cursor)

    def load_url(self, e=None):
        url_value = self.url_value.get()
        print(url_value)
        if url_value:
            self.active_tab.load(url_value)
            self.draw()

    def load_home_url(self):
        self.active_tab.load(DEFAULT_FILE)
   
    def new_tab(self, url):
        new_tab = Tab(HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()

    def draw(self):
        self.canvas.delete(CLEARABLE_CONTENT_TAG)
        self.active_tab.draw(self.canvas, self.chrome.bottom)
        # TODO: add tabs to clearable content
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)

class Tab:
    def __init__(self, tab_height):
        # TODO: share cache across tabs?
        self.cache = {}
        self.tab_height = tab_height
        self.scroll_offset = 0
        self.url = None
        self.display_list = []

    def load(self, input: str|url.URL):
        print("loading:", input)
        self.scroll_offset = 0
        is_view_source = False
        if isinstance(input, str):
            link = input
            if input.startswith(VIEW_SOURCE):
                is_view_source = True
                link = input[len(VIEW_SOURCE) :]

            self.url = url.URL(link)
        else:
            self.url = input
        cache_response = self.request_from_cache(self.url)
        if cache_response:
            body, cache_time = cache_response
        else:
            body, cache_time = self.url.request()
            self.cache_request(self.url, body, cache_time)
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
            style_url = self.url.resolve(link)
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
            # print(new_rules)
            rules.extend(new_rules)
        style(tree, sorted(rules, key=cascade_priority))

        self.document = layout.DocumentLayout(tree)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        # print(self.display_list)
    
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

    def draw(self, canvas, offset):
        for cmd in self.display_list:
            if cmd.rect.top> self.scroll_offset + self.tab_height:
                continue
            if cmd.rect.bottom < self.scroll_offset + VSTEP:
                continue
            cmd.execute(self.scroll_offset - offset, canvas, tags=[CLEARABLE_CONTENT_TAG])
    
    def scroll(self, offset):
        max_y = max(self.document.height + VSTEP - self.tab_height, 0)
        self.scroll_offset = min(max(0, self.scroll_offset + offset), max_y)
    
    def click(self, x, y):
        # print("click ", x, y)
        y += self.scroll_offset
        # filter all objects that are at this spot
        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width
                and obj.y <= y < obj.y + obj.height]
        # print(objs)
        if not objs: return
        elt = objs[-1].node
        # find the clickable element
        while elt:
            if isinstance(elt, html_parser.Element) and elt.tag == "a" and "href" in elt.attributes:
                href = elt.attributes["href"]
                print('href', href)
                # ignore fragment links
                if href.startswith("#"):
                    return
                url = self.url.resolve(href)
                return self.load(url)
            elt = elt.parent
        

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

def load_home_image():
    im = Image.open(HOME_IMAGE)
    im.thumbnail((20, 20), Image.Resampling.LANCZOS)
    home_img = ImageTk.PhotoImage(im)
    return home_img
 
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
    b.new_tab(arg)
    tkinter.mainloop()
