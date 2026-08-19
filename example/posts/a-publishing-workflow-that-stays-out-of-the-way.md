---
title: A publishing workflow that stays out of the way
date: 2026-08-09
categories: [Publishing]
tags: [workflow, markdown, writing]
description: A practical note on keeping posts, drafts, previews, and deployment close to the work itself.
summary: The best workflow gives writers a few dependable habits instead of a lot of interface.
---

# A publishing workflow that stays out of the way

A good publishing routine can be almost boring. Start a post, add a short description, preview it locally, and publish when it is ready.

Pagecraft provides a small command for the first step:

```bash
pagecraft new-post "A useful title" --category Publishing --tag writing
```

Drafts can stay beside published work without leaking into the public build. Future-dated posts work the same way. When a release is ready, a regular build handles the feed, archive, tags, categories, and search-engine discovery files in the same pass.
