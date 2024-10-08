from dataclasses import dataclass, field
from url import URL

END_CHARACTER_REF = ["<", ">", " ", "\n"]
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
SELF_CLOSING_TAGS = [
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
]
HEAD_TAGS = [
    "base",
    "basefont",
    "bgsound",
    "noscript",
    "link",
    "meta",
    "title",
    "style",
    "script",
]


@dataclass()
class Node:
    children: list["Node"] = field(kw_only=True, default_factory=list)
    style: dict[str, str] = field(kw_only=True, default_factory=dict)
    parent: "Node"

    def __eq__(self, other: object) -> bool:
        """Check equality

        Checks whether children, styles are equal
        """
        if isinstance(other, Node):
            return self.children == other.children and all(
                [
                    key in other.style and other.style[key] == value
                    for key, value in self.style.items()
                ]
            )
        return False

    def __repr__(self):
        return f"style:{repr(self.style)} children:{repr(self.children)}"


@dataclass()
class Text(Node):
    text: str
    is_focused = False

    def __repr__(self):
        return f"<Text: {repr(self.text)} {super().__repr__()}>"

    def __eq__(self, other: object) -> bool:
        is_eq = super().__eq__(other)
        if is_eq:
            return self.text == other.text
        return False


@dataclass()
class Element(Node):
    tag: str
    attributes: dict[str, str]
    is_focused = False

    def __repr__(self):
        return (
            f"<Element: {self.tag} {super().__repr__()} attr:{repr(self.attributes)}>"
        )

    def __eq__(self, other):
        is_eq = super().__eq__(other)
        if is_eq:
            return self.tag == other.tag and all(
                [
                    key in other.attributes and other.attributes[key] == value
                    for key, value in self.attributes.items()
                ]
            )
        return False

    def __hash__(self):
        return hash((id(self)))


def create_anon_block(parent: Node, style: dict[str, str], children: list[Node]):
    style["display"] = "block"
    return Element(parent, "_anon_", {}, children=children, style=style)


class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def add_text(self, text):
        if text.isspace():
            return
        self.add_missing_tags()
        parent = self.unfinished[-1] if self.unfinished else None
        node = Text(parent, text)
        if parent:
            parent.children.append(node)

    def add_tag(self, text):
        tag, attributes = get_tag_attributes(text)
        if tag.startswith("!"):
            return
        self.add_missing_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in SELF_CLOSING_TAGS:
            # what if we start wit a self closing tag?
            parent = self.unfinished[-1]
            node = Element(parent, tag, attributes)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(parent, tag, attributes)
            self.unfinished.append(node)

    def finish(self):
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def add_missing_tags(self, current_tag=None):
        """Adds missing tags. Called implicit_tags in book."""
        while True:
            open_tags = [node.tag for node in self.unfinished]
            # First tag needs to be HTML
            if not open_tags and current_tag != "html":
                self.add_tag("html")
            # Second tag should be head, body or close html tag
            elif open_tags == ["html"] and current_tag not in ["head", "body", "/html"]:
                if current_tag in HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            # Make sure we close the head tag if the current doesn't belong there
            elif (
                open_tags == ["html", "head"]
                and current_tag not in ["/head"] + HEAD_TAGS
            ):
                self.add_tag("/head")
            else:
                break

    def parse(self):
        in_tag = False
        in_character_reference = False
        saved_chars = ""
        for c in self.body:
            if in_character_reference and c in END_CHARACTER_REF:
                in_character_reference = False
                self.add_text(f"&{saved_chars}")
                saved_chars = ""
            if in_tag:
                if c == ">":
                    in_tag = False
                    self.add_tag(saved_chars)
                    saved_chars = ""
                else:
                    saved_chars += c
            elif in_character_reference:
                if c == ";":
                    in_character_reference = False
                    has_reference = saved_chars in CHARACTER_REF_MAP
                    self.add_text(
                        CHARACTER_REF_MAP[saved_chars]
                        if has_reference
                        else f"&{saved_chars};"
                    )
                    saved_chars = ""
                else:
                    saved_chars += c
            elif c == "<":
                in_tag = True
                if saved_chars:
                    self.add_text(saved_chars)
                saved_chars = ""
            elif c == "&":
                in_character_reference = True
                if saved_chars:
                    self.add_text(saved_chars)
                saved_chars = ""
            else:
                saved_chars += c
        # if we end while saving characters, spit them out
        if in_character_reference:
            self.add_text("&")
        elif in_tag:
            self.add_text("<")
        if saved_chars:
            self.add_text(saved_chars)
        return self.finish()


def get_tag_attributes(text: str) -> tuple[str, dict[str, str]]:
    parts = text.split(None, 1)
    tag = parts[0].casefold()
    key_buffer = ""
    val_buffer = None
    in_quotes = False
    attributes = {}
    attr_string = parts[1] if len(parts) > 1 else ""
    for c in attr_string:
        if c.isspace() and not in_quotes and key_buffer:
            val = "true"
            if not val_buffer == None:
                val = val_buffer
                val_buffer = None
            attributes[key_buffer.casefold()] = val
            key_buffer = ""
        elif c in ["'", '"'] and key_buffer:
            in_quotes = not in_quotes
            if not in_quotes:
                attributes[key_buffer.casefold()] = val_buffer if val_buffer else ""
                key_buffer = ""
            val_buffer = "" if in_quotes else None
        elif in_quotes:
            val_buffer += c
        elif c == "=":
            val_buffer = ""
        elif not c.isspace() and c not in ["/"]:
            if val_buffer == None:
                key_buffer += c
            else:
                val_buffer += c
    if key_buffer:
        val = "true"
        if not val_buffer == None:
            val = val_buffer
            val_buffer = ""
        attributes[key_buffer.casefold()] = val

    return tag, attributes


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


def tree_to_list(tree: Node, list: list[Node]) -> list[Node]:
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


if __name__ == "__main__":
    import sys

    if not len(sys.argv) > 1:
        print("need a url!")
    else:
        arg = sys.argv[1]
        (body, cache_time) = URL(arg).request()
        nodes = HTMLParser(body).parse()
        print_tree(nodes)
