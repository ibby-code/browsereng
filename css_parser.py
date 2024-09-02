import html_parser
from dataclasses import dataclass, field

type Selector = TagSelector | DescendantSelector

MEDIA_TAG = "@media"

@dataclass
class TagSelector:
    tag: str
    priority:int = 1

    def matches(self, node: html_parser.Node):
        return isinstance(node, html_parser.Element) and self.tag == node.tag

@dataclass
class DescendantSelector:
    ancestor: TagSelector
    descendant: TagSelector
    priority: int =  field(init=False)

    def __post_init__(self):
        self.priority = self.ancestor.priority + self.descendant.priority

    def matches(self, node: html_parser.Node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

class CSSParser:
    def __init__(self, style):
        self.style = style
        self.i = 0
    
    def body(self):
        pairs = {}
        while self.i < len(self.style) and self.style[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop] = val
                self.whitespace()
                # don't treat a missing ending ';' as an error
                if self.i == len(self.style) or self.style[self.i] == "}":
                    break
                self.literal(';')
                self.whitespace()
            except Exception as e:
                # debugging purposes
                print(f"body error at {self.i}\nchar:{self.style[self.i]}\nstyle:{self.style}\npairs: {pairs}\nerror {e}")
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def parse(self):
        rules = []
        while self.i < len(self.style):
            try:
                self.whitespace()
                selectors = self.selector()
                # ignoring media tags for now
                if isinstance(selectors[0], TagSelector) and selectors[0].tag == MEDIA_TAG:
                    self.ignore_until("{")
                    open_tags = 1
                    while open_tags > 0 and self.i < len(self.style):
                        self.i += 1
                        stop = self.ignore_until("{}")
                        if stop == "{":
                            open_tags += 1
                        elif stop == "}":
                            open_tags -= 1
                        else:
                            break
                    self.literal("}")
                    continue
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                for selector in selectors:
                    rules.append((selector, body))
            except Exception as e:
                # debugging purposes
                print(f"parse error at {self.i}\nchar:{self.style[self.i]}\nstyle:{self.style}\nrules: {rules}\nerror {e}")
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
                
        return rules

    def selector(self):
        out = TagSelector(self.word().casefold())
        if out.tag == MEDIA_TAG:
            return [out]
        self.whitespace()
        selectors = []
        while self.i < len(self.style) and self.style[self.i] != "{":
            if self.style[self.i] == ",":
                selectors.append(out)
                self.literal(",")
                self.whitespace()
                out = TagSelector(self.word().casefold())
                self.whitespace()
            else:
                tag = self.word()
                descendant = TagSelector(tag.casefold())
                out = DescendantSelector(out, descendant)
                self.whitespace()
        return selectors + [out] 
    
    def pair(self):
        self.whitespace()
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val
    
    def whitespace(self):
        while self.i < len(self.style) and self.style[self.i].isspace():
            self.i += 1
    
    def word(self):
        start = self.i
        while self.i < len(self.style):
            char = self.style[self.i]
            if char.isalnum() or char in "@#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception("Parsing error")
        return self.style[start: self.i]

    def literal(self, literal):
        if not (self.i < len(self.style) and self.style[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def ignore_until(self, chars):
        while self.i < len(self.style):
            char = self.style[self.i]
            if char in chars:
                return char
            else:
                self.i += 1
        return None

if __name__ == "__main__":
    print(*CSSParser(open('test.css').read()).parse(), sep='\n')
 