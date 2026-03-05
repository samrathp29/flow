#!/usr/bin/env python3
"""
Patch mem0ai's Qdrant vector store to fix the NONE-event PointStruct crash.

Bug: When mem0 processes a memory with event=NONE, it calls:
    self.vector_store.update(vector_id=..., vector=None, payload=...)

But Qdrant's PointStruct requires a real vector—passing None triggers a
pydantic ValidationError. The fix: use set_payload when vector is None.

Run this after `pip install mem0ai` if the bug reappears:
    python scripts/patch_mem0.py
"""
import sys
from pathlib import Path

BROKEN = """\
        point = PointStruct(id=vector_id, vector=vector, payload=payload)
        self.client.upsert(collection_name=self.collection_name, points=[point])"""

PATCHED = """\
        if vector is None:
            # Only update the payload — avoids PointStruct requiring a real vector.
            if payload is not None:
                self.client.set_payload(
                    collection_name=self.collection_name,
                    payload=payload,
                    points=[vector_id],
                )
        else:
            point = PointStruct(id=vector_id, vector=vector, payload=payload or {})
            self.client.upsert(collection_name=self.collection_name, points=[point])"""


def find_qdrant_file() -> Path | None:
    try:
        import mem0  # noqa: F401
    except ImportError:
        print("mem0 not installed", file=sys.stderr)
        return None
    import mem0.vector_stores.qdrant as q
    return Path(q.__file__)


def patch():
    path = find_qdrant_file()
    if path is None:
        sys.exit(1)

    text = path.read_text()

    if PATCHED in text:
        print("✓ Already patched — nothing to do.")
        return

    if BROKEN not in text:
        print("⚠ Could not find target code — mem0 may have been updated. Please inspect manually:")
        print(f"  {path}")
        sys.exit(1)

    patched = text.replace(BROKEN, PATCHED)
    path.write_text(patched)
    print(f"✓ Patched {path}")


if __name__ == "__main__":
    patch()
