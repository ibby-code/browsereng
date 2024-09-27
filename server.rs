use std::collections::HashMap;
use std::io::BufRead;
use std::io::BufReader;
use std::io::Read;
use std::io::Write;
use std::net::{TcpListener, TcpStream};

const OK_RESPONSE: &str = "200 OK";
const MISSING_RESPONSE: &str = "404 Not Found";

fn get_comments_html(entries: &Vec::<String>) ->  String {
    let mut out = String::new();
    out.push_str("<html><body>");
    for entry in entries {
        out.push_str(&format!("<p>{}</p>", entry));
    }
    out.push_str("<form action=add method=post> \
                    <p><input name=guest></p> \
                    <p><button>Sign the book!</button></p> \
                    </form");
    out.push_str("</body></html>");
    out
}

fn get_not_found_html(method: &str, url: &str) -> String {
    let mut out = String::new();
    out.push_str("<html><body>");
    out.push_str(&format!("<h1>{} {} not found!</h1>", method, url));
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

fn do_request(entries: &mut Vec::<String>, method: &str, url: &str, _headers: HashMap<String, String>, body: String) -> (&'static str, String) {
    let response =
        if method == "GET" && url == "/" {
            (OK_RESPONSE, get_comments_html(entries)) 
        } else if method == "POST" && url == "/add" {
            let params = decode_form(body);
            match params.get("guest") {
                Some(guest) => {
                    entries.push(guest.clone());
                },
                _ => println!("Missing guest value")
            }
            (OK_RESPONSE, get_comments_html(entries))
        } else {
            (MISSING_RESPONSE, get_not_found_html(method, url))
        };
    response
} 

fn handle_client(mut stream: TcpStream, entries: &mut Vec::<String>) -> std::io::Result<()> {
    let mut reader = BufReader::new(&stream);

    let mut line = String::new();
    reader.read_line(&mut line).expect("Fail to read lines");
    let v: Vec<&str> = line.as_str().splitn(3, " ").collect();
    if let [method, url, _version] = v[..] {
        assert!(["GET", "POST"].contains(&method), "Cannot support {} requests", method);
        let mut header_map = HashMap::new();
        let mut line = String::new();
        loop {
            line.clear();
            reader.read_line(&mut line).expect("Fail to read lines");
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
        println!("Good {header_map:?}");
        let mut body = String::new();
        match header_map.get("content-length") {
            Some(&ref number) => {
                match number.parse::<usize>() {
                    Ok(val) => {
                        let mut body_buf = vec![0; val];
                        reader.read_exact(&mut body_buf).expect("Error reading from buffer");
                        body = String::from_utf8(body_buf).expect("Body must be valid utf8");
                    },
                    Err(why) => {
                        println!("Could not parse content length: {why}");
                    } 
                }
        },
            _ => println!("No content length found!")
        } 
        println!("recieved body {body}");
        let (status, body) = do_request(entries, method, url, header_map, body);
        let mut response = String::from(format!("HTTP/1.0 {status}\r\n", status=status));
        response.push_str(&format!("Content-Length: {body_length}\r\n\r\n", body_length=body.len()));
        response.push_str(&body);
        println!("Writing response: {response}");
        stream.write(&response.as_bytes())?;
    } else {
        println!("Malformed header: {v:?}");
    }
    Ok(())
    
}

fn main() -> std::io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:8000")?;
    let mut entries = Vec::new();
    entries.push(String::from("Pavel was here"));

    for stream in listener.incoming() {
        match handle_client(stream?, &mut entries) {
            Ok(_) => println!("Client handled"),
            Err(e) => println!("Client exception: {e}"),
        }
    }
    Ok(())
}