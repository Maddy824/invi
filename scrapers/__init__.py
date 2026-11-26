"""Load scraper implementations only when requested."""

from importlib import import_module

_MODULES = {
    "BaseScraper": "base",
    "InstagramScraper": "instagram",
    "TwitterScraper": "twitter",
    "YouTubeScraper": "youtube",
}

__all__ = list(_MODULES)


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f"scrapers.{_MODULES[name]}"), name)
