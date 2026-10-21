from http.client import HTTPConnection
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from learning.serve import PUBLIC_SLUG, create_server, validate_binding


@pytest.fixture
def preview(tmp_path):
    (tmp_path / "clip.mp4").write_bytes(b"0123456789")
    (tmp_path / "proposal.pdf").write_bytes(b"%PDF-local-proposal")
    (tmp_path / "blocked.py").write_text("print('not served')", encoding="utf-8")
    (tmp_path / "proposal.zip").write_bytes(b"PK-test-archive")
    (tmp_path / "proposal.tex").write_bytes(b"\\documentclass{article}")
    (tmp_path / "favicon.svg").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    (tmp_path / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    server = create_server(tmp_path, 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_full_response_and_head(preview):
    with urlopen(preview + "/clip.mp4") as response:
        assert response.status == 200
        assert response.read() == b"0123456789"
        assert response.headers["Accept-Ranges"] == "bytes"
    with urlopen(Request(preview + "/clip.mp4", method="HEAD")) as response:
        assert response.headers["Content-Length"] == "10"
        assert response.read() == b""


@pytest.mark.parametrize("name,mime", [("favicon.svg", "image/svg+xml"), ("favicon.ico", "image/x-icon")])
def test_icon_mime_types(preview, name, mime):
    with urlopen(preview + "/" + name + "?v=1") as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == mime
        assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("header,expected,content_range", [
    ("bytes=2-5", b"2345", "bytes 2-5/10"),
    ("bytes=7-", b"789", "bytes 7-9/10"),
    ("bytes=-3", b"789", "bytes 7-9/10"),
    ("bytes=7-100", b"789", "bytes 7-9/10"),
])
def test_ranges(preview, header, expected, content_range):
    with urlopen(Request(preview + "/clip.mp4", headers={"Range": header})) as response:
        assert response.status == 206
        assert response.read() == expected
        assert response.headers["Content-Range"] == content_range


@pytest.mark.parametrize("header", ["bytes=20-30", "bytes=-0", "bytes=5-2", "bytes=", "bytes=1-2,4-5"])
def test_invalid_range(preview, header):
    with pytest.raises(HTTPError) as error:
        urlopen(Request(preview + "/clip.mp4", headers={"Range": header}))
    assert error.value.code == 416


def test_no_directory_listing_or_traversal(preview):
    for suffix, code in [("/", 404), ("/%2e%2e/secret.txt", 403), ("/.hidden.json", 403), ("/blocked.py", 404)]:
        with pytest.raises(HTTPError) as error:
            urlopen(preview + suffix)
        assert error.value.code == code


def test_local_proposal_pdf_and_ranges(preview):
    with urlopen(preview + "/proposal.pdf") as response:
        assert response.headers["Content-Type"] == "application/pdf"
        assert response.read() == b"%PDF-local-proposal"
    with urlopen(Request(preview + "/proposal.pdf", headers={"Range": "bytes=0-3"})) as response:
        assert response.status == 206
        assert response.read() == b"%PDF"


@pytest.mark.parametrize("filename,mime,content", [
    ("proposal.zip", "application/zip", b"PK-test-archive"),
    ("proposal.tex", "text/plain; charset=utf-8", b"\\documentclass{article}"),
])
def test_source_downloads_are_attachments(preview, filename, mime, content):
    with urlopen(preview + "/" + filename) as response:
        assert response.headers["Content-Type"] == mime
        assert response.headers["Content-Disposition"] == "attachment"
        assert response.read() == content


def test_network_binding_requires_one_existing_run(tmp_path):
    for host, run in [("0.0.0.0", None), ("0.0.0.0", "../outside"),
                      ("0.0.0.0", "missing"), ("example.org", None)]:
        with pytest.raises(ValueError):
            validate_binding(tmp_path, host, run)
    local = create_server(tmp_path, 0)
    try:
        assert local.server_address[0] == "127.0.0.1"
    finally:
        local.server_close()


def test_network_mode_only_serves_selected_run_and_no_backups(tmp_path):
    run = tmp_path / "selected-run"
    run.mkdir()
    (run / "index.html").write_text("Selected teaching website", encoding="utf-8")
    (run / "index.en.html").write_text("English teaching website", encoding="utf-8")
    (run / "index.before-refresh-example.html").write_text("old page", encoding="utf-8")
    (run / "browser-qa").mkdir()
    (run / "browser-qa/private.png").write_bytes(b"not shared")
    (run / "proposal").mkdir()
    (run / "proposal/proposal.zip").write_bytes(b"PK-current-source")
    (run / "clip.mp4").write_bytes(b"0123456789")
    (run / "frame one.png").write_bytes(b"test frame")
    (run / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    other = tmp_path / "another-run"
    other.mkdir()
    (other / "index.html").write_text("Other run", encoding="utf-8")
    server = create_server(tmp_path, 0, host="0.0.0.0", allowed_run="selected-run")
    assert server.server_address[0] == "0.0.0.0"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(base + "/") as response:
            assert response.status == 200
            assert response.url == base + f"/{PUBLIC_SLUG}/index.html"
            assert response.read() == b"Selected teaching website"
        with urlopen(base + "/selected-run/proposal/proposal.zip") as response:
            assert response.read() == b"PK-current-source"
            assert response.url == base + f"/{PUBLIC_SLUG}/proposal/proposal.zip"
        for suffix in ("/", "/index.html", "/index.en.html", "/proposal/proposal.zip", "/frame%20one.png"):
            with urlopen(base + "/selected-run" + suffix + "?source=legacy") as response:
                assert response.status == 200
                assert response.url == base + f"/{PUBLIC_SLUG}" + suffix + "?source=legacy"
        with urlopen(base + f"/{PUBLIC_SLUG}") as response:
            assert response.url == base + f"/{PUBLIC_SLUG}/"
            assert response.read() == b"Selected teaching website"
        with urlopen(base + "/favicon.ico") as response:
            assert response.url == base + f"/{PUBLIC_SLUG}/favicon.ico"
            assert response.headers["Content-Type"] == "image/x-icon"
        # Inspect redirect responses directly, including HEAD (urllib can change methods).
        connection = HTTPConnection("127.0.0.1", server.server_address[1])
        try:
            for method in ("GET", "HEAD"):
                connection.request(method, "/selected-run/index.en.html?chapter=6")
                response = connection.getresponse()
                assert response.status == 308
                assert response.getheader("Location") == f"/{PUBLIC_SLUG}/index.en.html?chapter=6"
                assert response.read() == b""
            connection.request("HEAD", f"/{PUBLIC_SLUG}/index.en.html")
            response = connection.getresponse()
            assert response.status == 200
            assert int(response.getheader("Content-Length")) > 0
            assert response.read() == b""
        finally:
            connection.close()
        with urlopen(Request(base + f"/{PUBLIC_SLUG}/clip.mp4", headers={"Range": "bytes=2-5"})) as response:
            assert response.status == 206
            assert response.read() == b"2345"
        for suffix in ("../another-run/index.html", "%2e%2e/another-run/index.html",
                       "..%5canother-run/index.html", ".hidden.json",
                       "index.before-refresh-example.html", "INDEX.BEFORE-REFRESH-EXAMPLE.HTML",
                       "browser-qa/private.png", "BROWSER-QA/private.png"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + f"/{PUBLIC_SLUG}/" + suffix)
            assert error.value.code == 403
        for relative in ("another-run/index.html", "selected-run/../another-run/index.html",
                         "selected-run/index.before-refresh-example.html",
                         "selected-run/INDEX.BEFORE-REFRESH-EXAMPLE.HTML",
                         "selected-run/browser-qa/private.png",
                         "selected-run/BROWSER-QA/private.png"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + "/" + relative)
            assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
