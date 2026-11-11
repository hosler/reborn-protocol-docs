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
| `PLI_LEVELWARP` / `PLI_LEVELWARPMOD` destination X/Y | **Local**, in the target level, when the destination is a named sub-level. The server adds that sub-level's origin (`PlayerClientPackets.cpp:75-83`). When the destination name ends in `.gmap`, or is the gmap level itself, the server takes the position with origin (0, 0), as **gmap-global** (`PlayerClientPackets.cpp:66-69`, `:85-88`) |
| `PLO_PLAYERWARP` X/Y | **Local**, in the target level |
| `PLO_PLAYERWARP2` X/Y | **Local**, then Z (`gchar z+50`), then separate `gmap_x`/`gmap_y` segment coordinates and the level name (`PlayerClient.cpp:1252`). The pre-2.x path never sends it (`PlayerClientOriginal.cpp:53`) |
| Player `GMAPLEVELX` (43), `GMAPLEVELY` (44) | **Segment (grid)** |
| NPC `GMAPLEVELX` (41), `GMAPLEVELY` (42) | **Segment (grid)** |
| Player/NPC X/Y and X2/Y2 entity properties | **Local** to the current segment, always. The reference server stores and relays them as level-local pixels, and the grid position travels separately in `GMAPLEVELX`/`GMAPLEVELY` |
| Level links, chests, signs, baddies, and board positions | **Local** |

#### What the reference does with X/Y and X2/Y2

All four of the player props X, Y, X2 and Y2 map to the same field,
`character.localPixelX/Y` (`server/include/object/Player.h:707-708`, `:770-771`). The X2/Y2
setter stores the received pixel value unchanged
(`server/src/player/PlayerProps.cpp:1072-1100`). NPC X2/Y2 map to the same field
(`server/include/object/NPC.h:702-703`). The server never writes a world value into X2/Y2.
The segment comes only from `GMAPLEVELX`/`GMAPLEVELY`, which the server accepts only
on a gmap level and reverts otherwise (`PlayerProps.cpp:905-967`).

The reference client agrees. It sends `netSigned14(floor(getlocalx() * 16 + 0.5))`
(`Preagonal/FourPlay/quattroplay/src/TPlayer.cpp:3336-3339`) and composes world as
`local + (mapX << 6)` (`Preagonal/FourPlay/quattroplay/src/TGaniObject.cpp:1503-1504`).

A live check against the reference server on a gmap level shows the same: the login
self props carry local 30.0/30.5 with the grid sent separately in `PLO_PLAYERWARP2`.
A client X2 of 31, 70.25 or -1.5 (local tiles) reaches other clients as only the X2 prop,
with the same value. There is no wrapping, and no `GMAPLEVELX`/`GMAPLEVELY` is added.
An out-of-range local is relayed as it is.

So the trap is the pairing, not the encoding. A level-warp coordinate is local, except
for the `.gmap` destinations in the table above. An entity X/Y or X2/Y2 is local to the segment named by
the same entity's `GMAPLEVELX`/`GMAPLEVELY`. World is derived as `local + grid * 64`
from a known grid, never read off the wire.

**Our client.** pyReborn resolves a player's world position as local plus that
player's own segment (`_resolve_player_world` in `pyreborn/handlers/entities.py`).
A value at or above 64, or below 0, is a local position just beyond the segment
edge, and both servers send it for the step that crosses a seam. The NPC decode
(`handle_npc_props`) still treats such a value as an already-world coordinate.
Against the reference that guess is wrong. Do not implement it from this document.

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

Legacy X/Y and level-warp fields use half-tile precision (a `GCHAR` of half-tiles, so
`value * 8` pixels on the server). X2/Y2 properties use
pixel precision, decoded as pixels divided by 16, or 1/16 tile. Segment
selection must happen **after decoding to tiles**, using the full decoded value
and `floor(world / 64)`.

Precision does not change boundary ownership: `63.5` and `63.9375` remain in
segment 0, while `64.0` belongs to segment 1. Do not round a pixel-precision
property to an integer tile before selecting its segment.

## Server-Side Segment Handling

- `PLO_LEVELNAME` is sent once per sub-level the server streams, with the sub-level
  name, and then again with the gmap name, so the client's current level stays the gmap
  (`PlayerClient.cpp:1446`, `:1504`).
- A client crossing a seam sends `GMAPLEVELX`/`GMAPLEVELY`. The server reverts them when
  the current level is not a gmap. Otherwise it leaves the old sub-level, sends the dynamic
  data of the new one and marks the eight neighbours as recently used
  (`PlayerProps.cpp:905-967`).

## The `.gmap` File Format

Parsed by `Map::Map(is_gmap_t, ...)` (`server/src/level/Map.cpp:88-257`). The header
`GRMAP001` is skipped wherever it appears (`Map.cpp:124`); it is not required on the first
line. Every other line is one `KEY value` pair:

| Key | Meaning |
|-----|---------|
| `WIDTH`, `HEIGHT` | grid size in segments |
| `LEVELNAMES` ... `LEVELNAMESEND` | one CSV row of level file names per grid row. An empty cell is a hole. Names are stored lower-cased. Rows or cells beyond `HEIGHT`/`WIDTH` are ignored, so `WIDTH` and `HEIGHT` must come before `LEVELNAMES` or the rows are dropped (`Map.cpp:147`, `:151`) |
| `MAPIMG`, `MINIMAPIMG` | image names, stored on the map |
| `NOAUTOMAPPING` | read and ignored by the server (client-side only) |
| `LOADFULLMAP` | keep every segment loaded |
| `LOADATSTART` ... `LOADATSTARTEND` | CSV rows of segment names to keep loaded |
| `GENERATED`, `GENSEED`, `GENBASE`, `GENEVENBORDERS`, `GENHEIGHT`, `GENCHAOS`, `LEVHEIGHT`, `LEVCHAOS`, `HEIGHTMAP` ... `HEIGHTMAPEND`, `RANDOMSEEDS` ... `RANDOMSEEDSEND` | procedural terrain generation. When no `LEVELNAMES` is given, `GENERATED` supplies the last level name and the server names the levels itself |

The older bigmap `.txt` form is the other branch of the same class (`Map.cpp:36-86`): no
header, one CSV row of level names per line, empty cells are holes, and the size is
derived from the rows.

`PLO_BIGMAP` and `PLO_MINIMAP` are separate. They come from the `bigmap` and `minimap`
server options, four comma-separated values each, and go to clients of version 2.1 and
later during login after `PLO_RESETCLIENT` (`PlayerClient.cpp:494-512`).

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
