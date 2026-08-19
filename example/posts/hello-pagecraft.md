---
title: A calmer way to publish a small site
date: 2026-08-15
updated: 2026-08-18
categories: [Publishing]
tags: [pagecraft, writing, static-sites]
description: A short introduction to Pagecraft and the case for keeping a publishing workflow close to plain files.
summary: Good publishing tools should disappear while you are writing.
---

# A calmer way to publish a small site

A personal site does not need a dashboard, a database, or a long setup ritual. It needs a place for writing, a dependable build, and enough structure to make old work easy to find.

Pagecraft keeps those pieces close together. Posts stay in Markdown, the site configuration stays in one YAML file, and templates remain ordinary HTML.

```python
from pagecraft.builder import Builder

Builder(".").build()
```

That small surface area is intentional. The generator should make publishing feel lighter, not add another system to maintain.
