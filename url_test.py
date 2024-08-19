import url
import unittest
from unittest.mock import mock_open, patch, MagicMock

FAKE_FILE = "\nHello\nWorld\n"
HTTP_RESPONSE = "HTTP/1.0 200 OK\r\n" + "Header1: Value1\r\n\r\n" + "Body text"

class TestUrl(unittest.TestCase):

    @patch('builtins.open', new_callable=mock_open, read_data=FAKE_FILE)
    def test_file(self, file):
        test_file = "C:/Users/user/Documents/txt.txt"
        u = url.URL(f"file://{test_file}")
        self.assertEqual(u.request(), FAKE_FILE) 
        file.assert_called_with(test_file, "r")

    def test_data(self):
        test_message = "hello world!"
        u = url.URL(f"data:text/html,{test_message}")
        self.assertEqual(u.request(), test_message)
    
    @patch('socket.socket')
    def test_http(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
        request = f"GET /something HTTP/1.1\r\n"
        request += f"Host: google.com\r\n"
        request += f"User-Agent: CanYouBrowseIt\r\n\r\n"
 
        test_url = "http://google.com:4229/something" 
        u = url.URL(test_url)
        response = u.request()

        mock_socket.connect.assert_called_once_with(('google.com', 4229))
        mock_socket.send.assert_called_once_with(request.encode("utf8"))
        self.assertEqual(response, "Body text")

    @patch('socket.socket')
    def test_http_no_port(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
 
        test_url = "http://google.com/something" 
        u = url.URL(test_url)
        u.request()

        mock_socket.connect.assert_called_once_with(('google.com', 80))

    @patch('socket.socket')
    def test_http_no_path(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
 
        test_url = "http://google.com:80" 
        u = url.URL(test_url)
        u.request()

        mock_socket.connect.assert_called_once_with(('google.com', 80))

    @patch('socket.socket')
    def test_http_reused(self, mock_socket_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)

        test_url = "http://google.com:80/something" 
        u = url.URL(test_url)
        u.request()
        file = mock_open(read_data=HTTP_RESPONSE)()
        mock_socket.makefile.return_value = file
        u.request()

        mock_socket_ctr.assert_called_once()

    @patch('socket.socket')
    def test_http_content_length(self, mock_socket_ctr):
        http_r = "HTTP/1.1 200 OK\r\n" + "Content-Length: 4\r\n\r\n" + "Body text"
        get_mock_socket(mock_socket_ctr, http_r)

        test_url = "http://google.com:80/something" 
        u = url.URL(test_url)
        response = u.request()

        self.assertEqual(response, "Body")

    @patch('socket.socket')
    def test_http_unsupported_header(self, mock_socket_ctr):
        http_r = "HTTP/1.1 200 OK\r\n" + "Transfer-Encoding: chunked\r\n\r\n" + "Body text"
        get_mock_socket(mock_socket_ctr, http_r)

        test_url = "http://google.com:80/something" 
        u = url.URL(test_url)

        try:
            u.request()
            self.assertFalse('Should have failed')
        except AssertionError:
            self.assertTrue('Assertion failed correctly') 

    @patch('ssl.create_default_context')
    @patch('socket.socket')
    def test_https(self, mock_socket_ctr, mock_ssl_default_context_ctr):
        mock_socket = get_mock_socket(mock_socket_ctr)
        mock_ctx = mock_ssl_default_context_ctr.return_value
        mock_ctx.wrap_socket.return_value = mock_socket

        test_url = "https://google.com/something" 
        u = url.URL(test_url)
        response = u.request()

        mock_socket.connect.assert_called_once_with(('google.com', 443))
        self.assertEqual(response, "Body text")

def get_mock_socket(mock_socket_ctr, http_response=HTTP_RESPONSE):
    mock_socket = MagicMock()
    mock_socket_ctr.return_value = mock_socket
    file = mock_open(read_data=http_response)()
    mock_socket.makefile.return_value = file
    return mock_socket

if __name__ == "__main__":
    unittest.main()
