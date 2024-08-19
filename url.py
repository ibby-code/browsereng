import socket
import ssl

HTTP_SCHEMES = ["http", "https", "view-source"]
REDIRECT_LIMIT = 5

class URL:
    def __init__(self, url):
        self.socket = None
        self.scheme, url = url.split(":", 1)
        # for http schemes
        if url.startswith("//"):
            url = url[2:]

        if self.scheme in HTTP_SCHEMES:
            # add / if not present for path
            if "/" not in url:
                url += "/"
            self.host, url = url.split("/", 1)
            self.path = "/" + url
            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)
            elif self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443
        else:
            self.host = url

    def request(self):
        if self.scheme in HTTP_SCHEMES:
            return self.make_http_request()
        elif self.scheme == "file":
            return self.make_file_request()
        elif self.scheme == "data":
            return self.make_data_request()

    def make_http_request(self, redirect = 0):
        if not self.socket:
            self.socket = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            if self.scheme == "https":
                ctx = ssl.create_default_context()
                self.socket = ctx.wrap_socket(self.socket, server_hostname=self.host)
            # connect to url
            self.socket.connect((self.host, self.port))
        # create GET request
        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"Host: {self.host}\r\n"
        request += f"User-Agent: CanYouBrowseIt\r\n\r\n"
        # encode request as bytes to send
        self.socket.send(request.encode("utf8"))
        # read all responses into var
        response = self.socket.makefile("r", encoding="utf8", newline="\r\n")

        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)

        # grab headers
        response_headers = {}
        line = response.readline()
        while line != "\r\n":
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()
            line = response.readline()

        assert status.isnumeric()
        status = int(status)
    
        # handle redirects in 300 range
        if status > 299 and status < 400 and 'location' in response_headers and redirect < REDIRECT_LIMIT:
            location = response_headers['location']
            redirect_url = URL(location)
            print(f"redirect {redirect} to {location}")
            if self.can_use_same_socket(redirect_url):
                self.path = redirect_url.path 
                return self.make_http_request(redirect = redirect + 1)
            else:
                return redirect_url.make_http_request(redirect = redirect + 1)
        elif status > 299 and status < 400 and redirect > REDIRECT_LIMIT:
            location = response_headers['location']
            return f"Redirect loop detected! Last redirect is to :{location}"

        # fail unsupported headers
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        # respect content-length
        if "content-length" in response_headers:
            content_length = response_headers["content-length"]
            content = response.read(int(content_length))
        else:
            content = response.read()
        return content

    def make_file_request(self):
        file = open(self.host, "r")
        return file.read()

    def make_data_request(self):
        # ex: full url "data:text/html,Hello World!"
        form, message = self.host.split(",", 1)
        return message

    def can_use_same_socket(self, urlB):
        return self.host == urlB.host and self.port == urlB.port
