<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/tests-14%20passing-2ea44f" alt="14 passing tests">
</p>

# Pagecraft

A small, fast Markdown-to-HTML static site generator. It takes a folder of Markdown files and turns them into a complete, styled website — with templates, tag pages, an RSS feed, highlighted code blocks, and builds that only regenerate what actually changed.

You write. Pagecraft handles the rest.

[Live demo →](https://pagecraft-demo.vercel.app)

---

## Table of Contents

- [What it is](#what-it-is)
- [Why I built it](#why-i-built-it)
- [Features](#features)
- [Quick start](#quick-start)
- [How a project is laid out](#how-a-project-is-laid-out)
- [Configuration](#configuration)
- [Commands](#commands)
- [How incremental builds work](#how-incremental-builds-work)
- [Deploying your site](#deploying-your-site)
- [Running the tests](#running-the-tests)
- [Under the hood](#under-the-hood)
- [What's next](#whats-next)
- [Contributing](#contributing)
- [License](#license)

---

## What it is

Pagecraft is a command-line tool written in Python. You point it at a folder of Markdown files, and it writes out a finished static website: HTML pages styled with a clean default theme, a homepage listing your posts, a tag index with one page per tag, an RSS feed for readers, and highlighted code blocks for anything you put in fenced code fences.

There's no database, no build server, and nothing to configure. The output is plain HTML and CSS — you can host it anywhere for free.

## Why I built it

I was tired of reaching for a full framework every time I wanted a simple blog or documentation site. Existing tools either wanted me to learn their conventions, or rebuilt every single page when I changed one word. Pagecraft exists to fix both: it's a single command (`pagecraft build`), and on subsequent runs it only rebuilds the files that actually changed. Editing one post takes well under a second.

## Features

**Markdown rendering.** Full CommonMark support — headings, tables, lists, blockquotes, links, images — with YAML front matter for titles, dates, tags, and descriptions.

**Templates.** Seven Jinja2 layouts ship out of the box (`base`, `index`, `post`, `page`, `tags`, `tag`, plus a post-card partial). Want your own design? Drop a `templates/` folder in your project and override whichever layouts you like; the rest are used as-is.

**Tags.** Add `tags: [python, tutorials]` to a post's front matter and Pagecraft generates a tag index page and one page per tag, listing every post that carries it.

**RSS feed.** A valid `feed.xml` is written automatically on every build, including the newest posts with their full content.

**Syntax highlighting.** Fenced code blocks are highlighted with Pygments (github-dark theme) and the matching stylesheet is shipped as `style.css` in the output.

**Asset copying.** Anything you put in `assets/` — images, extra CSS, JavaScript, fonts — gets copied verbatim into the build output.

**Incremental builds.** A content-hash manifest tracks every input and output file. Change one post and only that post, the homepage, its tag pages, and the feed get rebuilt. Everything else is untouched.

**Watch mode.** Run `pagecraft watch` and the site rebuilds itself whenever you save a file.

## Quick start

Install it:

```bash
git clone https://github.com/vincenzo-afk/Pagecraft.git
cd Pagecraft
pip install -e .
```

Create a new site and build it:

```bash
pagecraft init my-site
cd my-site
pagecraft build
```

That's it — your site is in `my-site/_site`. Preview it locally:

```bash
python3 -m http.server 8000 -d _site
# open http://localhost:8000
```

Or build the example site included in this repo:

```bash
pagecraft build --project example
python3 -m http.server 8000 -d example/_site
```

Writing a post is just adding a Markdown file with some front matter:

```markdown
---
title: Getting Started
date: 2026-08-19
tags: [tutorial]
description: How to get started with Pagecraft.
---

# Getting Started

Pagecraft renders **Markdown** into clean HTML. Code fences are
highlighted automatically:

```python
def greet(name):
    print(f"Hello, {name}!")
```
```

## How a project is laid out

```
my-site/
├── site.yaml          # optional — every setting has a default
├── posts/             # blog posts, one Markdown file each
├── pages/             # standalone pages (about, contact, ...)
├── assets/            # static files copied straight into the output
├── templates/         # optional — override any built-in layout
└── _site/             # the generated website
```

Front matter at the top of each file carries the metadata:

```yaml
---
title: My First Post
date: 2026-08-19
tags: [intro]
description: A short summary for listings and the RSS feed.
slug: my-first-post      # optional — auto-generated from the filename
---
```

Skip the `date` and Pagecraft uses the file's modification time. Skip the `slug` and it's generated from the filename. Skip the front matter entirely and the post still builds with defaults.

## Configuration

Everything is optional. Create a `site.yaml` in your project root to customize:

```yaml
title: My Pagecraft Site
description: A clean static site.
url: https://example.com
author: You
posts_dir: posts
pages_dir: pages
assets_dir: assets
output_dir: _site
permalinks: true            # posts land at /slug.html instead of /posts/slug.html
feed:
  enabled: true
  filename: feed.xml
  posts_limit: 20
```

No environment variables, no secrets, no external services. `site.yaml` is the whole configuration surface.

## Commands

| Command | What it does |
| --- | --- |
| `pagecraft init [path]` | Scaffolds a new project with config, a sample post, and an about page |
| `pagecraft build` | Builds incrementally — only changed files are regenerated |
| `pagecraft build --full` | Ignores the cache and rebuilds everything |
| `pagecraft clean` | Deletes the output folder and the build cache |
| `pagecraft watch` | Keeps rebuilding whenever a source file changes |

Every build prints a summary of what happened:

```
Pagecraft built 4 file(s); skipped 5 unchanged; copied 1 asset(s).
Output: /home/user/my-site/_site
```

## How incremental builds work

This is the part I'm most proud of. Pagecraft keeps a manifest (`.pagecraft/manifest.json`) with a SHA-256 hash for every input and output file. On each build it compares what changed against the previous run:

| What you changed | What gets rebuilt |
| --- | --- |
| One post | That post, the homepage, its tag pages, and the feed |
| One page | Just that page and the homepage |
| A template | Everything — layouts affect all pages |
| An asset | Only the output gets refreshed, no rendering |

A single-word edit in a post typically rebuilds in a fraction of a second, because most of the work is skipped entirely.

## Deploying your site

The `_site` folder is plain static content, so it goes anywhere:

- **GitHub Pages** — push `_site` to a `gh-pages` branch, or build in a workflow and deploy with `actions/deploy-pages`
- **Netlify / Vercel / Cloudflare Pages** — set the build command to `pagecraft build` and the output directory to `_site`
- **Any web server** — `cp -r _site /var/www/html`

The demo site is hosted live at [pagecraft-demo.vercel.app](https://pagecraft-demo.vercel.app).

## Running the tests

The test suite is written with pytest — fourteen tests covering config loading, rendering, highlighting, full and incremental builds, tag pages, RSS output, asset copying, and the CLI:

```bash
pip install -e ".[dev]"
pytest
```

Each test starts from a clean slate (the build output and cache are wiped before and after), so results are never polluted by a previous run.

## Under the hood

A few implementation notes, if you want to dig in:

- Markdown is rendered by Python-Markdown with the `tables`, `toc`, `smarty`, and `meta` extensions, plus a custom preprocessor that swaps fenced code blocks for Pygments output before the rest of the pipeline sees them.
- Layouts use Jinja2 inheritance — every template extends `base.html`, which holds the header, navigation, and footer.
- The builder collects posts and pages, renders them, applies templates, writes the index and tag pages, generates the RSS feed, and copies assets — in that order, skipping anything whose inputs haven't changed.
- Watch mode uses `watchdog` to observe `posts/`, `pages/`, `assets/`, `templates/`, and `site.yaml`.

## What's next

A short list of things I'd like to add: draft posts with a future publish date, pagination for large post lists, a `sitemap.xml` generator, and a `pagecraft new-post` command to scaffold a post file with today's date.

## Contributing

Contributions are welcome. Fork it, make your changes on a `feat/` or `fix/` branch, run `pytest` to make sure nothing broke, add tests for anything new, and open a pull request. Conventional Commits style for commit messages is appreciated but not enforced.

## License

MIT. See [LICENSE](LICENSE).

---

Built by [vincenzo-afk](https://github.com/vincenzo-afk).
