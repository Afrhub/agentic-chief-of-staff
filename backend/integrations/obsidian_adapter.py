"""Digital Brain — read a founder's Obsidian vault (a folder of markdown notes)
and surface the most relevant ones as context for the chief of staff.

Why keyword ranking, not embeddings: the vault is the founder's own notes, read
locally (perfect for the self-hosted deploy — data never leaves their box). A
plain keyword overlap is dependency-free, needs no API key, and is fully
testable. ponytail: upgrade to semantic recall (embed into SemanticMemory) only
if keyword recall proves too coarse and an embeddings provider is configured.
"""
import glob
import os
import re

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_WIKILINK = re.compile(r"\[\[([^\]|#]+)")          # [[Note]] / [[Note|alias]] / [[Note#h]]
_TAG = re.compile(r"(?:^|\s)#([A-Za-z0-9_/-]+)")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "is", "it", "for", "on",
         "with", "this", "that", "we", "i", "my", "our", "be", "are", "as", "at"}


def read_vault(vault_path: str, max_notes: int = 1000, max_bytes: int = 200_000) -> list:
    """Walk a vault folder → list of {title, path, text, tags, links}."""
    notes = []
    for path in sorted(glob.glob(os.path.join(vault_path, "**", "*.md"), recursive=True)):
        try:
            if os.path.getsize(path) > max_bytes:
                continue
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        body, tags = raw, []
        m = _FRONTMATTER.match(raw)
        if m:
            body = raw[m.end():]
            for line in m.group(1).splitlines():
                if line.lower().startswith("tags:"):
                    tags += re.findall(r"[A-Za-z0-9_/-]+", line.split(":", 1)[1])
        tags += _TAG.findall(body)

        notes.append({
            "title": os.path.splitext(os.path.basename(path))[0],
            "path": path,
            "text": body.strip(),
            "tags": sorted({t.lower() for t in tags}),
            "links": _WIKILINK.findall(body),
        })
        if len(notes) >= max_notes:
            break
    return notes


def _tokens(s: str) -> set:
    return {w for w in _WORD.findall((s or "").lower()) if len(w) > 2 and w not in _STOP}


def rank_notes(notes: list, query: str, k: int = 3) -> list:
    """Top-k notes by keyword overlap with the query (title + tags weighted)."""
    q = _tokens(query)
    if not q:
        return notes[:k]
    scored = []
    for n in notes:
        score = (
            len(q & _tokens(n["text"]))
            + 2 * len(q & _tokens(n["title"]))
            + 2 * len(q & set(n["tags"]))
        )
        if score:
            scored.append((score, n))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:k]]


if __name__ == "__main__":
    # ponytail self-check: parse a temp vault + rank by relevance.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "pricing.md"), "w") as f:
            f.write("---\ntags: pricing, strategy\n---\nWe raised prices 20%; [[churn]] risk flagged.\n")
        with open(os.path.join(d, "team.md"), "w") as f:
            f.write("# Team\nHiring a VP Sales next quarter. #hiring\n")
        ns = read_vault(d)
        assert len(ns) == 2, ns
        p = next(n for n in ns if n["title"] == "pricing")
        assert "pricing" in p["tags"] and "churn" in p["links"], p
        assert rank_notes(ns, "should we change our pricing?", k=1)[0]["title"] == "pricing"
        assert rank_notes(ns, "hiring a sales leader", k=1)[0]["title"] == "team"
        assert rank_notes(ns, "", k=2) == ns[:2]  # empty query → first k
    print("obsidian_adapter self-check ok")
