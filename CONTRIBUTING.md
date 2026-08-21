# Contributing to Pagecraft

Thank you for considering a contribution to Pagecraft. The project is a small Python static-site generator, so focused changes with a clear user-facing reason are easier to review and maintain.

## Before you start

For larger work, open an issue first so the proposed behavior and scope can be discussed. For a small bug fix or documentation correction, a pull request is welcome directly.

Please do not use public issues to report a security vulnerability. Follow the private reporting guidance in [SECURITY.md](SECURITY.md) instead.

## Local setup

Pagecraft supports Python 3.10 through 3.12. Create an isolated environment if you use one, then install the package with the development dependencies:

```bash
git clone https://github.com/vincenzo-afk/Pagecraft.git
cd Pagecraft
python3 -m pip install -e ".[dev]"
```

Run the same checks used by the repository workflow before opening a pull request:

```bash
python3 -m pytest
python3 -m build
```

The test suite is under `tests/`. It covers configuration parsing, front matter and routes, rendering, taxonomy pages, discovery files, incremental output, asset synchronization, and CLI commands.

## Making a change

Use a concise branch name that describes the work, such as `feat/feed-description`, `fix/stale-assets`, or `docs/template-overrides`. Keep each pull request limited to one connected change.

When a behavior changes, update or add a regression test. When a command, a `site.yaml` setting, a generated file, or a user-visible template behavior changes, update the relevant documentation in the same pull request. Built-in templates and the bundled package resources are intentionally kept in sync; modify both copies when changing a layout or the stylesheet.

Use short, imperative commit subjects. Conventional Commit prefixes such as `feat:`, `fix:`, `docs:`, and `test:` are welcome, but they are not required.

## Pull requests

A good pull request explains the problem, summarizes the change, and states how it was tested. The pull-request template asks for these details, including notes about documentation, compatibility, and security impact.

Please keep generated `_site/` output, `.pagecraft/` build manifests, local environments, and distribution artifacts out of commits. The repository `.gitignore` already covers the usual local artifacts.

## Code and documentation style

Match the surrounding Python style and use descriptive names. Favor small, testable functions and clear error messages because Pagecraft is used from the command line. Documentation should use exact, runnable commands and should not claim support for a feature that is not implemented.

## License

By contributing, you agree that your contribution may be distributed under the repository’s [MIT License](LICENSE).
