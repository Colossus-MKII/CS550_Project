"""The optional results preview is read-only and scoped to one output root."""

from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from tracking_lab.serve import Handler


def test_read_only_scoped_preview(tmp_path):
    (tmp_path / "index.html").write_text("<h1>local result</h1>", encoding="utf-8")
    (tmp_path / ".private").mkdir()
    (tmp_path / ".private/secret.txt").write_text("hidden", encoding="utf-8")
    (tmp_path / "video.mp4").write_bytes(b"0123456789")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(tmp_path))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for method, path, status in [
            ("GET", "/", 200),
            ("HEAD", "/", 200),
            ("GET", "/%2e%2e/README.md", 403),
            ("HEAD", "/.private/secret.txt", 403),
            ("GET", "/.private/secret.txt", 403),
            ("POST", "/new.txt", 501),
            ("GET", "/code/", 404),
        ]:
            connection = HTTPConnection("127.0.0.1", server.server_port)
            try:
                connection.request(method, path)
                response = connection.getresponse()
                assert response.status == status, (method, path, response.status)
                response.read()
            finally:
                connection.close()
        assert not (tmp_path / "new.txt").exists()
        for value, status, expected in [
            ("bytes=2-4", 206, b"234"),
            ("bytes=-3", 206, b"789"),
            ("bytes=4-", 206, b"456789"),
            ("bytes=20-", 416, b""),
        ]:
            connection = HTTPConnection("127.0.0.1", server.server_port)
            try:
                connection.request("GET", "/video.mp4", headers={"Range": value})
                response = connection.getresponse()
                assert response.status == status
                assert response.read() == expected
            finally:
                connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
