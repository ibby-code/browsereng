import unittest

from html_parser import HTMLParser, Element, Text, get_tag_attributes, create_anon_block, tree_to_list


TAG_ATTRIBUTES_CASES = [
    ("no attributes", "p ", {"tag": "p", "attrs": {}}),
    ("closing tag", "/p ", {"tag": "/p", "attrs": {}}),
    (
        "one attribute",
        'a href="google.com"',
        {"tag": "a", "attrs": {"href": "google.com"}},
    ),
    (
        "multiple attributes",
        'a href="google.com" target="_blank"',
        {"tag": "a", "attrs": {"href": "google.com", "target": "_blank"}},
    ),
    (
        "case insensitive",
        'a href="google.com" HREF="apple.com"',
        {"tag": "a", "attrs": {"href": "apple.com"}},
    ),
]


class TestHTMLParser(unittest.TestCase):
    def setUp(self):
        self.html_node = Element(None, "html", {}, children=[Element(None, "body", {})])
        self.body_node = self.html_node.children[0]
        self.body_node.parent = self.html_node

    def test_parse_no_tags(self):
        html = "hello moto"
        new_node = Text(self.body_node, html)
        self.body_node.children = [new_node]

        self.assertEqual(HTMLParser(html).parse(), self.html_node)

    def test_parse_full_tags(self):
        message = "hello moto"
        html = f'<html><body><p class="text">{message}</p></body></html>'
        p_node = Element(self.body_node, "p", {"class": "text"})
        self.body_node.children = [p_node]
        text_node = Text(p_node, message)
        p_node.children = [text_node]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_parse_missing_head_tag(self):
        html = "<html><script></script><p>hi</p></html>"
        head_node = Element(self.html_node, "head", {})
        self.html_node.children = [head_node, self.body_node]
        script_node = Element(head_node, "script", {})
        head_node.children = [script_node]
        p_node = Element(self.body_node, "p", {})
        self.body_node.children = [p_node]
        text_node = Text(p_node, "hi")
        p_node.children = [text_node]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_parse_unclosed_tag(self):
        html = "<p>hi"
        p_node = Element(self.body_node, "p", {"class": "text"})
        self.body_node.children = [p_node]
        text_node = Text(p_node, "hi")
        p_node.children = [text_node]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_parse_character_ref(self):
        html = "&gt;"
        text_node = Text(self.body_node, ">")
        self.body_node.children = [text_node]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_parse_almost_character_ref(self):
        html = "&gtclose panda"
        text_node_one = Text(self.body_node, "&gtclose")
        text_node_two = Text(self.body_node, " panda")
        self.body_node.children = [text_node_one, text_node_two]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_parse_almost_character_ref_at_end(self):
        html = "&gtclose"
        text_node_one = Text(self.body_node, "&")
        text_node_two = Text(self.body_node, "gtclose")
        self.body_node.children = [text_node_one, text_node_two]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_parse_self_closing_tags(self):
        html = "<input />hello"
        input_node = Element(self.body_node, "input", {})
        text_node = Text(self.body_node, "hello")
        self.body_node.children = [input_node, text_node]

        parsed = HTMLParser(html).parse()
        self.assertEqual(parsed, self.html_node)

    def test_create_anon_block(self):
        style = {"color": "red"}
        text_node = Text(self.body_node, "hello")
        node = Element(self.body_node, "_anon_", {}, children=[text_node], style=style)

        self.assertEqual(create_anon_block(self.body_node, style, [text_node]), node)

    def test_tree_to_list(self):
        p_node = Element(self.body_node, "p", {"class": "text"})
        self.body_node.children = [p_node]
        text_node = Text(p_node, "hello moto")
        p_node.children = [text_node]

        self.assertEqual(tree_to_list(self.html_node, []), [self.html_node, self.body_node, p_node, text_node])

    def test_get_tag_attributes(self):
        for title, input, ans in TAG_ATTRIBUTES_CASES:
            with self.subTest(title):
                tag, attrs = get_tag_attributes(input)
                self.assertEqual(tag, ans["tag"])
                self.assertEqual(attrs, ans["attrs"])


if __name__ == "__main__":
    unittest.main()
