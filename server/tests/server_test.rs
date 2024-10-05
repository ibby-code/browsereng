use regex::{Captures, Regex};
use std::io::{BufReader, Read, Write};
use std::net::TcpStream;
use std::thread;
extern crate server;

const ADD_POST_RESPONSE: &str = include_str!("data/add_post_response.txt");
const ADD_POST_RESPONSE_FAIL: &str = include_str!("data/add_post_response_fail.txt");
const INDEX_GET_REQUEST: &str = include_str!("data/index_get_request.txt");
const INDEX_GET_RESPONSE: &str = include_str!("data/index_get_response.txt");
const INDEX_POST_REQUEST: &str = include_str!("data/index_post_request.txt");
const INDEX_POST_RESPONSE: &str = include_str!("data/index_post_response.txt");
const INDEX_POST_REQUEST_FAIL: &str = include_str!("data/index_post_request_fail.txt");
const INDEX_POST_RESPONSE_FAIL: &str = include_str!("data/index_post_response_fail.txt");
const LOGIN_GET_REQUEST: &str = include_str!("data/login_get_request.txt");
const LOGIN_GET_RESPONSE: &str = include_str!("data/login_get_response.txt");
const NOT_FOUND_RESPONSE: &str = include_str!("data/not_found_response.txt");

const COMMENT_JS: &str = include_str!("../src/comment.js");
const COMMENT_CSS: &str = include_str!("../src/comment.css");

const RANDOM_REPLACEMENT: &str = "__rand__";

fn replace_content_length(response: String) -> String {
    let content_length_regex = Regex::new(r"Content-Length:[ \d]+").unwrap();
    content_length_regex
        .replace(&response, format!("Content-Length:{}", RANDOM_REPLACEMENT))
        .to_string()
}

/// Replaces value attr for nonce input element and returns value.
fn replace_nonce_and_content_length(response: String) -> (String, String) {
    let response = replace_content_length(response);
    let nonce_regex = Regex::new(r#"<input name="nonce"(.*)value="([\d]+)""#).unwrap();
    let Some(caps) = nonce_regex.captures(&response) else {
        return (response, String::new());
    };
    (
        nonce_regex
            .replace(&response, |caps: &Captures| {
                format!(
                    "<input name=\"nonce\"{}value=\"{}\"",
                    &caps[1], RANDOM_REPLACEMENT
                )
            })
            .to_string(),
        caps[2].to_string(),
    )
}

fn replace_token_value(response: String) -> (String, String) {
    let token_regex = Regex::new(r"token=(\w+)").unwrap();
    let Some(caps) = token_regex.captures(&response) else {
        return (response, String::new());
    };
    (
        token_regex
            .replace(&response, format!("token={}", RANDOM_REPLACEMENT))
            .to_string(),
        caps[1].to_string(),
    )
}

fn replace_csp_port(response: String) -> String {
    let csp_port_regex = Regex::new(r"default-src http://localhost:([\d]+)").unwrap();
    csp_port_regex.replace(&response, format!("default-src http://localhost:{}", RANDOM_REPLACEMENT)).to_string()
}

fn write_and_read_stream_response(request: &str, port: Option<usize>) -> String {
    let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port.unwrap_or(8000))).unwrap();
    let _ = stream.write(request.as_bytes());

    let mut response_bytes = Vec::new();
    BufReader::new(stream)
        .read_to_end(&mut response_bytes)
        .unwrap();
    replace_csp_port(String::from_utf8(response_bytes).expect("Could not parse response"))
}

// TODO: Don't use actual ports in integration tests! When running tests in parallel,
// we have multiple servers using the same port, so test output is based on a race condition.
// Fixed this with a hack (making some tests use diff ports) but the real fix is to not hog a machine's ports in tests!

#[test]
fn index_get_request() {
    thread::spawn(|| server::run_server());

    assert_eq!(
        replace_token_value(write_and_read_stream_response(INDEX_GET_REQUEST, None)).0,
        String::from(INDEX_GET_RESPONSE)
    );
}

#[test]
fn index_post_request() {
    let port = 8001;
    thread::spawn(move || server::run_server_at_port(port));

    assert_eq!(
        replace_nonce_and_content_length(
            replace_token_value(write_and_read_stream_response(
                INDEX_POST_REQUEST,
                Some(port)
            ))
            .0
        )
        .0,
        String::from(INDEX_POST_RESPONSE),
    );
}

#[test]
fn index_post_request_fail() {
    thread::spawn(|| server::run_server());

    assert_eq!(
        replace_token_value(write_and_read_stream_response(
            INDEX_POST_REQUEST_FAIL,
            None
        ))
        .0,
        String::from(INDEX_POST_RESPONSE_FAIL),
    );
}

#[test]
fn login_get_request() {
    thread::spawn(|| server::run_server());

    assert_eq!(
        replace_token_value(write_and_read_stream_response(LOGIN_GET_REQUEST, None)).0,
        String::from(LOGIN_GET_RESPONSE)
    );
}

#[test]
fn add_post_success() {
    let port = 8002;
    thread::spawn(move || server::run_server_at_port(port));

    // login
    let token_values = replace_token_value(write_and_read_stream_response(
        INDEX_POST_REQUEST,
        Some(port),
    ));
    // retreive cookie token and nonce
    let token = token_values.1;
    let nonce = replace_nonce_and_content_length(token_values.0);
    // craft post request to add entry
    let body = format!("guest=new_guest&nonce={nonce}", nonce = nonce.1);
    let request = format!(
        "POST /add HTTP/1.1\r\n\
        Content-Length:{content_length}\r\n\
        Host: google.com\r\n\
        Cookie: token={cookie}\r\n\
        User-Agent: CanYouBrowseIt\r\n\r\n\
        {body}",
        body = body,
        content_length = body.len(),
        cookie = token
    );
    // connect and send post to create entry
    let response = replace_nonce_and_content_length(
        replace_token_value(write_and_read_stream_response(&request, Some(port))).0,
    )
    .0;

    assert_eq!(response, ADD_POST_RESPONSE.to_string());
}

#[test]
fn add_post_fail_login() {
    thread::spawn(|| server::run_server());

    let body = "guest=new_guest";
    let request = format!(
        "POST /add HTTP/1.1\r\n\
        Content-Length:{content_length}\r\n\
        Host: google.com\r\n\
        User-Agent: CanYouBrowseIt\r\n\r\n\
        {body}",
        body = body,
        content_length = body.len(),
    );
    let response = replace_token_value(write_and_read_stream_response(&request, None)).0;
    assert_eq!(response, INDEX_GET_RESPONSE);
}

#[test]
fn add_post_fail_bad_nonce() {
    let port = 8003;
    thread::spawn(move || server::run_server_at_port(port));

    // login
    let token_values = replace_token_value(write_and_read_stream_response(
        INDEX_POST_REQUEST,
        Some(port),
    ));
    // craft post request to add entry
    let body = format!("guest=new_guest&nonce={nonce}", nonce = "4359084950348509");
    let request = format!(
        "POST /add HTTP/1.1\r\n\
        Content-Length:{content_length}\r\n\
        Host: google.com\r\n\
        Cookie: token={cookie}\r\n\
        User-Agent: CanYouBrowseIt\r\n\r\n\
        {body}",
        body = body,
        content_length = body.len(),
        cookie = token_values.1
    );
    // connect and send post to create entry
    let response = replace_nonce_and_content_length(
        replace_token_value(write_and_read_stream_response(&request, Some(port))).0,
    )
    .0;
    assert_eq!(response, ADD_POST_RESPONSE_FAIL.to_string());
}

#[test]
fn add_post_fail_no_value() {
    let port = 8004;
    thread::spawn(move || server::run_server_at_port(port));

    // login
    let token_values = replace_token_value(write_and_read_stream_response(
        INDEX_POST_REQUEST,
        Some(port),
    ));
    // retreive cookie token and nonce
    let token = token_values.1;
    let nonce = replace_nonce_and_content_length(token_values.0);
    // craft post request to add entry
    let body = format!("nonce={nonce}", nonce = nonce.1);
    let request = format!(
        "POST /add HTTP/1.1\r\n\
        Content-Length:{content_length}\r\n\
        Host: google.com\r\n\
        Cookie: token={cookie}\r\n\
        User-Agent: CanYouBrowseIt\r\n\r\n\
        {body}",
        body = body,
        content_length = body.len(),
        cookie = token
    );
    // connect and send post to create entry
    let response = replace_nonce_and_content_length(
        replace_token_value(write_and_read_stream_response(&request, Some(port))).0,
    )
    .0;

    assert_eq!(response, ADD_POST_RESPONSE_FAIL.to_string());
}

#[test]
fn serve_get_js() {
    thread::spawn(|| server::run_server());

    let request =
        "GET /comment.js HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n";
    let response = format!(
        "HTTP/1.0 200 OK\r\nContent-Length: {content_length}\r\nSet-Cookie: token={fake_token}; SameSite=Lax\r\n\
        Content-Security-Policy: default-src http://localhost:__rand__\r\n\r\n{body}",
        content_length=COMMENT_JS.len(),
        fake_token=RANDOM_REPLACEMENT,
        body=COMMENT_JS
    );
    assert_eq!(
        replace_token_value(write_and_read_stream_response(&request, None)).0,
        response
    );
}

#[test]
fn serve_get_css() {
    thread::spawn(|| server::run_server());

    let request =
        "GET /comment.css HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n";
    let response = format!(
        "HTTP/1.0 200 OK\r\nContent-Length: {content_length}\r\nSet-Cookie: token={fake_token}; SameSite=Lax\r\n\
        Content-Security-Policy: default-src http://localhost:__rand__\r\n\r\n{body}",
        content_length=COMMENT_CSS.len(),
        fake_token=RANDOM_REPLACEMENT,
        body=COMMENT_CSS
    );
    assert_eq!(
        replace_token_value(write_and_read_stream_response(&request, None)).0,
        response
    );
}

#[test]
fn unhandled_path() {
    thread::spawn(|| server::run_server());

    let request = "GET /list HTTP/1.1\r\nHost: google.com\r\nUser-Agent: CanYouBrowseIt\r\n\r\n";
    assert_eq!(
        replace_token_value(write_and_read_stream_response(&request, None)).0,
        NOT_FOUND_RESPONSE.to_string()
    );
}
