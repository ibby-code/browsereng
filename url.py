import socket
import ssl

HTTP_SCHEMES = ["http", "https", "view-source"]

class URL:
    def __init__(self, url):
        self.scheme, url = url.split(":", 1)
        # for http schemes
        if url.startswith('//'):
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
        elif self.scheme == 'file':
            return self.make_file_request()
        elif self.scheme == 'data':
            return self.make_data_request()

    def make_http_request(self):
        s = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
        )
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
        # connect to url
        s.connect((self.host, self.port))
        # create GET request
        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"Host: {self.host}\r\n"
        request += f"Connection: close\r\n"
        request += f"User-Agent: CanYouBrowseIt\r\n\r\n"
        # encode request as bytes to send
        s.send(request.encode("utf8"))
        # read all responses into var
        response = s.makefile("r", encoding="utf8", newline="\r\n")

        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)

        # grab headers
        response_headers = {}
        line = response.readline()
        while line != "\r\n":
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()
            line = response.readline()

        # fail unsupported headers
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        # everything else is content
        content = response.read()
        s.close()
        return content

    def make_file_request(self):
        file = open(self.host, "r")
        return file.read()

    def make_data_request(self):
        # ex: full url "data:text/html,Hello World!"
        form, message = self.host.split(",", 1)
        return message
    