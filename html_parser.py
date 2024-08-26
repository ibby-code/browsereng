from dataclasses import dataclass, field
from url import URL

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
SELF_CLOSING_TAGS = [
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
]

@dataclass()
class Node:
    children: list["Node"] = field(kw_only=True, default_factory=list)
    parent: "Node"

@dataclass()
class Text(Node):
    text: str

    def __repr__(self):
        return repr(self.text)

@dataclass()
class Element(Node):
    tag: str
    attributes: dict[str, str]

    def __repr__(self):
        return f"<{self.tag}>"

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def add_text(self, text):
        if text.isspace(): return
        parent = self.unfinished[-1] if self.unfinished else None
        node = Text(parent, text)
        if parent:
            parent.children.append(node)

    def add_tag(self, text):
        tag, attributes = get_tag_attributes(text)
        if tag.startswith("!"): return
        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
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
                    self.add_text(CHARACTER_REF_MAP[saved_chars] if has_reference else f"&{saved_chars};")
                    saved_chars = ""
                else:
                    saved_chars += c
            elif c == "<" :
                in_tag = True
                self.add_text(saved_chars)
                saved_chars = ""
            elif c == "&":
                in_character_reference = True 
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
            self.add_text(f"{saved_chars}")
        return self.finish() 

def get_tag_attributes(text: str) -> tuple[str, dict[str, str]]:
    parts = text.split(None, 1)
    tag = parts[0].casefold()
    key_buffer = ""
    val_buffer = ""
    in_quotes = False
    attributes = {}
    attr_string = parts[1] if len(parts) > 1 else ""
    for c in attr_string:
        if c.isspace() and not in_quotes and key_buffer:
            attributes[key_buffer.casefold()] = ""
            key_buffer = ""
        elif c in ["'", "\""] and key_buffer: 
            in_quotes = not in_quotes
            if not in_quotes:
                attributes[key_buffer.casefold()] = val_buffer
                key_buffer = ""
                val_buffer = ""
        elif in_quotes:
            val_buffer += c
        elif not c.isspace() and c not in ["/", "="]:
            key_buffer += c
    return tag, attributes

def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

if __name__ == "__main__":
    import sys
    if not len(sys.argv) > 1:
        print("need a url!")
    else:
        arg = sys.argv[1]
        (body, cache_time) = URL(arg).request()
        nodes = HTMLParser(body).parse()
        print_tree(nodes)
 