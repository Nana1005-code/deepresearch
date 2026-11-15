"""Isolated public-research square feature.

The module intentionally owns a separate SQLite database so failures or schema
changes here cannot corrupt the existing local research history database.
"""

from .store import ResearchSquareStore

__all__ = ["ResearchSquareStore"]
