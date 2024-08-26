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

    def __repr__(self):
        return f"<{self.tag}>"

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def add_text(self, text):
        parent = self.unfinished[-1] if self.unfinished else None
        node = Text(parent, text)
        if parent:
            parent.children.append(node)

    def add_tag(self, tag):
        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(parent, tag)
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
 