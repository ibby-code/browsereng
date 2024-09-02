import socket
import ssl

HTTP_SCHEMES = ["http", "https", "view-source"]
REDIRECT_LIMIT = 5

class URL:
    def __init__(self, url: str):
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
            self.port = 0
            self.path = "/"
    
    def get_id(self):
        return f"{self.scheme}{self.host}{self.port}{self.path}"

    # eq and hash to allow use as key in dict
    def __eq__(self, other):
        if isinstance(other, URL):
            return self.get_id() == other.get_id()
        return NotImplemented

    def __hash__(self):
        return hash((self.get_id()))
    
    def resolve(self, url: str):
        if "://" in url: return URL(url)
        if not url.startswith("/"):
            dir, _ = self.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        if url.startswith("//"):
            return URL(self.scheme + ":" + url)
        else:
            return URL(self.scheme + "://" + self.host + ":" + str(self.port) + url)

    def request(self):
        """Returns tuple with response and cache time"""
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
        raw_response = self.socket.makefile("rb", encoding="utf8", newline="\r\n")

        statusline = raw_response.readline().decode(encoding="utf-8")
        version, status, explanation = statusline.split(" ", 2)

        # grab headers
        response_headers = {}
        line = raw_response.readline().decode(encoding="utf-8")
        while line != "\r\n":
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()
            line = raw_response.readline().decode(encoding="utf-8")

        assert status.isnumeric()
        status = int(status)
    
        # handle redirects in 300 range
        if status > 299 and status < 400 and 'location' in response_headers and redirect < REDIRECT_LIMIT:
            raw_response.close()
            location = response_headers['location']
            redirect_url = URL(location)
            print(f"redirect {redirect} to {location}")
            if self.can_use_same_socket(redirect_url):
                self.path = redirect_url.path 
                return self.make_http_request(redirect = redirect + 1)
            else:
                return redirect_url.make_http_request(redirect = redirect + 1)
        elif status > 299 and status < 400 and redirect >= REDIRECT_LIMIT:
            raw_response.close()
            location = response_headers['location']
            return (f"Redirect loop detected! Last redirect is to :{location}", 0)

        # fail unsupported headers
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        # respect content-length
        if "content-length" in response_headers:
            content_length = int(response_headers["content-length"])
            content = raw_response.read(content_length).decode("utf-8") 
        else:
            content = raw_response.read().decode("utf-8")
        raw_response.close()

        # get time content should be cached
        cache_time = 0
        if "cache-control" in response_headers:
            cache_directives = response_headers["cache-control"].split(',')
            for directive in cache_directives:
                if directive.casefold().startswith('max-age'):
                    cache_time = int(directive.split('=')[1])
                elif directive.casefold() == 'nostore':
                    cache_time = 0
                    break
        return content, cache_time

    def make_file_request(self):
        file = open(self.host, "r")
        return file.read(), 0

    def make_data_request(self):
        # ex: full url "data:text/html,Hello World!"
        form, message = self.host.split(",", 1)
        return message, 0

    def can_use_same_socket(self, urlB):
        return self.host == urlB.host and self.port == urlB.port