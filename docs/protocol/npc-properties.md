# NPC Properties

NPCs are serialized with their **own property enum** (`NPCProp`, from GServer-v2
`server/include/object/NPC.h`'s `FOR_LIST_OF_NPC_PROPS` X-macro), with byte widths defined
in `PropertySerializers.cpp`. This enum is **not** the same as the player property enum —
sharing assumptions between them is the single biggest source of garbled NPC parsing.

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

A parser that decodes NPC prop 5 as a direction/sprite byte, or 17 as a 1-byte sprite, will
desync everything after it.

## Full NPCProp Table

Widths from `PropertySerializers.cpp`; cross-checked against pyReborn `parse_npc_props`.

| ID | Name | Wire encoding |
|----|------|---------------|
| 0 | IMAGE | `[GCHAR len][string]` |
| 1 | SCRIPT | **`[GSHORT len][raw]`** (2-byte length; MODERN gen sends len 0 — scripts come via the npc-server) |
| 2 | X | `[GCHAR]` TileCoord: `tile = (byte-32)/2`, signed if byte ≥ 216 |
| 3 | Y | `[GCHAR]` TileCoord (same as X) |
| 4 | POWER | `[GCHAR]` hp in half-hearts |
| 5 | RUPEES | **`[GINT3]` (3 bytes)** — *not* a direction |
| 6 | ARROWS | `[GCHAR]` |
| 7 | BOMBS | `[GCHAR]` |
| 8 | GLOVEPOWER | `[GCHAR]` |
| 9 | BOMBPOWER | `[GCHAR]` |
| 10 | SWORDIMAGE | `PropertySwordPower` — same variable format as player prop 8 (`+30` for custom image) |
| 11 | SHIELDIMAGE | `PropertyShieldPower` — same as player prop 9 (`+10` for custom image) |
| 12 | GANI | `[GCHAR len][string]` (modern); gen-0 BOWGIF preset rule |
| 13 | VISFLAGS | `[GCHAR]` bitfield: VISIBLE=1, DRAWOVER=2, DRAWUNDER=4, TIMERSHOW=8, CREATED=16, MALE=64 |
| 14 | BLOCKFLAGS | `[GCHAR]` bitfield: NOBLOCK=1, CANBECARRIED=2, CANBEPULLED=4, CANBEPUSHED=8 |
| 15 | MESSAGE | `[GCHAR len][string]` (chat) |
| 16 | HURTDXDY | **2 bytes**: `[GCHAR dx+32][GCHAR dy+32]` (0-64, 32=center) |
| 17 | ID | **`[GINT3]` (3 bytes)** |
| 18 | SPRITE | `[GCHAR]` `(sprite << 2) | direction`; direction = byte & 3 |
| 19 | COLORS | 5 bytes (classic) or 8 bytes (new-world) |
| 20 | NICKNAME | `[GCHAR len][string]` |
| 21 | HORSEIMAGE | `[GCHAR len][string]` |
| 22 | HEADIMAGE | `PropertyHeadGif` — `[GCHAR b]`: b<100 → preset id; b≥100 → read (b-100) string bytes |
| 23-32 | SAVE0-SAVE9 | `[GCHAR]` each |
| 33 | ALIGNMENT | `[GCHAR]` AP |
| 34 | IMAGEPART | **6 bytes**: `[GSHORT x][GSHORT y][GCHAR w][GCHAR h]` |
| 35 | BODYIMAGE | `[GCHAR len][string]` |
| 36-40 | GATTRIB1-5 | `[GCHAR len][string]` |
| 41 | GMAPLEVELX | `[GCHAR]` |
| 42 | GMAPLEVELY | `[GCHAR]` |
| 43 | Z | `[GCHAR]` `(z_tile + 50)` |
| 44-47 | GATTRIB6-9 | `[GCHAR len][string]` |
| 48 | UNKNOWN48 | `PropertyVoid` — 0 bytes; *not sent to client* |
| 49 | SCRIPTER | string; *server-internal, not sent to client* |
| 50 | NAME | string; *server-internal, not sent to client* |
| 51 | TYPE | string; *server-internal, not sent to client* |
| 52 | CURLEVEL | string; *server-internal, not sent to client* |
| 53-73 | GATTRIB10-30 | `[GCHAR len][string]` |
| 74 | CLASS | **`PropertyLongString` — `[GSHORT len][string]`** (2-byte length) |
| 75 | X2 | `[GSHORT]` PixelCoordinate: `pixel = val>>1`, negative if `val&1`; `tile = pixel/16` |
| 76 | Y2 | `[GSHORT]` PixelCoordinate (same as X2) |
| 77 | Z2 | `[GSHORT]` PixelCoordinate (same as X2) |

### Variable-width props to watch

The non-`PropertyString` string-ish props each have their own length scheme:

- **SCRIPT (1)** — GSHORT length (2 bytes), not GCHAR.
- **CLASS (74)** — `PropertyLongString`, GSHORT length (2 bytes).
- **IMAGEPART (34)** — fixed 6 bytes (`gshort x, gshort y, gchar w, gchar h`).
- **HURTDXDY (16)** — fixed 2 bytes.

### Server-internal props (48-52)

`UNKNOWN48`, `SCRIPTER`, `NAME`, `TYPE`, `CURLEVEL` are kept on the server and **never sent
to a game client** in `PLO_NPCPROPS`. (They *are* exchanged over the NC sub-protocol —
`PLO_NC_NPCADD` carries NAME=50/TYPE=51/CURLEVEL=52; see
[RC & NC Protocols](rc-nc-protocols.md).) A client parser should still skip them gracefully
if encountered.

## Worked Example

A char-NPC from `chicken1.nw` (hand-decoded from a raw `PLO_NPCPROPS` capture):

```
id 303, IMAGE="#c#", X=49.5, Y=51.5, SHIELDIMAGE="no-shield.gif", GANI="def[37]"
```

`GANI` really is the literal string `"def[37]"` on the wire — that is the NPC's animation
name with an embedded frame index, not a parse error.

## Notes

- With `serverside = true` (an npc-server loaded), scripts come through **empty** for
  serverside NPCs — only `getClientSideScript()` chunks are sent. The NPC still appears with
  image/gani/coords; clientside GS1 runs locally.
- NPC GANI-attribute prop IDs (for gattrib ordering) are `{36,37,38,39,40, 44,45,46,47, 53..73}`.
