# GMAP Coordinate System

A **GMAP** (`.gmap` file) joins a grid of individual 64×64 levels into one
overworld. Coordinate-frame confusion can cause serious errors:
a level warp and an entity property can describe the same position in different
frames.

The shared `reborn_protocol.coords` module defines these terms and conversions. A segment
is always `LEVEL_SIZE = 64` tiles on each axis. Its
board contains `LEVEL_TILE_COUNT = 4096` tiles.

## Coordinate Frames

| Frame | Units and range | Meaning |
|-------|-----------------|---------|
| **Local** | tiles, `0 <= x,y < 64` | Position inside one 64×64 segment |
| **Segment (grid)** | integer `(grid_x, grid_y)` | Which GMAP cell owns a world position |
| **World** | unbounded tiles | Continuous position: `local + grid * 64` |
| **Level-array index** | integer `0..4095` | Row-major board offset: `local_y * 64 + local_x` |
| **Screen** | pixels | Render/input position after the camera transform |

Use the frame names explicitly in APIs and state. Do not call all of them
simply `x` and `y`.

### Which frame the wire carries

| Packet or field | Frame carried |
|-----------------|---------------|
| `PLI_LEVELWARP` / `PLI_LEVELWARPMOD` destination X/Y | **Local**, in the target level |
| `PLO_PLAYERWARP` X/Y | **Local**, in the target level |
| `PLO_PLAYERWARP2` X/Y | **Local**, plus separate `gmap_x`/`gmap_y` segment coordinates |
| Player `GMAPLEVELX` (43), `GMAPLEVELY` (44) | **Segment (grid)** |
| NPC `GMAPLEVELX` (41), `GMAPLEVELY` (42) | **Segment (grid)** |
| Player/NPC X/Y or X2/Y2 entity properties | Position coordinates whose frame is server/context dependent. Normally **local**, but X2/Y2 may legitimately be **world** on GMAP streams |
| Level links, chests, signs, baddies, and board positions | **Local** |

The trap is therefore not the numeric encoding alone. A level-warp coordinate
must remain local even when the client stores the player in world coordinates,
while an entity X2/Y2 property at or above 64 may already be a world coordinate.
Keep accompanying segment properties and packet context until normalization.
Blindly adding the current segment origin can double-offset a world property.
The Reborn client normalizes this in the
`handle_player_props` and `handle_npc_props` handlers.

## World, Segment, and Local Conversion

For each axis:

```text
world   = local + segment * 64
segment = floor(world / 64)
local   = world % 64
```

`reborn_protocol.coords` exposes these as `local_to_world`, `segment_index`/`segment_at`, and
`local_coord`/`world_to_local`.

### Negative coordinates: floor, never truncation

The normative rule is **floor division**. The three common Python spellings
behave as follows:

| Spelling | Result for `world = -1` | Correct? |
|----------|-------------------------|----------|
| `math.floor(world / 64)` | `-1` | Yes |
| `world // 64` | `-1` | Yes, agrees with `floor` on wire coordinates |
| `int(world / 64)` | `0` | No, truncates toward zero |

`int(world / 64)` disagrees for negative, non-boundary coordinates and selects
the segment to the right or below the real one. This is an observable segment,
collision, and link-selection bug, not a presentation choice.

Worked boundary cases:

| World | Segment | Local |
|------:|--------:|------:|
| `63.9375` | `0` | `63.9375` |
| `64.0` | `1` | `0.0` |
| `-1` | `-1` | `63` |
| `-64` | `-1` | `0` |
| `-65` | `-2` | `63` |

The negative cases are the mirror of the positive rollover: `-1` is local tile
63 in segment -1, not local tile -1 in segment 0.

### Known floating-point limitation

The model promises local values in `[0, 64)`, but Python floating-point modulo
has one deliberately unfixed edge case. For a negative magnitude below one ULP
of 64, for example `-1e-16`, `world % 64` rounds to exactly `64.0`. That is
outside the promised interval.

Real wire coordinates cannot reach this case: position properties are multiples
of 1/16 tile. Those values are exact binary fractions, so the normal
world/local round trip is exact. `local_coord` preserves Python's ordinary `%`
behavior rather than adding an unreachable special case. `test_local_coord_float_artifact_near_zero`
pins the limitation.

## Level-Array Index

Board tiles use local integer coordinates. After bounds checking with
`in_level_bounds`, compute the row-major offset with `level_index`:

```text
index = local_y * 64 + local_x
```

Thus `(0, 0) -> 0`, `(63, 0) -> 63`, `(0, 1) -> 64`, and
`(63, 63) -> 4095`. Never index a board with world coordinates.

## Camera and Screen Coordinates

The camera operates on **world tiles** and produces **screen pixels**. For a
viewport `(screen_w, screen_h)`, camera center `(center_x, center_y)`, scale in
pixels per tile, and optional pixel shake offset:

```text
origin_x = screen_w / 2 - center_x * scale + offset_x
origin_y = screen_h / 2 - center_y * scale + offset_y

screen_x = world_x * scale + origin_x
screen_y = world_y * scale + origin_y
```

`camera_origin` computes the origin and `world_to_screen` applies it. Rendering
alone is insufficient: mouse and tile picking require the exact inverse,
`screen_to_world`:

```text
world_x = (screen_x - origin_x) / scale
world_y = (screen_y - origin_y) / scale
```

`visible_tile_range` applies that inverse at the viewport corners, floors the
left/top, and ceils the right/bottom to return an inclusive world-tile range
for culling. Flooring matters when the camera can see negative world tiles.

## Wire Precision and Segment Selection

Legacy X/Y and level-warp fields use half-tile precision. X2/Y2 properties use
pixel precision, decoded as pixels divided by 16, or 1/16 tile. Segment
selection must happen **after decoding to tiles**, using the full decoded value
and `floor(world / 64)`.

Precision does not change boundary ownership: `63.5` and `63.9375` remain in
segment 0, while `64.0` belongs to segment 1. Do not round a pixel-precision
property to an integer tile before selecting its segment.

## Loaded GMAP Versus Current Segment

Track these states separately:

- **GMAP loaded**: the client has parsed the grid. This may remain true inside a house,
  cave, or dungeon reached from the GMAP.
- **In a grid segment now**: the current level is one of that grid's segment
  files.

Coordinate normalization, perimeter clamping, and edge-link filtering must key
off the second state. The Reborn client exposes it as `Client.in_gmap_segment`.
When in a segment, clamp against the full `gmap_extent` so internal seams remain
crossable. Ordinary and interior levels use the local 64×64 bounds.

Links themselves remain local even in a GMAP segment. See
[Level Link Implementation](level-link-implementation.md#coordinate-frame-of-a-link)
for span and collision rules.
