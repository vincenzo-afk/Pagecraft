---
title: Incremental Builds Explained
date: 2026-08-18
tags: [static-sites, performance]
description: How Pagecraft rebuilds only what changed.
---

# Incremental Builds Explained

Nobody likes waiting for a full rebuild when a single word changed.
Pagecraft keeps a small content-hash cache in `.pagecraft/manifest.json`
and compares it against the current state of every file before writing
output.

| Scenario | What Pagecraft does |
| --- | --- |
| First build | Generates every post, page, index, tag page, and feed |
| Changed one post | Rebuilds only that post, index, tag pages, and feed |
| Unchanged post | Reuses the previously written HTML |
| Template change | Rebuilds everything, because layouts affect all pages |

A change *ripples* exactly where it needs to: editing a post regenerates
the post, the homepage listing, any tag pages that reference it, and the
RSS feed. Everything else stays untouched.

Run builds continuously with watch mode:

```bash
pagecraft watch
```
