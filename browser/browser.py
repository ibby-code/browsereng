import urllib.parse
import draw_commands
import layout
import html_parser
import js_context
import time
import tkinter
import tkinter.font
import typing
import url
import urllib
from display_constants import HEIGHT, POINTER_HOVER_TAG, SCROLL_STEP, WIDTH, VSTEP
from enum import Enum
from functools import partial
from PIL import ImageTk, Image
from css_parser import CSSParser, Selector

DEFAULT_BROWSER_TITLE = "CanYouBrowseIt"
BG_DEFAULT_COLOR = "white"
DEFAULT_FILE = "file://testing/test.html"
DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()
HOME_IMAGE = "img/home.png"
HOME_IMAGE_SIZE = 24

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


class LoadAction(Enum):
    NEW = "loading new url"
    HISTORY = "loading history"
    FORM = "submitting form"


class Focusable(Enum):
    ADDRESS_BAR = "address bar"
    CONTENT = "content"


class Event(Enum):
    KEY = "<KEY>"
    ENTER = "<RETURN>"
    BACKSPACE = "backspace"
    LEFT_ARROW = "left_arrow"
    RIGHT_ARROW = "right_arrow"
    ESCAPE = "escape"


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
        self.newtab_rect = draw_commands.Rect(
            self.padding,
            self.padding,
            self.padding + plus_width,
            self.padding + self.font_height,
        )

        back_width = self.font.measure("<") + 2 * self.padding
        self.back_rect = draw_commands.Rect(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding,
        )
        forward_width = self.font.measure(">") + 2 * self.padding
        self.forward_rect = draw_commands.Rect(
            self.back_rect.right,
            self.urlbar_top + self.padding,
            self.back_rect.right + forward_width,
            self.urlbar_bottom - self.padding,
        )

        home_width = HOME_IMAGE_SIZE + 2 * self.padding
        self.home_rect = draw_commands.Rect(
            self.padding + self.forward_rect.right,
            self.urlbar_top + self.padding,
            self.padding + home_width + self.forward_rect.right,
            self.urlbar_bottom - self.padding,
        )

        self.address_rect = draw_commands.Rect(
            self.padding + self.home_rect.right,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding,
        )
        self.focus = None
        self.address_bar_value = ""
        self.address_cursor_index = 0

    def click(self, x, y):
        self.focus = None
        if self.newtab_rect.containsPoint(x, y):
            self.browser.new_tab(DEFAULT_FILE)
        elif self.back_rect.containsPoint(x, y):
            self.browser.active_tab.go_back()
        elif self.forward_rect.containsPoint(x, y):
            self.browser.active_tab.go_forward()
        elif self.home_rect.containsPoint(x, y):
            self.browser.active_tab.load(DEFAULT_FILE)
        elif self.address_rect.containsPoint(x, y):
            self.focus = Focusable.ADDRESS_BAR
            self.address_bar_value = ""
            self.address_cursor_index = 0
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).containsPoint(x, y):
                    self.browser.active_tab = tab
                    break

    def blur(self):
        self.focus = None

    def keypress(self, char: str) -> bool:
        if self.focus == Focusable.ADDRESS_BAR:
            self.address_bar_value = (
                self.address_bar_value[: self.address_cursor_index]
                + char
                + self.address_bar_value[self.address_cursor_index :]
            )
            self.address_cursor_index = min(
                self.address_cursor_index + 1, len(self.address_bar_value)
            )
            return True
        return False

    def backspace(self) -> bool:
        if self.focus == Focusable.ADDRESS_BAR:
            self.address_bar_value = (
                self.address_bar_value[: self.address_cursor_index - 1]
                + self.address_bar_value[self.address_cursor_index :]
            )
            self.address_cursor_index = max(self.address_cursor_index - 1, 0)
            return True
        return False

    def arrow_key(self, event: Event):
        if self.focus == Focusable.ADDRESS_BAR:
            increment = 1 if event == Event.RIGHT_ARROW else -1
            new_val = self.address_cursor_index + increment
            self.address_cursor_index = min(
                max(new_val, 0), len(self.address_bar_value)
            )
            return True
        return False

    def enter(self) -> bool:
        if self.focus == Focusable.ADDRESS_BAR:
            self.browser.active_tab.load(self.address_bar_value)
            self.focus = None
            return True
        return False

    def escape(self):
        if self.focus:
            self.focus = None
            return True
        return False

    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width = self.font.measure("Tab X") + 2 * self.padding
        return draw_commands.Rect(
            tabs_start + tab_width * i,
            self.tabbar_top,
            tabs_start + tab_width * (i + 1),
            self.tabbar_bottom,
        )

    def paint(self):
        cmds = []
        # add background for chrome
        cmds.append(
            draw_commands.DrawRect(
                draw_commands.Rect(0, 0, WIDTH, self.bottom), "white"
            )
        )
        cmds.append(
            draw_commands.DrawLine(
                draw_commands.Rect(0, self.bottom, WIDTH, self.bottom), "black", 1
            )
        )
        # add new tab button
        cmds.append(draw_commands.DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(
            draw_commands.DrawText(
                self.newtab_rect.left + self.padding,
                self.newtab_rect.top,
                "+",
                self.font,
                "black",
                tags=[POINTER_HOVER_TAG],
            )
        )
        # draw tabs
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(
                draw_commands.DrawLine(
                    draw_commands.Rect(bounds.left, 0, bounds.left, bounds.bottom),
                    "black",
                    1,
                )
            )
            cmds.append(
                draw_commands.DrawLine(
                    draw_commands.Rect(bounds.right, 0, bounds.right, bounds.bottom),
                    "black",
                    1,
                )
            )
            cmds.append(
                draw_commands.DrawText(
                    bounds.left + self.padding,
                    bounds.top + self.padding,
                    "Tab {}".format(i),
                    self.font,
                    "black",
                    tags=[POINTER_HOVER_TAG],
                )
            )
            if tab == self.browser.active_tab:
                cmds.append(
                    draw_commands.DrawLine(
                        draw_commands.Rect(
                            0, bounds.bottom, bounds.left, bounds.bottom
                        ),
                        "black",
                        1,
                    )
                )
                cmds.append(
                    draw_commands.DrawLine(
                        draw_commands.Rect(
                            bounds.right, bounds.bottom, WIDTH, bounds.bottom
                        ),
                        "black",
                        1,
                    )
                )
        # draw back button
        back_tags = []
        back_color = "grey"
        if self.browser.active_tab.has_back_history():
            back_tags.append(POINTER_HOVER_TAG)
            back_color = "black"
        cmds.append(draw_commands.DrawOutline(self.back_rect, back_color, 1))
        cmds.append(
            draw_commands.DrawText(
                self.back_rect.left + self.padding,
                self.back_rect.top,
                "<",
                self.font,
                back_color,
                tags=back_tags,
            )
        )
        # draw forward button
        forward_tags = []
        forward_color = "grey"
        if self.browser.active_tab.has_forward_history():
            forward_tags.append(POINTER_HOVER_TAG)
            forward_color = "black"
        cmds.append(draw_commands.DrawOutline(self.forward_rect, forward_color, 1))
        cmds.append(
            draw_commands.DrawText(
                self.forward_rect.left + self.padding,
                self.forward_rect.top,
                ">",
                self.font,
                forward_color,
                tags=forward_tags,
            )
        )
        # draw home button
        cmds.append(draw_commands.DrawOutline(self.home_rect, "black", 1))
        self.image = load_home_image()
        height = self.home_rect.bottom - self.home_rect.top
        extra_space = height - self.image.height()
        h_padding = round(extra_space / 2)
        cmds.append(
            draw_commands.DrawImage(
                self.home_rect.left + self.padding,
                self.home_rect.top + h_padding,
                self.image,
                tags=[POINTER_HOVER_TAG],
            )
        )
        # draw address bar
        cmds.append(draw_commands.DrawOutline(self.address_rect, "black", 1))
        url = str(self.browser.active_tab.url)
        if self.focus == Focusable.ADDRESS_BAR:
            cmds.append(
                draw_commands.DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    self.address_bar_value,
                    self.font,
                    "black",
                )
            )
            w = self.font.measure(self.address_bar_value[: self.address_cursor_index])
            cmds.append(
                draw_commands.DrawLine(
                    draw_commands.Rect(
                        self.address_rect.left + self.padding + w,
                        self.address_rect.top,
                        self.address_rect.left + self.padding + w,
                        self.address_rect.bottom,
                    ),
                    "red",
                    1,
                )
            )
        else:
            cmds.append(
                draw_commands.DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    url,
                    self.font,
                    "black",
                )
            )
        return cmds


class Browser:
    def __init__(self):
        self.cookie_jar: dict[str, str] = {}
        self.url_cache: dict[url.URL, (str, int, int)] = {}
        self.tabs: list[Tab] = []
        self.active_tab: Tab | None = None
        self.window = tkinter.Tk()
        self.window.title(DEFAULT_BROWSER_TITLE)
        self.window.bind("<Key>", partial(self.handle_event, Event.KEY))
        self.window.bind("<Return>", partial(self.handle_event, Event.ENTER))
        self.window.bind("<BackSpace>", partial(self.handle_event, Event.BACKSPACE))
        self.window.bind("<Right>", partial(self.handle_event, Event.RIGHT_ARROW))
        self.window.bind("<Left>", partial(self.handle_event, Event.LEFT_ARROW))
        self.window.bind("<Escape>", partial(self.handle_event, Event.ESCAPE))
        self.window.bind("<Button-1>", self.click)
        self.window.bind("<Down>", partial(self.scroll, SCROLL_STEP))
        self.window.bind("<Up>", partial(self.scroll, -SCROLL_STEP))
        self.window.bind("<MouseWheel>", self.scroll_mouse)
        self.canvas = tkinter.Canvas(
            self.window, width=WIDTH, height=HEIGHT, bg=BG_DEFAULT_COLOR
        )
        self.canvas.tag_bind(
            POINTER_HOVER_TAG, "<Enter>", partial(self.set_cursor, "hand1")
        )
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
            self.focus = None
            self.active_tab.blur()
            self.chrome.click(e.x, e.y)
        else:
            self.focus = Focusable.CONTENT
            self.chrome.blur()
            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
        self.draw()

    def handle_event(self, event: Event, e: tkinter.Event):
        should_draw = False
        match event:
            case Event.ENTER:
                should_draw = self.chrome.enter()
                if not should_draw and self.focus == Focusable.CONTENT:
                    should_draw = self.active_tab.enter()
            case Event.BACKSPACE:
                should_draw = self.chrome.backspace()
                if not should_draw and self.focus == Focusable.CONTENT:
                    should_draw = self.active_tab.backspace()
            case Event.LEFT_ARROW | Event.RIGHT_ARROW:
                should_draw = self.chrome.arrow_key(event)
            case Event.ESCAPE:
                should_draw = self.chrome.escape()
            case Event.KEY:
                if len(e.char) == 0:
                    return
                if not (0x20 <= ord(e.char) < 0x7F):
                    return
                should_draw = self.chrome.keypress(e.char)
                if not should_draw and self.focus == Focusable.CONTENT:
                    should_draw = self.active_tab.keypress(e.char)
        if should_draw:
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

    def new_tab(self, url):
        new_tab = Tab(self.cookie_jar, self.url_cache, HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()

    def draw(self):
        self.canvas.delete(CLEARABLE_CONTENT_TAG)
        title = (
            self.active_tab.title if self.active_tab.title else DEFAULT_BROWSER_TITLE
        )
        self.window.title(title)
        self.active_tab.draw(self.canvas, self.chrome.bottom)
        # TODO: add tabs to clearable content
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)


class Tab:
    def __init__(
        self,
        cookie_jar: dict[str, str],
        cache: dict[url.URL, (str, int, int)],
        tab_height: int,
    ):
        self.cookie_jar = cookie_jar
        self.cache = cache
        self.title = ""
        self.backward_history = []
        self.forward_history = []
        self.tab_height = tab_height
        self.scroll_offset = 0
        self.url = None
        self.focus = None
        self.display_list = []

    def has_back_history(self) -> bool:
        return len(self.backward_history) > 1

    def has_forward_history(self) -> bool:
        return len(self.forward_history) > 0

    def load_stylesheets(self, nodes_list: list[html_parser.Node]):
        links = [
            node.attributes["href"]
            for node in nodes_list
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
        return rules

    def load_javascript(self, nodes_list: list[html_parser.Node]):
        scripts = [
            node.attributes["src"]
            for node in nodes_list
            if isinstance(node, html_parser.Element)
            and node.tag == "script"
            and "src" in node.attributes
        ]
        self.js = js_context.JSContext(self)
        for script in scripts:
            script_url = self.url.resolve(script)
            try:
                cached_response = self.request_from_cache(script_url)
                if cached_response:
                    js, cache_time = cached_response
                else:
                    js, cache_time = script_url.request()
                self.cache_request(script_url, js, cache_time)
            except:
                continue
            self.js.run(script, js)

    def load(
        self,
        input: str | url.URL,
        load_action: typing.Optional[LoadAction] = LoadAction.NEW,
        payload: typing.Optional[str] = None,
    ):
        print("loading:", input)
        if not load_action == LoadAction.FORM:
            self.backward_history.append(input)
        if load_action == LoadAction.NEW:
            self.forward_history = []
        self.scroll_offset = 0
        is_view_source = False
        if isinstance(input, str):
            link = input
            if input.startswith(VIEW_SOURCE):
                is_view_source = True
                link = input[len(VIEW_SOURCE) :]

            self.url = url.URL(self.cookie_jar, link)
        else:
            self.url = input
        skip_cache = load_action == LoadAction.FORM
        cache_response = None if skip_cache else self.request_from_cache(self.url)
        if cache_response:
            body, cache_time = cache_response
        else:
            body, cache_time = self.url.request(payload)
            if not skip_cache:
                self.cache_request(self.url, body, cache_time)
        self.nodes = (
            layout.Text(None, body)
            if is_view_source
            else html_parser.HTMLParser(body).parse()
        )
        nodes_list = html_parser.tree_to_list(self.nodes, [])
        self.rules = self.load_stylesheets(nodes_list)
        self.load_javascript(nodes_list)
        titles = [
            node.children[0].text
            for node in nodes_list
            if isinstance(node, html_parser.Element) and node.tag == "title"
        ]
        self.title = titles[0] if len(titles) else ""
        self.render()

    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = layout.DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        # print(self.display_list)

    def request_from_cache(self, url: url.URL) -> tuple[str, int] | None:
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

    def go_back(self):
        if len(self.backward_history) > 1:
            current = self.backward_history.pop()
            self.forward_history.append(current)
            back = self.backward_history.pop()
            self.load(back, LoadAction.HISTORY)

    def go_forward(self):
        if len(self.forward_history) > 0:
            next = self.forward_history.pop()
            self.load(next, LoadAction.HISTORY)

    def draw(self, canvas, offset):
        for cmd in self.display_list:
            if cmd.rect.top > self.scroll_offset + self.tab_height:
                continue
            if cmd.rect.bottom < self.scroll_offset + VSTEP:
                continue
            cmd.execute(
                self.scroll_offset - offset, canvas, tags=[CLEARABLE_CONTENT_TAG]
            )

    def scroll_to_fragment(self, fragment: str, layout_list):
        print(f"scrolling to {fragment}")
        layout_y = [
            item.y
            for item in layout_list
            if isinstance(item.node, layout.Element)
            and item.node.attributes.get("id", "") == fragment[1:]
        ]
        if not len(layout_y) > 0:
            return
        destination = layout_y[0]
        offset = abs(self.scroll_offset - destination)
        self.scroll(-offset if self.scroll_offset > destination else offset)

    def scroll(self, offset):
        max_y = max(self.document.height + VSTEP - self.tab_height, 0)
        self.scroll_offset = min(max(0, self.scroll_offset + offset), max_y)

    def blur(self):
        if self.focus:
            self.focus.is_focused = False
            self.focus = None
            self.render()

    def keypress(self, char):
        if self.focus:
            if self.js.dispatch_event(js_context.JSEvent.KEYDOWN, self.focus, char):
                return
            if self.focus.tag == "input":
                self.focus.attributes["value"] += char
                self.render()
                return True
        return False

    def backspace(self):
        if self.focus:
            if self.js.dispatch_event(
                js_context.JSEvent.KEYDOWN, self.focus, "backspace"
            ):
                return
            if self.focus.tag == "input":
                orig_value = self.focus.attributes["value"]
                # return if there is nothing to delete
                if not orig_value:
                    return False
                self.focus.attributes["value"] = orig_value[:-1]
                self.render()
                return True
        return False

    def enter(self):
        if self.focus:
            if self.js.dispatch_event(js_context.JSEvent.KEYDOWN, self.focus, "enter"):
                return
            if self.focus.tag == "input":
                elt = self.try_submit_form_parent(self.focus)
                if elt:
                    self.render()
                    return True
        return False

    def click(self, x, y):
        # print("click ", x, y)
        y += self.scroll_offset
        # filter all objects that are at this spot
        layout_list = html_parser.tree_to_list(self.document, [])
        objs = [
            obj
            for obj in layout_list
            if obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height
        ]
        # print(objs)
        if not objs:
            return
        elt = objs[-1].node
        # find the clickable element
        while elt:
            if not isinstance(elt, html_parser.Element):
                elt = elt.parent
                continue
            if elt.tag == "a" and "href" in elt.attributes:
                if self.js.dispatch_event(js_context.JSEvent.CLICK, elt):
                    return
                href = elt.attributes["href"]
                print("href", href)
                # ignore fragment links
                if href.startswith("#"):
                    return self.scroll_to_fragment(href, layout_list)
                url = self.url.resolve(href)
                return self.load(url)
            elif elt.tag == "input":
                if self.js.dispatch_event(js_context.JSEvent.CLICK, elt):
                    return
                elt.attributes["value"] = ""
                if self.focus:
                    self.focus.is_focused = False
                self.focus = elt
                elt.is_focused = True
                return self.render()
            elif elt.tag == "button":
                if self.js.dispatch_event(js_context.JSEvent.CLICK, elt):
                    return
                elt = self.try_submit_form_parent(elt)
            if elt:
                elt = elt.parent

    def try_submit_form_parent(
        self, elt: html_parser.Element
    ) -> html_parser.Element | None:
        # travel up until you find a form
        while elt:
            if (
                isinstance(elt, html_parser.Element)
                and elt.tag == "form"
                and "action" in elt.attributes
            ):
                return self.submit_form(elt)
            elt = elt.parent
        return elt

    def submit_form(self, elt: html_parser.Element):
        if self.js.dispatch_event(js_context.JSEvent.SUBMIT, elt):
            return
        inputs = [
            node
            for node in html_parser.tree_to_list(elt, [])
            if isinstance(node, html_parser.Element)
            and node.tag == "input"
            and "name" in node.attributes
        ]
        body = ""
        for input in inputs:
            name = urllib.parse.quote(input.attributes["name"])
            value = urllib.parse.quote(input.attributes.get("value", ""))
            body += f"&{name}={value}"
        body = body[1:]
        url = self.url.resolve(elt.attributes["action"])
        self.load(url, LoadAction.FORM, body)
        return elt


def paint_tree(layout_object, display_list):
    if layout_object.should_paint():
        display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)


def load_home_image():
    im = Image.open(HOME_IMAGE)
    im.thumbnail((HOME_IMAGE_SIZE, HOME_IMAGE_SIZE), Image.Resampling.LANCZOS)
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
