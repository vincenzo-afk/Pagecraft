"""Pagecraft command-line interface.

Commands
--------
pagecraft init          Create a new Pagecraft project in the current directory
pagecraft build         Build the site (incremental by default; --full for everything)
pagecraft clean         Remove the build output and cache
pagecraft watch         Rebuild automatically whenever source files change
"""

from __future__ import annotations

import argparse
import os
import sys

from .builder import Builder


def cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a new Pagecraft project."""
    target = os.path.abspath(args.path)
    os.makedirs(target, exist_ok=True)
    files = {
        "site.yaml": (
            "title: My Pagecraft Site\n"
            "description: A clean static site generated with Pagecraft.\n"
            "url: https://example.com\n"
            "author: You\n"
            "posts_dir: posts\n"
            "pages_dir: pages\n"
            "assets_dir: assets\n"
            "output_dir: _site\n"
            "permalinks: true\n"
            "feed:\n"
            "  enabled: true\n"
            "  filename: feed.xml\n"
            "  posts_limit: 20\n"
        ),
        "posts/first-post.md": (
            "---\n"
            "title: First Post\n"
            "date: 2026-08-19\n"
            "tags: [hello, pagecraft]\n"
            "description: Welcome to your new Pagecraft blog.\n"
            "---\n"
            "\n"
            "# First Post\n"
            "\n"
            "Start writing in Markdown. Pagecraft turns it into a polished static site.\n"
        ),
        "pages/about.md": (
            "---\n"
            "title: About\n"
            "---\n"
            "\n"
            "# About\n"
            "\n"
            "A simple about page.\n"
        ),
        "assets/.keep": "",
    }
    for path, content in files.items():
        full = os.path.join(target, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if not os.path.exists(full):
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"created {path}")
    print(f"\nPagecraft project initialized in {target}")
    print("Run `pagecraft build` to generate the site.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    builder = Builder(args.project, incremental=not args.full)
    result = builder.build()
    print(f"Pagecraft built {result['posts_built']} file(s); "
          f"skipped {result['files_skipped']} unchanged; "
          f"copied {result['assets_copied']} asset(s).")
    print(f"Output: {result['output_dir']}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    import shutil

    project = os.path.abspath(args.project)
    config = __import__("pagecraft.config", fromlist=["SiteConfig"]).SiteConfig.load(project)
    output_dir = os.path.join(project, config.output_dir)
    cache_dir = os.path.join(project, ".pagecraft")
    for directory in (output_dir, cache_dir):
        if os.path.isdir(directory):
            shutil.rmtree(directory)
            print(f"removed {directory}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    builder = Builder(args.project, incremental=True)
    watch_dirs = [
        os.path.join(args.project, d)
        for d in (builder.config.posts_dir, builder.config.pages_dir,
                  builder.config.assets_dir, "templates")
    ]
    watch_dirs.append(os.path.join(args.project, "site.yaml"))

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):  # noqa: N802
            if event.is_directory:
                return
            if ".pagecraft" in event.src_path:
                return
            print(f"change detected: {os.path.relpath(event.src_path, args.project)}")
            try:
                builder.build()
                print("build complete.\n")
            except Exception as exc:  # noqa: BLE001
                print(f"build failed: {exc}\n")

    observer = Observer()
    handler = Handler()
    for path in watch_dirs:
        if os.path.isdir(path):
            observer.schedule(handler, path, recursive=True)
        elif os.path.isfile(path):
            observer.schedule(handler, os.path.dirname(path), recursive=False)
    observer.start()
    builder.build()
    print("Watching for changes... (Ctrl+C to stop)")
    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagecraft", description="Pagecraft — a Markdown-to-HTML static site generator.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create a new Pagecraft project")
    init_p.add_argument("path", nargs="?", default=".", help="Project directory (default: current)")

    build_p = sub.add_parser("build", help="Build the site")
    build_p.add_argument("--project", default=".", help="Project root (default: current)")
    build_p.add_argument("--full", action="store_true", help="Rebuild everything, ignoring the cache")

    clean_p = sub.add_parser("clean", help="Remove build output and cache")
    clean_p.add_argument("--project", default=".", help="Project root (default: current)")

    watch_p = sub.add_parser("watch", help="Rebuild automatically on file changes")
    watch_p.add_argument("--project", default=".", help="Project root (default: current)")

    args = parser.parse_args(argv)
    return {
        "init": cmd_init,
        "build": cmd_build,
        "clean": cmd_clean,
        "watch": cmd_watch,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
