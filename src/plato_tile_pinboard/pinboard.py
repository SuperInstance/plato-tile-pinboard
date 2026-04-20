"""Tile pinboard — bookmark pins, boards, categories, and collaborative curation."""
import time
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

@dataclass
class Pin:
    tile_id: str
    pinned_by: str
    board: str = "default"
    note: str = ""
    tags: list[str] = field(default_factory=list)
    pinned_at: float = field(default_factory=time.time)
    weight: float = 1.0  # for sorting within board

@dataclass
class Board:
    name: str
    owner: str = ""
    description: str = ""
    is_public: bool = True
    created_at: float = field(default_factory=time.time)
    max_pins: int = 1000

class TilePinboard:
    def __init__(self):
        self._pins: dict[str, list[Pin]] = defaultdict(list)  # board -> pins
        self._boards: dict[str, Board] = {}
        self._tile_pins: dict[str, list[Pin]] = defaultdict(list)  # tile_id -> pins
        self._stats = {"total_pins": 0, "total_boards": 0}

    def create_board(self, name: str, owner: str = "", description: str = "",
                     is_public: bool = True, max_pins: int = 1000) -> Board:
        board = Board(name=name, owner=owner, description=description,
                     is_public=is_public, max_pins=max_pins)
        self._boards[name] = board
        self._stats["total_boards"] = len(self._boards)
        return board

    def pin(self, tile_id: str, pinned_by: str, board: str = "default",
            note: str = "", tags: list[str] = None, weight: float = 1.0) -> Pin:
        board_obj = self._boards.get(board)
        if not board_obj:
            board_obj = self.create_board(board)
        if len(self._pins[board]) >= board_obj.max_pins:
            raise ValueError(f"Board '{board}' is full ({board_obj.max_pins} pins)")
        pin = Pin(tile_id=tile_id, pinned_by=pinned_by, board=board,
                 note=note, tags=tags or [], weight=weight)
        self._pins[board].append(pin)
        self._tile_pins[tile_id].append(pin)
        self._stats["total_pins"] += 1
        return pin

    def unpin(self, tile_id: str, board: str = "", pinned_by: str = "") -> int:
        removed = 0
        boards = {board} if board else set(self._pins.keys())
        for b in boards:
            before = len(self._pins[b])
            self._pins[b] = [p for p in self._pins[b] if not (
                p.tile_id == tile_id and (not pinned_by or p.pinned_by == pinned_by))]
            removed += before - len(self._pins[b])
        if removed:
            self._tile_pins[tile_id] = [p for p in self._tile_pins.get(tile_id, [])
                                        if not (not board or p.board == board)]
        self._stats["total_pins"] = max(0, self._stats["total_pins"] - removed)
        return removed

    def get_board(self, name: str, sort_by: str = "weight", limit: int = 50) -> list[Pin]:
        pins = list(self._pins.get(name, []))
        if sort_by == "weight":
            pins.sort(key=lambda p: p.weight, reverse=True)
        elif sort_by == "recent":
            pins.sort(key=lambda p: p.pinned_at, reverse=True)
        elif sort_by == "note":
            pins.sort(key=lambda p: p.note)
        return pins[:limit]

    def boards_for_tile(self, tile_id: str) -> list[str]:
        return list(set(p.board for p in self._tile_pins.get(tile_id, [])))

    def search_pins(self, query: str, board: str = "") -> list[Pin]:
        q = query.lower()
        boards = {board} if board else set(self._pins.keys())
        results = []
        for b in boards:
            for p in self._pins[b]:
                if q in p.note.lower() or q in " ".join(p.tags).lower():
                    results.append(p)
        results.sort(key=lambda p: p.weight, reverse=True)
        return results[:50]

    def pins_by_agent(self, agent: str) -> list[Pin]:
        results = []
        for pins in self._pins.values():
            results.extend(p for p in pins if p.pinned_by == agent)
        results.sort(key=lambda p: p.pinned_at, reverse=True)
        return results

    def merge_boards(self, source: str, target: str) -> int:
        moved = 0
        for pin in self._pins.get(source, []):
            pin.board = target
            self._pins[target].append(pin)
            moved += 1
        self._pins.pop(source, None)
        self._boards.pop(source, None)
        return moved

    def board_stats(self, name: str) -> dict:
        pins = self._pins.get(name, [])
        agents = set(p.pinned_by for p in pins)
        tags = set()
        for p in pins:
            tags.update(p.tags)
        return {"board": name, "pins": len(pins), "unique_agents": len(agents),
                "tags": list(tags), "avg_weight": round(sum(p.weight for p in pins) / max(len(pins), 1), 2)}

    @property
    def stats(self) -> dict:
        return {**self._stats, "boards": len(self._boards),
                "tiles_pinned": len(self._tile_pins)}
