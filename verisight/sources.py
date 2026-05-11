from __future__ import annotations

from urllib.parse import urlparse

from verisight.schema import SearchItem, SourceType


OFFICIAL_HINTS = (
    ".gov",
    ".gov.",
    "docs.",
    "developer.",
    "developers.",
    "github.com",
)

ACADEMIC_HINTS = (
    ".edu",
    "arxiv.org",
    "doi.org",
    "nature.com",
    "science.org",
)

REPUTABLE_MEDIA_HINTS = (
    "wikipedia.org",
    "reuters.com",
    "apnews.com",
    "bbc.",
    "nytimes.com",
    "wsj.com",
    "ft.com",
    "economist.com",
    "nature.com",
    "science.org",
)

SOCIAL_HINTS = (
    "twitter.com",
    "x.com",
    "facebook.com",
    "reddit.com",
    "linkedin.com",
    "threads.net",
    "mastodon",
    "medium.com",
    "substack.com",
)

BLOG_HINTS = (
    "blog",
    "wordpress",
    "ghost",
    "medium.com",
    "substack.com",
)

FORUM_HINTS = (
    "reddit.com",
    "stackoverflow.com",
    "discourse",
    "forum",
    "community",
)

OFFICIAL_SOURCE_HINTS = (
    ".gov",
    ".gov.",
    ".edu",
    "docs.",
    "developer.",
    "developers.",
    "arxiv.org",
    "doi.org",
    "nature.com",
    "science.org",
    "reuters.com",
    "apnews.com",
    "bbc.",
)

COMMUNITY_SOURCE_HINTS = (
    "reddit.com",
    "stackoverflow.com",
    "discourse",
    "forum",
    "community",
    "github.com/issues",
    "github.com/discussions",
    "x.com",
    "twitter.com",
)


def extract_domain(url: str) -> str:
    """Extract normalized domain from URL."""
    return urlparse(url).netloc.lower()


def classify_source(url: str) -> str:
    """Classify source type from URL using deterministic rules."""
    domain = extract_domain(url)
    if any(hint in domain for hint in ACADEMIC_HINTS) or domain.endswith(".edu"):
        return SourceType.academic.value
    if any(hint in domain for hint in OFFICIAL_HINTS) or domain.startswith("gov.") or ".gov." in domain:
        return SourceType.official.value
    if any(hint in domain for hint in REPUTABLE_MEDIA_HINTS):
        return SourceType.reputable_media.value
    if any(hint in domain for hint in FORUM_HINTS):
        return SourceType.forum.value
    if any(hint in domain for hint in BLOG_HINTS):
        return SourceType.blog.value
    if any(hint in domain for hint in SOCIAL_HINTS):
        return SourceType.social.value
    return SourceType.web.value


def classify_source_type(url: str) -> SourceType:
    """Classify source type from URL returning SourceType enum."""
    return SourceType(classify_source(url))


def source_credibility(source_type: str) -> float:
    weights = {
        "official": 1.0,
        "academic": 0.95,
        "reputable_media": 0.8,
        "web": 0.55,
    }
    return weights.get(source_type, 0.45)


def matches_source_profile(item: SearchItem, profile: str) -> bool:
    """Return whether an item matches a high-level source profile."""
    if profile == "balanced":
        return True
    url = item.url.lower()
    domain = extract_domain(item.url)
    text = f"{item.title} {item.snippet}".lower()
    if profile == "official":
        if "github.com" in domain:
            return "/releases" in url or "/tags" in url
        return any(hint in domain or hint in url for hint in OFFICIAL_SOURCE_HINTS)
    if profile == "community":
        return any(hint in domain or hint in url or hint in text for hint in COMMUNITY_SOURCE_HINTS)
    return True
