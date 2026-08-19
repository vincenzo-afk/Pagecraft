---
title: Why incremental builds are a publishing feature
date: 2026-08-12
categories: [Tooling]
tags: [performance, static-sites, pagecraft]
description: Fast rebuilds keep the feedback loop short enough that publishing remains pleasant.
summary: A site generator should notice what changed without making correctness optional.
---

# Why incremental builds are a publishing feature

Fast builds are not just an engineering benchmark. They change how often someone is willing to preview a draft, adjust a title, or fix a tiny link.

Pagecraft renders the complete set of derived pages in memory, compares content hashes, writes only changed files, and removes stale output after a rename or deletion. That means tag pages, feeds, archives, pagination, and the sitemap stay honest without asking authors to remember a special command.

The important part is not merely skipping work. It is keeping the generated site correct when the source changes.
