import dukpy
from css_parser import CSSParser, SelectorParsingException
from enum import Enum
from html_parser import Element, HTMLParser, tree_to_list

RUNTIME_JS_FILE = "runtime.js"
RUNTIME_JS = open(RUNTIME_JS_FILE).read()

EVENT_DISPATCH_JS = (
    "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type, dukpy.payload))"
)


class JSEvent(Enum):
    CLICK = "click"
    KEYDOWN = "keydown"
    SUBMIT = "submit"


class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.node_to_handle: dict[Element, int] = {}
        self.handle_to_node: dict[int, Element] = {}
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.query_selector_all)
        self.interp.export_function("getAttribute", self.get_attribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("value_get", self.value_get)
        self.interp.export_function("XMLHttpRequest_send", self.XMLHttpRequest_send)
        self.run(RUNTIME_JS_FILE, RUNTIME_JS)

    def run(self, script: str, code: str):
        try:
            return self.interp.evaljs(code)
        except dukpy.JSRuntimeError as e:
            print("Script", script, "crashed", e)

    def dispatch_event(self, type: JSEvent, elt: Element, payload: str = "") -> bool:
        handle = self.node_to_handle.get(elt, -1)
        default_enabled = self.interp.evaljs(
            EVENT_DISPATCH_JS, type=type.value, handle=handle, payload=payload
        )
        return not default_enabled

    def query_selector_all(self, selector_text: str | None) -> list[int]:
        if not selector_text:
            return []
        try:
            selector = CSSParser(selector_text).selector()[0]
            nodes = [
                node
                for node in tree_to_list(self.tab.nodes, [])
                if selector.matches(node)
            ]
            return [self.get_handle(node) for node in nodes]
        except SelectorParsingException as e:
            print(e)
            return []

    def get_attribute(self, handle: int, attr: str) -> str:
        elt = self.handle_to_node[handle]
        attr = elt.attributes.get(attr, None)
        return attr if attr else ""

    def innerHTML_set(self, handle: int, s: str):
        doc = HTMLParser(f"<html><body>{s}</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
        self.tab.render()

    def value_get(self, handle: int) -> str:
        elt = self.handle_to_node[handle]
        if elt.tag == "input":
            return self.get_attribute(handle, "value")

    def XMLHttpRequest_send(self, method: str, url: str, body: str) -> str:
        full_url = self.tab.url.resolve(url)
        if not self.tab.is_request_allowed(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")
        # do we cache this at some point?
        _, response, _ = full_url.request(self.tab.url, body)
        return response

    def get_handle(self, elt: Element) -> int:
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle
