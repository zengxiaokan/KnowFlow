import bleach
import markdown

ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h2",
    "h3",
    "h4",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}
ALLOWED_PROTOCOLS = {"http", "https", "mailto"}


def render_assistant_markdown(value: str) -> str:
    """Render model output with a deliberately small, sanitised Markdown subset."""
    if not value:
        return ""
    rendered = markdown.markdown(
        value,
        extensions=["fenced_code", "nl2br", "sane_lists"],
        output_format="html5",
    )
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
