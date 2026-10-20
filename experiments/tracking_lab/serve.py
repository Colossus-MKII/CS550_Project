"""Read-only LOOPBACK preview of one pilot output folder, without uploads/listing.

Does not expose the project directory or change the public learning service.
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from . import ROOT


class Handler(SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(404)

    def allowed(self):
        path = Path(unquote(urlsplit(self.path).path).lstrip("/") or "index.html")
        root = Path(self.directory).resolve()
        target = (root / path).resolve()
        try:
            relative = target.relative_to(root)
        except ValueError:
            self.send_error(403)
            return False
        if any(
            part.startswith(".") or part.startswith("browser-qa")
            for part in relative.parts
        ):
            self.send_error(403)
            return False
        if target.suffix.lower() not in {
            ".html",
            ".json",
            ".jpg",
            ".png",
            ".mp4",
            ".txt",
        }:
            self.send_error(404)
            return False
        return True

    def do_GET(self):
        if self.allowed():
            super().do_GET()

    def do_HEAD(self):
        if self.allowed():
            super().do_HEAD()

    def send_head(self):
        """Support single byte ranges so browser videos can seek correctly."""
        self.range_remaining = None
        path = Path(self.translate_path(self.path))
        header = self.headers.get("Range")
        if path.suffix.lower() != ".mp4" or not header or not path.is_file():
            return super().send_head()
        total = path.stat().st_size
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
        if not match or not any(match.groups()):
            self.send_error(416)
            return None
        left, right = match.groups()
        if left:
            start, end = int(left), int(right) if right else total - 1
        else:
            start, end = max(0, total - int(right)), total - 1
        end = min(end, total - 1)
        if start > end or start >= total:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{total}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        stream = path.open("rb")
        stream.seek(start)
        self.range_remaining = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Content-Length", str(self.range_remaining))
        self.end_headers()
        return stream

    def copyfile(self, source, destination):
        if self.range_remaining is None:
            return super().copyfile(source, destination)
        remaining = self.range_remaining
        while remaining:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            destination.write(chunk)
            remaining -= len(chunk)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.relative_to((ROOT / "runs").resolve())
    if not (folder / "index.html").is_file():
        raise FileNotFoundError("Generate the report first")
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), partial(Handler, directory=str(folder))
    )
    print(f"Local pilot: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
