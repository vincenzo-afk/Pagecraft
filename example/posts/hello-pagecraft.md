---
title: Hello, Pagecraft!
date: 2026-08-15
tags: [intro, static-sites]
description: The first post on a brand new Pagecraft site.
---

# Hello, Pagecraft!

Welcome to the very first post generated with **Pagecraft**, a
Markdown-to-HTML static site generator with layouts, tags, RSS feeds,
syntax highlighting, asset copying, and incremental builds.

## Writing posts

Every post is just a Markdown file with a bit of front matter at the top:

```yaml
---
title: Hello, Pagecraft!
date: 2026-08-15
tags: [intro, static-sites]
description: The first post on a brand new Pagecraft site.
---
```

And here is some highlighted code, because code fences deserve proper
syntax highlighting:

```python
def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

if __name__ == "__main__":
    print(fibonacci(10))
```

Pagecraft also understands **bold**, *italic*, tables, blockquotes, and
everything else CommonMark supports. Happy writing!

A new sentence for testing.

A new sentence for testing.

A new sentence for testing.

A new sentence for testing.
