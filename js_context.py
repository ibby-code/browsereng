import browser
import dukpy
from css_parser import CSSParser, SelectorParsingException
from html_parser import Node

RUNTIME_JS_FILE = "runtime.js"
RUNTIME_JS = open(RUNTIME_JS_FILE).read()


class JSContext:
    def __init__(self, tab: browser.Tab):
        self.tab = tab
        self.node_to_handle: dict[Node, int] = {}
        self.handle_to_node: dict[int, Node] = {}
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.query_selector_all)
        self.interp.export_function("getAttribute", self.get_attribute)
        self.run(RUNTIME_JS_FILE, RUNTIME_JS)

    def run(self, script: str, code: str):
        try:
            return self.interp.evaljs(code)
        except dukpy.JSRuntimeError as e:
            print("Script", script, "crashed", e)

    def query_selector_all(self, selector_text: str | None):
        if not selector_text:
            return []
        try:
            selector = CSSParser(selector_text).selector()[0]
            nodes = [
                node
                for node in browser.tree_to_list(self.tab.nodes, [])
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

    def get_handle(self, elt: Node) -> int:
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle
