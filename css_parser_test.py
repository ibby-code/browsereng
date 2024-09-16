import unittest

from css_parser import (
    CSSParser,
    DescendantSelector,
    TagSelector,
    DirectDescendantSelector,
    ClassSelector,
)

BODY_TEST_CASES = [
    ("default", "display: block;", {"display": "block"}),
    ("missing ending semicolon", "display: block", {"display": "block"}),
    (
        "hypens in prop and value",
        "background-color: dark-red",
        {"background-color": "dark-red"},
    ),
    ("extra spaces", "  display   :   block  ;", {"display": "block"}),
    (
        "multiple rules",
        "display:block; background-color:red;",
        {"display": "block", "background-color": "red"},
    ),
    (
        "skips broken style",
        "display:block; jargon; background-color:red;",
        {"display": "block", "background-color": "red"},
    ),
]

PARSE_TEST_CASES = [
    ("empty", "", []),
    ("default", "h1 { display: block; }", [(TagSelector("h1"), {"display": "block"})]),
    (
        "multiple blocks",
        "h1 { display: block; background-color: dark-red} p { color: white; }",
        [
            (TagSelector("h1"), {"display": "block", "background-color": "dark-red"}),
            (TagSelector("p"), {"color": "white"}),
        ],
    ),
    (
        "empty block",
        "h1 { display: block; } p {}",
        [
            (TagSelector("h1"), {"display": "block"}),
            (TagSelector("p"), {}),
        ],
    ),
    (
        "descendant selector",
        "li p { color: red; }",
        [
            (DescendantSelector(TagSelector("li"), TagSelector("p")), {"color": "red"}),
        ],
    ),
    (
        "multi-level descendant selector",
        "li p a { color: red; }",
        [
            (
                DescendantSelector(
                    DescendantSelector(TagSelector("li"), TagSelector("p")),
                    TagSelector("a"),
                ),
                {"color": "red"},
            ),
        ],
    ),
    (
        "multi-element style",
        "li, p { color: red; }",
        [
            (TagSelector("li"), {"color": "red"}),
            (TagSelector("p"), {"color": "red"}),
        ],
    ),
    (
        "multi-element style w/descendant ",
        "li, li p { color: red; }",
        [
            (TagSelector("li"), {"color": "red"}),
            (DescendantSelector(TagSelector("li"), TagSelector("p")), {"color": "red"}),
        ],
    ),
    (
        "direct descendant",
        "li > p { color: red; }",
        [
            (
                DirectDescendantSelector(TagSelector("li"), TagSelector("p")),
                {"color": "red"},
            ),
        ],
    ),
    (
        "direct and indirect descendant",
        "li > p span { color: red; }",
        [
            (
                DescendantSelector(
                    DirectDescendantSelector(TagSelector("li"), TagSelector("p")),
                    TagSelector("span"),
                ),
                {"color": "red"},
            ),
        ],
    ),
    (
        "class selector",
        ".green-text { color: green; }",
        [
            (
                ClassSelector("green-text"),
                {"color": "green"},
            ),
        ],
    ),
    (
        "skips broken/unsupported selector",
        "h1 { display: block} p:before span {color: white;}  li {padding-left:2px;}",
        [
            (TagSelector("h1"), {"display": "block"}),
            (TagSelector("li"), {"padding-left": "2px"}),
        ],
    ),
    (
        "skips broken block",
        "h1 { display: block} p  color: white;  li {padding-left:2px;}",
        [
            (TagSelector("h1"), {"display": "block"}),
            (TagSelector("li"), {"padding-left": "2px"}),
        ],
    ),
    (
        "skips media tags",
        "h1 { display: block}\n @media (max-width:800px) {p  {color: white;}}\n  li {padding-left:2px;}",
        [
            (TagSelector("h1"), {"display": "block"}),
            (TagSelector("li"), {"padding-left": "2px"}),
        ],
    ),
]


class TestCSSParser(unittest.TestCase):

    def test_body(self):
        for title, input, ans in BODY_TEST_CASES:
            with self.subTest(title):
                parser = CSSParser(input)
                self.assertEqual(parser.body(), ans)

    def test_parse(self):
        for title, input, ans in PARSE_TEST_CASES:
            with self.subTest(title):
                parser = CSSParser(input)
                self.assertEqual(parser.parse(), ans)


if __name__ == "__main__":
    unittest.main()
