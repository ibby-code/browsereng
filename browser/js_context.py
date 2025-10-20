import dukpy
import threading
from css_parser import CSSParser, SelectorParsingException
from enum import Enum
from html_parser import Element, HTMLParser, tree_to_list
from task import Task

RUNTIME_JS_FILE = "runtime.js"
RUNTIME_JS = open(RUNTIME_JS_FILE).read()

EVENT_DISPATCH_JS = (
    "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type, dukpy.payload))"
)

SETTIMEOUT_JS = "__runSetTimeout(dukpy.handle)"
XHR_ONLOAD_JS = "__runXHROnload(dukpy.out, dukpy.handle)"
RUN_RAF_HANLDERS_JS = "__runRAFHandlers()"

class JSEvent(Enum):
    CLICK = "click"
    KEYDOWN = "keydown"
    SUBMIT = "submit"


class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.discarded = False
        self.node_to_handle: dict[Element, int] = {}
        self.handle_to_node: dict[int, Element] = {}
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.export_function("querySelectorAll", self.query_selector_all)
        self.interp.export_function("getAttribute", self.get_attribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("value_get", self.value_get)
        self.interp.export_function("XMLHttpRequest_send", self.XMLHttpRequest_send)
        self.interp.export_function("setTimeout", self.set_timeout)
        self.interp.export_function("requestAnimationFrame", self.request_animation_frame)
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
        self.tab.set_needs_render()

    def value_get(self, handle: int) -> str:
        elt = self.handle_to_node[handle]
        if elt.tag == "input":
            return self.get_attribute(handle, "value")

    def dispatch_xhr_onload(self, out, handle):
        if self.discarded: return
        self.interp.evaljs(XHR_ONLOAD_JS, out=out, handle=handle)

    def XMLHttpRequest_send(self, method: str, url: str, body: str, is_async: bool, handle) -> str:
        full_url = self.tab.url.resolve(url)
        if not self.tab.is_request_allowed(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")
        if full_url.origin() != self.tab.url.origin():
            raise Exception("Cross-origin XHR request not allowed")
        # do we cache this at some point?
        def run_load():
            _, response, _ = full_url.request(self.tab.url, body)
            task = Task(self.dispatch_xhr_onload, response, handle)
            self.tab.task_runner.schedule_task(task)
            return response
        if not is_async:
            return run_load()
        else:
            threading.Thread(target=run_load).start()
    
    def dispatch_settimeout(self, handle):
        if self.discarded: return
        self.interp.evaljs(SETTIMEOUT_JS, handle=handle)
    
    def set_timeout(self, handle, time):
        def run_callback():
            task = Task(self.dispatch_settimeout, handle)
            self.tab.task_runner.schedule_task(task)
        threading.Timer(time / 1000.0, run_callback).start()

    def dispatch_request_animaton_frame_handlers(self):
        self.interp.evaljs(RUN_RAF_HANLDERS_JS)

    def request_animation_frame(self):
        self.tab.browser.set_needs_animation_frame(self.tab)

    def get_handle(self, elt: Element) -> int:
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle
