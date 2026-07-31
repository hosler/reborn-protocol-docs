# Tile-type tables

The client ships two 4,096-byte lookup tables. Each byte is the type of one
base tile ID. Collision, water, damage, chair, and related decisions consume
the selected type rather than inferring behavior from tile artwork.

## Table provenance

`pyReborn/pyreborn/tiletypes1.dat` is the classic table. Its current bytes are
the classic table embedded in the official v6.0.3.7 Linux client binary. That
revision changed nine bytes from the older shipped file: indices 2958 and
3060-3061 are type 9, while 3248-3250 and 3264-3266 are type 2.

`pyReborn/pyreborn/tiletypesnw.dat` is the new-world table. The authors
extracted it from that binary at file offset `0x541740`. It occurs immediately
after the classic table at `0x540740`. The authors checked the result against
the labeled type-template tileset. The regions that the template identifies
report their labeled types instead of the mostly blocking results from the
classic table.

Both files are exactly 4,096 bytes. The loader takes one byte per base tile ID
and retains an all-walkable fallback for a missing classic file. A missing
new-world file logs once and falls back to classic.

Evidence:

- `pyReborn/pyreborn/tiletypes.py:1-31,66-101`
- `pyReborn/tests/unit/test_tilestype_selection.py:84-97,135-141`

## Per-level selection

Every level change resets `tilestype` to zero and examines registered full
tile definitions. The definition whose prefix is the longest match for the
stripped level name wins. For an equal-length tie, the first registered
definition wins. The client skips definitions with type 3 or greater, except
type 5. In
particular, type-4 partial pastes do not select a type table.

Reads route as follows:

| `tilestype` | Result |
| ---: | --- |
| 0 | classic `tiletypes1.dat` |
| 1 or 2 | new-world `tiletypesnw.dat` |
| 5 | no table. Every valid tile reports type 0 |

An off-level negative tile remains blocking. The selection registry persists
across level changes until a script removes its definitions.

Evidence:

- `Preagonal/FourPlay/quattroplay/src/TTiles.cpp:568-630`
- `Preagonal/FourPlay/quattroplay/src/TServerLevel.cpp:688-708,735-743`
- `pyReborn/pyreborn/tiletypes.py:103-145,153-200,203-248`
- `pyReborn/tests/unit/test_tilestype_selection.py:38-79,90-132,144-170`
