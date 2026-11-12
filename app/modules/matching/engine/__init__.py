"""Matching engine components."""

from app.modules.matching.engine.aliases import (
    COLOR_ALIASES,
    ITEM_ALIASES,
    apply_aliases,
)
from app.modules.matching.engine.fuzzy import (
    composite_similarity,
    detailed_fuzzy_match,
    fuzzy_match,
    levenshtein_similarity,
    token_similarity,
)
from app.modules.matching.engine.normalizer import normalize

__all__ = [
    "COLOR_ALIASES",
    "ITEM_ALIASES",
    "apply_aliases",
    "composite_similarity",
    "detailed_fuzzy_match",
    "fuzzy_match",
    "levenshtein_similarity",
    "normalize",
    "token_similarity",
]
