import url
import unittest
from unittest.mock import mock_open, call, patch, MagicMock

FAKE_FILE = "\nHello\nWorld\n"
HTTP_RESPONSE = "HTTP/1.0 200 OK\r\n" + "Header1: Value1\r\n\r\n" + "Body text"
HTTP_RESPONSE_HEADERS = {"header1": "Value1"}

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
        "resolveUrl": "test.css",
        "host": "",
        "port": 0,
        "scheme": "file",
        "path": "boo/foo/test.css",
    },
    {
        "name": "relative file url with ..",
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
                link = url.URL({}, test_data["originalUrl"])
                newUrl = link.resolve(test_data["resolveUrl"])
                self.assertEqual(newUrl.host, test_data["host"])
                self.assertEqual(newUrl.port, test_data["port"])
                self.assertEqual(newUrl.scheme, test_data["scheme"])
                self.assertEqual(newUrl.path, test_data["path"])

    @patch("builtins.open", new_callable=mock_open, read_data=FAKE_FILE)
    def test_file(self, file):
        test_file = "C:/Users/user/Documents/txt.txt"
        u = url.URL({}, f"file://{test_file}")
        self.assertEqual(u.request(), ({}, FAKE_FILE, 0))
        file.assert_called_with(test_file, "r")

    def test_data(self):
        test_message = "hello world!"
        u = url.URL({}, f"data:text/html,{test_message}")
        self.assertEqual(u.request(), ({}, test_message, 0))

    @patch("socket.socket")
    def test_http_get(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "GET /something HTTP/1.1\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"

        test_url = "http://google.com:4229/something"
        u = url.URL({}, test_url)
        response = u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 4229))
        mock_socket.send.assert_called_once_with(request.encode("utf-8"))
        self.assertEqual(response, (HTTP_RESPONSE_HEADERS, "Body text", 0))

    @patch("socket.socket")
    def test_http_post(self, mock_socket_ctr):
        body = "This body is a wonderland"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "POST /something HTTP/1.1\r\n" + \
            f"Content-Length: {len(body.encode("utf-8"))}\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"
        request += body

        test_url = "http://google.com:4229/something"
        u = url.URL({}, test_url)
        u.request(None, body)

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))

    @patch("socket.socket")
    def test_http_no_port(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)

        test_url = "http://google.com/something"
        u = url.URL({}, test_url)
        u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 80))

    @patch("socket.socket")
    def test_http_no_path(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)

        test_url = "http://google.com:80"
        u = url.URL({}, test_url)
        u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 80))

    @patch("socket.socket")
    def test_http_reused(self, mock_socket_ctr):
        get_mock_socket(mock_socket_ctr, [HTTP_RESPONSE, HTTP_RESPONSE])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)
        u.request()
        u.request()

        mock_socket_ctr.assert_called_once()

    @patch("socket.socket")
    def test_http_content_length(self, mock_socket_ctr):
        http_r = "HTTP/1.1 200 OK\r\n" + "Content-Length: 4\r\n\r\n" + "Body text"
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)
        response = u.request()

        self.assertEqual(response, ({"content-length": "4"}, "Body", 0))

    @patch("socket.socket")
    def test_http_transfer_encoding_chunked(self, mock_socket_ctr):
        http_r = (
            "HTTP/1.1 200 OK\r\n" +
            "Transfer-Encoding: chunked\r\n\r\n" +
            "8; ignore-stuff\r\n" +
            "birthday\r\n" +
            "4\r\n" +
            " day\r\n" + 
            "0\r\nsome-footer: some-value\r\n\r\n"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)

        response = u.request()
        self.assertEqual(response, ({'transfer-encoding': 'chunked'}, "birthday day", 0))

    @patch("socket.socket")
    def test_http_transfer_encoding_chunked_with_content_type(
        self, mock_socket_ctr):
        charset = "ascii"
        # ensure the string is long enough to test hex encoding 
        first_chunk = "birthday " * 10
        second_chunk = "day"
        http_r = (
            "HTTP/1.1 200 OK\r\n" +
            "Transfer-Encoding: chunked\r\n" +
            f"Content-Type: text/html; charset={charset}\r\n\r\n" +
            f"{hex(len(first_chunk))}; ignore-stuff\r\n" +
            f"{first_chunk} \r\n" +
            f"{hex(len(second_chunk))}\r\n" +
            f"{second_chunk} \r\n" + 
            "0\r\nsome-footer: some-value\r\n\r\n"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)

        response = u.request()
        self.assertEqual(response,
                         ({"transfer-encoding":"chunked", "content-type": f"text/html; charset={charset}"},
                          first_chunk + second_chunk,
                          0))
    
    @patch("socket.socket")
    def test_http_transfer_encoding_chunked_with_content_type_fails(
        self, mock_socket_ctr):
        charset = "ascii"
        first_chunk = "你好世界"
        http_r = (
            "HTTP/1.1 200 OK\r\n" +
            "Transfer-Encoding: chunked\r\n" +
            f"Content-Type: text/html; charset={charset}\r\n\r\n" +
            f"{hex(len(first_chunk))}; ignore-stuff\r\n" +
            f"{first_chunk} \r\n" +
            "0\r\nsome-footer: some-value\r\n\r\n"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)

        try:
            u.request()
            self.assertFalse("Expected decode error")
        except UnicodeDecodeError:
            self.assertTrue("Unicode decode error thrown correctly")
    
    @patch("socket.socket")
    def test_http_unsupported_header(self, mock_socket_ctr):
        http_r = (
            "HTTP/1.1 200 OK\r\n" + "Transfer-Encoding: gzip\r\n\r\n" + "Body text"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)

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
        u = url.URL({}, test_url)
        response = u.request()

        mock_socket.connect.assert_called_once_with(("google.com", 443))
        self.assertEqual(response, (HTTP_RESPONSE_HEADERS, "Body text", 0))

    @patch("socket.socket")
    def test_http_redirect(self, mock_socket_ctr):
        request_one = "GET /something HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n"
        request_two = "GET /somethingelse HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n"

        redirect_url = "http://google.com/somethingelse"
        http_r = f"HTTP/1.1 301 MovedPermanentely\r\nLocation: {redirect_url}\r\n\r\nBody text"
        mock_socket = get_mock_socket(mock_socket_ctr, [http_r, HTTP_RESPONSE])

        test_url = "http://google.com/something"
        u = url.URL({}, test_url)
        response = u.request()

        mock_socket.send.assert_has_calls(
            [call(request_one.encode("utf-8")), call(request_two.encode("utf-8"))]
        )
        self.assertEqual(response, (HTTP_RESPONSE_HEADERS, "Body text", 0))

    @patch("socket.socket")
    def test_http_redirect_new_socket(self, mock_socket_ctr):
        redirect_url = "http://google.com:4229/somethingelse"
        http_r = f"HTTP/1.1 301 MovedPermanentely\r\nLocation: {redirect_url}\r\n\r\nBody text"
        mock_socket = get_mock_socket(mock_socket_ctr, [http_r, HTTP_RESPONSE])

        test_url = "http://google.com/something"
        u = url.URL({}, test_url)
        response = u.request()

        mock_socket.connect.asset_has_calls(
            [call(("google.com", 80)), call(("google.com", 4229))]
        )
        self.assertEqual(response, (HTTP_RESPONSE_HEADERS, "Body text", 0))

    @patch("socket.socket")
    def test_http_redirect_limit(self, mock_socket_ctr):
        redirect_url = "http://google.com/somethingelse"
        http_r = f"HTTP/1.1 301 MovedPermanentely\r\nLocation: {redirect_url}\r\n\r\nBody text"
        get_mock_socket(
            mock_socket_ctr,
            [http_r, http_r, http_r, http_r, http_r, http_r, HTTP_RESPONSE],
        )

        test_url = "http://google.com/something"
        u = url.URL({}, test_url)
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
        u = url.URL({}, test_url)
        response = u.request()

        self.assertEqual(response, ({"cache-control": f"max-age={age}"}, "Body text", age))

    @patch("socket.socket")
    def test_http_cache_nostore(self, mock_socket_ctr):
        http_r = (
            "HTTP/1.1 200 OK\r\nCache-Control: max-age=1024,nostore\r\n\r\nBody text"
        )
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:80/something"
        u = url.URL({}, test_url)
        response = u.request()

        self.assertEqual(response, ({"cache-control": f"max-age=1024,nostore"}, "Body text", 0))

    @patch("socket.socket")
    def test_http_send_cookie(self, mock_socket_ctr):
        cookie = "my_cookie"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "GET /something HTTP/1.1\r\n" + \
            f"Cookie: {cookie}\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"

        test_url = "http://google.com:4229/something"
        u = url.URL({"google.com": (cookie, {})}, test_url)
        u.request()

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))

    @patch("socket.socket")
    def test_http_send_cookie_samesite_get(self, mock_socket_ctr):
        cookie = "my_cookie"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "GET /something HTTP/1.1\r\n" + \
            f"Cookie: {cookie}\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"

        test_url = "http://google.com:4229/something"
        referer = url.URL({}, "http://someothersite.com/something")
        u = url.URL({"google.com": (cookie, {"samesite": "lax"})}, test_url)
        u.request(referer)

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))


    @patch("socket.socket")
    def test_http_send_cookie_post_samesite_valid_referer(self, mock_socket_ctr):
        cookie = "my_cookie"
        body = "This body is a wonderland"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "POST /something HTTP/1.1\r\n" + \
            f"Content-Length: {len(body.encode("utf-8"))}\r\n" + \
            f"Cookie: {cookie}\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"
        request += body

        test_url = "http://google.com:4229/something"
        referer = url.URL({}, "http://google.com:4229/somethingelse")
        u = url.URL({"google.com": (cookie, {"same-site": "lax"})}, test_url)
        u.request(referer, body)

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))


    @patch("socket.socket")
    def test_http_send_cookie_samesite_invalid_referer(self, mock_socket_ctr):
        body = "This body is a wonderland"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "POST /something HTTP/1.1\r\n" + \
            f"Content-Length: {len(body.encode("utf-8"))}\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"
        request += body

        test_url = "http://google.com:4229/something"
        referer = url.URL({}, "http://someothersite.com/something")
        u = url.URL({"google.com": ("my_cookie", {"samesite": "lax"})}, test_url)
        u.request(referer, body)

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))

    @patch("socket.socket")
    def test_http_send_cookie_samesite_other(self, mock_socket_ctr):
        cookie = "my_cookie"
        body = "This body is a wonderland"
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = "POST /something HTTP/1.1\r\n" + \
            f"Content-Length: {len(body.encode("utf-8"))}\r\n" + \
            f"Cookie: {cookie}\r\n" + \
            "Host: google.com\r\n" + \
            "User-Agent: CanYouBrowseIt\r\n\r\n"
        request += body

        test_url = "http://google.com:4229/something"
        referer = url.URL({}, "http://someothersite.com/something")
        u = url.URL({"google.com": (cookie, {"same-site": "strict"})}, test_url)
        u.request(referer, body)

        mock_socket.send.assert_called_once_with(request.encode("utf-8"))


    @patch("socket.socket")
    def test_http_set_cookie(self, mock_socket_ctr):
        cookie = "my_cookie"
        cookie_jar = {}
        http_r = "HTTP/1.0 200 OK\r\n" + \
            f"set-cookie: {cookie}\r\n\r\n" + "Body text"
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:4229/something"
        u = url.URL(cookie_jar, test_url)
        u.request()

        self.assertEqual(cookie_jar.get("google.com", None), (cookie, {}))

    @patch("socket.socket")
    def test_http_set_cookie_with_params(self, mock_socket_ctr):
        cookie = "my_cookie"
        params = {"samesite": "lax", "key": "value", "key_without_value": "true"}
        full_cookie = f"{cookie};SameSite=Lax;key=value;key_without_value"
        cookie_jar = {}
        http_r = "HTTP/1.0 200 OK\r\n" + \
            f"set-cookie: {full_cookie}\r\n\r\n" + "Body text"
        get_mock_socket(mock_socket_ctr, [http_r])

        test_url = "http://google.com:4229/something"
        u = url.URL(cookie_jar, test_url)
        u.request()

        self.assertEqual(cookie_jar.get("google.com", None), (cookie, params))


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
