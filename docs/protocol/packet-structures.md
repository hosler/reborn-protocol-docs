# Reborn Protocol v2 - Packet Structure Reference

## Overview

This document describes the Reborn protocol packet structures. The description comes from
an analysis of the GServer-v2 codebase. Each packet structure includes primitive-level
details for implementations in different languages.

> **Prerequisites**: Before you use the packet structures, understand these subjects:
> - [Data Types](data-types.md) - G-type encoding (the +32 obsession)
> - [String Types](strings.md) - The three different string formats (yes, three)
> - [Encryption](encryption.md) - How packets are bundled and encrypted

## Protocol Architecture

### Packet Bundle Structure

The sender puts all packets in bundles that have this structure:

```
[UINT16: packet_size][PACKET_BUNDLE_DATA]
```

Where:
- `UINT16 packet_size`: Size of the bundle data in bytes (little-endian)
- `PACKET_BUNDLE_DATA`: Encrypted/compressed packet bundle

### Bundle Processing (GEN_5 Protocol)

For ENCRYPT_GEN_5 protocol (recommended):

1. **Bundle Structure**: `[UINT8: compression_type][ENCRYPTED_COMPRESSED_DATA]`
2. **Compression Types**:
   - `0x02`: COMPRESS_UNCOMPRESSED (no compression)
   - `0x04`: COMPRESS_ZLIB (zlib compression)
   - `0x06`: COMPRESS_BZ2 (bzip2 compression)

3. **Processing Order**:
   - Client → Server: Compress data → Encrypt → Send
   - Server → Client: Receive → Decrypt → Decompress

4. **Encryption**: Partial packet encryption using XOR-based stream cipher
   - Uses iterator-based key generation
   - Encryption limit depends on compression type

### Individual Packet Structure

Newlines (`\n`) separate the packets in each bundle. Raw data packets are the exception:

```
[UINT8: packet_id][PACKET_DATA]\n
```

Special case for raw data:
```
[UINT8: PLI_RAWDATA][UINT32: data_length]
[RAW_DATA_BYTES]
```

## Data Encoding Types

The wire-format details for G-types, coordinate packing, and property widths live in
[Data Types](data-types.md). This page describes packet layouts. If a field width matters,
use the information at the link.

## Client-to-Server Packets (PLI_*)

### PLI_LEVELWARP (0) - Level Warp Request
**Trigger**: Player moves to a different level
```
[GUCHAR: tile_x]     // X coordinate (in tiles)
[GUCHAR: tile_y]     // Y coordinate (in tiles)  
[STRING: level_name] // Target level name (reads to end of packet)
```

**GServer Implementation Notes**:
- Coordinates are read as `pPacket.readGChar() * 8` to get pixel position
- Level name uses `pPacket.readString("")` which reads to end of packet
- Requires appropriate permissions when `warptoforall = false`

**Variant**: PLI_LEVELWARPMOD (30) - includes modification time:
```
[GUINT5: mod_time]   // Level modification timestamp
[GUCHAR: tile_x]
[GUCHAR: tile_y]
[STRING: level_name] // Reads to end of packet
```

### PLI_BOARDMODIFY (1) - Tile Modification
**Trigger**: Player destroys/places tiles (e.g., cutting bushes)
```
[GUCHAR: start_x]    // Starting X coordinate (0-63)
[GUCHAR: start_y]    // Starting Y coordinate (0-63)
[GUCHAR: width]      // Width of modification area
[GUCHAR: height]     // Height of modification area
[GSHORT: tile]...    // width*height tiles, one GSHORT each (row-major)
```
**Source**: `PlayerClient::msgPLI_BOARDMODIFY` (`PlayerClientPackets.cpp:109-134`) reads
`x/y/w/h` via `readGUChar()` ×4, then the level applies the tiles (`Level::alterBoard`,
`Level.cpp:1476`, `tileData.readGShort()` per tile). The data is **not** a raw opaque
string. Each tile is a proper GSHORT. The server does **not echo it to the sender**. See
[GServer Behavior: PLI_BOARDMODIFY Is Not Echoed](gserver-behavior.md#pli_boardmodify-is-not-echoed-to-the-sender).

### PLI_PLAYERPROPS (2) - Player Property Update
**Trigger**: Player properties change (movement, appearance, stats, etc.)
```
[PROPERTY_DATA...]   // Variable-length property data
```

Property format:
```
[GUCHAR: prop_id][PROP_SPECIFIC_DATA]
```

### PLI_NPCPROPS (3) - NPC Property Update
**Trigger**: Client updates NPC properties (when no NPC-Server)
```
[GUINT: npc_id]      // NPC identifier
[STRING: prop_data]  // NPC property data
```

### PLI_BOMBADD (4) - Place Bomb
**Trigger**: Player places a bomb
```
[GUCHAR: tile_x]           // X position (in half-tiles)
[GUCHAR: tile_y]           // Y position (in half-tiles)
[GUCHAR: player_power]     // Player ID (upper 6 bits) + Power (lower 2 bits)
[GUCHAR: time_to_explode]  // Timer in 0.05s increments (default: 55 = 3 seconds)
```

### PLI_BOMBDEL (5) - Remove Bomb
**Trigger**: Bomb explodes or is removed
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
```

### PLI_TOALL (6) - Chat Message
**Trigger**: Player sends public chat
```
[STRING: message]    // Chat message text
```

### PLI_HORSEADD (7) - Add Horse
**Trigger**: Player places/spawns a horse
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[GUCHAR: dir_bush]   // Direction (2 bits) + Bush count (6 bits)
[STRING: image]      // Horse image filename
```

### PLI_HORSEDEL (8) - Remove Horse
**Trigger**: Horse is removed/destroyed
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
```

### PLI_ARROWADD (9) - Shoot Arrow
**Trigger**: Player fires an arrow
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[GUCHAR: flags]      // Direction (2 bits) + Reflect (1 bit) + From Player (1 bit)
[GUCHAR: sprite]     // Arrow sprite/type
[GUCHAR: power]      // Arrow power/damage
```

### PLI_FIRESPY (10) - Fire Spy
**Trigger**: Player uses fire spy weapon
```
[GUCHAR: (length << 3) | power]  // length = bits 3-7, power = low 3 bits
```
**Source**: `msgPLI_FIRESPY` (`PlayerClientPackets.cpp:314-330`). The relayed
`PLO_FIRESPY (20)` is `[GSHORT owner_id][GUCHAR: (length << 3) | power]`. It uses the same
byte after the sender player ID.

### PLI_THROWCARRIED (11) - Throw Carried Object
**Trigger**: Player throws carried item/NPC
```
// No additional data
```

### PLI_ITEMADD (12) - Drop Item
**Trigger**: Player drops an item
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[GUCHAR: item_id]    // NUMERIC LevelItemType id (0-24) — see PLO_ITEMADD table
```

### PLI_ITEMDEL (13) - Remove Item
**Trigger**: Item is destroyed (not picked up)
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
```

### PLI_ITEMTAKE (32) - Pick Up Item
**Trigger**: Player picks up an item
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
```

### PLI_CLAIMPKER (14) - Claim Player Kill
**Trigger**: Player dies and killer claims the kill
```
[GUSHORT: killer_id] // Player ID of the killer
```

### PLI_BADDYPROPS (15) - Baddy Property Update
**Trigger**: Client updates baddy properties (level leader only)
```
[GUCHAR: baddy_id]   // Baddy identifier (0-255)
[STRING: prop_data]  // Baddy property data
```

### PLI_BADDYHURT (16) - Hurt Baddy
**Trigger**: Baddy takes damage
```
[GUCHAR: baddy_id]   // Baddy identifier
[GUCHAR: damage]     // Damage amount
```

### PLI_BADDYADD (17) - Add Baddy
**Trigger**: Player spawns a baddy
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[GUCHAR: baddy_type] // Baddy type (0-9)
[GUCHAR: power]      // Baddy power/health (capped at 12)
[STRING: image]      // Baddy image filename
```

### PLI_FLAGSET (18) - Set Flag/Variable
**Trigger**: Player/script sets a client or server flag
```
[STRING: flag_data]  // Format: "flag_name=value" or "flag_name"
```

### PLI_FLAGDEL (19) - Delete Flag/Variable
**Trigger**: Player/script deletes a flag
```
[STRING: flag_name]  // Flag name to delete
```

### PLI_OPENCHEST (20) - Open Chest
**Trigger**: Player opens a treasure chest
```
[GCHAR: tile_x]      // X coordinate in tiles
[GCHAR: tile_y]      // Y coordinate in tiles
```

### PLI_PUTNPC (21) - Place NPC
**Trigger**: Player places an NPC (when putnpc enabled)
```
[GCHAR: image_len]   // Length of image string
[STRING: image]      // NPC image filename
[GCHAR: code_len]    // Length of code string  
[STRING: code_file]  // NPC script filename
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
```

### PLI_NPCDEL (22) - Delete NPC
**Trigger**: Player deletes an NPC
```
[GUINT: npc_id]      // NPC identifier to delete
```

### PLI_WANTFILE (23) - Request File
**Trigger**: Client needs a file (image, level, etc.)
```
[STRING: filename]   // Requested file path
```

### PLI_SHOWIMG (24) - Show Image
**Trigger**: Player displays an image to others
```
[IMAGE_DATA...]      // Image display data
```

### PLI_HURTPLAYER (26) - Hurt Player
**Trigger**: Player damages another player
```
[GUSHORT: victim_id] // Target player ID
[GCHAR: hurt_dx]     // Knockback X direction
[GCHAR: hurt_dy]     // Knockback Y direction  
[GUCHAR: power]      // Damage amount
[GUINT: npc_id]      // NPC ID (if NPC caused damage)
```

### PLI_EXPLOSION (27) - Create Explosion
**Trigger**: Player creates an explosion effect
```
[GUCHAR: radius]     // Explosion radius
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[GUCHAR: power]      // Explosion power
```

### PLI_PRIVATEMESSAGE (28) - Private Message
**Trigger**: Player sends PM to other players
```
[GUSHORT: player_count]        // Number of recipients
[GUSHORT: player_id]...        // Player IDs (repeated player_count times)
[STRING: message]              // Message text
```

### PLI_NPCWEAPONDEL (29) - Delete NPC Weapon
**Trigger**: Player removes weapon from inventory
```
[STRING: weapon_name] // Weapon name to remove
```

### PLI_WEAPONADD (33) - Add Weapon
**Trigger**: Player gains a weapon
```
[GUCHAR: weapon_type] // 0 = default weapon, >0 = NPC weapon
// If type == 0:
[GCHAR: item_id]      // Default weapon item ID
// If type > 0:
[GUINT: npc_id]       // Source NPC ID
```

### PLI_UPDATEFILE (34) - File Update Check
**Trigger**: Client checks if local file is current
```
[GUINT5: mod_time]   // Local file modification time
[STRING: filename]   // File to check
```

### PLI_ADJACENTLEVEL (35) - Request Adjacent Level
**Trigger**: Client requests neighboring level data
```
[GUINT5: mod_time]   // Level modification time
[STRING: level_name] // Adjacent level name
```

### PLI_HITOBJECTS (36) - Hit Objects
**Trigger**: Player's weapon hits objects/NPCs
```
[GCHAR: power]       // Hit power/damage (in half-increments)
[GCHAR: tile_x]      // X position (in half-tiles)
[GCHAR: tile_y]      // Y position (in half-tiles)
[GUINT: npc_id]      // NPC ID (optional, if hit came from NPC)
```

### PLI_LANGUAGE (37) - Set Language
**Trigger**: Player changes language setting
```
[STRING: language]   // Language code (e.g., "English")
```

### PLI_TRIGGERACTION (38) - Trigger Action
**Trigger**: Player activates a trigger/sign action
```
[GUINT: npc_id]      // Associated NPC ID
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[STRING: action_data] // Comma-separated action parameters
```

### PLI_MAPINFO (39) - Map Information
**Trigger**: Client requests map information
```
[STRING: data]       // Map-related data (usage unclear)
```

### PLI_SHOOT (40) - Shoot Projectile (v1)
**Trigger**: Player fires a projectile
```
[GINT: unknown]      // Unknown parameter (always 0 in tests)
[GCHAR: pixel_x]     // X position in pixels/16
[GCHAR: pixel_y]     // Y position in pixels/16
[GCHAR: pixel_z]     // Z position in pixels/16 + 50
[GUCHAR: angle]      // Horizontal angle (0-220 maps to 0-π)
[GUCHAR: z_angle]    // Z angle (0-220 maps to 0-π)
[GUCHAR: speed]      // Speed in pixels per 0.05s
[GCHAR: gani_len]    // Length of GANI string
[STRING: gani]       // GANI animation name
[GUCHAR: param_len]  // Length of shoot parameters
[STRING: shoot_params] // Shoot parameters
```

### PLI_SHOOT2 (48) - Shoot Projectile (v2)
**Trigger**: Player fires a projectile (v5.07+ clients)
```
[GUSHORT: pixel_x]   // X position in pixels
[GUSHORT: pixel_y]   // Y position in pixels
[GUSHORT: pixel_z]   // Z position in pixels
[GCHAR: offset_x]    // Level offset X
[GCHAR: offset_y]    // Level offset Y
[GUCHAR: angle]      // Horizontal angle (0-220)
[GUCHAR: z_angle]    // Z angle (0-220)
[GUCHAR: speed]      // Speed in pixels per 0.05s
[GUCHAR: gravity]    // Gravity factor
[GUSHORT: gani_len]  // Length of GANI string
[STRING: gani]       // GANI animation name
[GUCHAR: param_len]  // Length of shoot parameters
[STRING: shoot_params] // Shoot parameters
```

### PLI_SERVERWARP (41) - Server Warp Request
**Trigger**: Player requests to warp to another server
```
[STRING: server_name] // Target server name
```

### PLI_MUTEPLAYER (43) - Mute Player
**Trigger**: Player mutes another player (via playerlist)
```
[GSHORT: player_id]  // Target player ID
[GBYTE: mute_state]  // 1 = mute, 0 = unmute
```

### PLI_PROCESSLIST (44) - Process List
**Trigger**: Server requests client's running processes
```
[STRING: process_data] // Newline-separated process list
```

### PLI_VERIFYWANTSEND (47) - Verify File Checksum
**Trigger**: Client verifies file integrity before requesting
```
[GUINT5: checksum]   // CRC32 checksum of local file
[STRING: filename]   // File to verify
```

### PLI_RAWDATA (50) - Raw Data Marker
**Trigger**: Indicates next packet contains raw binary data
```
[GUINT: data_size]   // Size of following raw data in bytes
```

## Player Properties (PLI_PLAYERPROPS Data)

Player properties use the following format:
```
[GUCHAR: prop_id][PROP_DATA]
```

### Property Encodings by Type:

> **Width discipline:** the single most common parser bug is using the wrong width for a
> numeric prop. This error desynchronizes each property after it.
> [Data Types](data-types.md#player-property-data-types) gives the canonical width table
> and the cross-property exceptions.
> **Do not assume "a count fits in a byte."**

**NICKNAME (0)**: `[GCHAR: length][string]`
**MAXPOWER (1)**: `[GCHAR: hearts * 2]` (1 byte, half-hearts; 1 heart = 2)
**CURPOWER (2)**: `[GCHAR: current_power]` (1 byte, half-hearts)
**RUPEESCOUNT (3)**: `[GINT3: rupee_count]` (**3 bytes**, not 1)
**ARROWSCOUNT (4)**: `[GCHAR: arrow_count]`
**BOMBSCOUNT (5)**: `[GCHAR: bomb_count]`
**GLOVEPOWER (6)**: `[GCHAR: glove_power]` (0-3)
**BOMBPOWER (7)**: `[GCHAR: bomb_power]` (0-3)
**SWORDPOWER (8)**: Variable format (see below)
**SHIELDPOWER (9)**: Variable format (see below)

> ⚠️ **VARIABLE SIZE WARNING** - SWORDPOWER and SHIELDPOWER
>
> These properties change format based on their value:
>
> **SWORDPOWER** (`PropertySwordPower`):
> - power `0` → `[GCHAR: 0]`
> - power 1-4 with **no** custom image → `[GCHAR: power]` (1 byte)
> - otherwise → `[GCHAR: power+30][GCHAR: img_len][STRING: image]`. The **power byte comes
>   first** with a **+30** bias. The length-prefixed image name comes next.
>
> **SHIELDPOWER** (`PropertyShieldPower`):
> - power `0` → `[GCHAR: 0]`
> - power 1-3 with **no** custom image → `[GCHAR: power]` (1 byte)
> - otherwise → `[GCHAR: power+10][GCHAR: img_len][STRING: image]`. The bias is **+10**,
>   not +30 as it is for the sword.
>
> Yes, the format changes based on the value. Yes, the power byte precedes the length.
> Yes, sword and shield use different biases.
>
> When you receive the data, branch on the **raw decoded power byte**. A sword raw value
> `< 30` is bare. A raw value `>= 30` means `power = raw - 30`, followed by a
> length-prefixed image. Shield
> uses `< 10` and `>= 10` the same way. In particular, testing `power > 4` for sword
> is wrong. It attempts to read an image string that is absent from the bare form and
> desynchronizes every following property. The serializer/deserializer definitions are
> at `GServer-v2/server/src/utilities/PropertySerializers.cpp:68-163`.
>
> For a bare nonzero power, the receiver synthesizes `sword{N}.png` or
> `shield{N}.png`. Classic generation uses `.gif`. The reference shield implementation
> is intentionally asymmetric: serialization permits the bare form only through power
> 3, while deserialization synthesizes a default through power 4. Its deserializer also
> returns early when no bytes remain after a biased power, an explicit 1.41-client quirk.
> A custom sword name without an extension gains `.gif`. A custom shield name gains
> `.gif` only for classic generation
> (`GServer-v2/server/src/utilities/PropertySerializers.cpp:89-182`).
**GANI (10)**: `[GCHAR: length][string]` - Animation file
**HEADIMAGE (11)**: Variable format (see below) — *also called HEADGIF in some older docs*

> ⚠️ **MAGIC NUMBER ALERT** - HEADIMAGE
>
> The first byte has a dual interpretation:
> - If byte < 100: It is a **preset head ID** (no string follows, only the ID byte)
> - If byte ≥ 100: **Subtract 100** to get the actual string length, then read that many bytes
>
> Example: Byte value 105 means "read 5 bytes of string data for the head image filename."
> Byte value 5 means "use preset head #5, no string follows."
>
> This is a 100-offset preset/name union, **not** a normal length-prefixed string.
> Treating a preset byte as a string length consumes bytes belonging to the next
> property (`GServer-v2/server/src/utilities/PropertySerializers.cpp:261-290`).
**CURCHAT (12)**: `[GCHAR: length][string]` - Current chat bubble
**COLORS (13)**: `[8 bytes: color_data]` (server new-world mode) or `[5 bytes]`
(other mode). This is server-wide configurable policy, not a width implied by the
client version or handshake. Each byte is a palette index (+32 encoded). See
[Colors](data-types.md#colors-5-or-8-bytes) for safe width retry.
**ID (14)**: `[GSHORT: player_id]` (2 bytes)
**X (15)**: `[GCHAR: x * 2]` - signed half-tiles; decoded values `>=216` are
negative signed bytes before division by 2. *Not* pixels/2.
**Y (16)**: same signed half-tile encoding as X
**SPRITE (17)**: `[GCHAR: (sprite << 2) | direction]` - direction = low 2 bits, sprite/frame = rest
**STATUS (18)**: `[GCHAR: status_flags]` - Player status bits
**CARRYSPRITE (19)**: one unsafe GCHAR byte. The oracle maps it to
`PropertyUnsafeByte`. Its writer adds 32 without the ordinary G-byte clamp. Values
above 223 therefore differ from a clamped-byte writer
(`GServer-v2/server/include/object/Player.h:633`,
`GServer-v2/server/include/utilities/PropertySerializers.h:220-231`).
**CURLEVEL (20)**: `[GCHAR: length][string]` - Current level name
**HORSEGIF (21)**: `[GCHAR: length][string]` - Horse image
**HORSEBUSHES (22)**: `[GCHAR: bush_count]` - Bushes eaten by horse
**EFFECTCOLORS (23)**: Variable - `[GCHAR: first]`. If `first == 0`, the property is only
that 1 byte. Otherwise, it is 5 bytes (`first` + 4 color bytes). Visual effect colors
(RGBA tint)
**CARRYNPC (24)**: `[GINT3: npc_id]` (**3 bytes**) - Carried NPC ID
**APCOUNTER (25)**: `[GSHORT: ap_time]` (**2 bytes** — not 1) - AP recovery counter
**MAGICPOINTS (26)**: `[GCHAR: mp_count]` - Magic points
**KILLSCOUNT (27)**: `[GINT3: kill_count]` (**3 bytes**) - Player kills
**DEATHSCOUNT (28)**: `[GINT3: death_count]` (**3 bytes**) - Player deaths
**ONLINESECS (29)**: `[GINT3: online_time]` (**3 bytes**) - Online time in seconds
**IPADDR (30)**: `[GINT5: ip_address]` (**5 bytes**) - IP as a packed gint5
integer, not one byte or five raw octets. The independent list-server reader calls
`readGInt5()` for this property
(`graal-serverlist/server/src/ServerPlayer.cpp:59-62`).
**UDPPORT (31)**: `[GINT3: udp_port]` (**3 bytes** — not GSHORT) - UDP port
**ALIGNMENT (32)**: `[GCHAR: ap_value]` - Alignment Points
**ADDITFLAGS (33)**: `[GCHAR: flags]` - Additional player flags
**ACCOUNTNAME (34)**: `[GCHAR: length][string]` - Account name
**BODYIMG (35)**: `[GCHAR: length][string]` - Body image
**RATING (36)**: `[GINT3: packed_rating]` (3 bytes) - ELO rating + deviation packed into a single gint3 (`PropertyEloRating`), `(rating & 0xFFF) << 9 | (deviation & 0x1FF)`. Not two floats.

> ⚠️ **PROP NUMBERING IS NOT CONTIGUOUS** - props 37-74
>
> The custom-attribute (GATTRIB) range is **interleaved** with other props. Do **not** assume GATTRIB1-30 fills 37-74. The real layout:

| Prop # | Name | Format |
|--------|------|--------|
| 37-41 | GATTRIB1-5 | `[GCHAR: length][string]` |
| 42 | ATTACHNPC | `[GCHAR: type][GINT3: npc_id]` (**4 bytes** — a type byte then a 3-byte id, *not* a bare gint3) |
| 43 | GMAPLEVELX | `[GCHAR: gmap_x]` - GMAP segment column |
| 44 | GMAPLEVELY | `[GCHAR: gmap_y]` - GMAP segment row |
| 45 | Z | `[GCHAR: (z_tile + 50)]` - Z position in **tiles** + 50, clamped [-50,170] |
| 46-49 | GATTRIB6-9 | `[GCHAR: length][string]` |
| 50 | JOINLEAVELVL | `[GCHAR]` join/leave-level flag |
| 51 | DISCONNECT | **`PropertyVoid` — 0 bytes** (no payload). *Not* a "connected" flag byte. |
| 52 | LANGUAGE | `[GCHAR: length][string]` - client language |
| 53 | PLAYERLISTSTATUS | **`[GCHAR]` — a single status byte, NOT a string** |
| 54-74 | GATTRIB10-30 | `[GCHAR: length][string]` |
| 75 | OSTYPE | `[GCHAR: length][string]` - client OS |
| 76 | TEXTCODEPAGE | `[GINT3]` (3 bytes) |
| 77 | ONLINESECS2 | `[GINT5]` (5 bytes) |
| 78 | X2 | `[GSHORT]` (2 bytes) high-precision X pixel coord — see X2/Y2 encoding below |
| 79 | Y2 | `[GSHORT]` (2 bytes) high-precision Y pixel coord |
| 80 | Z2 | `[GSHORT]` (2 bytes) high-precision Z pixel coord |
| 81 | PLAYERLISTCATEGORY | `[GCHAR]` (1 byte) |
| 82 | COMMUNITYNAME | `[GCHAR: length][string]` |
| 83 | *(unspecified)* | Absent from the oracle property-list macro; width and meaning are not specified |

If a parser treats 37-74 as one flat GATTRIB block, it misaligns each subsequent
property. Props **51** (void) and **53** (1 byte, not a string) also frequently
desynchronize a simple parser.

### Property-stream ordering and failure handling

The server must send player and NPC property pairs in strictly ascending property-ID
order. The reference full-list and modified-player builders iterate IDs upward
(`GServer-v2/server/src/player/PlayerProps.cpp:1291-1317`,
`GServer-v2/server/src/player/PlayerProps.cpp:1357-1380`), while its shared change
collector sorts by ID because a client stops processing when it encounters a property it
does not understand (`GServer-v2/server/src/utilities/PropertySerializers.cpp:668-689`).

Disordered properties can silently truncate data without a reported protocol error.
A strict parser can stop early and keep only the prefix. An NPC builder that
emits dictionary-insertion order can therefore produce an NPC with only image/X/Y while
silently losing later gani, nickname, colors, gear, head image, image part, and GATTRIB
properties. Sort pairs by numeric ID before serialization. The list-server player-property
subset is an exception. Its switch consumes each property that is present. Thus, that
subset does not require ascending order
(`graal-serverlist/server/src/ServerPlayer.cpp:31-77`).

Stream walkers must also obey these rules:

- An unknown property is not safely skippable without its real declared payload width.
  Blindly skipping one byte after the ID desynchronizes any multi-byte or variable-width
  value. Stop cleanly if the width is unknown.
- A property ID at end-of-packet with zero payload is truncation for every non-void
  property, not successful full consumption.
- Do not infer a shape for player prop 83: it is absent from
  `FOR_LIST_OF_PLAYER_PROPS` (`GServer-v2/server/include/object/Player.h:613-696`).

### Packet-context policy is intentional

The shared wire descriptor table does not give each packet context the same semantics.
Reborn's `StreamPolicy`, `parse_player_props`, and `parse_other_player` symbols preserve
these differences:

- `PLO_OTHERPLPROPS` has a leading GSHORT player ID; `PLO_PLAYERPROPS` does not.
- An empty other-player `CURCHAT` surfaces as `""` to clear a chat bubble, while an
  empty self-property text may remain absent. Other text fields likewise surface or
  disappear according to the packet handler's contract.
- Account-name precedence is context-specific: some accumulators keep the first
  authoritative name, while rename/update contexts let the last occurrence win.
- `JOINLEAVELVL` is meaningful in other-player roster traffic, including the standalone
  join/leave prefix, but is not ordinary self-state.

These application semantics use one wire codec. A future implementation must not
combine them only because they share payload descriptors.

**X2/Y2/Z2 (78/79/80)** are the high-precision pixel coordinates used on GMAPs and for
sub-tile positions. Each is a GSHORT carrying `value = (abs(pixels) << 1) | (negative ? 1 : 0)`.
Decode with `pixels = value >> 1`. If `value & 1`, use `pixels = -pixels`. Then use
`tiles = pixels / 16`.
See [Data Types: X2/Y2 Encoding](data-types.md#x2y2-encoding-the-weird-one).

## Remote Control Packets (PLI_RC_*)

RC (Remote Control) clients use these packets for server administration.

> **For the complete, byte-validated RC and NC reference**, see
> [RC & NC Protocols](rc-nc-protocols.md).
> It includes the login handshakes, the GEN_2 versus GEN_5 distinction, the full PLI/PLO
> tables, and the `getPropsForRCPacket` blob layout. The entries below are a quick
> subset.

### PLI_RC_SERVEROPTIONSGET (51) - Get Server Options
**Trigger**: RC requests server configuration
```
// No additional data
```

### PLI_RC_SERVEROPTIONSSET (52) - Set Server Options  
**Trigger**: RC updates server configuration
```
[STRING: options_data] // Server configuration text
```

### PLI_RC_FOLDERCONFIGGET (53) - Get Folder Config
**Trigger**: RC requests folder configuration
```
// No additional data
```

### PLI_RC_FOLDERCONFIGSET (54) - Set Folder Config
**Trigger**: RC updates folder configuration
```
[STRING: folder_config] // Folder configuration data
```

### PLI_RC_PLAYERPROPSGET (59) - Get Player Properties
**Trigger**: RC requests player information
```
[STRING: player_name] // Player account name
```

### PLI_RC_PLAYERPROPSSET (60) - Set Player Properties
**Trigger**: RC modifies player properties
```
[STRING: player_name] // Target player
[STRING: prop_data]   // Property modifications
```

### PLI_RC_DISCONNECTPLAYER (61) - Disconnect Player
**Trigger**: RC kicks a player
```
[STRING: player_name] // Player to disconnect
```

### PLI_RC_ADMINMESSAGE (63) - Admin Message
**Trigger**: RC sends server-wide message
```
[STRING: message] // Admin message text
```

### PLI_RC_PRIVADMINMESSAGE (64) - Private Admin Message
**Trigger**: RC sends private message to player
```
[STRING: player_name] // Target player
[STRING: message]     // Private message
```

### PLI_RC_SERVERFLAGSGET (68) - Get Server Flags
**Trigger**: RC requests server flags
```
// No additional data
```

### PLI_RC_SERVERFLAGSSET (69) - Set Server Flags
**Trigger**: RC updates server flags
```
[STRING: flags_data] // Server flags data
```

### PLI_RC_ACCOUNTADD (70) - Add Account
**Trigger**: RC creates new player account
```
[STRING: account_data] // Account creation data
```

### PLI_RC_ACCOUNTDEL (71) - Delete Account
**Trigger**: RC deletes player account
```
[STRING: account_name] // Account to delete
```

### PLI_RC_FILEBROWSER_* - File Browser Operations
Various file management operations for RC file browser functionality.

## NPC Control Packets (PLI_NC_*)

NC (NPC Control) clients use these packets for NPC and content management.

### PLI_NC_NPCGET (103) - Get NPC
**Trigger**: NC requests NPC data
```
[GINT: npc_id] // NPC identifier
```

### PLI_NC_NPCDELETE (104) - Delete NPC
**Trigger**: NC deletes an NPC
```
[GINT: npc_id] // NPC identifier
```

### PLI_NC_NPCSCRIPTGET (106) - Get NPC Script
**Trigger**: NC requests NPC script
```
[GINT: npc_id] // NPC identifier
```

### PLI_NC_NPCSCRIPTSET (109) - Set NPC Script
**Trigger**: NC updates NPC script
```
[GINT: npc_id]        // NPC identifier
[GSTRING: script]     // New script code
```

### PLI_NC_NPCADD (111) - Add NPC
**Trigger**: NC creates new NPC
```
[GSTRING: npc_info] // NPC data: name,id,type,scripter,level,x,y
```

### PLI_NC_WEAPONLISTGET (115) - Get Weapon List
**Trigger**: NC requests weapon list
```
// No additional data
```

### PLI_NC_WEAPONGET (116) - Get Weapon
**Trigger**: NC requests weapon data
```
[STRING: weapon_name] // Weapon name
```

### PLI_NC_WEAPONADD (117) - Add Weapon
**Trigger**: NC creates/updates weapon
```
[GCHAR: name_len]     // Weapon name length
[STRING: weapon_name] // Weapon name
[GCHAR: image_len]    // Image name length
[STRING: image_name]  // Image filename
[STRING: script_code] // Weapon script
```

## Special Packets

### PLI_REQUESTUPDATEBOARD (130) - Request Level Update
**Trigger**: Client requests level board update
```
[GCHAR: level_len]   // Level name length
[STRING: level_name] // Level name
[GUINT5: mod_time]   // Modification time
[GSHORT: x]          // X coordinate
[GSHORT: y]          // Y coordinate  
[GSHORT: width]      // Width
[GSHORT: height]     // Height
```

### PLI_REQUESTTEXT (152) - Request Server Text
**Trigger**: Client requests server-stored value
```
[STRING: key] // Key to retrieve
```

### PLI_SENDTEXT (154) - Send Server Text
**Trigger**: Client sets server-stored value
```
[STRING: key_value] // "key=value" format
```

### PLI_UPDATEGANI (157) - Update GANI Animation
**Trigger**: Client requests GANI bytecode update
```
[GUINT5: checksum]   // CRC32 of client's cached gani bytecode (0 forces a resend)
[STRING: gani_name]  // GANI name (without .gani extension), to end of packet
```
Server replies with `PLO_GANISCRIPT (134)` only if the CRC differs, then **always**
`PLO_LOADGANI (195)` (`msgPLI_UPDATEGANI`, `PlayerClientPackets.cpp:1460-1483`).

### PLI_UPDATESCRIPT (158) - Update Weapon Script
**Trigger**: Client requests weapon bytecode
```
[STRING: weapon_name] // Weapon name, to end of packet (no checksum field)
```
Server replies with `PLO_WEAPONBYTECODE2 (140)`
(`msgPLI_UPDATESCRIPT`, `PlayerClientPackets.cpp:1485-1493`).

### PLI_UPDATECLASS (161) - Update NPC Class
**Trigger**: Client requests class bytecode
```
[GINT5: checksum]    // CRC32 of client's cached class bytecode (0 forces a resend)
[STRING: class_name] // Class name, to end of packet
```
If the CRC differs, the server replies with `PLO_LOADSCRIPT (197)` form 2
(RAWDATA-framed). Unknown classes get a header-only `PLO_WEAPONBYTECODE2 (140)` instead
(`msgPLI_UPDATECLASS`, `PlayerClientPackets.cpp:1495-1530`). This packet requires an NPC
server (`hasNPCServer()`). Otherwise, the server ignores it.

### PLI_UPDATEPACKAGEREQUESTFILE (159) - Update Package Request
**Trigger**: Client requests update package files
```
[GCHAR: name_len]      // Package name length
[STRING: package_name] // Update package name
[GUCHAR: install_type] // 1=install, 2=reinstall
[STRING: checksums]    // File checksums (GUINT5 per file)
```

## Encryption Details (ENCRYPT_GEN_5)

### Key Generation
- Initial key set via PLI_SET_ENC_KEY or login
- Iterator starts at predefined value based on generation
- Key stream generated using: `key = (key + iterator++) & 0xFF`

### Encryption Limits
The compression type sets the encryption limit:
- COMPRESS_UNCOMPRESSED: 40 bytes
- COMPRESS_ZLIB: 4096 bytes  
- COMPRESS_BZ2: 65536 bytes

### Decryption Process
1. Extract compression type (first byte)
2. Apply XOR decryption with generated key stream
3. Decompress using appropriate algorithm
4. Parse individual packets

## Data Type Reference

See [Data Types](data-types.md) for the canonical encoding table, coordinate rules, and
property-width notes.

## Implementation Notes

1. **Byte Order**: [Data Types](data-types.md) summarizes multi-byte primitive encoding
2. **String Termination**: [String Types](strings.md) documents the string formats
3. **Coordinate System**: Coordinate frames and GMAP packing live in [Data Types](data-types.md)
4. **Error Handling**: The receiver should ignore invalid packets and stay connected
5. **Version Compatibility**: Some packets vary by client version (check version ID)

## Server-to-Client Packets (PLO_*)

### PLO_LEVELBOARD (0) - Level Board Data
**Trigger**: Player enters level or requests level data
```
[tile_data...][\n]   // Newline-terminated inline board data
```
This packet contains inline, newline-terminated board data. The server normally does
*not* send the full 64×64 board here. The server sends the complete 8192-byte tile dump
out of band as **PLO_BOARDPACKET (101)**. A preceding **PLO_RAWDATA (100)** length packet
announces it. The server uses PLO_LEVELBOARD for the inline or partial board
representation. Each tile is a
16-bit value (2 bytes) representing the tile index.

### PLO_LEVELLINK (1) - Level Link/Warp

> ⚠️ **THE TRAP** ⚠️
>
> This packet does NOT use a length-prefixed GSTRING. Multiple client implementations
> have made this mistake. The server sends raw string data until a newline (0x0A).
> If you read the first byte as a length, you will read 'l' from "level.nw".
> You will compute length = 108 - 32 = 76 and consume half the next packet. Do not do this.
>
> See [String Types: The PLO_LEVELLINK Trap](strings.md#the-plo_levellink-trap-) for details.

**Trigger**: Level has warp/link destinations (only sent when serverside=false)
```
[STRING: link_data] // Raw newline-terminated string (NOT a GSTRING!)
```
**String Type**: Newline-terminated (NOT length-prefixed).

**Link Data Format**: "destlevel x y width height destx desty"
- destlevel: Target level name
- x, y: Link area position (tiles, 0-63)
- width, height: Link area size (tiles)
- destx, desty: Destination position (can be "playerx"/"playery" or numeric)

**Important Server Behavior**:
- When `serverside = false`: Server sends level links to client, client must handle warping
- When `serverside = true`: Server handles level links automatically
- Special values: "playerx"/"playery" mean "keep player's current position"

### PLO_BADDYPROPS (2) - Baddy Properties
**Trigger**: Baddy properties change or player enters level
```
[GCHAR: baddy_id]    // Baddy identifier (leading byte)
[GCHAR: prop_id][value...] ...   // sequence of prop pairs
```

Baddy props use their **own** `BaddyProp` enum (GServer `LevelBaddy`), distinct from
player/NPC props. `getProps()` emits props 1..10 in order (prop 0 = ID is the leading byte):

| ID | Name | Payload |
|----|------|---------|
| 0 | ID | *(the leading byte; not repeated)* |
| 1 | X | `[GCHAR]` position.x()/8 (half-tile units) |
| 2 | Y | `[GCHAR]` position.y()/8 |
| 3 | TYPE | `[GCHAR]` baddy type id |
| 4 | POWERIMAGE | `[GCHAR: power][GCHAR: img_len][image]` — power byte **then** length-prefixed image |
| 5 | MODE | `[GCHAR]` BaddyMode |
| 6 | ANI | `[GCHAR]` animation index |
| 7 | DIR | `[GCHAR]` `(headDirection << 2) | direction` |
| 8 | VERSESIGHT | `[GCHAR: len][string]` |
| 9 | VERSEHURT | `[GCHAR: len][string]` |
| 10 | VERSEATTACK | `[GCHAR: len][string]` |

> Prop **4 (POWERIMAGE)** is a power byte followed by a length-prefixed image string.
> A parser can lose synchronization if it reads power as a bare byte. pyReborn reliably
> reads ID/X/Y/TYPE. Clients that only need the type can stop after prop 3.

### PLO_NPCPROPS (3) - NPC Properties  
**Trigger**: NPC properties change or player enters level
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[GCHAR: prop_id][payload]...   // NPC property pairs (their OWN enum, not player props)
```

> NPCs use a **distinct `NPCProp` enum**. Prop 5 is RUPEES (not a direction), 17 is ID,
> 75/76/77 are X2/Y2/Z2. See the full table in [NPC Properties](npc-properties.md).

### PLO_LEVELCHEST (4) - Level Chest
**Trigger**: Player opens chest or enters level with chests
```
[GCHAR: opened]      // 1 = already opened by this account, 0 = unopened
[GCHAR: tile_x]      // Chest X coordinate (WHOLE tiles, 0-63)
[GCHAR: tile_y]      // Chest Y coordinate (WHOLE tiles, 0-63)
// present ONLY when opened == 0 (unopened chest announced on level entry):
[GCHAR: item_id]     // LevelItemType numeric id (see PLO_ITEMADD table)
[GCHAR: sign_index]  // associated sign index
```
**Two forms**:
- **3-byte form** (`opened == 1`): an already-opened chest, or the response to the player
  opening a chest. No trailing item/sign.
- **5-byte form** (`opened == 0`): an unopened chest announced on level entry, carrying the
  reward `item_id` and `sign_index`.

> Coordinates are **whole tiles**, not half-tiles. `PLI_OPENCHEST` must echo the same
> whole-tile coordinates. Otherwise, the server will not match the chest.

### PLO_LEVELSIGN (5) - Level Sign
**Trigger**: Player enters level with signs
```
[GCHAR: tile_x]      // Sign X coordinate (WHOLE tiles, 0-63)
[GCHAR: tile_y]      // Sign Y coordinate (WHOLE tiles, 0-63)
[ENCODED_TEXT...]    // Reborn sign-encoded text, to end of packet (NOT plain ASCII!)
```

> ⚠️ **The sign text is NOT plain ASCII.** The server encodes it with a custom alphabet and a
> button-symbol escape table (`encodeSign`/`decodeSign` in GServer `LevelSign.cpp`). Each
> encoded byte is `alphabet_index + 32` (a GCHAR). Reading it as a raw string gives
> garbage.

**Decoding**: For each byte, use `code = byte - 32`. If `code` is in the symbol code-table
(`ctab`), emit `#` followed by the mapped button symbol. Otherwise, emit
`signAlphabet[code]`. The decoder removes literal `#K` (code 13) sequences.

**Sign alphabet** (`signText`, verbatim — index 0 = 'A'):
```
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?-.,#>()#####"####':/~&### <####;\n
```

**Button-symbol escape tables**:
```
signSymbols = "ABXYudlrhxyz#4."
ctablen     = {1,1,1,1,1,1,1,1,2,1,1,1,2,2,1}
ctabindex   = {0,1,2,3,4,5,6,7,8,10,11,12,13,15,17}
ctab        = {91,92,93,94,77,78,79,80,74,75,71,72,73,86,86,87,88,67}
```
`signSymbols` are controller/keyboard glyphs (A/B/X/Y buttons, u/d/l/r dpad, etc.).

### PLO_LEVELNAME (6) - Level Name
**Trigger**: Player enters level
```
[STRING: level_name] // Current level name
```

### PLO_BOARDMODIFY (7) - Board Modification
**Trigger**: Another player modifies tiles, or a script/server-initiated board change is
replayed to a player entering a non-gmap level (see
[Version-Gated Behavior](version-gated-behavior.md#level-entry-replay-path-sublevel-sendboardchangestoplayer-version-check-is-live)).
```
[GCHAR: start_x]     // Starting X coordinate (0-63)
[GCHAR: start_y]     // Starting Y coordinate (0-63)
[GCHAR: width]       // Modification width
[GCHAR: height]      // Modification height
[GSHORT: tile]...    // width*height tiles, one GSHORT each (row-major)
```
**Layer-prefixed variant**: script/server board changes (not plain client tile edits) may
prefix the packet with a 5th leading byte: if the first byte read is **>= 64**, it encodes
`layer + 64` and everything above shifts one field later. `LevelBoardChange::
getPropsForSingleLevel` (`LevelBoardChange.cpp:72-80`) is the server-side builder for both
the plain-edit relay (`msgPLI_BOARDMODIFY`'s echo to other players) and the layered form.
A plain player edit never sets the layer prefix.

**Source**: `LevelBoardChange.cpp:72-80` (build), `Level::alterBoard` (`Level.cpp:1476`,
tiles read via `readGShort()`).

### PLO_BOARDMODIFY2 (186) - Board Modification (GMAP / Map-Position Form)
**Trigger**: Board change broadcast on a gmap, or replayed to a player entering a level
whose version puts it in the "classic" replay style (see
[Version-Gated Behavior](version-gated-behavior.md#board-changes-two-different-code-paths-only-one-is-live)).
```
[GCHAR: mapX]        // GMAP segment column (0,0 for non-gmap levels)
[GCHAR: mapY]        // GMAP segment row
[GCHAR: start_x]     // Starting X coordinate (0-63)
[GCHAR: start_y]     // Starting Y coordinate (0-63)
[GCHAR: width]       // Modification width
[GCHAR: height]      // Modification height
[GSHORT: tile]...    // width*height tiles, one GSHORT each (row-major)
```
**Source**: `LevelBoardChange::getPropsForMapClassic` (`LevelBoardChange.cpp:82-94`).
`mapX`/`mapY` are always present, even for non-gmap levels (where they resolve to `0,0`),
because `LevelBoardChange` objects always carry an explicit `MapPosition`. A commented-out
`getPropsForMapNewMain()` sibling (`LevelBoardChange.cpp:97-104`) exists in source but is
**dead code**. The server never calls it or compiles it into the live send path. Do not implement
against it.

### PLO_OTHERPLPROPS (8) - Other Player Properties
**Trigger**: Other player's properties change
```
[GUSHORT: player_id] // Player identifier
[PROPERTY_DATA...]   // Player property updates
```

### PLO_PLAYERPROPS (9) - Own Player Properties  
**Trigger**: Own player's properties change
```
[PROPERTY_DATA...]   // Player property updates
```

### PLO_ISLEADER (10) - Level Leader Status
**Trigger**: Player becomes level leader
```
// No additional data
```

### PLO_BOMBADD (11) - Bomb Added
**Trigger**: Player places bomb
```
[GUSHORT: player_id] // Player who placed bomb
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
[GCHAR: power]       // Bomb power
[GCHAR: timer]       // Time to explosion
```

### PLO_BOMBDEL (12) - Bomb Removed
**Trigger**: Bomb explodes or is removed
```
[GUSHORT: player_id] // Player who placed bomb
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
```

### PLO_TOALL (13) - Chat Message
**Trigger**: Player sends public chat
```
[GUSHORT: player_id] // Sender player ID
[STRING: message]    // Chat message
```

### PLO_PLAYERWARP (14) - Player Warp
**Trigger**: Player warps to new location
```
[GCHAR: pixel_x]     // New X position (pixels/2)
[GCHAR: pixel_y]     // New Y position (pixels/2)  
[STRING: level_name] // New level name
```

### PLO_WARPFAILED (15) - Warp Failed
**Trigger**: Player warp attempt fails
```
// No additional data - client returns to previous position
```

### PLO_DISCMESSAGE (16) - Disconnect Message
**Trigger**: The server disconnects the player
```
[STRING: reason]     // Disconnect reason
```

### PLO_HORSEADD (17) - Horse Added
**Trigger**: The server spawns a horse
```
[GUSHORT: player_id] // Player who added horse
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
[GCHAR: dir_bush]    // Direction + bush count
[STRING: image]      // Horse image
```

### PLO_HORSEDEL (18) - Horse Removed
**Trigger**: The server destroys a horse
```
[GUSHORT: player_id] // Player who removed horse
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
```

### PLO_ARROWADD (19) - Arrow Added
**Trigger**: Player fires arrow
```
[GUSHORT: player_id] // Player who fired
[GCHAR: tile_x]      // Starting X position
[GCHAR: tile_y]      // Starting Y position
[GCHAR: flags]       // Direction and flags
[GCHAR: sprite]      // Arrow sprite
[GCHAR: power]       // Arrow power
```

### PLO_FIRESPY (20) - Fire Spy
**Trigger**: Player uses fire spy
```
[GUSHORT: player_id] // Player who used fire spy
[GCHAR: length_power] // Length and power data
```

### PLO_THROWCARRIED (21) - Throw Carried Object
**Trigger**: Player throws carried object
```
[GUSHORT: player_id] // Player who threw object
```

### PLO_ITEMADD (22) - Item Added
**Trigger**: A player drops an item or the server spawns one
```
[GCHAR: x * 2]       // X position (half-tiles; tile = value/2)
[GCHAR: y * 2]       // Y position (half-tiles)
[GCHAR: item_id]     // NUMERIC LevelItemType id (0-24), NOT a length-prefixed string
```

> `item_id` is a single numeric byte. The `LevelItemType` table below maps it. It is
> **not** a string. (`PLI_ITEMADD (12)` uses the same `[x*2][y*2][item_id]` layout.)

**LevelItemType table** (`LevelItem.h`, index = id):

| id | name | id | name | id | name |
|----|------|----|------|----|------|
| 0 | greenrupee | 9 | shield | 18 | lizardsword |
| 1 | bluerupee | 10 | sword | 19 | goldrupee |
| 2 | redrupee | 11 | fullheart | 20 | fireball |
| 3 | bombs | 12 | superbomb | 21 | fireblast |
| 4 | darts | 13 | battleaxe | 22 | nukeshot |
| 5 | heart | 14 | goldensword | 23 | joltbomb |
| 6 | glove1 | 15 | mirrorshield | 24 | spinattack |
| 7 | bow | 16 | glove2 | | |
| 8 | bomb | 17 | lizardshield | | |

### PLO_ITEMDEL (23) - Item Removed
**Trigger**: A player picks up an item or the server destroys one
```
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
```

### PLO_NPCMOVED (24) - NPC Moved (Level Change)
**Trigger**: An NPC's `CURLEVEL` property changes (the NPC warps to a different level)
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[GCHAR: x / 8]        // NPC's OLD position in the level it's leaving, in half-tiles
[GCHAR: y / 8]        // (captured BEFORE removal from the old level)
[STRING: new_level]   // The NEW level name being warped to, to end of packet
```
> The previous version of this document incorrectly specified a bare `[GUINT: npc_id]`.
> The packet carries the NPC's old position and the destination level name.

**Source**: `NPC::setPropWith`, case `NPCProp::CURLEVEL` (`object/NPC.cpp:1337-1355`):
```cpp
>> (int)id >> (char)(localPosition.x()/8) >> (char)(localPosition.y()/8) << strProp->value
```
Here, `localPosition` is the position in the level that the NPC leaves. The server captures
it before removal. The server assigns the new level name in `strProp->value`.

### PLO_SIGNATURE (25) - Player Signature
**Trigger**: Player requests signature verification
```
[STRING: signature]  // Player signature data
```

### PLO_NPCSETSCRIPT (26) - NPC Action
**Trigger**: NPC performs action
```
[GUINT: npc_id]      // NPC identifier
[ACTION_DATA...]     // Action-specific data
```

### PLO_BADDYHURT (27) - Baddy Hurt
**Trigger**: Baddy takes damage
```
[GCHAR: baddy_id]    // Baddy identifier
[GCHAR: damage]      // Damage amount
```

### PLO_FLAGSET (28) - Flag Set
**Trigger**: Server or player sets a flag
```
[STRING: flag_data]  // "flag_name=value" format
```

### PLO_NPCDEL (29) - NPC Deleted
**Trigger**: The server removes an NPC from the level
```
[GUINT: npc_id]      // NPC identifier
```

### PLO_FILESENDFAILED (30) - File Send Failed
**Trigger**: Requested file could not be sent
```
[STRING: filename]   // Failed file name
```

### PLO_FLAGDEL (31) - Flag Deleted
**Trigger**: The server removes a flag
```
[STRING: flag_name]  // Flag name to delete
```

### PLO_SHOWIMG (32) - Show Image
**Trigger**: Player displays image
```
[GUSHORT: player_id] // Player showing image
[IMAGE_DATA...]      // Image display data
```

### PLO_NPCWEAPONADD (33) - NPC Weapon Added
**Trigger**: Player gains weapon from NPC
```
[GCHAR: name_len]    // Weapon name length
[STRING: name]       // Weapon name
[GCHAR: type]        // Weapon type (0=client-side, 1=server-side)
[GCHAR: image_len]   // Image name length
[STRING: image]      // Weapon image
[GCHAR: script_type] // Script type flag
[GUSHORT: script_len] // Script length
[STRING: script]     // Weapon script
```

### PLO_NPCWEAPONDEL (34) - NPC Weapon Deleted
**Trigger**: The server removes a weapon from the player
```
[STRING: weapon_name] // Weapon to remove
```

### PLO_RC_ADMINMESSAGE (35) - Admin Message
**Trigger**: Server sends admin message
```
[STRING: message]    // Admin message text
```

### PLO_EXPLOSION (36) - Explosion
**Trigger**: Explosion occurs
```
[GUSHORT: player_id] // Player who caused explosion
[GCHAR: radius]      // Explosion radius
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
[GCHAR: power]       // Explosion power
```

### PLO_PRIVATEMESSAGE (37) - Private Message
**Trigger**: Player receives PM
```
[GSHORT: from_id]    // Sender player ID (reborn short — ((b1-32)<<7)|(b2-32), NOT raw big-endian)
[CSV body...]        // toCSV: "","Private message:",<msg>   (or "Mass message:")
```

> There are two important details. First, `from_id` is a **GSHORT** (reborn-encoded), not
> a raw 16-bit big-endian value. If you decode it as `(b0<<8)|b1`, you get incorrect IDs.
> Second, the body is a quoted-CSV structure (`"<sender>","Private message:",<msg>`), not
> a bare message string.

### PLO_PUSHAWAY (38) - Push Away
**Trigger**: A force pushes the player
```
[PUSH_DATA...]       // Push force and direction data
```

### PLO_LEVELMODTIME (39) - Level Modification Time
**Trigger**: A client requests the level modification time
```
[GUINT5: mod_time]   // Level modification timestamp
```

### PLO_HURTPLAYER (40) - Hurt Player
**Trigger**: Player takes damage
```
[GSHORT: attacker_id] // Attacking player ID (0 for environment/self)
[GCHAR: hurt_dx]      // Knockback X direction
[GCHAR: hurt_dy]      // Knockback Y direction
[GCHAR: power]        // Damage in HALF-HEARTS
[GINT3: npc_id]       // NPC ID (3 bytes — NOT 4) if NPC caused the damage
```

> **The server is a pure relay for PvP.** It forwards `PLO_HURTPLAYER` to the victim. The
> victim's client decrements its own `CURPOWER` and rebroadcasts. `power` is in half-hearts.
> `PLI_HURTPLAYER (26)` has the identical field layout (with `victim_id` instead of
> `attacker_id`), `npc_id` also a **GINT3 (3 bytes)**.

### PLO_NEWWORLDTIME (42) - New World Time
**Trigger**: Server updates world time
```
[GCHAR: time_data]   // World time information
```

### PLO_DEFAULTWEAPON (43) - Default Weapon
**Trigger**: Player gains default weapon
```
[GCHAR: weapon_type] // Default weapon type (0-5)
```

### PLO_HASNPCSERVER (44) - Has NPC Server
**Trigger**: Server indicates NPC-Server presence
```
// No additional data - informs client not to update NPC props
```

### PLO_FILEUPTODATE (45) - File Up To Date
**Trigger**: Requested file is current
```
[STRING: filename]   // Current file name
```

### PLO_HITOBJECTS (46) - Hit Objects
**Trigger**: Weapon hits objects/NPCs
```
[GUSHORT: player_id] // Player who hit (0 for NPC)
[GCHAR: power]       // Hit power
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
[GUINT: npc_id]      // NPC ID (if NPC hit)
```

### PLO_STAFFGUILDS (47) - Staff Guilds
**Trigger**: Server sends staff guild information
```
[STRING: guild_data] // Staff guild information
```

### PLO_TRIGGERACTION (48) - Trigger Action
**Trigger**: The server runs a trigger action
```
[GUSHORT: player_id] // Player who triggered
[ACTION_DATA...]     // Action data
```

### PLO_PLAYERWARP2 (49) - Player Warp v2
**Trigger**: Player warps with GMAP coordinates
```
[GCHAR: x]           // X position (half-tiles, x*2)
[GCHAR: y]           // Y position (half-tiles)
[GCHAR: z]           // Z position (serialized)
[GCHAR: gmap_x]      // GMAP segment column (mapPosition.x())
[GCHAR: gmap_y]      // GMAP segment row (mapPosition.y())
[STRING: level_name] // Target level/gmap name, to end of packet — DON'T forget this field
```

> The trailing level name (e.g. `"chicken.gmap"`) is easy to miss. The server appends
> `<< level->levelName` after `gmap_y`. Several parsers stopped at `gmap_y` and dropped it.

### PLO_ADDPLAYER (55) - Add Player (Legacy)
**Trigger**: Player joins server (pre-v5.07)
```
[PLAYER_DATA...]     // Player information
```

### PLO_DELPLAYER (56) - Delete Player (Legacy)
**Trigger**: Player leaves server (pre-v5.07)
```
[GUSHORT: player_id] // Player who left
```

### PLO_LARGEFILESTART (68) - Large File Start
**Trigger**: The server starts a large file transfer (file > 32000 bytes)
```
[STRING: filename]   // File being transferred (raw, to end of packet)
```

> The total size is **not** in this packet. It arrives separately as `PLO_LARGEFILESIZE (84)`.
> Full chunked sequence for a large file:
> ```
> PLO_LARGEFILESTART (68): [filename]
> PLO_LARGEFILESIZE  (84): [GINT5 total_size]
>   ...then per 32000-byte chunk:
>   PLO_RAWDATA (100): [GINT3 chunk_packet_len]
>   PLO_FILE    (102): [GINT5 modtime][GCHAR name_len][name][chunk_data][0x0A]
> PLO_LARGEFILEEND   (69): [filename]
> ```

### PLO_LARGEFILEEND (69) - Large File End
**Trigger**: Large file transfer completes
```
[STRING: filename]   // Completed file name (raw, to end of packet)
```

### PLO_RC_CHAT (74) - RC Chat
**Trigger**: RC client chat message
```
[STRING: message]    // RC chat message
```

### PLO_PROFILE (75) - Player Profile
**Trigger**: Profile information response
```
[STRING: profile_data] // Player profile data
```

### PLO_SERVERTEXT (82) - Server Text Response
**Trigger**: Response to PLI_REQUESTTEXT/PLI_SENDTEXT
```
[STRING: response]   // Server text response
```

### PLO_LARGEFILESIZE (84) - Large File Size
**Trigger**: Large file size notification
```
[GUINT5: file_size]  // File size in bytes
```

### PLO_RAWDATA (100) - Raw Data
**Trigger**: Raw binary data transfer
```
[GINT3: data_length] // Length of raw data
[RAW_DATA...]        // Raw binary data
```

### PLO_BOARDPACKET (101) - Full Board (8192 bytes)
**Trigger**: Player enters a level — the full tile board is sent here.
```
[8192 bytes tile_data]   // 64×64 tiles, 2 bytes per tile (little-endian)
```
The server sends this **raw 8192-byte board dump** as raw data. It sends the dump
immediately after a **PLO_RAWDATA (100)** packet that announces the byte count. A client
usually receives a level's tiles this way, not through PLO_LEVELBOARD.

### PLO_FILE (102) - File Data
**Trigger**: File content transfer (small files, ≤ 32000 bytes)

The server sends a file as **two packets**. A `PLO_RAWDATA (100)` announces the byte count
of the *following* packet. The `PLO_FILE (102)` packet follows it.

```
[GINT5: modtime]     // 5 bytes — file modification time (operator>>(long long))
[GCHAR: name_len]    // 1 byte
[name]               // name_len raw bytes
[file_data]          // raw file bytes
[0x0A]               // single trailing newline
```

> The document previously specified `[GCHAR file_type][GUINT5 file_size][data]`. That
> specification is incorrect. There is no "file type" byte and no inline size. The
> preceding `PLO_RAWDATA` supplies the size. A `GINT5 modtime` precedes a
> GCHAR-length-prefixed name.
>
> The announced `PLO_RAWDATA` length = `1 (file id byte) + 5 (modtime) + 1 + name_len +
> data_len + 1 (trailing \n)`.
>
> **Double-strip trap:** the raw-data framing layer already strips the trailing `\n`. Do
> **not** strip it a second time when parsing the file body, or files ending in `0x0A` come
> out truncated.
>
> **Pre-2.1 client variant:** This variant has no `modtime` field. It uses
> `[GCHAR name_len][name][data]`, has no trailing newline, and has a correspondingly
> smaller RAWDATA length.

> **Historical parser trap** (found and fixed during this audit): the `modtime` field is a
> **7-bit-per-byte GINT5** (`CString::writeGInt5`), not five 8-bit bytes. An earlier
> pyReborn `parse_file` decoded it with an 8-bit shift (`mod_time = (mod_time << 8) | b`),
> producing garbage timestamps while leaving filename/data offsets intact. Byte
> consumption is 5 bytes either way, so the bug was invisible except in the decoded value.
> Fixed in the current `parse_file` (`pyReborn/pyreborn/packet_codec/files.py:11`, which now
> carries its own warning comment). GINT5 is always 7-bit-per-byte. The C++ code is the
> ground truth.

### PLO_UPDATEPACKAGESIZE (105) - Update Package Size
**Trigger**: Update package download size
```
[GCHAR: name_len]    // Package name length
[STRING: package]    // Package name
[GUINT5: total_size] // Total download size
```

### PLO_UPDATEPACKAGEDONE (106) - Update Package Done
**Trigger**: Update package download complete
```
[STRING: package]    // Completed package name
```

### PLO_BOARDLAYER (107) - Board Layer
**Trigger**: Additional level layer data
```
[GCHAR: layer_id]    // Layer identifier
[LAYER_DATA...]      // Layer tile data
```

### PLO_NPCBYTECODE (131) - NPC Bytecode
**Trigger**: Sent automatically alongside `PLO_NPCPROPS` on level entry for clients
`>= CLVER_4_0211` when the NPC has compiled GS2 bytecode. Wrapped in raw-data framing: a
`PLO_RAWDATA (100)` announcing the byte count precedes it.
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[BYTECODE...]        // Raw compiled GS2 bytecode, to end of packet
```
**Source**: `Level::sendNPCsToPlayer` (`level/Level.cpp:1352-1358`):
```cpp
if (player->getVersion() >= CLVER_4_0211 && !npc->getScript().getClientByteCode().empty())
{
    CString byteCodePacket = CString() >> (char)PLO_NPCBYTECODE >> (int)npc->id;
    byteCodePacket.write(/* raw bytecode */);
    player->sendPacket(CString() >> (char)PLO_RAWDATA >> (int)byteCodePacket.length());
    player->sendPacket(byteCodePacket);
}
```
(`>> (int)` is `writeGInt`, a **3-byte** GINT3, `CString.cpp:1671`.) These implementations
validate the bytes: pyReborn `parse_npc_bytecode` (`packets.py`) and
`game_tester/tier5_tests.py:test_npc_bytecode_synthetic`.

### PLO_GANISCRIPT (134) - GANI Bytecode
**Trigger**: Response to `PLI_UPDATEGANI (157)` when the client's CRC32 differs from the
server's current gani bytecode. Wrapped in `PLO_RAWDATA` framing.
```
[GCHAR: name_len]    // Gani name length
[gani_name]          // WITHOUT the .gani suffix
[BYTECODE...]        // Compiled gani-script bytecode, to end of packet
```
**Source**: `GameAni::getBytecodePacket` (`animation/GameAni.cpp:107-122`). The server
strips a trailing `.gani` from the stored name before sending. Always followed by a
`PLO_LOADGANI (195)` load command (sent regardless of whether the bytecode itself was
sent again (`msgPLI_UPDATEGANI`, `PlayerClientPackets.cpp:1460-1483`).

### PLO_WEAPONBYTECODE2 (140) - Weapon Bytecode
**Trigger**: Response to `PLI_UPDATESCRIPT (158)` (on-demand weapon-bytecode fetch), and
also the server's fallback answer to a `PLI_UPDATECLASS` for a **nonexistent** class.
The fallback has only a header and empty bytecode. This is a deliberate workaround.
```
[GSHORT: header_len] // Length of the header CSV
[header CSV]         // "weapon,<name>,1,<desKey>"  (quoted-CSV; no CRC in THIS header)
[BYTECODE...]        // Compiled GS2 bytecode, to end of packet (MAY be empty)
```
**Source**: `Weapon::sendByteCodeToPlayer` (`object/Weapon.cpp:299-308`). The header CSV is
Reborn quoted-CSV (`toCSV`): `weapon,<name>,1,<desKey>` where `<desKey>` is a 64-bit script
hash packed as two GINT5s (`Weapon.cpp:230-252`). This is `m_header` **without** the
CRC32. The server sends the CRC-bearing variant (`m_headerWithCRC`) in `PLO_LOADSCRIPT (197)`
instead. The unknown-class fallback (`msgPLI_UPDATECLASS`, `PlayerClientPackets.cpp:
1515-1528`) sends a `class,<name>,1,...` header with **empty bytecode**. The code comments
it "should technically be PLO_LOADSCRIPT" but the client breaks `player.join()` scripts if
a missing class arrives that way. Parsers must accept an empty bytecode tail.

### PLO_NPCDEL2 (150) - NPC Delete v2
**Trigger**: NPC removed from specific level
```
[GCHAR: level_len]   // Level name length
[STRING: level_name] // Level name
[GINT3: npc_id]      // NPC identifier
```

### PLO_HIDENPCS (151) - Hide NPCs
**Trigger**: NPCs should be hidden
```
// No additional data
```

### PLO_SAY2 (153) - Say/Sign Text
**Trigger**: Display text/sign content
```
[STRING: text]       // Text to display
```

### PLO_FREEZEPLAYER2 (154) - Freeze Player
**Trigger**: Player movement is frozen
```
// No additional data
```

### PLO_UNFREEZEPLAYER (155) - Unfreeze Player
**Trigger**: Player movement is restored
```
// No additional data
```

### PLO_SETACTIVELEVEL (156) - Set Active Level
**Trigger**: Set level for receiving objects
```
[STRING: level_name] // Active level name
```

### PLO_MOVE (165) - NPC Move Command (v1, < CLVER_2_3)
**Trigger**: Server-driven NPC movement for clients below `CLVER_2_3`. See
[Version-Gated Behavior](version-gated-behavior.md#npc-movement-plo_move-vs-plo_move2) and
its `PLO_MOVE2 (189)` counterpart above. Built from `NPC.cpp:441` (`move1`, the legacy
sibling of `getMoveQueuePacketData`'s `result.second`/`move2` form). This document does
not independently derive the exact `move1` field layout. It documents only the confirmed
version gate and send site. `IEnums.h` has a maintainer comment: `// Unhandled by 6.037.`
```
[MOVEMENT_DATA...]   // Format not documented here (see note above)
```

### PLO_GHOSTMODE (170) - Ghost Mode
**Trigger**: Player enters/exits ghost mode
```
[GCHAR: ghost_state] // 1=enter ghost, 0=exit ghost
```

### PLO_MINIMAP (172) - Minimap Data
**Trigger**: Minimap information
```
[STRING: minimap_file] // Minimap image file
[GCHAR: offset_x]      // Map offset X
[GCHAR: offset_y]      // Map offset Y
```

### PLO_GHOSTTEXT (173) - Ghost Text
**Trigger**: Text display in ghost mode
```
[STRING: text]       // Ghost mode text
```

### PLO_GHOSTICON (174) - Ghost Icon
**Trigger**: Ghost mode icon state
```
[GCHAR: icon_state]  // 1=show icon, 0=hide icon
```

### PLO_SHOOT (175) - Shoot Projectile (v1, < CLVER_5_07)
**Trigger**: Projectile broadcast to clients below `CLVER_5_07`. See
[Version-Gated Behavior](version-gated-behavior.md#projectiles-plo_shoot-vs-plo_shoot2).
The server builds the packet with `newPacket.constructShootV1()`
(`Server.cpp:2283-2292`) and prefixes it with `[GSHORT: owner_id]`. This document does
not independently derive the exact `constructShootV1()` field layout. `IEnums.h` has
this comment: `// Unhandled by 6.037.`
```
[GSHORT: owner_id]
[SHOOT_DATA...]      // constructShootV1() body — format not documented here
```

### PLO_DISABLECLASSICMODE (176) - Disable Classic Mode
**Trigger**: The server tells the client to turn off old client-side mechanics.
`Player.cpp:701` sends it once, unconditionally, to every login-server client.
```
// No additional data
```

Older sources call packet 176 `PLO_FULLSTOP`. That name and the
freeze-input-and-hide-HUD behavior belong to packet **177**. Do not freeze the
client on 176, because every login-server connection receives it.

### PLO_FULLSTOP2 (177) - Full Stop
**Trigger**: The client stops responding to normal input and hides the HUD.
Clients 5.07 and later do not handle it.
```
// No additional data
```

### PLO_SERVERWARP (178) - Server Warp
**Trigger**: Warp to different server
```
[STRING: server_info] // gtokenized text, read to end: name,name,host,port[,...]
```
The reference server does not build this packet. It relays the list server's
`SVO_SERVERINFO` text verbatim, and only to a client whose version is 2.1 or later
(`ServerList.cpp:966-975` at GServer-v2 beta4). The open list server builds that text as
`name`, `name`, `ip`, `port` joined with `gtokenize()`
(`graal-serverlist/server/src/ServerConnection.cpp:1345-1346`). So the fields are
gtokenized (a field with a space, comma, slash or non-ASCII byte is quoted; pinned gs2lib
`src/CString.cpp:1220-1227`), and field 0 repeats the server name.
The decompiled reference client needs more than three fields and uses field 1 as the
name, field 2 as the host and field 3 as the port (`TServerList.cpp:131-170`).

The following is reported in squirelworks' client-analysis notes (`protocol/packet-ids.md`,
`protocol/v5v6-lab-play.md`) and is not verified against the reference. The 2.31 client
also needs at least four comma fields and does not use field 0. A lab test with a real 2.31
client showed that it closes the connection and logs in again to the new host with a fresh
login, with no list-server step. While a 4.x-6.x client is connected to a server whose name starts with
"login", it draws no characters and no HUD. A `PLO_SERVERWARP` to a server with another
name ends that mode.

### PLO_RPGWINDOW (179) - RPG Window
**Trigger**: Display RPG-style window
```
[WINDOW_DATA...]     // RPG window content
```

### PLO_STATUSLIST (180) - Status List
**Trigger**: Player status information
```
[STATUS_DATA...]     // Status list data
```

### PLO_LISTPROCESSES (182) - List Processes
**Trigger**: Request client process list
```
// No additional data - client responds with process list
```

### PLO_BOARDHEIGHTS (185) - Board Height Layer
**Trigger**: The server sends this packet when it delivers a level with a height layer to a player.
```
[GCHAR: mapX]         // GMAP segment column (0 for non-gmap)
[GCHAR: mapY]         // GMAP segment row (0 for non-gmap)
[GCHAR: blockX]       // Height-block origin X (server always sends 0)
[GCHAR: blockY]       // Height-block origin Y (server always sends 0)
[GCHAR: blockW]       // Height-block width (server always sends 8)
[GCHAR: blockH]       // Height-block height (server always sends 8)
[(blockW+1)*(blockH+1) entries, row-major (index = y*9+x for the default 8x8 block):]
  [GCHAR: whole + 50]  // Integer height part, biased by +50
  [GCHAR: frac * 128]  // Fractional height part, scaled by 128
```
**Source**: `SubLevel::sendBoardHeightsToPlayer` (`level/Level.cpp:437-474`). The block
size is currently always the fixed `0,0` origin / `8,8` extent (a 9×9 grid of height
samples), giving `(8+1)*(8+1) = 81` height-value pairs after the 6-byte header.

### PLO_UPDATEPACKAGEISUPDATED (187) - Package Updated
**Trigger**: Notify client of package update
```
[STRING: filename]   // Updated file name
```

### PLO_MOVE2 (189) - NPC Move Command (v2, >= CLVER_2_3)
**Trigger**: Server-driven NPC movement (`move`/`movexy` GS scripting) for clients at or
above `CLVER_2_3`. See
[Version-Gated Behavior](version-gated-behavior.md#npc-movement-plo_move-vs-plo_move2)
for the `PLO_MOVE`/`PLO_MOVE2` version split.
```
[GINT3: npc_id]      // NPC identifier (3 bytes, NOT GUINT)
[GSHORT: pos_x]       // Target X, X2/Y2-style pixel-coord encoding (see below)
[GSHORT: pos_y]       // Target Y, same encoding
[GSHORT: dx]           // X delta, same encoding
[GSHORT: dy]           // Y delta, same encoding
[GSHORT: time_50ms]   // Duration of the move, in 0.05s ticks
[GCHAR: options]      // Movement option flags
```
Each `GSHORT` coordinate/delta field uses the same encoding as player `X2`/`Y2` properties
(`PropertyPixelCoordinate::serialize`, `PropertySerializers.cpp:375-381`):
`value = (abs(pixels) << 1) | (negative ? 1 : 0)`. See
[Data Types: X2/Y2 Encoding](data-types.md#x2y2-encoding-the-weird-one) for the decode.

**Source**: `NPC::getMoveQueuePacketData` (`object/NPC.cpp:381-429`, the `result.second`
form), sent via `NPC::sendMoveQueueToLevel`/`sendMoveQueueToPlayer` (`NPC.cpp:443,460`).

### PLO_SHOOT2 (191) - Shoot Projectile (v2, >= CLVER_5_07)
**Trigger**: Projectile broadcast to clients at or above `CLVER_5_07`. See
[Version-Gated Behavior](version-gated-behavior.md#projectiles-plo_shoot-vs-plo_shoot2).
The server builds the packet with `newPacket.constructShootV2()`
(`Server.cpp:2283-2292`) and prefixes it with `[GSHORT: owner_id]`. This document does
not independently derive the exact `constructShootV2()` field layout. `IEnums.h` has
this comment: "Valid message in 5.07 and 6.037. The code it uses is unique."
```
[GSHORT: owner_id]
[SHOOT_DATA...]      // constructShootV2() body — format not documented here
```

### PLO_RESETCLIENT (194) - Clear Weapons
**Trigger**: Remove all weapons from player
```
// No additional data - clears weapon list
```

### PLO_LOADGANI (195) - Load GANI
**Trigger**: Always sent in response to `PLI_UPDATEGANI (157)` (after the optional
`PLO_GANISCRIPT` bytecode refresh), telling the client to activate the gani.
```
[GCHAR: name_len]    // GANI name length
[gani_name]          // GANI name (no .gani suffix)
[stringlist]         // Reborn quoted-CSV, e.g. "SETBACKTO idle" — to end of packet
```
> The packet ID is **195**, not 253 as an earlier revision of this page specified
> (`IEnums.h:316`). The trailing stringlist currently carries only the `SETBACKTO`
> directive but is a general quoted-CSV list.

**Source**: `msgPLI_UPDATEGANI` (`PlayerClientPackets.cpp:1481`):
```cpp
sendPacket(CString() >> (char)PLO_LOADGANI >> (char)gani.length() << gani << "\"SETBACKTO " << findAni->getSetBackTo() << "\"");
```

### PLO_LOADSCRIPT (197) - Load Script (TWO payload forms)
**Trigger**: (a) weapon-header announcement during weapon registration. (b) class-bytecode
delivery in response to `PLI_UPDATECLASS (161)` through `PLO_RAWDATA` framing.

**Form 1 — weapon announcement** (`Weapon::registerWeaponWithPlayer`, `object/Weapon.cpp:295`):
```
[header CSV]         // RAW, no length prefix, no bytecode — to end of packet
                     // "weapon,<name>,1,<desKey>,<crc32>"  (m_headerWithCRC)
```

**Form 2 — class bytecode** (`ScriptClass::getClassPacket`, `scripting/ScriptClass.cpp:66-77`):
```
[GCHAR: header_len]  // Length of the header CSV
[header CSV]         // "class,<name>,1,<desKey>,<crc32>"
[BYTECODE...]        // Compiled GS2 bytecode, to end of packet
```

**Disambiguation** (as implemented in pyReborn `parse_loadscript`): form 1 is pure CSV text
whose payload starts with a known script-type name (`weapon,`/`npc,`/`class,`/`gani,`).
Form 2's first byte is a small GCHAR length. Check for a leading known-type prefix first.
If there is no such prefix, use the length-prefixed read. Header fields:
`type,name,saveToDisk[0/1],desKey
(two GINT5s = 64-bit hash),crc32 (GINT5)` per the `IEnums.h:317` comment and
`Weapon.cpp:242-257` / `ScriptClass.cpp:44-54` header construction.

## Ids Whose Layout Comes from the Reference Enum Comments and Client Observation

The pinned gs2lib (`include/IEnums.h`) names each id below and gives its layout in the
enum comment. The reference server sends few of them and handles none of the client ids
in game sessions. The "Layout" column follows the enum comment. Detail beyond the comment,
the "Clients" column and the "What the client does" column are observations: static reads
of the original clients, reported in squirelworks' client-analysis notes
(`protocol/unknown-ids-2026-11-06.md`, `client-internals/serveroptions-198.md`); not
verified against the reference unless a citation is given. `c` = GCHAR, `s` = GSHORT,
`i5` = GINT5, `str` = GCHAR length + bytes. The decompiled reference client is under
`Preagonal/FourPlay/quattroplay/src/`.

| Id | Reference name (`IEnums.h`) | Layout | Clients (observed) | What the client does |
|---|---|---|---|---|
| PLI 25 | `PLI_TOWEAPON` (`:57`) | `str name`, `str image`, `s scriptLength`, script (`{GSTRING name}{GSTRING image}{GSHORT scriptLength}{STRING script}`). Unlike `PLO_NPCWEAPONADD` it has no prop-id bytes between the fields (compare `Weapon.cpp:176-182`) | 1.21 to 1.37 (also in the enum comment) | Uploads each weapon the player holds. 1.38 replaced it with `PLI_WEAPONADD (33)`. GServer-v2 beta4 has no handler: it logs "Unknown Player Packet" and disconnects after the third invalid packet within a minute (`Player.cpp:1657-1674`, counter reset `PlayerClient.cpp:276-280`). A lab test saw beta4 drop a 1.33 client for it |
| PLO 104 | `PLO_FILEDECRYPTKEY` (`:258`) | `str filename`, `c keyPurpose`, `i5 lo`, `i5 hi` | 3.153 to 6.03r7 | Stores an 8-byte DES key (`lo`, `hi` little-endian) for the package or file with that name. The enum comment gives purpose 0 = `.gpake`, 1 = `.enc`. The decompiled client parses the same layout (`TClient.cpp:5100-5125`, little-endian key at `:4852-4861`). The server never sends it |
| PLO 108 | `PLO_PING` (`:262`) | `c sub`, `s value` | 4.20, 6.01, 6.03 (not 5.x) | `sub` 0: the client answers `PLI 162` with `!` + `s min(value, 0x6FFF)`. `sub` 1: the client stores `value`. Handled before the main dispatch, like 100. The decompiled client does the same (`TClient.cpp:1994-2021`, `:935-957`). The server never sends it |
| PLI 162 | `PLI_PONG` (`:162`) | `c type`, `s value`. Game clients send type 1 (`!`) on a reply to 108. RC3: empty | as above | The answer to PLO 108. RC3 and the 2010 Linux RC send it empty every 60 s. The server handles it only for RC, as a stub (`PlayerRC.cpp:86`, `packets/PlayerRCPackets.cpp:1608-1612`) |
| PLO 109 | `PLO_HTTPDOWNLOAD` (`:263`) | `i5 modtime`, `str localname`, `str url` | 5.24r4 to 6.03r7 | Downloads the URL over HTTP and stores it under the local name. The decompiled client parses the same layout (`TClient.cpp:5075-5098`). The server never sends it |
| PLO 168 | `PLO_ONLINEMODE` (`:289`) | empty | 2.05 to 6.03r7 | Sets a one-time flag on the local player. The server sends it after the login burst (`Player.cpp:762-763`) |
| PLO 181 | `PLO_PLAYERNOUDP` (`:302`) | `s player_id`, `c toggle` | 2.17 to 5.24r4 | Sets a boolean on that player to `toggle > 0`. The enum comment says the toggle removes the player from the "nearby" list that UDP peer-to-peer uses. The server never sends it |
| PLO 193 | `PLO_WEAPONHASH` (`:314`) | `i5 crc32`, rest = weapon name | 4.04r2 to 5.12 | Loads the cached `weblevels/weapons/<name>.code` if its zlib CRC32 matches. If not, the client asks for the script with `PLI_UPDATESCRIPT (158)`. The server sends it to clients before 5.07 (`Weapon.cpp:197-199`), and the value is the zlib CRC32 of the bytecode (`:352-353`) |
| PLO 198 | `PLO_SERVEROPTIONS` (`:318`) | `i5 value` | 5.24 / 6.00 beta and later | Stored, and not read anywhere up to 6.03. The server never sends it |

The reference names PLO 60, 81, 83 and 110 `PLO_UNHANDLED60`, `PLO_UNHANDLED81`,
`PLO_UNHANDLED83` and `PLO_UNHANDLED110` (`IEnums.h:229`, `:250`, `:252`, `:264`). The same
notes report that no client of any age handles them, and that includes the staff clients.

## Encryption Implementation Details

### ENCRYPT_GEN_5 Key Stream Generation

The GEN_5 encryption uses an XOR-based stream cipher:

```c++
class CEncryption {
    uint8_t m_key;           // Current encryption key
    uint32_t m_iterator;     // Iterator for key generation
    int32_t m_limit;         // Encryption byte limit
    uint32_t m_gen;          // Encryption generation (5)
    
    static const uint32_t ITERATOR_START[6] = {
        0, 0, 0x4A80B38, 0x481C622, 0x481C6A2, 0x12345678
    };
};

void decrypt(CString& buffer) {
    for (int i = 0; i < m_limit && i < buffer.length(); i++) {
        buffer[i] ^= (m_key + m_iterator++);
        m_iterator &= 0xFF;
    }
}
```

### Compression Integration

GEN_5 protocol supports multiple compression methods:

1. **COMPRESS_UNCOMPRESSED (0x02)**: No compression, 40-byte encryption limit
2. **COMPRESS_ZLIB (0x04)**: Zlib compression, 4096-byte encryption limit  
3. **COMPRESS_BZ2 (0x06)**: Bzip2 compression, 65536-byte encryption limit

The compression type sets the compression algorithm and the encryption limit.

### Packet Bundle Processing

```
Outgoing (Client → Server):
1. Create packet bundle with individual packets
2. Compress bundle using specified method
3. Prepend compression type byte
4. Encrypt first N bytes (based on compression type)
5. Send with 2-byte length prefix

Incoming (Server → Client):
1. Read 2-byte length prefix
2. Read bundle data
3. Extract compression type (first byte)
4. Decrypt first N bytes using key stream
5. Decompress using specified method
6. Parse individual packets (newline-separated)
```

This document describes the core packet structures that the Reborn protocol uses.
Implementations must use these exact formats for compatibility with existing servers
and clients.
