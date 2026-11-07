"""Keep a JSON file's sorted key order across repairs."""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Any


class JsonKeyOrder:
    """Repairs serialise JSON in insertion order, so a key a fix adds lands last in its object. A repository
    that keeps its JSON keys sorted (a `sort json files` or `pretty-format-json --autofix` pre-commit hook)
    then rejects the repaired file. A file whose keys were sorted before the repair is written back sorted."""

    MIN_EVIDENCE = 3  # adjacent key pairs in order before a file counts as deliberately sorted

    @staticmethod
    def ordered_pairs(value: Any) -> int | None:
        """Count adjacent key pairs in sorted order across every object; None when one pair is out of order."""
        count = 0
        stack = [value]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                keys = list(node)
                if any(a > b for a, b in pairwise(keys)):
                    return None
                count += max(len(keys) - 1, 0)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        return count

    @classmethod
    def preserve(cls, original: str, new: str) -> str:
        """Return `new` with sorted keys when `original` had sorted keys and `new` lost that order."""
        try:
            before, after = json.loads(original), json.loads(new)
        except ValueError:
            return new
        if new != json.dumps(after, indent=2, ensure_ascii=False) + "\n":
            return new  # not produced by dump_json: hand-shaped text is left alone
        evidence = cls.ordered_pairs(before)
        if evidence is None or evidence < cls.MIN_EVIDENCE or cls.ordered_pairs(after) is not None:
            return new
        return json.dumps(after, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
