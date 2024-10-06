import time
import typing
import urllib.parse
from css_parser import CSSParser, Selector
from display_constants import DEFAULT_FONT_SIZE_PX, CLEARABLE_CONTENT_TAG, VSTEP, WIDTH
from draw_commands import DrawRect
from enum import Enum
from html_parser import Element, Node, Text, HTMLParser, tree_to_list
from layout import DocumentLayout
from js_context import JSContext, JSEvent
from url import URL

DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()
VIEW_SOURCE = "view-source:"

INHERITED_PROPERTIES = {
    "font-family": "Times",
    "font-size": f"{DEFAULT_FONT_SIZE_PX}px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
    "cursor": "auto",
}


class LoadAction(Enum):
    NEW = "loading new url"
    HISTORY = "loading history"
    FORM = "submitting form"


class Tab:
    def __init__(
        self,
        cookie_jar: dict[str, str],
        cache: dict[URL, (str, int, int)],
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

    def is_request_allowed(self, u: URL):
        return not self.allowed_origins or u.origin() in self.allowed_origins

    def load_stylesheets(self, nodes_list: list[Node]):
        links = [
            node.attributes["href"]
            for node in nodes_list
            if isinstance(node, Element)
            and node.tag == "link"
            and node.attributes.get("rel") == "stylesheet"
            and "href" in node.attributes
        ]
        rules = DEFAULT_STYLE_SHEET.copy()
        for link in links:
            style_url = self.url.resolve(link)
            if not self.is_request_allowed(style_url):
                print("Blocked stylesheet", link, "from loading due to CSP")
                continue
            try:
                cached_response = self.request_from_cache(style_url)
                if cached_response:
                    headers, css, cache_time = cached_response
                else:
                    headers, css, cache_time = style_url.request(self.url)
                    self.cache_request(style_url, headers, css, cache_time)
            except:
                continue
            new_rules = CSSParser(css).parse()
            # print(new_rules)
            rules.extend(new_rules)
        return rules

    def load_javascript(self, nodes_list: list[Node]):
        scripts = [
            node.attributes["src"]
            for node in nodes_list
            if isinstance(node, Element)
            and node.tag == "script"
            and "src" in node.attributes
        ]
        self.js = JSContext(self)
        for script in scripts:
            script_url = self.url.resolve(script)
            if not self.is_request_allowed(script_url):
                print("Blocked script", script, "from loading due to CSP")
                continue
            try:
                cached_response = self.request_from_cache(script_url)
                if cached_response:
                    headers, js, cache_time = cached_response
                else:
                    headers, js, cache_time = script_url.request(self.url)
                    self.cache_request(script_url, headers, js, cache_time)
            except:
                continue
            self.js.run(script, js)

    def load(
        self,
        input: str | URL,
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

            new_url = URL(self.cookie_jar, link)
        else:
            new_url = input
        skip_cache = load_action == LoadAction.FORM
        cache_response = None if skip_cache else self.request_from_cache(new_url)
        if cache_response:
            headers, body, cache_time = cache_response
        else:
            try:
                headers, body, cache_time = new_url.request(self.url, payload)
                if not skip_cache:
                    self.cache_request(new_url, headers, body, cache_time)
            except ConnectionError as e:
                headers = {}
                body = create_error_html(e)
        self.url = new_url
        self.nodes = Text(None, body) if is_view_source else HTMLParser(body).parse()
        self.allowed_origins = None
        if "content-security-policy" in headers:
            csp = headers["content-security-policy"].split()
            if len(csp) > 0 and csp[0] == "default-src":
                self.allowed_origins = []
                for origin in csp[1:]:
                    self.allowed_origins.append(URL({}, origin).origin())
        nodes_list = tree_to_list(self.nodes, [])
        self.rules = self.load_stylesheets(nodes_list)
        self.load_javascript(nodes_list)
        titles = [
            node.children[0].text
            for node in nodes_list
            if isinstance(node, Element) and node.tag == "title"
        ]
        self.title = titles[0] if len(titles) else ""
        self.render()

    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        # print(self.display_list)

    def request_from_cache(self, url: URL) -> tuple[str, int, dict[str, str]] | None:
        if url in self.cache:
            headers, content, store_time, max_age = self.cache[url]
            print(f"retrieving at {store_time} with {max_age} at {time.time()}")
            if store_time + max_age > time.time():
                return (content, 0, headers)
            else:
                del self.cache[input]

    def cache_request(
        self, url: URL, headers: dict[str, str], body: str, cache_time: int
    ):
        if cache_time > 0:
            print(f"storing at {time.time()} with {cache_time}")
            self.cache[url] = (headers, body, time.time(), cache_time)

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

    def raster(self, canvas):
        DrawRect("white", x1=0, y1=0, x2=WIDTH, y2=self.tab_height).execute(canvas)
        for cmd in self.display_list:
            cmd.execute(canvas)

    def scroll_to_fragment(self, fragment: str, layout_list):
        print(f"scrolling to {fragment}")
        layout_y = [
            item.y
            for item in layout_list
            if isinstance(item.node, Element)
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
            if self.js.dispatch_event(JSEvent.KEYDOWN, self.focus, char):
                return
            if self.focus.tag == "input":
                self.focus.attributes["value"] += char
                self.render()
                return True
        return False

    def backspace(self):
        if self.focus:
            if self.js.dispatch_event(JSEvent.KEYDOWN, self.focus, "backspace"):
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
            if self.js.dispatch_event(JSEvent.KEYDOWN, self.focus, "enter"):
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
        layout_list = tree_to_list(self.document, [])
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
            if not isinstance(elt, Element):
                elt = elt.parent
                continue
            if elt.tag == "a" and "href" in elt.attributes:
                if self.js.dispatch_event(JSEvent.CLICK, elt):
                    return
                href = elt.attributes["href"]
                print("href", href)
                # ignore fragment links
                if href.startswith("#"):
                    return self.scroll_to_fragment(href, layout_list)
                url = self.url.resolve(href)
                return self.load(url)
            elif elt.tag == "input":
                if self.js.dispatch_event(JSEvent.CLICK, elt):
                    return
                elt.attributes["value"] = ""
                if self.focus:
                    self.focus.is_focused = False
                self.focus = elt
                elt.is_focused = True
                return self.render()
            elif elt.tag == "button":
                if self.js.dispatch_event(JSEvent.CLICK, elt):
                    return
                elt = self.try_submit_form_parent(elt)
            if elt:
                elt = elt.parent

    def try_submit_form_parent(self, elt: Element) -> Element | None:
        # travel up until you find a form
        while elt:
            if (
                isinstance(elt, Element)
                and elt.tag == "form"
                and "action" in elt.attributes
            ):
                return self.submit_form(elt)
            elt = elt.parent
        return elt

    def submit_form(self, elt: Element):
        if self.js.dispatch_event(JSEvent.SUBMIT, elt):
            return
        inputs = [
            node
            for node in tree_to_list(elt, [])
            if isinstance(node, Element)
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


def style(node: Node, rules: list[tuple[Selector, dict[str, str]]]):
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
    if isinstance(node, Element) and "style" in node.attributes:
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


def create_error_html(exception: ConnectionError) -> str:
    return f"<html><body><h1>Page load error</h1><p>{exception}</p></body></html>"


def cascade_priority(rule):
    selector, body = rule
    return selector.priority


def paint_tree(layout_object, display_list):
    if layout_object.should_paint():
        display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)
