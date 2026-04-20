"""Tile pinboard — pin tiles with categories, expiry, priorities, search, and limits."""
import time
import re
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
from enum import Enum

class PinPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

@dataclass
class Pin:
    id: str
    tile_id: str
    content: str
    category: str = "general"
    priority: PinPriority = PinPriority.NORMAL
    pinned_by: str = ""
    expires_at: float = 0.0  # 0 = never expires
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    pin_count: int = 1  # how many times re-pinned

class TilePinboard:
    def __init__(self, max_pins: int = 1000, max_per_category: int = 100):
        self.max_pins = max_pins
        self.max_per_category = max_per_category
        self._pins: dict[str, Pin] = {}
        self._by_category: dict[str, list[str]] = defaultdict(list)
        self._pin_log: list[dict] = []

    def pin(self, tile_id: str, content: str, category: str = "general",
            priority: PinPriority = PinPriority.NORMAL, pinned_by: str = "",
            expires_at: float = 0.0, tags: list[str] = None) -> Pin:
        pin_id = f"pin-{tile_id}-{int(time.time())}"
        # Check if already pinned — bump pin_count
        existing = self._find_by_tile(tile_id)
        if existing:
            existing.pin_count += 1
            existing.priority = max(existing.priority, priority)
            existing.expires_at = max(existing.expires_at, expires_at)
            self._log("repin", existing.id)
            return existing
        if len(self._pins) >= self.max_pins:
            self._evict()
        cat_pins = self._by_category.get(category, [])
        if len(cat_pins) >= self.max_per_category:
            self._evict_category(category)
        pin = Pin(id=pin_id, tile_id=tile_id, content=content, category=category,
                 priority=priority, pinned_by=pinned_by, expires_at=expires_at,
                 tags=tags or [])
        self._pins[pin_id] = pin
        self._by_category[category].append(pin_id)
        self._log("pin", pin_id)
        return pin

    def unpin(self, pin_id: str) -> bool:
        pin = self._pins.pop(pin_id, None)
        if not pin:
            return False
        cat_list = self._by_category.get(pin.category, [])
        if pin_id in cat_list:
            cat_list.remove(pin_id)
        self._log("unpin", pin_id)
        return True

    def unpin_by_tile(self, tile_id: str) -> int:
        to_remove = [pid for pid, p in self._pins.items() if p.tile_id == tile_id]
        for pid in to_remove:
            self.unpin(pid)
        return len(to_remove)

    def get(self, pin_id: str) -> Optional[Pin]:
        return self._pins.get(pin_id)

    def get_by_tile(self, tile_id: str) -> Optional[Pin]:
        return self._find_by_tile(tile_id)

    def by_category(self, category: str) -> list[Pin]:
        pin_ids = self._by_category.get(category, [])
        return [self._pins[pid] for pid in pin_ids if pid in self._pins]

    def by_priority(self, priority: PinPriority = None) -> list[Pin]:
        pins = list(self._pins.values())
        if priority:
            pins = [p for p in pins if p.priority == priority]
        pins.sort(key=lambda p: (p.priority.value, -p.pin_count, -p.created_at), reverse=True)
        return pins

    def search(self, query: str, category: str = "") -> list[Pin]:
        query_lower = query.lower()
        results = []
        for pin in self._pins.values():
            if category and pin.category != category:
                continue
            if (query_lower in pin.content.lower() or
                query_lower in pin.tile_id.lower() or
                any(query_lower in t.lower() for t in pin.tags)):
                results.append(pin)
        results.sort(key=lambda p: p.pin_count, reverse=True)
        return results

    def tags(self) -> dict[str, int]:
        counts = defaultdict(int)
        for pin in self._pins.values():
            for tag in pin.tags:
                counts[tag] += 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def categories(self) -> dict[str, int]:
        return {cat: len(ids) for cat, ids in self._by_category.items()}

    def purge_expired(self) -> int:
        now = time.time()
        expired = [pid for pid, p in self._pins.items()
                   if p.expires_at > 0 and p.expires_at < now]
        for pid in expired:
            self.unpin(pid)
        return len(expired)

    def top_pins(self, n: int = 10) -> list[Pin]:
        pins = sorted(self._pins.values(), key=lambda p: p.pin_count, reverse=True)
        return pins[:n]

    def recent_pins(self, n: int = 10) -> list[Pin]:
        pins = sorted(self._pins.values(), key=lambda p: p.created_at, reverse=True)
        return pins[:n]

    def _find_by_tile(self, tile_id: str) -> Optional[Pin]:
        for pin in self._pins.values():
            if pin.tile_id == tile_id:
                return pin
        return None

    def _evict(self):
        """Evict lowest priority, oldest pin."""
        if not self._pins:
            return
        victim = min(self._pins.values(),
                     key=lambda p: (p.priority.value, -p.pin_count, p.created_at))
        self.unpin(victim.id)

    def _evict_category(self, category: str):
        cat_pins = self._by_category.get(category, [])
        if not cat_pins:
            return
        oldest = min(cat_pins, key=lambda pid: self._pins[pid].created_at if pid in self._pins else 0)
        self.unpin(oldest)

    def _log(self, action: str, pin_id: str):
        self._pin_log.append({"action": action, "pin_id": pin_id, "timestamp": time.time()})
        if len(self._pin_log) > 1000:
            self._pin_log = self._pin_log[-1000:]

    @property
    def stats(self) -> dict:
        return {"pins": len(self._pins), "categories": len(self._by_category),
                "max_pins": self.max_pins, "utilization": len(self._pins) / self.max_pins,
                "tags": len(self.tags()), "log_entries": len(self._pin_log)}
