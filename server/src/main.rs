use rand::random;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};

const OK_RESPONSE: &str = "200 OK";
const MISSING_RESPONSE: &str = "404 Not Found";
const UNAUTHORIZED_RESPONSE: &str = "401 Unauthorized";

const COMMENT_JS: &str = include_str!("comment.js");
const COMMENT_CSS: &str = include_str!("comment.css");
const LOGIN_FORM_HTML: &str = include_str!("login_form.html");
const INVALID_LOGIN_HTML: &str = "<html><body><h1>Invalid Login!</h1><a href=\"/login\">Try again!</a></body></html>";
const LOGIN_REQUIRED_HTML: &str =
    "<html><body><h1>You must be logged in to perform this action!</h1><a href=\"/login\">Sign in!</a></body></html>";

const MAX_ENTRY_LENGTH: usize = 10;

const TOKEN_STRING_SIZE: usize = "token=".len();

#[derive(Debug)]
enum ServerError {
    MalformedHeader,
    Utf8ParseError,
    UnsupportedMethod,
    WriteToStream,
}

type ServerResult = Result<usize, ServerError>;

fn get_comments_html(session: &HashMap<String, String>, entries: &Vec<(String, String)>) -> String {
    let mut out = String::new();
    out.push_str("<html><head><link rel=\"stylesheet\" href=\"comment.css\"/></head><body>");
    for entry in entries {
        out.push_str(&format!(
            "<p>{entry} <i>by {user}</i></p>",
            entry = entry.0,
            user = entry.1
        ));
    }
    let login_form_html = match session.get("user") {
        Some(user) => format!(
            "<h1>Hello, {user}</h1> \
            <form action=\"add\" method=\"post\"> \
            <p><input name=\"guest\"></p> \
            <p><button>Sign the book!</button></p> \
            </form>",
            user = user
        ),
        _ => String::from("<a href=\"/login\">Sign in to write in the guest book</a>"),
    };
    out.push_str(&login_form_html);
    out.push_str("<strong></strong>");
    out.push_str("<script src=\"/comment.js\"></script>");
    out.push_str("</body></html>");
    out
}

fn get_not_found_html(method: &str, url: &str) -> String {
    let mut out = String::new();
    out.push_str("<html><body>");
    out.push_str(&format!("<h1>{} {} not found!</h1>", method, url));
    out.push_str("</body></html>");
    out
}

fn decode_form(body: String) -> HashMap<String, String> {
    let mut params = HashMap::new();
    for field in body.split("&") {
        if let [name, value] = field.splitn(2, "=").collect::<Vec<&str>>()[..] {
            // Need to use url decoding here
            params.insert(name.to_owned(), value.to_owned());
        } else {
            println!("Failed to parse field {field}");
        }
    }
    params
}

fn is_valid_user(username: &str, password: &str) -> bool {
    return match username {
        "crashoverride" => password == "0cool",
        "cerealkiller" => password == "emmanuel",
        _ => false,
    };
}

fn do_login(session: &mut HashMap<String, String>, data: HashMap<String, String>) -> bool {
    let username = data.get("username");
    let password = data.get("password");
    if username.is_none() || password.is_none() {
        return false;
    }
    let user = username.unwrap();
    let pass = password.unwrap();
    if is_valid_user(user, pass) {
        session.insert(String::from("user"), String::from(user));
        return true;
    }
    return false;
}

fn do_request(
    entries: &mut Vec<(String, String)>,
    session: &mut HashMap<String, String>,
    method: &str,
    url: &str,
    _headers: &HashMap<String, String>,
    body: String,
) -> (&'static str, String) {
    let response = if method == "GET" && url == "/" {
        (OK_RESPONSE, get_comments_html(session, entries))
    } else if method == "GET" && url == "/login" {
        return (OK_RESPONSE, String::from(LOGIN_FORM_HTML));
    } else if method == "GET" && url == "/comment.js" {
        return (OK_RESPONSE, String::from(COMMENT_JS));
    } else if method == "GET" && url == "/comment.css" {
        return (OK_RESPONSE, String::from(COMMENT_CSS));
    } else if method == "POST" && url == "/" {
        let params = decode_form(body);
        let logged_in = do_login(session, params);
        return match logged_in {
            true => (OK_RESPONSE, get_comments_html(session, entries)),
            false => (UNAUTHORIZED_RESPONSE, String::from(INVALID_LOGIN_HTML)),
        };
    } else if method == "POST" && url == "/add" {
        let params = decode_form(body);
        let user = match session.get("user") {
            Some(user) => user,
            _ => return (UNAUTHORIZED_RESPONSE, String::from(LOGIN_REQUIRED_HTML)),
        };
        match params.get("guest") {
            Some(guest) => {
                if guest.chars().count() <= MAX_ENTRY_LENGTH {
                    entries.push((guest.clone(), user.clone()));
                }
            }
            _ => println!("Missing guest value"),
        }
        (OK_RESPONSE, get_comments_html(session, entries))
    } else {
        (MISSING_RESPONSE, get_not_found_html(method, url))
    };
    response
}

fn get_server_error_body(err: ServerError) -> String {
    format!(
        "<html><body><p>Server error!</p><p>Details: {:?}</p></body></html>",
        err
    )
}

fn get_server_error_response(err: ServerError) -> String {
    let body = get_server_error_body(err);
    let mut response = String::from("HTTP/1.0 500\r\n");
    response.push_str(&format!(
        "Content-Length: {body_length}\r\n\r\n",
        body_length = body.len()
    ));
    response.push_str(&body);
    response
}

fn read_response_headers(reader: &mut BufReader<&TcpStream>) -> HashMap<String, String> {
    let mut header_map = HashMap::new();
    let mut line = String::new();
    loop {
        line.clear();
        match reader.read_line(&mut line) {
            Ok(_) => (),
            Err(why) => {
                println!("Error: {}", why);
                continue;
            }
        }
        if line == "\r\n" {
            break;
        }
        let v: Vec<&str> = line.as_str().splitn(2, ":").collect();
        if let [header, value] = v[..] {
            header_map.insert(header.to_lowercase().to_owned(), value.trim().to_owned());
        } else {
            println!("Error parsing header on {v:?}");
        }
    }
    return header_map;
}

fn handle_client(
    mut stream: TcpStream,
    entries: &mut Vec<(String, String)>,
    session_data: &mut HashMap<String, HashMap<String, String>>,
) -> ServerResult {
    let mut reader = BufReader::new(&stream);

    let mut line = String::new();
    match reader.read_line(&mut line) {
        Ok(_) => (),
        Err(e) => {
            println!("First line error: {e:?}");
            return Err(ServerError::Utf8ParseError);
        }
    }
    let v: Vec<&str> = line.as_str().splitn(3, " ").collect();
    let [method, url, _version] = match v[..] {
        [method, url, _version] => [method, url, _version],
        _ => {
            println!("Malformed header: {v:?}");
            return Err(ServerError::MalformedHeader);
        }
    };
    if !["GET", "POST"].contains(&method) {
        return Err(ServerError::UnsupportedMethod);
    }
    let header_map = read_response_headers(&mut reader);
    println!("Good {header_map:?}");
    let mut body = String::new();
    let content_length_str = match header_map.get("content-length") {
        Some(c) => c,
        _ => "0",
    };
    let content_length = match content_length_str.parse::<usize>() {
        Ok(val) => val,
        Err(why) => {
            println!("Could not parse content length: {why}");
            0
        }
    };
    if content_length != 0 {
        let mut body_buf = vec![0; content_length];
        reader
            .read_exact(&mut body_buf)
            .expect("Error reading from buffer");
        body = String::from_utf8(body_buf).expect("Body must be valid utf8");
    }

    let token = match &header_map.get("cookie") {
        Some(cookie) => &cookie[TOKEN_STRING_SIZE..],
        _ => &random::<usize>().to_string()[2..],
    };

    println!("recieved body {body}");
    let mut session = &mut session_data
        .entry(token.to_string())
        .or_insert(HashMap::new());
    let (status, body) = do_request(entries, &mut session, method, url, &header_map, body);
    let mut response = String::from(format!("HTTP/1.0 {status}\r\n", status = status));
    response.push_str(&format!(
        "Content-Length: {body_length}\r\n",
        body_length = body.len()
    ));
    if header_map.get("cookie").is_none() {
        response.push_str(&format!("Set-Cookie: token={token}\r\n", token = token));
    }
    response.push_str("\r\n");
    response.push_str(&body);
    println!("Writing response: {response}");
    return match stream.write(&response.as_bytes()) {
        Ok(bytes) => Ok(bytes),
        Err(_) => Err(ServerError::WriteToStream),
    };
}

fn main() -> std::io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:8000")?;
    let mut session_data = HashMap::new();
    let mut entries = Vec::new();
    entries.push((
        String::from("Pavel was here"),
        String::from("crashoverride"),
    ));

    for stream in listener.incoming() {
        match handle_client(stream?, &mut entries, &mut session_data) {
            Ok(bytes) => println!("Client handled, set {} bytes", bytes),
            Err(why) => println!("Server exception: {why:?}"),
        }
    }
    Ok(())
}
