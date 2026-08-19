"""Markdown-to-HTML rendering with Pygments syntax highlighting.

Pagecraft extends the standard ``fenced_code`` Markdown extension with a
Pygments-based highlighter so code fences render with real syntax
highlighting and a copy of the matching Pygments stylesheet is emitted
into the build output.
"""

from __future__ import annotations

from markupsafe import Markup
import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

STYLE = "github-dark"

import re

FENCE_RE = re.compile(
    r"^`{3,}(?P<lang>[^\s`]*)\s*\n(?P<code>.*?)\n`{3,}\s*$",
    re.DOTALL | re.MULTILINE,
)


def highlight_code(code: str, language: str) -> Markup:
    """Highlight *code* written in *language* using Pygments."""
    try:
        lexer = get_lexer_by_name(language or "text")
    except ClassNotFound:
        lexer = TextLexer()
    formatter = HtmlFormatter(style=STYLE, cssclass="highlight")
    return Markup(highlight(code, lexer, formatter))


class PygmentsFencePreprocessor(Preprocessor):
    """Replace fenced code blocks with Pygments-highlighted HTML."""

    def run(self, lines: list[str]) -> list[str]:
        text = "\n".join(lines)

        def replacer(match: re.Match) -> str:
            lang = match.group("lang")
            code = match.group("code").rstrip("\n") + "\n"
            return "\n" + str(highlight_code(code, lang)) + "\n"

        return FENCE_RE.sub(replacer, text).split("\n")


class PygmentsExtension(Extension):
    def extendMarkdown(self, md):  # noqa: N802
        md.preprocessors.register(
            PygmentsFencePreprocessor(md), "pygments_fence", 50
        )


def render_markdown(source: str) -> str:
    """Render a Markdown document to HTML with Pygments-highlighted fences.

    Fences are replaced in a preprocessor running *before* the fenced-code
    extension (priority 25) so the highlighted HTML lands in the output
    untouched.
    """
    return markdown.markdown(
        source,
        extensions=["tables", "toc", "smarty", "meta", PygmentsExtension()],
        output_format="html5",
    )


def generate_stylesheet() -> str:
    """Return the Pygments CSS stylesheet for the selected theme."""
    return HtmlFormatter(style=STYLE).get_style_defs(".highlight")
