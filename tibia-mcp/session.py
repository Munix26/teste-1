"""Parse Hunt Analyzer sessions and line them up with the wiki data.

Three things about the analyzer's export are easy to get wrong, so they live
here instead of in every analysis script:

1. It is plain text, not JSON, despite looking structured.

2. Item names carry English articles the wiki names do not
   ("2x a small sapphire" -> "Small Sapphire"), and the analyzer lowercases
   everything.

3. The `Session: 02:39h` line is rounded to the minute. The timestamps on the
   `From ... to ...` line are not, and every per-hour figure divides by this
   number, so we always take the duration from the timestamps.

Creature and item stats come from the committed *-data.js artifacts, not from
Postgres. The container recycles often and the database is usually down, but a
session only needs HP, exp and prices — all of which those files already carry.
"""
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Rareness page bounds, as percentages. Same source as loot.py, which keeps
# them as fractions for the gold estimate; here we compare against observed
# drop counts, which read more naturally in percent.
RARITY_PCT = {
    "always": (100.0, 100.0),
    "common": (25.0, 100.0),
    "uncommon": (5.0, 25.0),
    "semi-rare": (1.0, 5.0),
    "rare": (0.5, 1.0),
    "very rare": (0.0, 0.5),
}

TIMESTAMP = r"(\d{4}-\d{2}-\d{2}),\s*(\d{2}:\d{2}:\d{2})"
LINE_RANGE = re.compile(r"From\s+" + TIMESTAMP + r"\s+to\s+" + TIMESTAMP)
ENTRY = re.compile(r"^\s*([\d,]+)x\s+(.+?)\s*$")

# "Raw XP Gain: 1,550,380" -> the field name we expose on Session.
FIELDS = {
    "Raw XP Gain": "raw_xp",
    "XP Gain": "xp",
    "Loot": "loot",
    "Supplies": "supplies",
    "Balance": "balance",
    "Damage": "damage",
    "Healing": "healing",
}


def _load_js(filename, variable):
    """Read one of the `window.X = <json>;` data artifacts."""
    with open(os.path.join(ROOT, filename), encoding="utf-8") as fh:
        text = fh.read()
    body = text.split("=", 1)[1].strip()
    return json.loads(body.rstrip().rstrip(";"))


def creatures():
    """Creature records keyed by lowercased name."""
    return {c["name"].lower(): c for c in _load_js("creatures-data.js", "CREATURES")}


def items():
    """Item records keyed by lowercased name."""
    return {i["n"].lower(): i for i in _load_js("items-data.js", "ITEMDATA")["items"]}


def price_range(value):
    """'8,000 - 20,000' -> (8000, 20000); '158' -> (158, 158); else None.

    The wiki gives NPC value as a *range*, because different NPCs pay
    differently for the same item. Collapsing it to the lower bound — which is
    what the `p` field in creatures-data.js does — understates every gold
    estimate built on top of it.
    """
    if not value or value == "Negotiable":
        return None
    numbers = re.findall(r"\d+", str(value).replace(",", ""))
    if not numbers:
        return None
    return int(numbers[0]), int(numbers[-1])


def amount_range(value):
    """'1-100' -> (1, 100); 1 -> (1, 1).

    Stackable drops make the naive check wrong: 77,257 gold coins over 1,641
    kills is not a 4,708% drop rate, it is a normal chance paying out a stack.
    The comparable quantity is units per kill, which needs this range.
    """
    if isinstance(value, int):
        return value, value
    numbers = re.findall(r"\d+", str(value or "1"))
    if not numbers:
        return 1, 1
    return int(numbers[0]), int(numbers[-1])


def canonical(name, known):
    """Map an analyzer name onto a wiki name, or None if there is no match.

    `known` is any dict keyed by lowercased wiki names.
    """
    key = name.strip().lower()
    for article in ("a ", "an ", "the "):
        if key.startswith(article):
            key = key[len(article):]
            break
    for candidate in (key, f"{key} (item)", key.removesuffix("s")):
        if candidate in known:
            return known[candidate]["name" if "name" in known[candidate] else "n"]
    return None


@dataclass
class Session:
    """One Hunt Analyzer export."""
    start: datetime
    end: datetime
    raw_xp: int = 0
    xp: int = 0
    loot: int = 0
    supplies: int = 0
    balance: int = 0
    damage: int = 0
    healing: int = 0
    kills: dict = field(default_factory=dict)
    looted: dict = field(default_factory=dict)
    source: str = ""

    @property
    def seconds(self):
        return (self.end - self.start).total_seconds()

    @property
    def hours(self):
        return self.seconds / 3600.0

    @property
    def total_kills(self):
        return sum(self.kills.values())

    def per_hour(self, amount):
        return amount / self.hours if self.hours else 0.0

    def minus(self, earlier):
        """This session's totals minus an earlier snapshot of the same session.

        The analyzer reports cumulative totals from a fixed start, so two
        exports taken at different moments subtract into the stretch between
        them. Only valid when both share a start timestamp.
        """
        if earlier.start != self.start:
            raise ValueError("snapshots do not share a start timestamp")
        delta = Session(start=earlier.end, end=self.end,
                        source=f"{earlier.source} -> {self.source}")
        for name in FIELDS.values():
            setattr(delta, name, getattr(self, name) - getattr(earlier, name))
        for source, target in ((self.kills, delta.kills), (self.looted, delta.looted)):
            for key, value in source.items():
                target[key] = value
        for key, value in earlier.kills.items():
            delta.kills[key] = delta.kills.get(key, 0) - value
        for key, value in earlier.looted.items():
            delta.looted[key] = delta.looted.get(key, 0) - value
        delta.kills = {k: v for k, v in delta.kills.items() if v}
        delta.looted = {k: v for k, v in delta.looted.items() if v}
        return delta


def parse(text, source=""):
    """Parse one analyzer export into a Session."""
    stamps = LINE_RANGE.search(text)
    if not stamps:
        raise ValueError("no 'From <date>, <time> to <date>, <time>' line found")
    start = datetime.strptime(f"{stamps.group(1)} {stamps.group(2)}", "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(f"{stamps.group(3)} {stamps.group(4)}", "%Y-%m-%d %H:%M:%S")
    session = Session(start=start, end=end, source=source)

    for label, attribute in FIELDS.items():
        # Anchored to line start so "XP Gain" does not also match "Raw XP Gain".
        match = re.search(rf"^{re.escape(label)}:\s*([\d,]+)", text, re.M)
        if match:
            setattr(session, attribute, int(match.group(1).replace(",", "")))

    bucket = None
    for line in text.splitlines():
        heading = line.strip().rstrip(":").lower()
        if heading == "killed monsters":
            bucket = session.kills
            continue
        if heading == "looted items":
            bucket = session.looted
            continue
        if bucket is None:
            continue
        entry = ENTRY.match(line)
        if entry:
            bucket[entry.group(2)] = bucket.get(entry.group(2), 0) + int(entry.group(1).replace(",", ""))
        elif line.strip() and not line.startswith((" ", "\t")):
            bucket = None
    return session


def load(path):
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read(), source=os.path.basename(path))


def poisson_compatible(observed, low, high, alpha=0.025):
    """Is `observed` consistent with an expected count somewhere in [low, high]?

    Counts of rare drops are Poisson noise around the true rate. With three
    Terra Legs out of a few hundred kills, almost any rate inside the wiki's
    band is plausible, so comparing the point estimate to the band flags
    "misses" that are nothing of the sort. Exact tail probability, no scipy.
    """
    if low <= observed <= high:
        return True
    if observed < low:
        # P(X <= observed | lambda = low)
        term, total = 1.0, 1.0
        for k in range(1, int(observed) + 1):
            term *= low / k
            total += term
        return total * pow(2.718281828459045, -low) > alpha
    # P(X >= observed | lambda = high)
    term, total = 1.0, 1.0
    for k in range(1, int(observed)):
        term *= high / k
        total += term
    return 1.0 - total * pow(2.718281828459045, -high) > alpha
