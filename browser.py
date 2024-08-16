import url

DEFAULT_FILE = 'file://C:/Users/ibbya/Documents/recurse/browser/test.txt'

VIEW_SOURCE = 'view-source:'
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

def show(body, show_html = False):
    in_tag = False
    in_character_reference = False 
    saved_chars = ""
    for c in body:
        if in_tag and not show_html:
            if c == ">":
                in_tag = False
        elif in_character_reference:
            if c in END_CHARACTER_REF:
                in_character_reference = False
                print(f"&{saved_chars}{c}", end="")
                saved_chars = ""
            elif c == ";":
                in_character_reference = False
                has_reference = saved_chars in CHARACTER_REF_MAP
                print(CHARACTER_REF_MAP[saved_chars] if has_reference else f"&{saved_chars};", end="")
                saved_chars = ""
            else:
                saved_chars += c
        elif c == "<" and not show_html:
            in_tag = True
        elif c == "&":
            in_character_reference = True 
        else:
            print(c, end="")
    if saved_chars:
        print(f"&{saved_chars}", end="")

def load(input):
    is_view_source = False
    if input.startswith(VIEW_SOURCE):
        is_view_source = True
        input = input[len(VIEW_SOURCE):]

    print(input)
    request = url.URL(input)
    body = request.request()
    show(body, is_view_source)

if __name__ == "__main__":
    import sys
    if not len(sys.argv) > 1:
        arg = DEFAULT_FILE
    else:
        arg = sys.argv[1]
    load(arg)
