# NPC Properties

The server serializes NPCs with their **own property enum**, IDs **0 through 77**
(`GServer-v2/server/include/object/NPC.h:52-147`), whose serializers are bound by
`FOR_LIST_OF_NPC_PROPS` (`GServer-v2/server/include/object/NPC.h:626-704`). The
authoritative wire-width table lives in
[Data Types](data-types.md#npc-property-data-types). This enum is **not** the same as the
player property enum. If a parser uses the player property rules, it can corrupt the NPC
data.

## Packet Framing

`PLO_NPCPROPS (3)` (and the client-side `PLI_NPCPROPS (3)`):

```
[GINT3: npc_id]                 // 3 bytes
[GCHAR: prop_id][payload] ...   // repeated property pairs to end of packet
```

## Why You Can't Reuse Player-Prop Semantics

Three IDs that mean completely different things than in the player enum:

| ID | Player enum | NPC enum |
|----|-------------|----------|
| 5 | BOMBSCOUNT (1 byte) | **RUPEES (GINT3, 3 bytes)** |
| 17 | SPRITE (1 byte) | **ID (GINT3, 3 bytes)** |
| 75/76/77 | OSTYPE / TEXTCODEPAGE / ONLINESECS2 | **X2 / Y2 / Z2 (pixel coords)** |

If a parser decodes NPC prop 5 as a direction or sprite byte, all subsequent data loses
synchronization. The same error occurs if the parser decodes prop 17 as a 1-byte sprite.

## Full NPCProp Table
Widths come from `PropertySerializers.cpp`. The table cross-checks them against pyReborn's `parse_npc_props`.
For the canonical wire-width and encoding notes, see
[Data Types](data-types.md#npc-property-data-types).

| ID | Name | Wire encoding |
|----|------|---------------|
| 0 | IMAGE | `[GCHAR len][string]` |
| 1 | SCRIPT | **`[GSHORT len][raw]`** (2-byte length). A MODERN-generation server always sends len 0 because scripts come via the npc-server; other generations send `getClientSideScript()` (`PropertySerializers.cpp:553-557`) |
| 2 | X | `[GCHAR]` TileCoord: `tile = (byte-32)/2`. The value is negative when the decoded value (wire byte minus 32) is ≥ 216, which is wire bytes 248-255 and 0-31 (`PropertySerializers.cpp:487-501`). The writer remaps half-tile 223 to 224 (`:477-481`). The source comment says this avoids a newline, but the wire byte for 223 is 255; the half-tile that gives `0x0A` is 234, which is not remapped |
| 3 | Y | `[GCHAR]` TileCoord (same as X) |
| 4 | POWER | `[GCHAR]` hp in half-hearts (`NPCProp::HALFHEARTS` in the source enum) |
| 5 | RUPEES | **`[GINT3]` (3 bytes)** (*not* a direction; `NPCProp::GRALATS` in the source enum) |
| 6 | ARROWS | `[GCHAR]` |
| 7 | BOMBS | `[GCHAR]` |
| 8 | GLOVEPOWER | `[GCHAR]` |
| 9 | BOMBPOWER | `[GCHAR]` |
| 10 | SWORDIMAGE | `PropertySwordPower`: bare power or `power+30` then length-prefixed image, **not a plain string** |
| 11 | SHIELDIMAGE | `PropertyShieldPower`: bare power or `power+10` then length-prefixed image, **not a plain string** |
| 12 | GANI | `[GCHAR len][string]` (modern), gen-0 BOWGIF preset rule. For an NPC that is not a character the server always sends it empty, `[GCHAR 0]`, in both full and delta packets (`NPC.cpp:1745-1748`, `:1791-1794`) |
| 13 | VISFLAGS | `[GCHAR]` bitfield: VISIBLE=1, DRAWOVER=2, DRAWUNDER=4, TIMERSHOW=8, CREATED=16, UNKNOWN (bit 6, 0x20; named `UNKNOWNBIT6`)=32, MALE=64 (`NPC.h:157-167`) |
| 14 | BLOCKFLAGS | `[GCHAR]` bitfield: NOBLOCK=1, CANBECARRIED=2, CANBEPULLED=4, CANBEPUSHED=8 |
| 15 | MESSAGE | `[GCHAR len][string]` (chat) |
| 16 | HURTDXDY | **2 bytes**: `[GCHAR dx+32][GCHAR dy+32]` (0-64, 32=center) |
| 17 | ID | **`[GINT3]` (3 bytes)** |
| 18 | SPRITE | `[GCHAR]` `(sprite << 2) | direction`, direction = byte & 3 |
| 19 | COLORS | 5 bytes (classic) or 8 bytes (new-world). The serializer picks the width by `isNewWorldMode()` (`PropertySerializers.h:793-796`), but NPC COLORS are always read as 5 bytes (`PropertyColors<true>`, `NPC.h:646`) |
| 20 | NICKNAME | `[GCHAR len][string]` |
| 21 | HORSEIMAGE | `[GCHAR len][string]` |
| 22 | HEADIMAGE | `PropertyHeadGif`, `[GCHAR b]`: b<100 → preset id, b≥100 → read (b-100) string bytes |
| 23-32 | SAVE0-SAVE9 | `[GCHAR]` each |
| 33 | ALIGNMENT | `[GCHAR]` AP |
| 34 | IMAGEPART | **6 bytes**: `[GSHORT x][GSHORT y][GCHAR w][GCHAR h]` |
| 35 | BODYIMAGE | `[GCHAR len][string]` |
| 36-40 | GATTRIB1-5 | `[GCHAR len][string]` |
| 41 | GMAPLEVELX | `[GCHAR]` |
| 42 | GMAPLEVELY | `[GCHAR]` |
| 43 | Z | `[GCHAR]` `(z_tile + 50)` |
| 44-47 | GATTRIB6-9 | `[GCHAR len][string]` |
| 48 | UNKNOWN48 | `PropertyVoid`, 0 bytes (nothing sets it, so it is not sent) |
| 49 | SCRIPTER | string (*filtered by `canSendProp()`, not sent to game clients*) |
| 50 | NAME | string (*filtered by `canSendProp()`, not sent to game clients*) |
| 51 | TYPE | string (*filtered by `canSendProp()`, not sent to game clients*) |
| 52 | LEVEL | string. **Sent to game clients** on non-classic servers. See below |
| 53-73 | GATTRIB10-30 | `[GCHAR len][string]` |
| 74 | CLASS | **`PropertyLongString`: `[GSHORT len][string]`** (2-byte length) |
| 75 | X2 | `[GSHORT]` PixelCoordinate: `pixel = val>>1`, negative if `val&1`, `tile = pixel/16` |
| 76 | Y2 | `[GSHORT]` PixelCoordinate (same as X2) |
| 77 | Z2 | `[GSHORT]` PixelCoordinate (same as X2) |

### Variable-width props to watch

The non-`PropertyString` string-ish props each have their own length scheme.
[Data Types](data-types.md#npc-property-data-types) summarizes the wire formats.
In particular, the NPC macro binds IDs 10 and 11 to the same power serializers as player
gear (`GServer-v2/server/include/object/NPC.h:637-638`). Reading either as a plain string
makes its power byte become a bogus length and corrupts the remainder of the NPC stream.
HEADIMAGE 22 is likewise the 100-offset preset/name form, not a plain string
(`GServer-v2/server/include/object/NPC.h:649`).

NPC property pairs follow the same ascending-ID emission requirement as player
properties. This is especially important for a full appearance record: insertion-order
output can make a strict receiver stop after IMAGE/X/Y and silently discard GANI,
NICKNAME, COLORS, SWORDIMAGE, SHIELDIMAGE, HEADIMAGE, IMAGEPART, and GATTRIBs. Sort the
pairs numerically before writing them.

### Props 48-52

`NPC.h` marks 48-52 "NOT HANDLED BY CLIENT, DO NOT SEND"
(`GServer-v2/server/include/object/NPC.h:108-114`). The send filter does not follow
that comment completely. `canSendProp()` (`GServer-v2/server/src/object/NPC.cpp:64-78`)
removes only `SCRIPTER` (49), `NAME` (50) and `TYPE` (51), plus every prop above
`BODYIMAGE` (35) on a CLASSIC server and `CLASS` (74) on CLASSIC and NEWMAIN servers. Nothing sets `UNKNOWN48`, so it is not sent.
`NPC::warp()` sets `LEVEL` (52) on every level change (`NPC.cpp:213`), so on a newmain or
modern server **prop 52 goes to every game client** in `PLO_NPCPROPS`. No client version
check applies.

This may matter for old clients. Static reads of the 2.22 and 2.31 NPC prop parsers
reported in squirelworks' client-analysis notes (`protocol/player-props.md`, "Highest ids
parsed by later clients"; static read, not lab-tested) say both stop at ids 48-52, so these
clients would lose every prop after 52 in that packet: GATTRIB10-30, CLASS and X2/Y2/Z2.
This is not verified against the reference. The decompiled reference client behaves
differently: `Preagonal/FourPlay/quattroplay/src/TServerNPC.cpp:1372-1376` skips unknown
ids 0 to 0x53 as exactly 2 bytes (id plus one byte), with no case for ids 0x30-0x34. A
length-prefixed string such as prop 52 would therefore desynchronize that parser instead
of ending the stream. Advice, not reference behavior: a server that serves 2.x clients may
prefer to leave out prop 52 or send it last.

The NC sub-protocol also uses these props. `PLO_NC_NPCADD` carries NAME=50, TYPE=51 and
LEVEL=52. See [RC & NC Protocols](rc-nc-protocols.md).

## Worked Example

A char-NPC from `chicken1.nw`, hand-decoded from a raw `PLO_NPCPROPS` capture. The
capture is not in the repository, so this example is **unverified**:

```
id 303, IMAGE="#c#", X=49.5, Y=51.5, SHIELDIMAGE="no-shield.gif", GANI="def[37]"
```

`GANI` really is the literal string `"def[37]"` on the wire. That is the NPC's animation
name with an embedded frame index, not a parse error.

## Notes

- Only the server generation decides the SCRIPT prop (`PropertySerializers.cpp:553-557`),
  not `serverside`. A MODERN server sends length 0. Any other generation sends
  `getClientSideScript()`, which holds the clientside portion of the script, not the
  serverside part. The NPC still appears with image/gani/coords, and clientside GS1 runs locally.
- NPC GANI-attribute prop IDs (for gattrib ordering) are `{36,37,38,39,40, 44,45,46,47, 53..73}`.
