"""Tile pinboard — bookmark important tiles."""
import time
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class Pin:
    tile_id: str
    category: str = "general"
    note: str = ""
    pinned_by: str = ""
    pinned_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    weight: float = 1.0

class TilePinboard:
    def __init__(self, max_pins: int = 200, default_ttl: float = 0):
        self.max_pins = max_pins
        self.default_ttl = default_ttl
        self._pins: dict[str, Pin] = {}
        self._categories: dict[str, list[str]] = defaultdict(list)

    def pin(self, tile_id: str, category: str = "general", note: str = "",
            pinned_by: str = "", ttl: float = 0) -> Pin:
        now = time.time()
        pin = Pin(tile_id=tile_id, category=category, note=note,
                  pinned_by=pinned_by, expires_at=now + ttl if ttl > 0 else 0)
        if tile_id in self._pins:
            old = self._pins[tile_id]
            self._categories[old.category] = [t for t in self._categories[old.category] if t != tile_id]
        self._pins[tile_id] = pin
        self._categories[category].append(tile_id)
        if len(self._pins) > self.max_pins:
            self._evict_oldest()
        return pin

    def unpin(self, tile_id: str) -> bool:
        pin = self._pins.pop(tile_id, None)
        if pin:
            self._categories[pin.category] = [t for t in self._categories[pin.category] if t != tile_id]
            return True
        return False

    def is_pinned(self, tile_id: str) -> bool:
        pin = self._pins.get(tile_id)
        if not pin:
            return False
        if pin.expires_at > 0 and time.time() > pin.expires_at:
            self.unpin(tile_id)
            return False
        return True

    def get_pin(self, tile_id: str) -> Pin:
        return self._pins.get(tile_id)

    def by_category(self, category: str) -> list[Pin]:
        tile_ids = self._categories.get(category, [])
        return [self._pins[tid] for tid in tile_ids if tid in self._pins and self.is_pinned(tid)]

    def search(self, query: str) -> list[Pin]:
        q = query.lower()
        return [p for p in self._pins.values()
                if self.is_pinned(p.tile_id) and
                (q in p.tile_id.lower() or q in p.note.lower() or q in p.category.lower())]

    def _evict_oldest(self):
        valid = [(tid, p) for tid, p in self._pins.items() if self.is_pinned(tid)]
        if valid:
            valid.sort(key=lambda x: x[1].pinned_at)
            self.unpin(valid[0][0])

    def purge_expired(self) -> int:
        expired = [tid for tid, p in self._pins.items() if p.expires_at > 0 and time.time() > p.expires_at]
        for tid in expired:
            self.unpin(tid)
        return len(expired)

    @property
    def stats(self) -> dict:
        cats = {k: len(v) for k, v in self._categories.items() if v}
        return {"total_pins": len(self._pins), "categories": cats, "max_pins": self.max_pins}
