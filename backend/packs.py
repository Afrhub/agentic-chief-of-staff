"""Vertical packs — the config layer that retargets the engine across industries.

A pack (packs/<id>.yaml) declares an industry's signal vocabulary, the
chief-of-staff persona used to frame alerts, and which sources feed it. The
coordinator and signal collectors read the active pack; nothing about the engine
is industry-specific. Add an industry by dropping in a YAML file.
"""
import glob
import logging
import os

import yaml

logger = logging.getLogger(__name__)

_PACK_DIR = os.path.join(os.path.dirname(__file__), "packs")
DEFAULT_PACK_ID = os.getenv("DCERN_DEFAULT_PACK", "saas")

_cache: dict = {}
_loaded = False


def _load() -> dict:
    global _loaded
    if _loaded:
        return _cache
    for path in sorted(glob.glob(os.path.join(_PACK_DIR, "*.yaml"))):
        try:
            with open(path) as f:
                pack = yaml.safe_load(f)
            if pack and pack.get("id"):
                _cache[pack["id"]] = pack
        except Exception as e:  # one bad pack must not break the others
            logger.error(f"failed to load pack {path}: {e}")
    _loaded = True
    logger.info(f"loaded {len(_cache)} vertical pack(s): {list(_cache)}")
    return _cache


def list_packs() -> list:
    """[{id, name}] for the onboarding picker."""
    return [{"id": p["id"], "name": p.get("name", p["id"])} for p in _load().values()]


def get_pack(pack_id=None) -> dict:
    """Return the pack by id, falling back to the default. Never raises."""
    packs = _load()
    return packs.get(pack_id) or packs.get(DEFAULT_PACK_ID) or {}


if __name__ == "__main__":
    # ponytail self-check: both shipped packs load and the default resolves.
    ids = {p["id"] for p in list_packs()}
    assert {"saas", "ecommerce"} <= ids, ids
    assert get_pack("ecommerce")["persona"]
    assert get_pack("nonexistent")["id"] == DEFAULT_PACK_ID  # fallback
    assert get_pack(None).get("id") == DEFAULT_PACK_ID
    print("packs self-check ok:", sorted(ids))
