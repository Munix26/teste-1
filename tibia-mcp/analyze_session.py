"""Report on Hunt Analyzer sessions, checked against the wiki data.

    python3 tibia-mcp/analyze_session.py sessions/*.txt

Exports that share a start timestamp are cumulative snapshots of one hunt, so
they are also reported as the stretches between them. That split is the point:
totals hide when the hunt got faster, when a bonus expired, and when supply
cost started outrunning loot.

Everything printed here is either measured or derived from the committed wiki
data — no assumed skill, no assumed drop chance.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session import (RARITY_PCT, amount_range, canonical, creatures, items, load,
                     poisson_compatible, price_range)


def money(value):
    return f"{round(value):,}"


def kill_stats(session, by_name):
    """Expected exp and HP for the kills in a session, from the creature data."""
    exp = hp = 0
    unknown = []
    for name, count in session.kills.items():
        record = by_name.get(canonical(name, by_name).lower() if canonical(name, by_name) else "")
        if not record:
            unknown.append(name)
            continue
        exp += (record["exp"] or 0) * count
        hp += (record["hp"] or 0) * count
    return exp, hp, unknown


def report_columns(sessions, by_name):
    """The per-stretch metric table."""
    rows = [
        ("duracao (min)", lambda s, e, h: f"{s.seconds / 60:.0f}"),
        ("kills", lambda s, e, h: f"{s.total_kills:,}"),
        ("kills/h", lambda s, e, h: money(s.per_hour(s.total_kills))),
        ("raw xp/h", lambda s, e, h: money(s.per_hour(s.raw_xp))),
        ("erro vs banco %", lambda s, e, h: f"{(s.raw_xp / e - 1) * 100:+.2f}" if e else "-"),
        ("overkill %", lambda s, e, h: f"{(s.damage / h - 1) * 100:+.1f}" if h else "-"),
        ("multiplicador xp", lambda s, e, h: f"{s.xp / s.raw_xp:.4f}" if s.raw_xp else "-"),
        ("loot/kill", lambda s, e, h: money(s.loot / s.total_kills) if s.total_kills else "-"),
        ("supply/kill", lambda s, e, h: money(s.supplies / s.total_kills) if s.total_kills else "-"),
        ("lucro/kill", lambda s, e, h: money(s.balance / s.total_kills) if s.total_kills else "-"),
        ("balance/h", lambda s, e, h: money(s.per_hour(s.balance))),
        ("dano/h", lambda s, e, h: money(s.per_hour(s.damage))),
        ("cura/dano %", lambda s, e, h: f"{s.healing / s.damage * 100:.1f}" if s.damage else "-"),
        ("cura hp/s", lambda s, e, h: money(s.healing / s.seconds) if s.seconds else "-"),
    ]
    stats = [kill_stats(s, by_name) for s in sessions]
    headers = [s.source for s in sessions]
    width = max(14, max(len(h) for h in headers) + 2)

    print("".ljust(22) + "".join(h.rjust(width) for h in headers))
    for label, fn in rows:
        cells = [fn(s, stats[i][0], stats[i][1]) for i, s in enumerate(sessions)]
        print(label.ljust(22) + "".join(c.rjust(width) for c in cells))

    unknown = {name for _, _, names in stats for name in names}
    if unknown:
        print(f"\n  criaturas fora do banco: {', '.join(sorted(unknown))}")


def report_drops(session, by_name, by_item):
    """Observed drop yield against the wiki's rarity bands.

    Compared as units per kill rather than as a drop rate, because the wiki
    documents a chance *and* a stack size and only their product is observable
    from a session: a looted-items list cannot tell one stack of 80 gold from
    eighty separate drops. For items that never stack the two are the same
    number, so those still read as a percentage.
    """
    sources = defaultdict(list)
    for name, count in session.kills.items():
        wiki = canonical(name, by_name)
        if not wiki:
            continue
        for entry in by_name[wiki.lower()]["loot"]:
            sources[entry["n"]].append((count, entry["r"], amount_range(entry.get("a"))))

    print("\nRENDIMENTO DE DROP OBSERVADO")
    print("  " + "item".ljust(30) + "obs".rjust(8) + "kills".rjust(8)
          + "por kill".rjust(11) + "faixa wiki".rjust(18) + "  veredito")
    inside = noise = diverge = 0
    for name, count in sorted(session.looted.items()):
        wiki = canonical(name, by_item)
        drops = sources.get(wiki or "", [])
        if not drops:
            continue
        kills = sum(k for k, _, _ in drops)
        low = min(RARITY_PCT.get(r, RARITY_PCT["common"])[0] / 100 * a[0] for _, r, a in drops)
        high = max(RARITY_PCT.get(r, RARITY_PCT["common"])[1] / 100 * a[1] for _, r, a in drops)
        stacks = max(a[1] for _, _, a in drops) > 1
        yielded = count / kills

        if low <= yielded <= high:
            verdict, inside = "dentro da faixa", inside + 1
        elif stacks:
            # Stack sizes are not Poisson, so there is no honest noise test.
            verdict, diverge = "FORA DA FAIXA", diverge + 1
        elif poisson_compatible(count, kills * low, kills * high):
            verdict, noise = "ruido de Poisson", noise + 1
        else:
            verdict, diverge = "DIVERGENCIA REAL", diverge + 1

        if stacks:
            shown, band = f"{yielded:.2f}", f"{low:.2f}-{high:.2f}"
        else:
            shown, band = f"{yielded * 100:.2f}%", f"{low * 100:g}-{high * 100:g}%"
        print("  " + wiki.ljust(30) + f"{count:,}".rjust(8) + f"{kills:,}".rjust(8)
              + shown.rjust(11) + band.rjust(18) + "  " + verdict)
    print(f"\n  {inside} dentro da faixa | {noise} explicados por ruido | {diverge} divergentes")


def report_loot_value(session, by_item):
    """Reported loot against the NPC price range the wiki documents.

    Reported as a range because the wiki's own prices are ranges. Items with no
    NPC price at all are excluded and listed, so the bounds read as what they
    are: a partial valuation, not a total.
    """
    low = high = 0
    unpriced = []
    for name, count in session.looted.items():
        wiki = canonical(name, by_item)
        bounds = price_range(by_item[wiki.lower()]["v"]) if wiki else None
        if not bounds:
            unpriced.append(f"{name} x{count:,}")
            continue
        low += bounds[0] * count
        high += bounds[1] * count

    print("\nVALOR DO LOOT vs PRECO NPC DO WIKI")
    print(f"  faixa prevista : {money(low)} - {money(high)}")
    print(f"  loot reportado : {money(session.loot)}")
    if high > low:
        position = (session.loot - low) / (high - low) * 100
        print(f"  posicao        : {position:.0f}% entre o minimo e o maximo")
    if unpriced:
        print(f"  sem preco NPC  : {', '.join(sorted(unpriced))}")


def main(paths):
    by_name, by_item = creatures(), items()
    sessions = sorted((load(p) for p in paths), key=lambda s: (s.start, s.end))

    groups = defaultdict(list)
    for s in sessions:
        groups[s.start].append(s)

    for start, snapshots in sorted(groups.items()):
        print("=" * 78)
        print(f"HUNT DE {start:%Y-%m-%d %H:%M:%S}  ({len(snapshots)} export"
              f"{'s' if len(snapshots) > 1 else ''})")
        print("=" * 78)

        columns = list(snapshots)
        if len(snapshots) > 1:
            # Snapshots are cumulative; the stretches between them are what
            # actually shows change over the hunt.
            columns = [snapshots[0]]
            for earlier, later in zip(snapshots, snapshots[1:]):
                columns.append(later.minus(earlier))
            for index, column in enumerate(columns, 1):
                column.source = f"trecho {index}"
            total = snapshots[-1]
            total.source = "TOTAL"
            columns.append(total)

        report_columns(columns, by_name)
        report_drops(snapshots[-1], by_name, by_item)
        report_loot_value(snapshots[-1], by_item)
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
