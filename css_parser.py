import html_parser
from dataclasses import dataclass, field

type Selector = TagSelector | DescendantSelector

MEDIA_TAG = "@media"
UNIVERSAL_SELECTOR = "*"
PROPERY_VALUE_ALLOWED_CHARS = "@#-.%'" + '"'

@dataclass
class ClassSelector:
    class_selector: str
    priority:int = 1

    def matches(self, node: html_parser.Node):
        if not isinstance(node, html_parser.Element): return False
        classes = node.attributes.get('class', '').split(' ')
        return self.class_selector in classes

@dataclass
class TagSelector:
    tag: str
    priority:int = 2

    def matches(self, node: html_parser.Node):
        return isinstance(node, html_parser.Element) and (self.tag == UNIVERSAL_SELECTOR or self.tag == node.tag)

type IndividualSelector = ClassSelector|TagSelector

def get_individual_selector(selector: str) -> IndividualSelector:
    if selector.startswith('.'):
        return ClassSelector(selector[1:])
    else:
        return TagSelector(selector)

@dataclass
class DescendantSelector:
    ancestor: IndividualSelector 
    descendant: IndividualSelector 
    priority: int =  field(init=False)

    def __post_init__(self):
        self.priority = self.ancestor.priority + self.descendant.priority

    def matches(self, node: html_parser.Node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

@dataclass
class DirectDescendantSelector:
    ancestor: IndividualSelector 
    descendant: IndividualSelector 
    priority: int =  field(init=False)

    def __post_init__(self):
        self.priority = self.ancestor.priority + self.descendant.priority

    def matches(self, node: html_parser.Node):
        return self.descendant.matches(node) and node.parent and self.ancestor.matches(node.parent)

class SelectorParsingException(Exception):
    pass

class WordParsingException(Exception):
    pass

class LiteralParsingException(Exception):
    pass

class CSSParser:
    def __init__(self, style):
        self.style = style
        self.i = 0
    
    def parse(self):
        rules = []
        while self.i < len(self.style):
            try:
                self.whitespace()
                selectors = self.selector()
                # ignoring media tags for now
                if isinstance(selectors[0], TagSelector) and selectors[0].tag == MEDIA_TAG:
                   self.ignore_block()
                   continue
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                for selector in selectors:
                    rules.append((selector, body))
            except SelectorParsingException as e:
                # debugging purposes
                # error_c = self.style[self.i] if self.i < len(self.style) else 'EOF'
                # print(f"selector exception at {self.i}\nchar:{error_c}")
                why = self.ignore_until([";", "{"])
                if why == ";":
                    # if we see a pair, try to move past it
                    self.literal(";")
                    self.whitespace()
                else:
                    # if we see open brackets, skip the block since we have no selector
                    self.ignore_block()
            except (WordParsingException, LiteralParsingException) as e:
                # debugging purposes
                # error_c = self.style[self.i] if self.i < len(self.style) else 'EOF'
                # print(f"parse error at {self.i}\nchar:{error_c}\nerror {e}")
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
                
        return rules

    def selector(self):
        try:
            out = get_individual_selector(self.word().casefold())
            if isinstance(out, TagSelector) and out.tag == MEDIA_TAG:
                return [out]
            self.whitespace()
            selectors = []
            while self.i < len(self.style) and self.style[self.i] != "{":
                if self.style[self.i] == ",":
                    selectors.append(out)
                    self.literal(",")
                    self.whitespace()
                    out = get_individual_selector(self.word().casefold())
                    self.whitespace()
                elif self.style[self.i] == '>':
                    self.literal(">")
                    self.whitespace()
                    tag = self.word()
                    descendant = get_individual_selector(tag.casefold())
                    out = DirectDescendantSelector(out, descendant)
                    self.whitespace()
                else:
                    tag = self.word()
                    descendant = get_individual_selector(tag.casefold())
                    out = DescendantSelector(out, descendant)
                    self.whitespace()
            return selectors + [out] 
        except (WordParsingException, LiteralParsingException) as e:
            raise SelectorParsingException(e)

    def body(self):
        pairs = {}
        while self.i < len(self.style) and self.style[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop] = val
                # don't treat a missing ending ';' as an error
                if self.i == len(self.style) or self.style[self.i] == "}":
                    break
                self.literal(';')
                self.whitespace()
            except Exception as e:
                # debugging purposes
                # print(f"body error at {self.i}\nchar:{self.style[self.i]}\npairs: {pairs}\nerror {e}")
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs
    
    def pair(self):
        self.whitespace()
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word(", ")
        self.whitespace()
        return prop.casefold(), val.strip()
    
    def whitespace(self):
        while self.i < len(self.style) and self.style[self.i].isspace():
            self.i += 1
    
    def word(self, extra_allowed_chars = ""):
        start = self.i
        allowed_chars = PROPERY_VALUE_ALLOWED_CHARS + extra_allowed_chars 
        while self.i < len(self.style):
            char = self.style[self.i]
            if char.isalnum() or char in allowed_chars:
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise WordParsingException("Error parsing word")
        return self.style[start: self.i]

    def literal(self, literal):
        if not (self.i < len(self.style) and self.style[self.i] == literal):
            raise LiteralParsingException("Error parsing literal")
        self.i += 1

    def ignore_until(self, chars):
        while self.i < len(self.style):
            char = self.style[self.i]
            if char in chars:
                return char
            else:
                self.i += 1
        return None
    
    def ignore_block(self):
        """Moves the pointer past the next {} block"""
        if self.i >= len(self.style) - 1:
            return
        if self.style[self.i] != "{":
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

if __name__ == "__main__":
    print(*CSSParser(open('test.css').read()).parse(), sep='\n')
 