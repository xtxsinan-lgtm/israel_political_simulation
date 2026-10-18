from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, TypeVar

T = TypeVar("T")

MASK32 = 0xFFFFFFFF

CONTRACT_STREAMS: List[str] = [
    "events",
    "world",
    "elections",
    "combat",
    "random_events",
    "core",
    "politics",
    "ai",
    "economy",
    "cosmetic",
]

EXTRA_MODULE_STREAMS: List[str] = [
    "parliament",
    "party",
    "characters",
    "palestine",
    "military",
    "authoritarian",
]

ALL_DEFAULT_STREAMS: List[str] = CONTRACT_STREAMS + [
    s for s in EXTRA_MODULE_STREAMS if s not in CONTRACT_STREAMS
]


def mul32(a: int, b: int) -> int:
    """Portable 32-bit unsigned multiplication modulo 2^32."""
    return ((a & MASK32) * (b & MASK32)) & MASK32


def rotl32(x: int, k: int) -> int:
    """Portable 32-bit left rotation."""
    x &= MASK32
    return (((x << k) & MASK32) | (x >> (32 - k))) & MASK32


def fnv1a32(name: str) -> int:
    """FNV-1a 32-bit hash of an ASCII string."""
    h = 0x811C9DC5
    for b in name.encode("ascii"):
        h ^= b
        h = mul32(h, 0x01000193)
    return h


def fmix32(h: int) -> int:
    """MurmurHash3 32-bit finalizer."""
    h &= MASK32
    h ^= h >> 16
    h = mul32(h, 0x85EBCA6B)
    h ^= h >> 13
    h = mul32(h, 0xC2B2AE35)
    h ^= h >> 16
    return h & MASK32


class RngStream:
    """Deterministic xoshiro128** PRNG stream (M01 §4.4.2)."""

    __slots__ = ("name", "s0", "s1", "s2", "s3", "calls")

    def __init__(self, master_seed: int = 19770620, name: str = "core") -> None:
        self.name: str = name
        base = ((master_seed & MASK32) ^ fnv1a32(name)) & MASK32
        self.s0: int = fmix32((base + 0x9E3779B9) & MASK32)
        self.s1: int = fmix32((base + 0x3C6EF372) & MASK32)
        self.s2: int = fmix32((base + 0xDAA66D2B) & MASK32)
        self.s3: int = fmix32((base + 0x78DDE6E4) & MASK32)
        if (self.s0 | self.s1 | self.s2 | self.s3) == 0:
            self.s0 = 1
        self.calls: int = 0

    def next_u32(self) -> int:
        """Advance xoshiro128** state by 1 step and return uint32 in [0, 2^32 - 1]."""
        result = mul32(rotl32(mul32(self.s1, 5), 7), 9)
        t = (self.s1 << 9) & MASK32
        self.s2 ^= self.s0
        self.s3 ^= self.s1
        self.s1 ^= self.s2
        self.s0 ^= self.s3
        self.s2 ^= t
        self.s3 = rotl32(self.s3, 11)
        self.calls += 1
        return result

    def next_float(self) -> float:
        """Return IEEE-754 double in [0.0, 1.0)."""
        return self.next_u32() / 4294967296.0

    def random(self) -> float:
        """Alias for next_float()."""
        return self.next_float()

    def chance(self, p: float) -> bool:
        """Bernoulli trial with probability p."""
        if p <= 0.0:
            return False
        if p >= 1.0:
            return True
        return self.next_float() < p

    def range_int(self, lo: int, hi: int) -> int:
        """Return uniform integer in [lo, hi] inclusive."""
        if hi <= lo:
            return lo
        return lo + int(math.floor(self.next_float() * (hi - lo + 1)))

    def randint(self, lo: int, hi: int) -> int:
        """Alias for range_int(lo, hi) inclusive."""
        return self.range_int(lo, hi)

    def uniform(self, a: float, b: float) -> float:
        """Return uniform float in [a, b)."""
        return a + (b - a) * self.next_float()

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        """Deterministic Box-Muller normal variate."""
        u1 = max(1e-12, self.next_float())
        u2 = self.next_float()
        z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return mu + sigma * z0

    def choice(self, seq: Sequence[T]) -> T:
        """Pick one item uniformly from a non-empty sequence."""
        if not seq:
            raise ValueError("Cannot choose from an empty sequence")
        idx = self.range_int(0, len(seq) - 1)
        return seq[idx]

    def weighted_pick(self, items: Sequence[T], weights: Sequence[float]) -> Optional[T]:
        """Weighted random selection without floating-point order ambiguity."""
        if not items or len(items) != len(weights):
            return None
        clean_weights = [max(0.0, float(w)) for w in weights]
        total_w = sum(clean_weights)
        if total_w <= 0.0:
            return None
        threshold = self.next_float() * total_w
        acc = 0.0
        last_valid: Optional[T] = None
        for item, w in zip(items, clean_weights):
            if w > 0.0:
                last_valid = item
                acc += w
                if threshold < acc:
                    return item
        return last_valid

    def shuffle(self, items: List[T]) -> List[T]:
        """Deterministic Fisher-Yates shuffle in-place."""
        n = len(items)
        for i in range(n - 1, 0, -1):
            j = self.range_int(0, i)
            items[i], items[j] = items[j], items[i]
        return items

    def clone(self) -> RngStream:
        """Return an independent copy of this stream."""
        cp = RngStream.__new__(RngStream)
        cp.name = self.name
        cp.s0 = self.s0
        cp.s1 = self.s1
        cp.s2 = self.s2
        cp.s3 = self.s3
        cp.calls = self.calls
        return cp

    def to_dict(self) -> Dict[str, int]:
        return {
            "s0": int(self.s0),
            "s1": int(self.s1),
            "s2": int(self.s2),
            "s3": int(self.s3),
            "calls": int(self.calls),
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any], master_seed: int = 19770620) -> RngStream:
        st = cls(master_seed=master_seed, name=name)
        st.s0 = int(data.get("s0", st.s0)) & MASK32
        st.s1 = int(data.get("s1", st.s1)) & MASK32
        st.s2 = int(data.get("s2", st.s2)) & MASK32
        st.s3 = int(data.get("s3", st.s3)) & MASK32
        if (st.s0 | st.s1 | st.s2 | st.s3) == 0:
            st.s0 = 1
        st.calls = int(data.get("calls", 0))
        return st


class DeterministicRNG:
    """Container of named independent deterministic PRNG substreams."""

    def __init__(self, master_seed: int = 19770620) -> None:
        self.master_seed: int = int(master_seed) & MASK32
        self.streams: Dict[str, RngStream] = {}
        for name in ALL_DEFAULT_STREAMS:
            self.streams[name] = RngStream(self.master_seed, name)

    def stream(self, name: str) -> RngStream:
        """Return the named substream, creating it deterministically if not yet present."""
        st = self.streams.get(name)
        if st is None:
            st = RngStream(self.master_seed, name)
            self.streams[name] = st
        return st

    def __getitem__(self, name: str) -> RngStream:
        return self.stream(name)

    def __getattr__(self, name: str) -> RngStream:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.stream(name)

    def clone(self) -> DeterministicRNG:
        cp = DeterministicRNG.__new__(DeterministicRNG)
        cp.master_seed = self.master_seed
        cp.streams = {k: v.clone() for k, v in self.streams.items()}
        return cp

    def to_dict(self) -> Dict[str, Any]:
        # Only serialize canonical contract streams + any stream with calls > 0 for clean saves
        out_streams: Dict[str, Dict[str, int]] = {}
        for k in sorted(self.streams.keys()):
            if k == "cosmetic":
                continue
            if k in CONTRACT_STREAMS or self.streams[k].calls > 0:
                out_streams[k] = self.streams[k].to_dict()
        return {
            "master_seed": self.master_seed,
            "streams": out_streams,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], default_seed: int = 19770620) -> DeterministicRNG:
        if "master_seed" in data:
            seed = int(data["master_seed"]) & MASK32
            raw_streams = data.get("streams", {})
        else:
            seed = int(default_seed) & MASK32
            raw_streams = data
        rng = cls(master_seed=seed)
        if isinstance(raw_streams, dict):
            for k, v in raw_streams.items():
                if isinstance(v, dict) and "s0" in v:
                    rng.streams[k] = RngStream.from_dict(k, v, master_seed=seed)
        return rng


RNG = DeterministicRNG
RNGStream = RngStream
