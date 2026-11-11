# NPC Properties

The server serializes NPCs with their **own property enum**, IDs **0 through 77**
(`GServer-v2/server/include/object/NPC.h:52-147`), whose serializers are bound by
`FOR_LIST_OF_NPC_PROPS` (`GServer-v2/server/include/object/NPC.h:580-659`). The
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
| 1 | SCRIPT | **`[GSHORT len][raw]`** (2-byte length, MODERN gen sends len 0 because scripts come via the npc-server) |
| 2 | X | `[GCHAR]` TileCoord: `tile = (byte-32)/2`, signed if byte ≥ 216 |
| 3 | Y | `[GCHAR]` TileCoord (same as X) |
| 4 | POWER | `[GCHAR]` hp in half-hearts |
| 5 | RUPEES | **`[GINT3]` (3 bytes)** (*not* a direction) |
| 6 | ARROWS | `[GCHAR]` |
| 7 | BOMBS | `[GCHAR]` |
| 8 | GLOVEPOWER | `[GCHAR]` |
| 9 | BOMBPOWER | `[GCHAR]` |
| 10 | SWORDIMAGE | `PropertySwordPower`: bare power or `power+30` then length-prefixed image, **not a plain string** |
| 11 | SHIELDIMAGE | `PropertyShieldPower`: bare power or `power+10` then length-prefixed image, **not a plain string** |
| 12 | GANI | `[GCHAR len][string]` (modern), gen-0 BOWGIF preset rule |
| 13 | VISFLAGS | `[GCHAR]` bitfield: VISIBLE=1, DRAWOVER=2, DRAWUNDER=4, TIMERSHOW=8, CREATED=16, MALE=64 |
| 14 | BLOCKFLAGS | `[GCHAR]` bitfield: NOBLOCK=1, CANBECARRIED=2, CANBEPULLED=4, CANBEPUSHED=8 |
| 15 | MESSAGE | `[GCHAR len][string]` (chat) |
| 16 | HURTDXDY | **2 bytes**: `[GCHAR dx+32][GCHAR dy+32]` (0-64, 32=center) |
| 17 | ID | **`[GINT3]` (3 bytes)** |
| 18 | SPRITE | `[GCHAR]` `(sprite << 2) | direction`, direction = byte & 3 |
| 19 | COLORS | 5 bytes (classic) or 8 bytes (new-world) |
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
| 52 | LEVEL (CURLEVEL) | string. **Sent to game clients** on non-classic servers. See below |
| 53-73 | GATTRIB10-30 | `[GCHAR len][string]` |
| 74 | CLASS | **`PropertyLongString`: `[GSHORT len][string]`** (2-byte length) |
| 75 | X2 | `[GSHORT]` PixelCoordinate: `pixel = val>>1`, negative if `val&1`, `tile = pixel/16` |
| 76 | Y2 | `[GSHORT]` PixelCoordinate (same as X2) |
| 77 | Z2 | `[GSHORT]` PixelCoordinate (same as X2) |

### Variable-width props to watch

The non-`PropertyString` string-ish props each have their own length scheme.
[Data Types](data-types.md#npc-property-data-types) summarizes the wire formats.
In particular, the NPC macro binds IDs 10 and 11 to the same power serializers as player
gear (`GServer-v2/server/include/object/NPC.h:591-592`). Reading either as a plain string
makes its power byte become a bogus length and corrupts the remainder of the NPC stream.
HEADIMAGE 22 is likewise the 100-offset preset/name form, not a plain string
(`GServer-v2/server/include/object/NPC.h:603`).

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
`BODYIMAGE` (35) on a CLASSIC server. Nothing sets `UNKNOWN48`, so it is not sent.
`NPC::warp()` sets `LEVEL` (52) on every level change (`NPC.cpp:213`), so on a newmain or
modern server **prop 52 goes to every game client** in `PLO_NPCPROPS`. No client version
check applies.

This matters for old clients. A static read of the 2.22 and 2.31 NPC prop parsers shows that
both stop at ids 48-52. An unknown id ends the stream, so these clients lose every prop
after 52 in that packet: GATTRIB10-30, CLASS and X2/Y2/Z2. Source: Graal_analysis
[`protocol/player-props.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/player-props.md),
"Highest ids parsed by later clients" (static read, not lab-tested). A server that serves
2.x clients should leave out prop 52 or send it last.

The NC sub-protocol also uses these props. `PLO_NC_NPCADD` carries NAME=50, TYPE=51 and
LEVEL=52. See [RC & NC Protocols](rc-nc-protocols.md).

## Worked Example

A char-NPC from `chicken1.nw` (hand-decoded from a raw `PLO_NPCPROPS` capture):

```
id 303, IMAGE="#c#", X=49.5, Y=51.5, SHIELDIMAGE="no-shield.gif", GANI="def[37]"
```

`GANI` really is the literal string `"def[37]"` on the wire. That is the NPC's animation
name with an embedded frame index, not a parse error.

## Notes

- With `serverside = true` (an npc-server loaded), scripts come through **empty** for
  serverside NPCs. The server sends only `getClientSideScript()` chunks. The NPC still
  appears with image/gani/coords, and clientside GS1 runs locally.
- NPC GANI-attribute prop IDs (for gattrib ordering) are `{36,37,38,39,40, 44,45,46,47, 53..73}`.
