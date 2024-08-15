import socket
import ssl

class URL:
    def __init__(self, url):
        self.scheme, url = url.split("://", 1)
        # make sure correct scheme
        assert self.scheme in ["http", "https"]
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

    def request(self):
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
        request = f"GET {self.path} HTTP/1.0\r\n"
        request += f"Host: {self.host}\r\n\r\n"
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

