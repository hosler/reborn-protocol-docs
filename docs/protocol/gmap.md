# GMAP Coordinate System

A **GMAP** (`.gmap` file) stitches a grid of individual 64×64 levels into one seamless
overworld. Understanding the coordinate frames is essential — getting them wrong renders the
player standing in one segment while the camera shows another.

## The Three Frames

| Frame | Range | Meaning |
|-------|-------|---------|
| **Local** | 0-63 tiles | Position within the current 64×64 segment |
| **World** | unbounded | Position across the whole gmap |
| **Segment (grid)** | grid coords | Which segment of the gmap grid you're in |

Conversions (tiles):

```
world  = local + grid * 64
grid   = floor(world / 64)
local  = world % 64
```

> Use `math.floor()` for the division — negative world coords (possible at gmap edges)
> round toward negative infinity, and integer truncation gives the wrong segment.

## How the Current Segment Is Identified

- Player props **GMAPLEVELX (43)** and **GMAPLEVELY (44)** carry the segment column/row
  (1 byte each).
- `PLO_PLAYERWARP2 (49)` also carries `gmap_x`/`gmap_y` (= `mapPosition.x()/y()`), plus the
  trailing gmap name.
- The `.gmap` file itself defines the grid layout (which `.nw` level sits at each cell).

## High-Precision Pixel Coords (X2/Y2/Z2)

Sub-tile positions and gmap movement use player props **X2 (78) / Y2 (79) / Z2 (80)** (and
the NPC equivalents **75/76/77**). The wire-format packing is documented in
[Data Types](data-types.md#x2y2-encoding-the-weird-one).

## The gs2emu LOCAL-Coordinate Quirk

⚠️ **The single biggest GMAP gotcha.** Even when a player is on a gmap, GServer-v2 sends
**LOCAL per-segment coordinates** in `PLO_PLAYERPROPS` X/Y (and X2/Y2) rather than world
coordinates. The reconstruction formula and the coordinate frames are documented in
[Data Types](data-types.md#coordinate-frames-in-gmaps).

## "A GMAP Is Loaded" ≠ "I'm In A Segment Right Now"

Track these two states separately:

- **gmap loaded** — a `.gmap` is parsed and its grid is known. Stays true while you're in
  any interior level reached *from* the gmap.
- **in a grid segment right now** — the current level name is actually one of the grid's
  segment `.nw` files.

Interior levels (houses, caves, dungeons, PK arenas) are reached *from* a gmap but are **not
grid segments**. Per-frame decisions — coordinate frame, edge clamping, edge-link filtering —
must key off "in a grid segment right now," not merely "a gmap is loaded." pyReborn exposes
this as `Client.in_gmap_segment` (`gmap_width > 0 and current_level in gmap_grid.values()`).

## Edge Links vs Interior Links

On a gmap, links that sit against a level border are **edge links** between adjacent
segments; the gmap system handles those transitions seamlessly, so clients typically ignore
them. Links to non-segment levels (interiors) are honored as real warps. See
[Level Link Implementation](level-link-implementation.md) for the edge-link heuristic.

## Collision at Segment Boundaries

When in a grid segment, clamp movement to the **full gmap perimeter**
(`gmap_width*64 × gmap_height*64`) so the player can cross internal segment seams but still
blocks at the outer rim. Interior/non-gmap levels clamp to the normal 0-63 bounds.
