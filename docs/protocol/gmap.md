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
edge, and both servers send it for the step that crosses a seam. It decodes an NPC
the same way: `place_npc` in `pyreborn/npc_handler.py` sets
`world = local + cell * 64` from the NPC's own `GMAPLEVELX`/`GMAPLEVELY`
(`world_from_wire` in `pyreborn/gmap_coords.py`), whatever the local value is. The reference
client does the same: its NPC world position is always `mapX << 6` plus the stored local value
(`Preagonal/FourPlay/quattroplay/src/TServerNPC.cpp:330`).

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

Before `enterLevel` calls `leaveLevel`, `warp` stores the destination's local pixels and
sets the cell to the destination cell for a gmap destination, or (0,0) for a non-gmap
destination (`PlayerClient.cpp:1246-1274`). On the old level, the leave is therefore recorded
and announced around the destination cell and position for a gmap destination, or cell
(0,0) plus the destination's local position for a non-gmap destination
(`PlayerClient.cpp:1361-1362`, `:1390-1392`). `leaveLevel` returns early when the old gmap has
no sub-level at that cell, in which case no leave is recorded or announced (`:1356-1359`).
This was read, not run.

## NPC Framing on a Gmap

A gmap is one `Level` on the reference server. Its NPCs belong to that `Level`, not to a
segment. `LevelLoader::loadGmap` loads every segment's NPCs with the gmap level
(`server/src/loader/LevelLoader.cpp:217`). It sets the NPC's level name to the `.gmap`
name (`:384`), the cell in `mapX`/`mapY`, and stamps `GMAPLEVELX`/`GMAPLEVELY` (`:386-391`).
`NPC::getLevelName()` returns that name (`server/src/object/NPC.cpp:628-631`).

| Field | Content on a gmap |
|-------|-------------------|
| NPC X/Y (2/3) and X2/Y2 (75/76) | **Local** pixels of the cell (`server/include/object/NPC.h:702-703`) |
| NPC `GMAPLEVELX`/`GMAPLEVELY` (41/42) | The cell, `GBYTE1` (`NPC.h:668-669`). The gmap loader and `addNPC` stamp both props for every cell, including (0,0) (`LevelLoader.cpp:386-391`, `Server.cpp:1499-1502`). Only an NPC not stamped by either relies on the reset's always-sent set, which stamps the cell props only outside (0,0) (`NPC.cpp:144-150`) |
| Movement across a seam | The server wraps local into the new cell and sends only the axis that changed (`NPC.cpp:457-468`). A script `x`/`y` write does the same (`NPC.cpp:1870-1925`). `NPC::warp` sends X2/Y2 and both cell props (`NPC.cpp:188-198`) |
| `PLO_SETACTIVELEVEL` | The gmap name. Sent before the first NPC of a block and again whenever the owner changes (`server/src/level/Level.cpp:1446-1464`), and once after the NPC block (`server/src/player/PlayerClient.cpp:1555`). Live sends carry no wrapper: `sendPacketToNearby` wraps a packet in `SETACTIVELEVEL` only for a recipient whose level name differs (`server/src/Server.cpp:2400-2412`), and everyone on one gmap shares the name |
| `PLO_NPCDEL2` | `{GChar len}{level}{GInt3 id}` with the NPC's level name, the gmap name here. The server sends it to a recipient whose own level name differs from the NPC's, and plain `PLO_NPCDEL` to the rest (`Server.cpp:1630-1637`) |
| `PLO_NPCMOVED` | Only when the NPC changes `Level` (`NPC.cpp:203-210`), and it names the destination level. A seam crossing inside one gmap is a props update (X2/Y2 and the changed cell axis), not `PLO_NPCMOVED` |

The reference client reads the same frame. `setnpclevel` (the handler of `PLO_SETACTIVELEVEL`)
resolves a `.gmap` name with `getMap` and any other name with `getLevel`
(`Preagonal/FourPlay/quattroplay/src/TClient.cpp:3777-3784`). A new NPC is added to that
level (`TClient.cpp:2894-2935`). Added to a map, it keeps its own `mapX`/`mapY`. Added to a plain level, it
copies the level's cell (`TServerNPC.cpp:305-325`). Props 0x29/0x2a set the cell axis by axis
(`TServerNPC.cpp:1271-1282`), and 0x4b/0x4c set the local x/y (`:1347-1362`).

**Not established**: where the reference client places an NPC when `PLO_SETACTIVELEVEL`
names a segment `.nw` while the player is on that gmap. The plain-level branch copies the
segment's cell, but the visibility code returns early when the NPC's level is not the
player's map (`TServerNPC.cpp:422-423`). Only the gmap-name form is verified.

pyReborn reads this framing in `handle_npc_props` (`pyreborn/handlers/entities.py`).
pygserver sends both cell props for every gmap NPC, including (0,0)
(`pygserver/pygserver/npc.py:751-756`).

## Range on Entry and Hop

**NPCs.** Entry and a segment hop send the NPCs of the 3x3 cells around the player's cell,
clipped to the grid (`PlayerClient::sendDynamicLevelData`, `PlayerClient.cpp:1524-1552`;
`Level::findNPCsInRangeForData`, `Level.cpp:3425-3477`). The filter time is the leave
time of the **entered** cell (`getLevelLastEnteredTime(subLevel)`, `PlayerClient.cpp:1534`).
The server never consults a neighbour's own record. On a first visit to the entered cell
the record is empty, and the NPCs of all nine cells go out with every prop ever set.

- Nothing is deduplicated on a one-cell hop. The six cells that the old and new 3x3 share
  are sent again, in full on a first visit to the new cell, otherwise with the props changed
  since the player last left it.
- A repeat is harmless to the reference client. `setnpcprops` on a known id updates the
  NPC (`TClient.cpp:2946-2955`).
- **No packet** goes out for a cell that leaves the range. The client hides those NPCs
  itself: a map-owned NPC is visible only while `|player cell - NPC cell| <= 1` on both axes
  (`TServerNPC.cpp:407-456`), re-tested when the player's map position changes
  (`checkMapPos`, `TServerNPC.cpp:1385-1386`). The client keeps the cached NPC.
- Horses and baddies are not sent on a gmap (`PlayerClient.cpp:1538-1542`).
- Board changes go out for the entered cell only. A change in a neighbour cell reaches the
  client live, to the 3x3 around the change (`server/src/level/LevelBoardChange.cpp:51-62`).

**A hop** runs the `GMAPLEVELX`/`GMAPLEVELY` setters (`server/src/player/PlayerProps.cpp:905-973`).
Each setter records the leave time of the cell being left (`leaveSubLevel`), stores the
new cell, sends the dynamic data above, and marks the eight neighbours as recently used.
There is no `PLO_LEVELNAME`, no static data, and no join or leave of the `Level`. The setters run per axis in wire
order, so a diagonal hop also leaves and enters the cell at the new value of the first
axis and the old value of the second.

**Players.** Entry and hop exchange `JOINLEAVELVL = 1` props both ways with the players
that `findPlayersInRangeForSync` returns (`PlayerClient.cpp:1586-1602`). On a gmap that is a
tile box, inclusive on both axes, `abs(dx) <= syncdistancex` and `abs(dy) <= syncdistancey`,
default 192 tiles each (`Level.cpp:3265-3318`, `server/include/Server.h:127`). The default covers a
3x3 gmap. The audience rules are in [Server-Side Behavior](serverside-behavior.md#gmap-audiences).

## Client Level Targets

The reference client keeps two level targets. Read both when you route a packet.

| Target | Set by | Receives |
|--------|--------|----------|
| Level data (`serverlevel`) | `PLO_LEVELNAME` | chests, signs, links, board, board layers, board changes, items, explosions, baddies, horses |
| NPC owner (`npcserverlevel`) | `PLO_SETACTIVELEVEL` | NPC props |

- `setserverlevel` (the `PLO_LEVELNAME` handler) keeps a `.gmap` name only as a name. The
  target becomes the **player's own level** when the player is on that map, and stays
  unchanged otherwise (`TClient.cpp:3224-3241`). It never touches the NPC owner. So an NPC
  owner set by an earlier `PLO_SETACTIVELEVEL` stays in force until the next one.
- The server answers `PLI_ADJACENTLEVEL` with the same two names as an entry: the
  neighbour's `.nw` name first, then `getLevelName()` (`PlayerClient.cpp:1460`, `:1518`,
  which on a gmap is the gmap name). The neighbour's block is therefore addressed to the
  neighbour until the closing `.gmap` name returns the target to the player's own level.
- Items, explosions and the item-removal packet are dropped when the level-data target is
  not the player's own level (`TClient.cpp:3595`, `:3665`, `:3719`). Bombs use the player's action
  level (`TClient.cpp:3584`).
- A warp that names a loaded `.gmap` moves the level-data target to that map and clears
  the bound level. The entry stream binds it again (`TClient.cpp:2998-3004`, `:3050-3060`, `:3398-3404`).
  A warp to a plain level leaves the target alone, and the level load then points the NPC
  owner at the new level only when the target does not already name it (`TPlayer.cpp:941-946`).
- A known NPC with an id of 1000 or more is added to the NPC owner level on every props
  packet when there is one (`TClient.cpp:2950-2951`). A map owner leaves it where it is.

pyReborn keeps both targets (`level_scope`, `npc_level` in `pyreborn/client_state.py`) and
the 3x3 visibility test in `npc_in_range` (`pyreborn/npc_handler.py`). Blocking and touch are not gated by it.
It also applies the reference client's gate for item add, item removal and explosions:
they apply only when the level-data target is the player's own level (`_scope_is_own_level`,
`pyreborn/handlers/entities.py:223-224`, `:242-243`, `pyreborn/handlers/combat.py:111`).

## Script Coordinates on a Gmap

On the reference server a gmap is one `Level` whose size is the whole map
(`sizeInTiles()`, `server/include/level/Level.h:462-472`). Server-side GS1 positions are
**whole-map tiles**, `mapX * 64 + localPixel / 16` (`server/include/object/Character.h:65-68`).

| Construct (server-side GS1) | Frame |
|-----------------------------|-------|
| NPC `x`/`y`, `players[i].x`/`y`, player `x`/`y` | Whole-map. Reads return `getTilePosition()` (`NPC.cpp:1870-1901`, `server/src/player/Player.cpp:1395-1424`). A write recomputes the cell from the global pixel and stamps the changed `GMAPLEVELX`/`GMAPLEVELY` (`NPC.cpp:1878-1925`) |
| `tiles[x,y]` | Whole-map. The index is `(max(0,x) << 32) \| max(0,y)` (`GS1Visitor.cpp:1597-1604`). The setter and getter wrap with `x %= width`, clamp, and pick the segment from the result, so a missing segment reads 0 and ignores a write (`GS1Variables.cpp:389-444`). The neighbour hop for an index above 64 applies only on a bigmap (`:365-385`) |
| `updateboard x,y,w,h` | Whole-map rectangle. Four arguments, each `max(0, v)`; `toWholeTileRectangleArea` truncates the position and sizes the rectangle `ceil(frac + w)` (`GS1Commands.cpp:3714-3727`, `Extents.h:786-795`). One part per segment goes to the 3x3 around that part as `PLO_BOARDMODIFY2` (`LevelBoardChange.cpp:51-62`) |
| `putnpc image,file,x,y` | Whole-map tiles. `addNPC` takes the cell from `toMapPosition(x, y)` and stamps both cell props (`Server.cpp:1495-1503`). The props packet goes to the 3x3 around the NPC (`Server.cpp:1587-1591`) |
| Signs, baddies | Local to their segment |

Reads and writes of `tiles[]` use different layers. The getter reads the instanced or file
tile (`Level.cpp:3121-3133`). The setter writes a script-only layer, sends nothing, and
`updateboard` later publishes it (`Level.cpp:3135-3153`, `:1751-1799`). A part of the rectangle with no
script layer stays tile 0. `updateboard` changes revert after `respawntime` (default 15 s,
`include/Server.h:134`). `updateboard2` equals `updateboard` unless `savelevels` is set
(`Level.cpp:1852-1875`).

**Not established**: the rounding of fractional `updateboard` arguments beyond the
`toWholeTileRectangleArea` code above, and the `playerx`/`playery` builtin name mapping
(only the object property `x` at `Player.cpp:1395` was read).

**Client-side scripts** (GS1 and GS2) use the same whole-map frame for an NPC's `x` and `y`.
The client reads `local + (mapX << 6)` and writes `value - (mapX << 6)`
(`TServerNPCProperties.cpp:331-345`; players: `TServerPlayerProperties.cpp:229-236`).
The NPC position write applies only when the NPC belongs to a map or `0 <= value < 64`;
see [NPC and player positions](../implementation/gs1-client-host.md#npc-and-player-positions).
It drops the NPC's queued moves either way (`TServerNPCProperties.cpp:334-345`).
A player write follows the same pattern. It is clamped to the plain-level range unless the
player is on a map or the script is a weapon's (`TServerPlayerProperties.cpp:17-34`). Signs and baddies stay local.
See [GS1 Client Host](../implementation/gs1-client-host.md#boards-and-gmap-coordinates).

The client `move dx,dy,time,options` command is a queued move
(`TServerNPCProperties.cpp:558-561`, `TServerNPC::addNPCMove`, `TServerNPC.cpp:619-741`),
stepped once per tick by `doNPCMove` (`TServerNPC.cpp:1628-1840`). The low two option bits
pick the squeeze mode: 0 scales every pending duration to the new total, 1 does so only when
the queue spans more than 10 tiles (`:669-720`). The other bits:

| Bit | Meaning | Source |
|-----|---------|--------|
| 0x04 | Stop at a wall | `TServerNPC.cpp:1735` |
| 0x08 | Fire `movementfinished` | `:1661`, `:1746` |
| 0x10 | Face the move | `:1670` |
| 0x20 | Stop at water | `:1737` |
| 0x40 | Update the default animation | `:1648` |

A server move (`PLO_MOVE2`) enters the same queue with mode 1 (`TClient.cpp:5229`).

## Position Frames Sent by the Client

A client packet that carries a position on a gmap carries a position **local to the sender's
level**, unwrapped (a value past the segment edge stays past it). The reference server adds
the sender's cell origin (`getSubLevelOrigin()`) and does not wrap.

| Packet | Client rule | Server rule |
|--------|-------------|-------------|
| `PLI_TRIGGERACTION` | A script `triggeraction` sends `x - (mapX << 6)`, encoded `0..110` tiles (`TInitStatics.cpp:3954-3978`, `TClient.cpp:4306-4362`) | `pixelLoc = origin + wire` (`PlayerClientPackets.cpp:1057-1059`, `:1315`). The reference then tests that global point against the NPC's box wrapped to local pixels (`server/include/npcserver/NPCServer.h:260`, `server/include/utilities/Extents.h:612-620`), so a client trigger action only hits an NPC when the sender is in the gmap's first cell |
| `PLI_BADDYADD` (`putcomp`) | Local, unwrapped | The server takes the wire value modulo 64 tiles (`toLocalPixelPosition`) and files the baddy in the sender's level (`PlayerClientPackets.cpp:554-562`). On a gmap the reference creates no baddy at all (`Level.cpp:1930-1934`) |
| `PLI_HITOBJECTS` | `hitobjects` sends `x - (mapX << 6)`, and sends **nothing** for a point outside 0..64 (`TClient.cpp:1448-1464`, `TInitStatics.cpp:3409-3423`) | Reads half-tiles as local (`PlayerClientPackets.cpp:1019-1031`) |
| `PLI_PUTNPC` | The reference client has no sender for this packet. pyReborn sends the script's whole-map tile, clamped to the byte range | The server reads the position as tiles of the **whole map** and takes the cell from the value itself (`PlayerClientPackets.cpp:754-780`, `Server.cpp:1495-1503`). The wire byte is a `GUCHAR` of half-tiles, so the range ends at 111.5 tiles. pygserver creates the NPC in the loaded segment that holds the point, and nowhere when none does (pygserver commit `1735ea9`) |
| `PLI_BOMBADD` (`putbomb`) | The wire byte read as local; a client that wraps to 0..63 sends what the server reads | Reads each byte modulo 128 half-tiles, i.e. modulo 64 tiles (`PlayerClientPackets.cpp:215-217`) |
| `PLI_HORSEADD` | The wire value is read as local | `origin + wire` in the sender's cell (`PlayerClientPackets.cpp:257-269`) |

The reference client also runs `triggeraction` locally first (`TInitStatics.cpp:3966`).
pyReborn does not port that step, so a client NPC's own `action<name>` event does not fire for
the sender.

## pygserver Divergences on a Gmap

These are deliberate and differ from the reference server. Each one has a cost, listed here.

- **Client trigger actions hit from any cell and across a seam.** The reference compares
  a global point with a local NPC box, so it only hits when the sender is in the first cell
  (above; read from source, not reproduced live). pygserver tests NPCs in the loaded segments
  in the 3x3 around the point, with the point expressed in each segment's frame
  (`fire_trigger_at` in `pygserver/pygserver/npc.py`, `segments_around` in
  `pygserver/pygserver/gs1/frame.py`). Scripts can therefore receive actions the reference misses.
- **Baddies stay on gmap segments.** The reference has none on a gmap: `addBaddy`
  returns nothing (`Level.cpp:1930-1934`) and entry sends none (`PlayerClient.cpp:1538-1542`).
  pygserver keeps and ticks them per segment. Scripts that branch on `compuscount` differ,
  and `compusdied` can fire.
- **A client bomb is still relayed when an NPC server exists.** The reference hands the
  bomb to its own bomb engine and relays nothing (`PlayerClientPackets.cpp:226-240`).
- **A level change releases a carried NPC.** The reference moves the carried NPC with the
  player (`PlayerClient.cpp:1556-1583`). pygserver sends `CARRYNPC 0` and drops the id.
  A pickup on a gmap is refused as on the reference (`PlayerProps.cpp:670-676`).
- **Enter and leave events fire on a segment hop.** The reference queues `playerenters` and
  `playerleaves` only from `Level::addPlayer`/`removePlayer` (`Level.cpp:1533`, `:1544`), that is,
  when a player enters or leaves the gmap. Recipients are the NPCs within `eventdistance`
  (default 64 tiles) of the player's global position (`Level.cpp:3396-3423`, `Server.h:129`).
  A hop runs neither (`PlayerProps.cpp:905-973`). pygserver fires both for every NPC of the
  segment, with no distance test. This was surveyed and left unchanged on purpose: content
  such as `funtimes-pygserver/world/chicken1.nw` relies on the hop-time event. In the reference
  a server-side NPC more than 64 tiles from the entry point never gets `playerenters`.
  In the same survey, GS1 `players[]`, `playerscount`, `npcs[]` and `npcscount` cover the whole
  gmap in the reference (`GS1Variables.cpp:92-155`); pygserver's cover the script's segment only.
- **The visit record stays on the cell actually left.** On a warp the reference sets
  the player's cell to the destination cell for a gmap destination, or (0,0) for a non-gmap
  destination, before `enterLevel` calls `leaveLevel` (`PlayerClient.cpp:1246-1274`). The leave
  is recorded and announced on the old level around the destination cell and position for
  a gmap destination, or cell (0,0) plus the destination's local position for a non-gmap
  destination (`:1361-1362`, `:1390-1392`). `leaveLevel` returns early when the old gmap has no
  sub-level at that cell, in which case no leave is recorded or announced (`:1356-1359`).
  This was read, not run.

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
