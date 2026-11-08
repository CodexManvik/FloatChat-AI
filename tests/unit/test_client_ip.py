from types import SimpleNamespace

from api.limits import client_ip


def request(headers, host="10.0.0.1"):
    return SimpleNamespace(headers={k.lower(): v for k, v in headers.items()}, client=SimpleNamespace(host=host))


def test_cloudflare_header_wins_over_spoofable_forwarded_for():
    # Render sits behind Cloudflare, which sets CF-Connecting-IP itself; X-Forwarded-For keeps whatever the client sent
    req = request({"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "1.2.3.4, 203.0.113.7"})
    assert client_ip(req) == "203.0.113.7"


def test_falls_back_to_forwarded_for_then_socket():
    assert client_ip(request({"X-Forwarded-For": "198.51.100.2, 10.0.0.9"})) == "198.51.100.2"
    assert client_ip(request({})) == "10.0.0.1"


def test_trusted_frontend_can_pass_the_visitor_ip():
    headers = {"CF-Connecting-IP": "35.0.0.1", "X-Frontend-Token": "s3cret", "X-Visitor-IP": "203.0.113.50"}
    assert client_ip(request(headers), frontend_token="s3cret") == "203.0.113.50"


def test_visitor_ip_is_ignored_without_the_right_token():
    headers = {"CF-Connecting-IP": "35.0.0.1", "X-Frontend-Token": "guess", "X-Visitor-IP": "203.0.113.50"}
    assert client_ip(request(headers), frontend_token="s3cret") == "35.0.0.1"
    assert client_ip(request(headers), frontend_token="") == "35.0.0.1"  # feature off when no token configured
