use std::io::{BufReader, Read, Write};
use std::net::TcpStream;
use std::thread;
extern crate server;

const INDEX_GET_REQUEST: &str = include_str!("data/index_get_request.txt");
const INDEX_GET_RESPONSE: &str = include_str!("data/index_get_response.txt");
const INDEX_POST_REQUEST: &str = include_str!("data/index_post_request.txt");
const INDEX_POST_RESPONSE: &str = include_str!("data/index_post_response.txt");
const INDEX_POST_REQUEST_FAIL: &str = include_str!("data/index_post_request_fail.txt");
const INDEX_POST_RESPONSE_FAIL: &str = include_str!("data/index_post_response_fail.txt");
const LOGIN_GET_REQUEST: &str = include_str!("data/login_get_request.txt");
const LOGIN_GET_RESPONSE: &str = include_str!("data/login_get_response.txt");

const COMMENT_JS: &str = include_str!("../src/comment.js");
const COMMENT_CSS: &str = include_str!("../src/comment.css");

const RANDOM_REPLACEMENT: &str = "__rand__";

fn replace_content_length(response:String) -> String {
    let separator = "Content-Length:";
    let (before, after) = match response.split_once(separator) {
        Some(result) => result,
        _ => return response,
    };
    let end_index = match after.find("\r\n") {
        Some(result) => result,
        _ => return response,
    };
    [before, separator, RANDOM_REPLACEMENT, &after[end_index..]].join("")
}

fn replace_nonce_and_content_length(response: String) -> String {
    let response = replace_content_length(response);
    let input_separator = "<input name=\"nonce\"";
    let (before_input, after_input) = match response.split_once(input_separator) {
        Some(result) => result,
        _ => return response,
    };
    let nonce_separator = "value=\"";
    let (before_nonce, after_nonce) = match after_input.split_once(nonce_separator) {
        Some(result) => result,
        _ => return response,
    };
    let nonce_end_index = match after_nonce.find("\"") {
        Some(result) => result,
        _ => return response,
    };
    return format!(
        "{before_input}{input_separator}{before_nonce}{nonce_separator}{fake_nonce}\"{after_nonce}",
        before_input = before_input,
        input_separator = input_separator,
        before_nonce = before_nonce,
        nonce_separator = nonce_separator,
        fake_nonce = RANDOM_REPLACEMENT,
        after_nonce = &after_nonce[nonce_end_index..]
    );
}

fn replace_token_value(response: String) -> String {
    let (before_token, after_token) = match response.split_once("token=") {
        Some(result) => result,
        _ => return response,
    };
    let token_end_index = match after_token.find(|c: char| !c.is_alphanumeric()) {
        Some(result) => result,
        _ => return response,
    };
    return format!(
        "{before_token}token={fake_token}{after_token}",
        before_token = before_token,
        fake_token = RANDOM_REPLACEMENT,
        after_token = &after_token[token_end_index..]
    );
}

fn read_stream_response(stream: &mut TcpStream) -> String {
    let mut response_bytes = Vec::new();
    BufReader::new(stream)
        .read_to_end(&mut response_bytes)
        .expect("Failed to read server data");
    let response = String::from_utf8(response_bytes).expect("Could not parse response");
    replace_token_value(response)
}

#[test]
fn index_get_request() {
    thread::spawn(|| server::run_server());

    let mut stream = TcpStream::connect("127.0.0.1:8000").expect("Could not connect to server");
    let _ = stream.write(INDEX_GET_REQUEST.as_bytes());
    assert_eq!(
        read_stream_response(&mut stream),
        String::from(INDEX_GET_RESPONSE)
    );
}

#[test]
fn index_post_request() {
    thread::spawn(|| server::run_server());

    let mut stream = TcpStream::connect("127.0.0.1:8000").expect("Could not connect to server");
    let _ = stream.write(INDEX_POST_REQUEST.as_bytes());
    assert_eq!(
        replace_nonce_and_content_length(read_stream_response(&mut stream)),
        String::from(INDEX_POST_RESPONSE),
    );
}

#[test]
fn index_post_request_fail() {
    thread::spawn(|| server::run_server());

    let mut stream = TcpStream::connect("127.0.0.1:8000").expect("Could not connect to server");
    let _ = stream.write(INDEX_POST_REQUEST_FAIL.as_bytes());
    assert_eq!(
        read_stream_response(&mut stream),
        String::from(INDEX_POST_RESPONSE_FAIL),
    );
}

#[test]
fn login_get_request() {
    thread::spawn(|| server::run_server());

    let mut stream = TcpStream::connect("127.0.0.1:8000").expect("Could not connect to server");
    let _ = stream.write(LOGIN_GET_REQUEST.as_bytes());
    assert_eq!(
        read_stream_response(&mut stream),
        String::from(LOGIN_GET_RESPONSE)
    );
}

#[test]
fn serve_get_js() {
    thread::spawn(|| server::run_server());

    let mut stream = TcpStream::connect("127.0.0.1:8000").expect("Could not connect to server");
    let _ = stream.write(
        "GET /comment.js HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n"
            .as_bytes(),
    );
    let response = format!(
        "HTTP/1.0 200 OK\r\nContent-Length: {content_length}\r\nSet-Cookie: token={fake_token}; SameSite=Lax\r\n\r\n{body}",
        content_length=COMMENT_JS.len(),
        fake_token=RANDOM_REPLACEMENT,
        body=COMMENT_JS
    );
    assert_eq!(read_stream_response(&mut stream), response,);
}

#[test]
fn serve_get_css() {
    thread::spawn(|| server::run_server());

    let mut stream = TcpStream::connect("127.0.0.1:8000").expect("Could not connect to server");
    let _ = stream.write(
        "GET /comment.css HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n"
            .as_bytes(),
    );
    let response = format!(
        "HTTP/1.0 200 OK\r\nContent-Length: {content_length}\r\nSet-Cookie: token={fake_token}; SameSite=Lax\r\n\r\n{body}",
        content_length=COMMENT_CSS.len(),
        fake_token=RANDOM_REPLACEMENT,
        body=COMMENT_CSS
    );
    assert_eq!(read_stream_response(&mut stream), response,);
}

// add_post_success
// add_post_fail_login
// add_post_fail_bad_nonce
// add_post_fail_no_value
// no_handler
