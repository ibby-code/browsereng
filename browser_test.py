
import browser
import unittest
from unittest.mock import patch

SHOW_TEST_CASES = [
    ('<div>Hi</div', 'Hi'),
    ('&lt;Hi&gt;', '<Hi>'),
    ('&george;', '&george;'),
    ('&<div>Sam;', '&Sam;'),
    ('<span &lt>People</span> Hi', 'People Hi')
]

class TestBrowser(unittest.TestCase):
    
    @patch('url.URL')
    def test_load_url(self, url_ctr):
        url_ctr.return_value.request.return_value = '<div>Hi</div>'
        self.assertEqual(browser.load('http://google.com'), 'Hi') 

    @patch('url.URL')
    def test_load_view_source(self, url_ctr):
        url_ctr.return_value.request.return_value = '<div>Hi</div>'
        self.assertEqual(browser.load('view-source:http://google.com'), '<div>Hi</div>') 


    def test_show(self):
        for (input, ans) in SHOW_TEST_CASES:
            with self.subTest(input):
                self.assertEqual(browser.show(input), ans)



if __name__ == "__main__":
    unittest.main()
