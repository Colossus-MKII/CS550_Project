"""Self-hosted learning preview, loopback by default, with MP4 byte-range seeking.

python -m learning.serve --port 8765
Explicit network access: --host 0.0.0.0 --run <run-folder>.
No uploads, directory listings, or access outside output_root.
This HTTP preview has no authentication or TLS; it is not a production server.
Opening index.html directly in a desktop browser is also supported.
"""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit


PUBLIC_SLUG = "cs550-tracking-lab"


class PreviewHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, output_root, allowed_run=None, **kwargs):
        self.output_root = Path(output_root).resolve()
        self.allowed_run = allowed_run
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_file(head_only=True)

    def do_GET(self):
        self.send_file(head_only=False)

    def redirect(self, location, status=302):
        query = urlsplit(self.path).query
        self.send_response(status)
        self.send_header("Location", location + ("?" + query if query else ""))
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def send_file(self, head_only):
        requested = unquote(urlsplit(self.path).path).lstrip("/")
        relative = requested
        if requested == "favicon.ico" and self.allowed_run:
            self.redirect(f"/{PUBLIC_SLUG}/favicon.ico")
            return
        if not relative and self.allowed_run:
            self.redirect(f"/{PUBLIC_SLUG}/index.html")
            return
        if self.allowed_run and (relative == PUBLIC_SLUG or relative.startswith(PUBLIC_SLUG + "/")):
            # Keep timestamped experiment files intact behind a stable project URL.
            relative = self.allowed_run + relative[len(PUBLIC_SLUG):]
        path = (self.output_root / relative).resolve()
        if not path.is_relative_to(self.output_root) or any(part.startswith(".") for part in Path(relative).parts):
            self.send_error(403)
            return
        if self.allowed_run:
            run_root = (self.output_root / self.allowed_run).resolve()
            if not run_root.is_relative_to(self.output_root) or not path.is_relative_to(run_root):
                self.send_error(403)
                return
            if any(".before-refresh-" in part.lower() or part.lower().startswith("browser-qa")
                   for part in path.relative_to(run_root).parts):
                self.send_error(403)
                return
        if path.is_dir():
            path = path / "index.html"
        if not path.is_file() or path.suffix.lower() not in {".html", ".mp4", ".jpg", ".png", ".svg", ".ico", ".json", ".jsonl", ".txt", ".pdf", ".zip", ".tex"}:
            self.send_error(404)
            return
        if self.allowed_run:
            if requested == PUBLIC_SLUG:
                self.redirect(f"/{PUBLIC_SLUG}/", status=308)
                return
            if self.allowed_run != PUBLIC_SLUG and (requested == self.allowed_run or requested.startswith(self.allowed_run + "/")):
                suffix = requested[len(self.allowed_run):] or "/"
                self.redirect(quote(f"/{PUBLIC_SLUG}{suffix}", safe="/"), status=308)
                return
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        requested_range = self.headers.get("Range")
        if requested_range:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested_range)
            if not match or not any(match.groups()) or not size:
                self.range_error(size)
                return
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                start = max(0, size - int(last))
            if start >= size or start > end:
                self.range_error(size)
                return
            status = 206
        self.send_response(status)
        download_types = {".zip": "application/zip", ".tex": "text/plain; charset=utf-8"}
        image_types = {".svg": "image/svg+xml", ".ico": "image/x-icon"}
        self.send_header("Content-Type", download_types.get(path.suffix.lower()) or image_types.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        if path.suffix.lower() in download_types:
            # Constant disposition avoids reflecting arbitrary filenames into headers.
            self.send_header("Content-Disposition", "attachment")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only:
            return
        try:
            with path.open("rb") as source:
                source.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = source.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Browsers cancel old range requests when the seek position changes.

    def range_error(self, size):
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()


def validate_binding(root, host, allowed_run):
    if host not in {"127.0.0.1", "0.0.0.0"}:
        raise ValueError("Use 127.0.0.1 or 0.0.0.0 for the binding address")
    if host == "0.0.0.0" and not allowed_run:
        raise ValueError("Network binding requires --run to limit exposure to one teaching run")
    if allowed_run:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", allowed_run):
            raise ValueError("Run must be a single folder name")
        run_root = (Path(root).resolve() / allowed_run).resolve()
        if not run_root.is_relative_to(Path(root).resolve()) or not run_root.is_dir():
            raise ValueError("Run directory must exist inside the learning output root")


def create_server(root, port, host="127.0.0.1", allowed_run=None):
    validate_binding(root, host, allowed_run)
    return ThreadingHTTPServer((host, port), partial(
        PreviewHandler, output_root=root, allowed_run=allowed_run))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--run", help="Serve only this run folder; required for network access")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "outputs/learning")
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("Output directory does not exist; run a lesson first.")
    try:
        validate_binding(args.directory, args.host, args.run)
    except ValueError as error:
        parser.error(str(error))
    with create_server(args.directory, args.port, args.host, args.run) as server:
        print(f"Learning preview listening on {args.host}:{args.port}", flush=True)
        print(f"Local URL: http://127.0.0.1:{args.port}/{PUBLIC_SLUG if args.run else '<run-folder>'}/index.html", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
