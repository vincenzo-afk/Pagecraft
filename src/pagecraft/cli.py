"""Command-line interface for Pagecraft."""
from __future__ import annotations

import argparse
from datetime import date
import http.server
import json
import os
from pathlib import Path
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from typing import Callable

from .builder import BuildError, Builder
from .config import ConfigError, SiteConfig
from .content import slugify


def _build(args: argparse.Namespace, *, incremental: bool | None = None) -> tuple[Builder, dict]:
    builder = Builder(
        args.project,
        incremental=(not getattr(args, "full", False)) if incremental is None else incremental,
        include_drafts=getattr(args, "drafts", False),
        include_future=getattr(args, "future", False),
    )
    return builder, builder.build()


def _print_report(result: dict, *, verbose: bool = False, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(
        f"Pagecraft generated {len(result['generated'])} file(s); "
        f"skipped {result['files_skipped']} unchanged; copied {result['assets_copied']} asset(s); "
        f"removed {len(result['removed'])} stale file(s)."
    )
    print(f"Output: {result['output_dir']}")
    if verbose:
        for label in ("generated", "copied", "removed", "skipped"):
            values = result.get(label, [])
            if values:
                print(f"\n{label}:")
                print("\n".join(f"  - {item}" for item in values))


def cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a complete v0.2 Pagecraft project without overwriting files."""
    target = Path(args.path).resolve()
    today = date.today().isoformat()
    files = {
        "site.yaml": (
            "title: My Pagecraft Site\n"
            "description: Notes, essays, and useful things.\n"
            "url: https://example.com\n"
            "author: Your Name\n"
            "language: en\n"
            "posts_dir: posts\n"
            "pages_dir: pages\n"
            "assets_dir: assets\n"
            "output_dir: _site\n"
            "permalinks: true\n"
            "pagination:\n  per_page: 8\n"
            "feed:\n  enabled: true\n  filename: feed.xml\n  posts_limit: 20\n"
            "sitemap:\n  enabled: true\n  filename: sitemap.xml\n"
            "robots:\n  enabled: true\n  filename: robots.txt\n"
            "seo:\n  default_image: ''\n  twitter_handle: ''\n"
            "theme:\n  mode: auto\n"
            "navigation:\n  - label: Home\n    url: /\n  - label: About\n    url: /about.html\n  - label: Archive\n    url: /archive.html\n"
        ),
        "posts/first-post.md": (
            "---\n"
            "title: First Post\n"
            f"date: {today}\n"
            "categories: [Writing]\n"
            "tags: [hello, pagecraft]\n"
            "description: Welcome to a new Pagecraft site.\n"
            "---\n\n"
            "# First Post\n\n"
            "Start writing in Markdown. Pagecraft takes care of the site around it.\n"
        ),
        "pages/about.md": (
            "---\ntitle: About\ndescription: A short introduction.\n---\n\n"
            "# About\n\nA simple page with a little context about this site.\n"
        ),
        "assets/.keep": "",
        ".gitignore": "_site/\n.pagecraft/\n__pycache__/\n",
    }
    created = 0
    for relative, content in files.items():
        path = target / relative
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created += 1
        print(f"created {relative}")
    print(f"\nPagecraft project ready in {target} ({created} new file(s)).")
    print("Try `pagecraft serve` to preview it locally.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    try:
        _, result = _build(args)
    except (BuildError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_report(result, verbose=args.verbose, as_json=args.json)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        builder = Builder(args.project, include_drafts=args.drafts, include_future=args.future)
        issues = builder.check()
    except (BuildError, ConfigError) as exc:
        issues = [str(exc)]
    if args.json:
        print(json.dumps({"valid": not issues, "issues": issues}, indent=2))
    elif issues:
        print("Pagecraft found issues:", file=sys.stderr)
        print("\n".join(f"  - {issue}" for issue in issues), file=sys.stderr)
    else:
        print("Pagecraft check passed.")
    return 1 if issues else 0


def cmd_clean(args: argparse.Namespace) -> int:
    try:
        project = Path(args.project).resolve()
        config = SiteConfig.load(str(project))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for directory in (project / config.output_dir, project / ".pagecraft"):
        if directory.is_dir():
            shutil.rmtree(directory)
            print(f"removed {directory}")
    return 0


def cmd_new_post(args: argparse.Namespace) -> int:
    try:
        project = Path(args.project).resolve()
        config = SiteConfig.load(str(project))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    slug = slugify(args.title)
    filename = f"{date.today().isoformat()}-{slug}.md"
    path = project / config.posts_dir / filename
    if path.exists():
        print(f"error: refusing to overwrite existing post: {path}", file=sys.stderr)
        return 1
    categories = args.category or []
    tags = args.tag or []
    lines = ["---", f"title: {args.title}", f"date: {date.today().isoformat()}"]
    if args.draft:
        lines.append("draft: true")
    if categories:
        lines.append("categories: [" + ", ".join(categories) + "]")
    if tags:
        lines.append("tags: [" + ", ".join(tags) + "]")
    lines.extend(["description: ''", "---", "", f"# {args.title}", "", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"created {path.relative_to(project)}")
    if args.editor:
        editor = os.environ.get("EDITOR")
        if not editor:
            print("EDITOR is not set; post created without opening an editor.", file=sys.stderr)
        else:
            subprocess.run([editor, str(path)], check=False)
    return 0


def _start_watcher(args: argparse.Namespace, callback: Callable[[], None]):
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    project = Path(args.project).resolve()
    config = SiteConfig.load(str(project))
    ignored = {str(project / config.output_dir), str(project / ".pagecraft"), str(project / ".git")}
    debounce = max(0.05, getattr(args, "debounce", 0.35))

    class Handler(FileSystemEventHandler):
        timer: threading.Timer | None = None
        lock = threading.Lock()

        def on_any_event(self, event):  # noqa: N802
            if event.is_directory:
                return
            paths = [getattr(event, "src_path", ""), getattr(event, "dest_path", "")]
            if any(path and any(os.path.commonpath([path, item]) == item for item in ignored) for path in paths):
                return
            with self.lock:
                if self.timer:
                    self.timer.cancel()
                self.timer = threading.Timer(debounce, callback)
                self.timer.daemon = True
                self.timer.start()

    observer = Observer()
    observer.schedule(Handler(), str(project), recursive=True)
    observer.start()
    return observer


def cmd_watch(args: argparse.Namespace) -> int:
    def rebuild() -> None:
        try:
            _, result = _build(args, incremental=True)
            print(f"Rebuilt: {len(result['generated'])} generated, {result['files_skipped']} unchanged.")
        except (BuildError, ConfigError) as exc:
            print(f"Build failed: {exc}", file=sys.stderr)

    rebuild()
    try:
        observer = _start_watcher(args, rebuild)
    except Exception as exc:  # pragma: no cover - platform observer setup
        print(f"error: could not start watcher: {exc}", file=sys.stderr)
        return 1
    print("Watching for changes… press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
        observer.join(timeout=2)
        return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        builder, result = _build(args, incremental=True)
    except (BuildError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_report(result, verbose=False, as_json=False)

    observer = None
    if args.watch:
        def rebuild() -> None:
            try:
                _, report = _build(args, incremental=True)
                print(f"Rebuilt: {len(report['generated'])} generated, {report['files_skipped']} unchanged.")
            except (BuildError, ConfigError) as exc:
                print(f"Build failed: {exc}", file=sys.stderr)
        observer = _start_watcher(args, rebuild)

    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=builder.output_dir, **kw)
    class ReusableServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    try:
        with ReusableServer((args.host, args.port), handler) as server:
            print(f"Serving {builder.output_dir} at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        if observer:
            observer.stop()
            observer.join(timeout=2)
    return 0


def _project_flags(parser: argparse.ArgumentParser, *, full: bool = False, json_output: bool = False) -> None:
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--drafts", action="store_true", help="Include draft posts in this build")
    parser.add_argument("--future", action="store_true", help="Include posts dated in the future")
    if full:
        parser.add_argument("--full", action="store_true", help="Ignore the existing build manifest")
    if json_output:
        parser.add_argument("--json", action="store_true", help="Print a machine-readable report")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagecraft", description="Pagecraft — a fast, thoughtful Markdown static site generator.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create a new Pagecraft project")
    init_p.add_argument("path", nargs="?", default=".", help="Project directory (default: current)")

    build_p = sub.add_parser("build", help="Build the site")
    _project_flags(build_p, full=True, json_output=True)
    build_p.add_argument("--verbose", action="store_true", help="List generated, copied, removed, and skipped files")

    check_p = sub.add_parser("check", help="Validate configuration, routes, and local links without writing output")
    _project_flags(check_p, json_output=True)

    clean_p = sub.add_parser("clean", help="Remove build output and cache")
    clean_p.add_argument("--project", default=".", help="Project root (default: current directory)")

    post_p = sub.add_parser("new-post", help="Create a dated Markdown post")
    post_p.add_argument("title", help="Title for the new post")
    post_p.add_argument("--project", default=".", help="Project root (default: current directory)")
    post_p.add_argument("--draft", action="store_true", help="Start as a draft")
    post_p.add_argument("--category", action="append", help="Category (repeatable)")
    post_p.add_argument("--tag", action="append", help="Tag (repeatable)")
    post_p.add_argument("--editor", action="store_true", help="Open the new post with $EDITOR")

    watch_p = sub.add_parser("watch", help="Build once and rebuild automatically on source changes")
    _project_flags(watch_p)
    watch_p.add_argument("--debounce", type=float, default=0.35, help="Seconds to wait after a change (default: 0.35)")

    serve_p = sub.add_parser("serve", help="Build and serve the static output locally")
    _project_flags(serve_p)
    serve_p.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    serve_p.add_argument("--watch", action="store_true", help="Rebuild automatically while serving")
    serve_p.add_argument("--debounce", type=float, default=0.35, help="Seconds to wait after a change (default: 0.35)")

    args = parser.parse_args(argv)
    return {
        "init": cmd_init,
        "build": cmd_build,
        "check": cmd_check,
        "clean": cmd_clean,
        "new-post": cmd_new_post,
        "watch": cmd_watch,
        "serve": cmd_serve,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
