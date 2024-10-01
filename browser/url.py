import socket
import ssl

HTTP_SCHEMES = ["http", "https", "view-source"]
REDIRECT_LIMIT = 5


class URL:
    def __init__(self, cookie_jar: dict[str, str], url: str):
        self.cookie_jar = cookie_jar
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
            self.host = ""
            self.port = 0
            self.path = url

    def get_id(self):
        return f"{self.scheme}://{self.host}:{self.port}{self.path}"

    def __str__(self) -> str:
        port_part = ":" + str(self.port)
        if (
            not self.port
            or (self.scheme == "https" and self.port == 443)
            or (self.scheme == "http" and self.port == 80)
        ):
            port_part = ""
        return self.scheme + "://" + self.host + port_part + self.path

    # eq and hash to allow use as key in dict
    def __eq__(self, other):
        if isinstance(other, URL):
            return self.get_id() == other.get_id()
        return NotImplemented

    def __hash__(self):
        return hash((self.get_id()))

    # trying to make this work for files
    def resolve(self, url: str):
        if "://" in url:
            return URL(self.cookie_jar, url)
        if self.scheme == "file":
            if "/" in self.path:
                url = get_relative_url(self.path.rsplit("/", 1)[0] + "/", url)
        elif not url.startswith("/"):
            url = get_relative_url(self.path, url)
        if url.startswith("//"):
            return URL(self.cookie_jar, self.scheme + ":" + url)
        else:
            base = (
                self.scheme
                + "://"
                + self.host
                + (":" + str(self.port) if self.port else "")
            )
            if not base.endswith("/") and not url.startswith("/"):
                base += "/"
            return URL(self.cookie_jar, base + url)

    def request(self, payload=None):
        """Returns tuple with response and cache time"""
        if self.scheme in HTTP_SCHEMES:
            return self.make_http_request(payload)
        elif self.scheme == "file":
            return self.make_file_request()
        elif self.scheme == "data":
            return self.make_data_request()

    def make_http_request(self, payload=None, redirect=0):
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
        # create request
        method = "POST" if payload else "GET"
        request = f"{method} {self.path} HTTP/1.1\r\n"
        if payload:
            length = len(payload.encode("utf-8"))
            request += f"Content-Length: {length}\r\n"
        cookie = self.cookie_jar.get(self.host, None)
        if cookie:
            request += f"Cookie: {cookie}\r\n"
        request += f"Host: {self.host}\r\n"
        request += f"User-Agent: CanYouBrowseIt\r\n\r\n"
        # encode request as bytes to send
        if payload: request += payload
        self.socket.send(request.encode("utf-8"))
        # read all responses into var
        raw_response = self.socket.makefile("rb", encoding="utf-8", newline="\r\n")

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
        if (
            status > 299
            and status < 400
            and "location" in response_headers
            and redirect < REDIRECT_LIMIT
        ):
            raw_response.close()
            location = response_headers["location"]
            redirect_url = URL(self.cookie_jar, location)
            print(f"redirect {redirect} to {location}")
            if self.can_use_same_socket(redirect_url):
                self.path = redirect_url.path
                return self.make_http_request(redirect=redirect + 1)
            else:
                return redirect_url.make_http_request(redirect=redirect + 1)
        elif status > 299 and status < 400 and redirect >= REDIRECT_LIMIT:
            raw_response.close()
            location = response_headers["location"]
            return (f"Redirect loop detected! Last redirect is to :{location}", 0)

        # fail unsupported headers
        assert "content-encoding" not in response_headers
        assert response_headers["transfer-encoding"] == "chunked" if "transfer-encoding" in response_headers else True

        cookie = response_headers.get("set-cookie", None)
        if cookie:
            self.cookie_jar[self.host] = cookie

        # respect content-length
        if "transfer-encoding" in response_headers:
            content = ""
            content_type = response_headers.get("content-type", "").split(";")
            charset = "utf-8"
            if len(content_type) == 2:
                charset_vals = content_type[1].split("=")
                if len(charset_vals) == 2 and charset_vals[0].strip() == "charset":
                    charset = charset_vals[1]
            while True:
                chunk_size = int(raw_response.readline().split(b";", 1)[0].strip(), 16)
                # ignoring footer data
                if not chunk_size: break
                content += raw_response.read(chunk_size).decode(charset)
                raw_response.readline()

        elif "content-length" in response_headers:
            content_length = int(response_headers["content-length"])
            content = raw_response.read(content_length).decode("utf-8")
        else:
            content = raw_response.read().decode("utf-8")
        raw_response.close()

        # get time content should be cached
        cache_time = 0
        if "cache-control" in response_headers:
            cache_directives = response_headers["cache-control"].split(",")
            for directive in cache_directives:
                if directive.casefold().startswith("max-age"):
                    cache_time = int(directive.split("=")[1])
                elif directive.casefold() == "nostore":
                    cache_time = 0
                    break
        return content, cache_time

    def make_file_request(self):
        file = open(self.path, "r")
        return file.read(), 0

    def make_data_request(self):
        # ex: full url "data:text/html,Hello World!"
        form, message = self.path.split(",", 1)
        return message, 0

    def can_use_same_socket(self, urlB):
        return (
            self.scheme == urlB.scheme
            and self.host == urlB.host
            and self.port == urlB.port
        )


def get_relative_url(original, new):
    if new.startswith("/"):
        return new
    dir, _ = original.rsplit("/", 1)
    while new.startswith("../"):
        _, new = new.split("/", 1)
        if "/" in dir:
            dir, _ = dir.rsplit("/", 1)
        else:
            dir = ""
    return dir + ("/" if dir else "") + new
