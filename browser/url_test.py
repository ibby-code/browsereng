import url
import unittest
from unittest.mock import mock_open, call, patch, MagicMock

FAKE_FILE = "\nHello\nWorld\n"
HTTP_RESPONSE = "HTTP/1.0 200 OK\r\n" + "Header1: Value1\r\n\r\n" + "Body text"

RESOLVE_TEST_CASES = [
    {
        "name": "absolute url",
        "originalUrl": "https://www.google.com/",
        "resolveUrl": "https://www.facebook.com/image.svg",
        "host": "www.facebook.com",
        "port": 443,
        "scheme": "https",
        "path": "/image.svg",
    },
    {
        "name": "relative url",
        "originalUrl": "https://www.google.com/",
        "resolveUrl": "image.svg",
        "host": "www.google.com",
        "port": 443,
        "scheme": "https",
        "path": "/image.svg",
    },
    {
        "name": "relative url with slash",
        "originalUrl": "https://www.google.com/",
        "resolveUrl": "/image.svg",
        "host": "www.google.com",
        "port": 443,
        "scheme": "https",
        "path": "/image.svg",
    },
    {
        "name": "back relative url",
        "originalUrl": "https://www.google.com/news/listing/",
        "resolveUrl": "../favorites",
        "host": "www.google.com",
        "port": 443,
        "scheme": "https",
        "path": "/news/favorites",
    },
    {
        "name": "relative scheme url",
        "originalUrl": "https://www.google.com/news/listing/",
        "resolveUrl": "//www.example.com/example",
        "host": "www.example.com",
        "port": 443,
        "scheme": "https",
        "path": "/example",
    },
    {
        "name": "file url",
        "originalUrl": "file://test.html",
        "resolveUrl": "test.css",
        "host": "",
        "port": 0,
        "scheme": "file",
        "path": "test.css",
    },
    {
        "name": "relative file url",
        "originalUrl": "file://boo/foo/test.html",
        "resolveUrl": "../../test.css",
        "host": "",
        "port": 0,
        "scheme": "file",
        "path": "test.css",
    },
]


class TestUrl(unittest.TestCase):

    def test_resolve(self):
        for test_data in RESOLVE_TEST_CASES:
            with self.subTest(test_data["name"]):
                link = url.URL(test_data["originalUrl"])
                newUrl = link.resolve(test_data["resolveUrl"])
                self.assertEqual(newUrl.host, test_data["host"])
                self.assertEqual(newUrl.port, test_data["port"])
                self.assertEqual(newUrl.scheme, test_data["scheme"])
                self.assertEqual(newUrl.path, test_data["path"])

    @patch("builtins.open", new_callable=mock_open, read_data=FAKE_FILE)
    def test_file(self, file):
        test_file = "C:/Users/user/Documents/txt.txt"
        u = url.URL(f"file://{test_file}")
        self.assertEqual(u.request(), (FAKE_FILE, 0))
        file.assert_called_with(test_file, "r")

    def test_data(self):
        test_message = "hello world!"
        u = url.URL(f"data:text/html,{test_message}")
        self.assertEqual(u.request(), (test_message, 0))

    @patch("socket.socket")
    def test_http_get(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = f"GET /something HTTP/1.1\r\n"
        request += f"Host: google.com\r\n"
        request += f"User-Agent: CanYouBrowseIt\r\n\r\n"

        test_url = "http://google.com:4229/something"
        u = url.URL(test_url)
        response = u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 4229))
        mock_socket.send.assert_called_once_with(request.encode("utf-8"))
        self.assertEqual(response, ("Body text", 0))

    @patch("socket.socket")
    def test_http_post(self, mock_socket_ctr):
        body = "This body is a wonderland"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = f"POST /something HTTP/1.1\r\n"
        request += f"Content-Length: {len(body.encode("utf-8"))}\r\n"
        request += f"Host: google.com\r\n"
        request += f"User-Agent: CanYouBrowseIt\r\n\r\n"
        request += body

        test_url = "http://google.com:4229/something"
        u = url.URL(test_url)
        u.request(body)

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))

    @patch("socket.socket")
    def test_http_no_port(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)

        test_url = "http://google.com/something"
        u = url.URL(test_url)
        u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 80))

    @patch("socket.socket")
    def test_http_no_path(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)

        test_url = "http://google.com:80"
        u = url.URL(test_url)
        u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 80))

    @patch("socket.socket")
    def test_http_reused(self, mock_socket_ctr):
        get_mock_socket(mock_socket_ctr, [HTTP_RESPONSE, HTTP_RESPONSE])

        test_url = "http://google.com:80/something"
        u = url.URL(test_url)
        u.request()
        u.request()

        mock_socket_ctr.assert_called_once()

    @patch("socket.socket")
    def test_http_content_length(self, mock_socket_ctr):
        http_r = "HTTP/1.1 200 OK\r\n" + "Content-Length: 4\r\n\r\n" + "Body text"
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL(test_url)
        response = u.request()

        self.assertEqual(response, ("Body", 0))

    @patch("socket.socket")
    def test_http_unsupported_header(self, mock_socket_ctr):
        http_r = (
            "HTTP/1.1 200 OK\r\n" + "Transfer-Encoding: chunked\r\n\r\n" + "Body text"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL(test_url)

        try:
            u.request()
            self.assertFalse("Should have failed")
        except AssertionError:
            self.assertTrue("Assertion failed correctly")

    @patch("ssl.create_default_context")
    @patch("socket.socket")
    def test_https(self, mock_socket_ctr, mock_ssl_default_context_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
        mock_ctx = mock_ssl_default_context_ctr.return_value
        mock_ctx.wrap_socket.return_value = mock_socket

        test_url = "https://google.com/something"
        u = url.URL(test_url)
        response = u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 443))
        self.assertEqual(response, ("Body text", 0))

    @patch("socket.socket")
    def test_http_redirect(self, mock_socket_ctr):
        request_one = f"GET /something HTTP/1.1\r\n"
        request_one += f"Host: google.com\r\n"
        request_one += f"User-Agent: CanYouBrowseIt\r\n\r\n"
        request_two = f"GET /somethingelse HTTP/1.1\r\n"
        request_two += f"Host: google.com\r\n"
        request_two += f"User-Agent: CanYouBrowseIt\r\n\r\n"

        redirect_url = "http://google.com/somethingelse"
        http_r = f"HTTP/1.1 301 MovedPermanentely\r\nLocation: {redirect_url}\r\n\r\nBody text"
        mock_socket = get_mock_socket(mock_socket_ctr, [http_r, HTTP_RESPONSE])

        test_url = "http://google.com/something"
        u = url.URL(test_url)
        response = u.request()

        mock_socket.send.assert_has_calls(
            [call(request_one.encode("utf-8")), call(request_two.encode("utf-8"))]
        )
        self.assertEqual(response, ("Body text", 0))

    @patch("socket.socket")
    def test_http_redirect_new_socket(self, mock_socket_ctr):
        redirect_url = "http://google.com:4229/somethingelse"
        http_r = f"HTTP/1.1 301 MovedPermanentely\r\nLocation: {redirect_url}\r\n\r\nBody text"
        mock_socket = get_mock_socket(mock_socket_ctr, [http_r, HTTP_RESPONSE])

        test_url = "http://google.com/something"
        u = url.URL(test_url)
        response = u.request()

        mock_socket.connect.asset_has_calls(
            [call(("google.com", 80)), call(("google.com", 4229))]
        )
        self.assertEqual(response, ("Body text", 0))

    @patch("socket.socket")
    def test_http_redirect_limit(self, mock_socket_ctr):
        redirect_url = "http://google.com/somethingelse"
        http_r = f"HTTP/1.1 301 MovedPermanentely\r\nLocation: {redirect_url}\r\n\r\nBody text"
        get_mock_socket(
            mock_socket_ctr,
            [http_r, http_r, http_r, http_r, http_r, http_r, HTTP_RESPONSE],
        )

        test_url = "http://google.com/something"
        u = url.URL(test_url)
        response = u.request()

        self.assertEqual(
            response,
            (f"Redirect loop detected! Last redirect is to :{redirect_url}", 0),
        )

    @patch("socket.socket")
    def test_http_cache_control(self, mock_socket_ctr):
        age = 1024
        http_r = f"HTTP/1.1 200 OK\r\nCache-Control: max-age={age}\r\n\r\nBody text"
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL(test_url)
        response = u.request()

        self.assertEqual(response, ("Body text", age))

    @patch("socket.socket")
    def test_http_cache_nostore(self, mock_socket_ctr):
        http_r = (
            f"HTTP/1.1 200 OK\r\nCache-Control: max-age=1024,nostore\r\n\r\nBody text"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL(test_url)
        response = u.request()

        self.assertEqual(response, ("Body text", 0))


def get_mock_socket(mock_socket_ctr, http_responses=[HTTP_RESPONSE]):
    mock_socket = MagicMock()
    mock_socket_ctr.return_value = mock_socket
    return_values = []
    for resp in http_responses:
        return_values.append(mock_open(read_data=resp.encode("utf-8"))())
    mock_socket.makefile.side_effect = return_values
    return mock_socket


if __name__ == "__main__":
    unittest.main()
