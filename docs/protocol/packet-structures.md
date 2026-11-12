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
- `UINT16 packet_size`: Size of the bundle data in bytes, **big-endian** (high byte first).
  For GEN_5 the size includes the compression-type byte.
- `PACKET_BUNDLE_DATA`: Encrypted/compressed packet bundle

### Bundle Processing (GEN_5 Protocol)

For the ENCRYPT_GEN_5 protocol:

1. **Bundle Structure**: `[UINT8: compression_type][ENCRYPTED_COMPRESSED_DATA]`
2. **Compression Types**:
   - `0x02`: COMPRESS_UNCOMPRESSED (no compression)
   - `0x04`: COMPRESS_ZLIB (zlib compression)
   - `0x06`: COMPRESS_BZ2 (bzip2 compression)

3. **Processing Order** (the same in both directions):
   - Sending: Compress data → Encrypt → Send
   - Receiving: Decrypt → Decompress

4. **Encryption**: Partial packet encryption using XOR-based stream cipher
   - Uses iterator-based key generation
   - Encryption limit depends on compression type

### Individual Packet Structure

Newlines (`\n`) separate the packets in each bundle. Raw data packets are the exception:

```
[GCHAR: packet_id][PACKET_DATA]\n
```

The id byte is GCHAR-encoded (id + 32); the reference reads it with `readGUChar()`, which
subtracts 32 (`server/include/network/IPacketHandler.h:337`).

Special case for raw data:
```
[GCHAR: PLO_RAWDATA (100) or PLI_RAWDATA (50)][GINT3: data_length]\n
[RAW_DATA_BYTES]     // exactly data_length bytes, newlines included
```
The length is a GINT3 (3 bytes), not a UINT32. See
[Data Types: GINT3](data-types.md#gint-gint3-three-bytes-same-energy).

## Data Encoding Types

The wire-format details for G-types, coordinate packing, and property widths live in
[Data Types](data-types.md). This page describes packet layouts. If a field width matters,
use the information at the link.

## Client-to-Server Packets (PLI_*)

### PLI_LEVELWARP (0) - Level Warp Request
**Trigger**: Player moves to a different level
```
[GCHAR: x]           // X coordinate (in half-tiles)
[GCHAR: y]           // Y coordinate (in half-tiles)
[STRING: level_name] // Target level name (reads to end of packet)
```

**GServer Implementation Notes** (`PlayerClient::msgPLI_LEVELWARP`,
`server/src/player/packets/PlayerClientPackets.cpp:52-107`):
- Coordinates are read as `pPacket.readGChar() * 8` into a local pixel position
  (`:59`). At 16 pixels per tile that makes each unit a half-tile. The handler has
  no permission check.
- Level name uses `pPacket.readString("")` which reads to end of packet
- If the warp fails, the handler warps the player back to its current level at its current
  position (`:92-97`). If that also fails, it warps to the configured unstick level and
  tile (`:98-104`). The handler itself writes no `PLO_WARPFAILED`, but the calls it makes do:
  `warp(string)` sends it when the level cannot be loaded (`PlayerClient.cpp:1211`), and
  `enterLevel` sends it, with `level->levelName`, when the level data cannot be sent
  (`PlayerClient.cpp:1294`).

**Variant**: PLI_LEVELWARPMOD (30) - includes modification time:
```
[GUINT5: mod_time]   // Level modification timestamp
[GCHAR: x]           // X coordinate (in half-tiles)
[GCHAR: y]           // Y coordinate (in half-tiles)
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
`server/src/level/Level.cpp:1610`, `tileData.readGShort()` per tile at `:1737`). The
data is **not** a raw opaque string. Each tile is a proper GSHORT. The server does **not
echo it to the sender**. See
[GServer Behavior: PLI_BOARDMODIFY Is Not Echoed](gserver-behavior.md#pli_boardmodify-is-not-echoed-to-the-sender).

One exception: when the `clientsidepushpull` option is on (default true, `server/include/Server.h:133`) and the change is a 4x4 push-pull
stone, `Level::alterBoard` rejects it and sends a `PLO_BOARDMODIFY` for the same area
back to the sender (`Level.cpp:1660-1664`).

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
[GINT3: npc_id]      // NPC identifier
[STRING: prop_data]  // NPC property data
```

### PLI_BOMBADD (4) - Place Bomb
**Trigger**: Player places a bomb
```
[GUCHAR: tile_x]           // X position (in half-tiles)
[GUCHAR: tile_y]           // Y position (in half-tiles)
[GUCHAR: player_power]     // Player ID (upper 6 bits) + Power (lower 2 bits)
[GUCHAR: time_to_explode]  // Timer in 0.05s increments; remaining time = (value + 1) * 50 ms
```
**Source**: `PlayerClient::msgPLI_BOMBADD` (`PlayerClientPackets.cpp:215-242`). The reference
computes `(readGUChar() * 50ms) + 50ms`. Its comment says a bomb takes 3 seconds, but the
client has already counted down to 2.75 s when it sends the packet
(`PlayerClientPackets.cpp:222-225`). So a value of 55 means 2.8 s remaining. The reference
defines no default value.

### PLI_BOMBDEL (5) - Remove Bomb
**Trigger**: Bomb explodes or is removed
```
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
```

### PLI_TOALL (6) - Chat Message
**Trigger**: Player sends public chat
```
[GUCHAR: message_len] // Length of the message
[STRING: message]     // Chat message text
```
**Source**: `Player::msgPLI_TOALL` (`server/src/player/Player.cpp:1759-1785`). The server
ignores the packet when the sender is jailed. **Reference quirk**: the server does not use
`message_len` as a length. `Player.cpp:1765` calls `readString(readGUChar())`; the unsigned
char becomes a `CString` holding its decimal text (gs2lib `CString.cpp:133-138`), and
`readString(const CString&)` (gs2lib `CString.cpp:272-291`) treats that text as a delimiter.
The server therefore reads the rest of the packet and cuts it at the first occurrence of the
length's decimal digits (a 5-character message loses everything from its first `5`; a message
that starts with those digits becomes empty). A client that sends the length byte plus the
text still works for any message that does not contain those digits. It relays
`PLO_TOALL >> short id >> char len << message` to every other player that does not have the
`PLFLAG_NOTOALL` flag set.

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
[GCHAR: power]       // Arrow power/damage (read with `readGChar`, `PlayerClientPackets.cpp:293`)
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
**Trigger**: Client updates baddy properties (intended to come from the level leader)
```
[GUCHAR: baddy_id]   // Baddy identifier (0-255)
[STRING: prop_data]  // Baddy property data
```
The server does not check that the sender is the leader. It needs only a level with
players, applies the properties, and relays them to every player in the level part except
the leader, which is the first player in the level's list (`msgPLI_BADDYPROPS`,
`PlayerClientPackets.cpp:495-522`).

### PLI_BADDYHURT (16) - Hurt Baddy
**Trigger**: Baddy takes damage
```
[GUCHAR: baddy_id]   // Baddy identifier
[GCHAR: hurt_dx]     // Knockback X (midpoint 64)
[GCHAR: hurt_dy]     // Knockback Y (midpoint 64)
[GUCHAR: damage]     // Damage amount, in half hearts
```
**Source**: `msgPLI_BADDYHURT` (`PlayerClientPackets.cpp:524-542`). The four fields are
documented only in a comment. The server does not parse them. It forwards the raw bytes as
`PLO_BADDYHURT` to the level leader only, and ignores the packet when there is no leader.

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
[GINT3: npc_id]      // NPC identifier to delete
```

### PLI_WANTFILE (23) - Request File
**Trigger**: Client needs a file (image, level, etc.)
```
[STRING: filename]   // Requested file path
```

### PLI_SHOWIMGPLAYER (24) - Show Image
**Trigger**: Player displays an image to others
```
[IMAGE_DATA...]      // Image display data; the server does not parse it
```
**Source**: `msgPLI_SHOWIMGPLAYER` (`PlayerClientPackets.cpp:814-818`) relays
`PLO_SHOWIMGPLAYER (32) >> short player_id << body` to nearby players, excluding the
sender. The reference enum name is `PLI_SHOWIMGPLAYER` (gs2lib `IEnums.h:56`).

### PLI_HURTPLAYER (26) - Hurt Player
**Trigger**: Player damages another player
```
[GUSHORT: victim_id] // Target player ID
[GCHAR: hurt_dx]     // Knockback X direction
[GCHAR: hurt_dy]     // Knockback Y direction  
[GUCHAR: power]      // Damage amount
[GINT3: npc_id]      // NPC ID (if NPC caused damage)
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

### PLI_PACKETCOUNT (31) - Packet Count Check
**Trigger**: Client reports how many packets it has sent
```
[GUSHORT: count]     // Packets the client counts as sent
```
**Source**: `Player::msgPLI_PACKETCOUNT` (`server/src/player/Player.cpp:1858-1867`) logs a
warning when `count` differs from the server's own packet counter, or when that counter
is above 10000. It then resets the counter to 0. It sends nothing back.

### PLI_WEAPONADD (33) - Add Weapon
**Trigger**: Player gains a weapon
```
[GUCHAR: weapon_type] // 0 = default weapon, >0 = NPC weapon
// If type == 0:
[GCHAR: item_id]      // Default weapon item ID
// If type > 0:
[GINT3: npc_id]       // Source NPC ID
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
[GINT3: npc_id]      // NPC ID (optional, if hit came from NPC)
```

### PLI_LANGUAGE (37) - Set Language
**Trigger**: Player changes language setting
```
[STRING: language]   // Language code (e.g., "English")
```

### PLI_TRIGGERACTION (38) - Trigger Action
**Trigger**: Player activates a trigger/sign action
```
[GINT3: npc_id]      // Associated NPC ID
[GUCHAR: tile_x]     // X position (in half-tiles)
[GUCHAR: tile_y]     // Y position (in half-tiles)
[STRING: action_data] // Comma-separated action parameters
```

### PLI_TAMPERCHECK (39) - Memory Hash Report
**Trigger**: Client reports hashes of parts of its own memory
```
[GINT5: memory_hash1]  // layout from the gs2lib IEnums.h:71 comment
[GINT5: memory_hash2]
```
**Source**: gs2lib `IEnums.h:71` names it `PLI_TAMPERCHECK` and gives the layout in a
comment. The server handler reads the packet as one string and discards it
(`msgPLI_TAMPERCHECK`, `PlayerClientPackets.cpp:1323-1327`). It is not a map request.

### PLI_SHOOT (40) - Shoot Projectile (v1)
**Trigger**: Player fires a projectile
```
[GINT3: shooter]     // Always 0 from the GS2 `shoot` path; the server ignores it
[GCHAR: x]           // Half-tiles, level-local (server: readGChar() * 8 pixels)
[GCHAR: y]           // Half-tiles, level-local
[GCHAR: z]           // Whole tiles + 50 (server: 16 * (byte - 50) pixels)
[GUCHAR: angle]      // 0-220 maps to 0-2π (step 2π/220)
[GUCHAR: z_angle]    // 0-220 maps to -π/2..π/2 (step π/220)
[GUCHAR: power]      // 1/44 tile per 0.05 s step; 220 = 5 tiles per step
[GCHAR: gani_len]    // Length of GANI string
[STRING: gani]       // GANI name, optionally ",aniparams"
[GUCHAR: param_len]  // Length of shoot parameters
[STRING: shoot_params] // Shoot parameters
```
**Source**: `PlayerClient::msgPLI_SHOOT`
(`GServer-v2/server/src/player/packets/PlayerClientPackets.cpp:1329-1377`). The server
comments give the angle as "0 to 2*pi = 0-220" and the power as "44 parts of a tile, up
to 5 whole tiles (220)". An earlier revision of this page gave x/y as pixels/16, the
angle as 0-π, and the power as pixels. Those units are wrong.

The z_angle range is conflicting in the server source. The comment at
`PlayerClientPackets.cpp:1355` says "-pi to pi", but `Server.cpp:2530` clamps to ±π/2
with 110 as the centre, and `LevelShoot.h:20` agrees. This page uses ±π/2.

The server does not read a gravity field here. It sets the relayed gravity from the
script variable `gravity` cast to a byte (`PlayerClientPackets.cpp:1357`). So the
default 2.0 is relayed as the byte value 2. See [Gravity units](#shoot-gravity-units).

### PLI_SHOOT2 (48) - Shoot Projectile (v2)
**Trigger**: Player fires a projectile (5.07+ clients)

> ⚠️ **Server and client disagree on this layout.** The table below is what GServer-v2
> reads (`PlayerClientPackets.cpp:1379-1410`). The Windows 5.12, 5.24r4, 6.00b1 and
> 6.03r7 clients send a different body. See
> [Client-side SHOOT2 layout](#client-side-shoot2-layout).

```
[GUSHORT: pixel_x]   // Server reads plain pixels
[GUSHORT: pixel_y]
[GUSHORT: pixel_z]
[GCHAR: offset_x]    // Gmap level offset X
[GCHAR: offset_y]    // Gmap level offset Y
[GUCHAR: angle]      // 0-220 maps to 0-2π
[GUCHAR: z_angle]    // 0-220 maps to -π/2..π/2 (±π/2; see the z_angle note under PLI_SHOOT)
[GUCHAR: power]      // 1/44 tile per 0.05 s step
[GUCHAR: gravity]    // Server reads one byte
[GUSHORT: gani_len]  // Server reads a GSHORT length
[STRING: gani]       // GANI animation name
[GUCHAR: param_len]  // The server ignores this value and reads to the end
[STRING: shoot_params] // Shoot parameters, read to end of packet
```

#### Client-side SHOOT2 layout

Static reads of the clients (5.0.0.7 receiver; 5.12, 5.24r4, 6.00b1 and 6.03r7 senders)
are reported in squirelworks' client-analysis notes; not verified against the reference.
They give this body for both `PLI_SHOOT2 (48)` and the part of `PLO_SHOOT2 (191)` after the
player id:

| # | Field | Bytes | Encoding |
|---|---|---|---|
| 1-3 | x, y, z | 2 each | X2-style GSHORT: `(abs(pixels) << 1) \| sign`, level-local pixels |
| 4-5 | offset x, y | 1 each | GCHAR, signed gmap level offset (adds 64 tiles per step) |
| 6 | angle | 1 | GCHAR, 64 steps over 2π (decompiled client) |
| 7 | zangle | 1 | GCHAR, 64 steps over π, from −π/2 (decompiled client) |
| 8 | power | 1 | GCHAR, 64 steps (decompiled client) |
| 9 | gravity | **2** | X2-style GSHORT, value `/ 256` |
| 10 | gani | 1 + n | **GCHAR** length, then `gani[,aniparams]` |
| 11 | shoot params | 1 + n | GCHAR length, then the string; the decompiled client always sends it (length byte 0x20 when empty) |

The GServer-v2 gravity byte plus GSHORT gani length is 3 bytes, and the client gravity
GSHORT plus GCHAR gani length is also 3 bytes. So the later fields stay aligned, but
the positions and the gravity decode differently. No lab test confirms the effect yet.
Source: squirelworks' client-analysis notes, `protocol/shoot-5007.md` (static reads,
not lab-tested).

Rows 6-8 differ from the server's 220-step scale. The decompiled reference client
(`Preagonal/FourPlay/quattroplay/src/TClient.cpp:1608-1610`) encodes angle as
`64 * angle / 2π`, zangle as `(z + π/2) * 64 / π` and power as `64 * power / <constant>`,
i.e. 64 steps for angle, zangle and power, not 220. Row 11 follows
`TClient.cpp:1622-1637`, which always sends the params, with `0x20` for an empty string.
The earlier 220-step formulas and "optional" wording in the notes are not supported by
the decompiled client.

#### Shoot gravity units

GServer-v2 uses three different gravity units:

| Path | Gravity sent in `PLO_SHOOT2` | Source |
|---|---|---|
| `PLI_SHOOT (40)` relay | script `gravity` cast to a byte (2.0 → 2) | `PlayerClientPackets.cpp:1357` |
| `PLI_SHOOT2 (48)` relay | the received byte, unchanged; the NPC-server hook divides it by 16 | `PlayerClientPackets.cpp:1392,1406` |
| NPC-server shot | `gravity * 16` (2.0 → 32) | `GServer-v2/server/src/Server.cpp:2532` |

The clients read so far use a fourth form: the 2-byte ×256 value above.

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
Unverified beyond the gs2lib `IEnums.h:74` comment: the reference server registers no
handler for this id. It falls through to `Player::msgPLI_NULL`, which logs the packet as
unknown and disconnects the player after the third invalid packet
(`server/src/player/Player.cpp:283,1657-1675`).

### PLI_PROCESSLIST (44) - Process List
**Trigger**: Client reports its running processes
```
[STRING: process_data] // gtokenized, newline-separated process list
```
**Source**: `msgPLI_PROCESSLIST` (`PlayerClientPackets.cpp:1420-1424`) guntokenizes the
string, splits it on newlines and discards the result. The request in the other
direction is `PLO_HASPROCESSRUNNING (183)`, which the client answers with
`PLI_PROCESSRUNNING (45)` (gs2lib `IEnums.h:76`, `:304`).

### PLI_PROCESSRUNNING (45) - Process Running Reply
**Trigger**: Client answers `PLO_HASPROCESSRUNNING (183)`
```
[GCHAR: flag]        // 1 if a matching process is running
```
Layout from the gs2lib `IEnums.h:76` comment. The reference server registers no handler
for this id.

### PLI_ENTERLEVEL (46) - Level Entered
**Trigger**: Client entered a new level
```
[GCHAR: 1]
```
Layout from the gs2lib `IEnums.h:77` comment. The server handler does nothing
(`msgPLI_ENTERLEVEL`, `PlayerClientPackets.cpp:1426-1429`).

### PLI_VERIFYWANTSEND (47) - Verify File Checksum
**Trigger**: Client verifies file integrity before requesting
```
[GUINT5: checksum]   // CRC32 checksum of local file
[STRING: filename]   // File to verify
```

### PLI_RAWDATA (50) - Raw Data Marker
**Trigger**: Indicates next packet contains raw binary data
```
[GINT3: data_size]   // Size of following raw data in bytes
```
The server parses it with `readGUInt()`, which is the 3-byte GINT3 read
(`server/include/network/IPacketHandler.h:366`; gs2lib `CString.cpp:1836`).

### PLI_PROFILEGET (80) - Request Player Profile
**Trigger**: Client asks for a player's profile
```
[STRING: account_name] // Account whose profile is wanted, to end of packet
```
**Source**: `Player::msgPLI_PROFILEGET` (`server/src/player/Player.cpp:1878-1883`) does not
parse the body. It forwards the whole packet, id byte included, to the list server as
`SVO_GETPROF >> short player_id`. The list server skips that id byte and reads the account
name (`graal-serverlist/server/src/ServerConnection.cpp:868-876`). It answers with the
profile fields.

### PLI_PROFILESET (81) - Set Own Profile
**Trigger**: Client saves its own profile
```
[GCHAR: account_len][STRING: account]   // Must equal the sender's own account name
[GCHAR: len][STRING: name]
[GCHAR: len][STRING: age]               // decimal text
[GCHAR: len][STRING: gender]
[GCHAR: len][STRING: country]
[GCHAR: len][STRING: messenger]
[GCHAR: len][STRING: email]
[GCHAR: len][STRING: website]
[GCHAR: len][STRING: hangout]
[GCHAR: len][STRING: quote]
```
**Source**: `Player::msgPLI_PROFILESET` (`Player.cpp:1885-1894`) ignores the packet unless the
account name matches. Otherwise it forwards the whole packet, id byte included, to the
list server as `SVO_SETPROF`. The list server skips the id byte and reads the nine
length-prefixed fields above (`graal-serverlist/server/src/ServerConnection.cpp:904-926`).

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
**MAXPOWER (1)**: `[GCHAR: full_hearts]` (1 byte, whole hearts, not half-hearts). The
reference list binds `FULLHEARTS` to `account.maxHitpoints`
(`GServer-v2/server/include/object/Player.h:693`). Only CURPOWER (2) uses half-hearts.
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
> at `server/src/utilities/PropertySerializers.cpp:98-154` (sword) and `:159-218`
> (shield).
>
> For a bare nonzero power, the receiver synthesizes `sword{N}.png` or
> `shield{N}.png`. Classic generation uses `.gif`. The reference shield implementation
> is intentionally asymmetric: serialization permits the bare form only through power
> 3, while deserialization synthesizes a default through power 4. Its deserializer also
> returns early when no bytes remain after a biased power, an explicit 1.41-client quirk.
> In classic generation only, a custom sword or shield name without an extension gains
> `.gif` (`server/src/utilities/PropertySerializers.cpp:134-139` for the sword, `:198-203`
> for the shield).
**GANI (10)**: `[GCHAR: length][string]` - Animation file. In the classic server
generation (0) this prop is BOWGIF instead: a byte below 10 is a bow preset with no
string, and any other byte is `10 + length` followed by the image name, with `.gif`
appended when the name has no dot. The server picks the form by its generation, not by
client version (`server/src/utilities/PropertySerializers.cpp:223-264`).
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
> property (`server/src/utilities/PropertySerializers.cpp:282-334`; serialize
> `:284-295`, deserialize `:297-315`).
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
(`server/include/object/Player.h:711`,
`server/include/utilities/PropertySerializers.h:229-258`).
**CURLEVEL (20)**: `[GCHAR: length][string]` - Current level name
**HORSEGIF (21)**: `[GCHAR: length][string]` - Horse image
**HORSEBUSHES (22)**: `[GCHAR: bush_count]` - Bushes eaten by horse
**EFFECTCOLORS (23)**: Variable - `[GCHAR: first]`. If `first == 0`, the property is only
that 1 byte. Otherwise, it is 5 bytes (`first` + 4 color bytes). Visual effect colors.
The reference shows only the byte layout, not what the four bytes mean
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
| 83 | UNKNOWN83 | The server does not handle it: it is absent from the property-list macro (`FOR_LIST_OF_PLAYER_PROPS`), so it is never sent or parsed. The enum comment says v6 reads a GBYTE5 and stores it if the number is below 1,000,000,000 (`server/include/player/PlayerProps.h:111-112`) |

If a parser treats 37-74 as one flat GATTRIB block, it misaligns each subsequent
property. Props **51** (void) and **53** (1 byte, not a string) also frequently
desynchronize a simple parser.

### Property-stream ordering and failure handling

The server must send player and NPC property pairs in strictly ascending property-ID
order. The reference full-list and modified-player builders iterate IDs upward
(`server/src/player/PlayerProps.cpp:1325-1351`,
`server/src/player/PlayerProps.cpp:1393-1418`), while its shared change
collector sorts by ID because a client stops processing when it encounters a property it
does not understand (`server/src/utilities/PropertySerializers.cpp:681-747`; the sort
comment is at `:683-685`).

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
- Do not infer a shape for player prop 83 from the server: it is absent from
  `FOR_LIST_OF_PLAYER_PROPS` (`server/include/object/Player.h:691-774`). Only the enum
  comment above describes it.

### What old clients parse

The ascending-order rule matters most for old clients. Each old client stops at the first
prop id its parser does not know. It keeps the props before it and drops the rest of the
packet. The table below and the notes after it are observations reported in squirelworks'
client-analysis notes (`protocol/player-props.md`; static reads of the 1.35, 1.36, 2.05, 2.22
and 2.31 clients). They are not verified against the reference, which holds no such client:

| Client | `PLO_PLAYERPROPS` (self) | `PLO_OTHERPLPROPS` | `PLO_NPCPROPS` |
|---|---|---|---|
| 2.05 | 0-42 | stops at 1, 3-7, 14, 22, 23, 25-29, 43-49 and 52 up | 0-40 |
| 2.22 | up to 74; stops at 50, 51, 53 | up to 76; stops at 1, 3-7, 14, 22, 25-29 | up to 73; stops at 48-52 |
| 2.31 | up to 80; stops at 50, 51, 53, 75-77 | up to 80; stops at 1, 3-7, 14, 22, 25-29, 77 | up to 77; stops at 48-52 |

The reference server already avoids part of this in its login prop lists:
`loginPropsClientOthers` omits 1-7, 14, 22, 23, 25-29, 42, 50-52, 75-77 and 81, and
`loginPropsClientSelf` omits 50-53, 75-77 and 81, among others
(`GServer-v2/server/include/player/PlayerProps.h:134-170` at `origin/beta4`). That is consistent
with the table. The reference does not filter props by client version
(`getPropsPacketFromList`, `server/src/player/PlayerProps.cpp:1325`), so it still sends
props 43-49 and 52 and above to a 2.05 client.

Consequences, as observed in those notes:

- Do not send another player's MAXPOWER (1), RUPEES (3), ID (14), HORSEBUSHES (22) or
  counters (25-29) to a 2.x client in `PLO_OTHERPLPROPS`, or send them last.
- No client up to 2.31 parses player prop 77 (ONLINESECS2) or 81 (PLAYERLISTCATEGORY).
- 2.05 is reported to skip one byte after prop 51, although the prop has no payload. Do not
  put other props after 51. This is an observation of the 2.05 client, not confirmed.

Two older forms also differ from the table above (both are observations from the same
notes, not confirmed against the reference):

- **`PLO_OTHERPLPROPS` player id in 1.21-1.35.** The original 1.35 client reads a
  **one-byte** GCHAR player id before the prop stream, not a GSHORT. 1.36 and later read two
  bytes. The reference server writes a GSHORT id for every client version
  (`server/src/player/PlayerClientOriginal.cpp:225,235`), so if the observation is right, the
  reference does not match the 1.35 client.
- **Prop 10 before 2.1.** It is BOWGIF, not GANI: `c(10 + len)` + image name, or a single
  `c(bowpower)` byte when there is no image. The form is confirmed
  (`server/src/utilities/PropertySerializers.cpp:223-258`), but the reference selects it by
  server generation, not by client version (`PlayerProps.cpp:339-353`); its comments say
  "1.411 and earlier" and "pre-2.x", which do not cover 2.05. That 2.05 uses this form is
  an observation, not confirmed.

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
[STRING: options_data] // gtokenized (quoted CSV) options text
```
Needs `PLPERM_SETSERVEROPTIONS`. The server guntokenizes the string
(`msgPLI_RC_SERVEROPTIONSSET`, `server/src/player/packets/PlayerRCPackets.cpp:61-81`).
All the RC handlers below log a `[Hack]` line and refuse when the sender is a plain
client (`isClient()`), except where noted.

### PLI_RC_FOLDERCONFIGGET (53) - Get Folder Config
**Trigger**: RC requests folder configuration
```
// No additional data
```

### PLI_RC_FOLDERCONFIGSET (54) - Set Folder Config
**Trigger**: RC updates folder configuration
```
[STRING: folder_config] // gtokenized (quoted CSV) folder list
```
Needs `PLPERM_SETFOLDEROPTIONS`. The server turns the CSV into lines of
`foldersconfig.txt` (`msgPLI_RC_FOLDERCONFIGSET`, `PlayerRCPackets.cpp:151-173`).

### PLI_RC_PLAYERPROPSGET (59) - Get Player Properties
**Trigger**: RC requests player information
```
// Deprecated: the server reads nothing
```
The handler is an empty "Deprecated" stub (`PlayerRCPackets.cpp:200-204`). Player
information is requested with `PLI_RC_PLAYERPROPSGET2 (73)` and `PLI_RC_PLAYERPROPSGET3 (74)`.

### PLI_RC_PLAYERPROPSSET (60) - Set Player Properties
**Trigger**: RC modifies player properties
```
[GUSHORT: player_id]  // Target player
[RC_PROP_BLOB]        // Property modifications
```
Needs `PLPERM_SETATTRIBUTES` for another player, or `PLPERM_SETSELFATTRIBUTES` for the
sender's own account (`msgPLI_RC_PLAYERPROPSSET`, `PlayerRCPackets.cpp:206-231`). The
reference comment calls the handler "Deprecated?". The blob is read by
`Player::setPropsFromRCPacket` (`server/src/player/PlayerProps.cpp:1242-1323`):
```
[GCHAR: world_len][STRING: world]          // skipped
[GCHAR: props_len][STRING: props]          // a normal player-property stream
[GUSHORT: flag_count] then flag_count x [GCHAR: len][STRING: "name=value"]
[GUSHORT: chest_count] then chest_count x [GCHAR: len][GUCHAR: x][GUCHAR: y][STRING: level (len - 2 bytes)]
[GUCHAR: weapon_count] then weapon_count x [GCHAR: len][STRING: weapon]
```

### PLI_RC_DISCONNECTPLAYER (61) - Disconnect Player
**Trigger**: RC kicks a player
```
[GUSHORT: player_id]  // Player to disconnect
[STRING: reason]      // Optional, to end of packet
```
Needs `PLPERM_DISCONNECT` (`msgPLI_RC_DISCONNECTPLAYER`, `PlayerRCPackets.cpp:233-262`). A
non-empty reason is added to the disconnect message the player sees.

### PLI_RC_ADMINMESSAGE (63) - Admin Message
**Trigger**: RC sends server-wide message
```
[STRING: message] // Admin message text
```

### PLI_RC_PRIVADMINMESSAGE (64) - Private Admin Message
**Trigger**: RC sends private message to player
```
[GUSHORT: player_id]  // Target player
[STRING: message]     // Private message
```
Needs `PLPERM_ADMINMSG` (`msgPLI_RC_PRIVADMINMESSAGE`, `PlayerRCPackets.cpp:296-310`).

### PLI_RC_SERVERFLAGSGET (68) - Get Server Flags
**Trigger**: RC requests server flags
```
// No additional data
```

### PLI_RC_SERVERFLAGSSET (69) - Set Server Flags
**Trigger**: RC updates server flags
```
[GUSHORT: flag_count]
// flag_count times:
[GUCHAR: len][STRING: flag]   // "name=value"
```
Needs `PLPERM_SETSERVERFLAGS`. The server rewrites `serverflags.txt` from these entries
(`msgPLI_RC_SERVERFLAGSSET`, `PlayerRCPackets.cpp:354-401`).

### PLI_RC_ACCOUNTADD (70) - Add Account
**Trigger**: RC creates new player account
```
[GUCHAR: len][STRING: account]
[GUCHAR: len][STRING: password]      // read, not used
[GUCHAR: len][STRING: email]
[GUCHAR: banned]
[GUCHAR: only_load]
[GUCHAR: admin_level]                // read, not used
[GUCHAR: len][STRING: admin_worlds]  // read, not used
[GUCHAR: len][STRING: ban_reason]
```
Needs `PLPERM_MODIFYSTAFFACCOUNT`. The `banned` and `ban_reason` fields apply only if the
sender also has `PLPERM_BAN` (`msgPLI_RC_ACCOUNTADD`, `PlayerRCPackets.cpp:403-435`).

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
**Trigger**: Client requests text from the server or the list server
```
[STRING: request] // gtokenized (quoted CSV) string
```
After guntokenizing, the request is a `\n`-separated `weapon`, `type`, `option` and
optional further parameters, for example `<weapon>,lister,serverinfo`. The server answers
from the type and option, for example by forwarding to the list server or with
`PLO_SERVERTEXT`. There is no key/value store on this path
(`Player::msgPLI_REQUESTTEXT`, `server/src/player/PlayerRequestText.cpp:18-158`).

### PLI_SENDTEXT (154) - Send Server Text
**Trigger**: Client sends text to the server or the list server
```
[STRING: text] // gtokenized (quoted CSV) string, same shape as PLI_REQUESTTEXT
```
Handled by `Player::msgPLI_SENDTEXT` (`PlayerRequestText.cpp:160-278`). The reference
reads `weapon`, `type`, `option` and the remaining parameters, with the same dispatch on
`type` as PLI_REQUESTTEXT (for example `irc` and `lister`).

### PLI_UPDATEGANI (157) - Update GANI Animation
**Trigger**: Client requests GANI bytecode update
```
[GUINT5: checksum]   // CRC32 of client's cached gani bytecode (0 forces a resend)
[STRING: gani_name]  // GANI name (without .gani extension), to end of packet
```
Server replies with `PLO_GANISCRIPT (134)` only if the CRC differs, then
`PLO_LOADGANI (195)` with `[GCHAR len][gani]"SETBACKTO <x>"`
(`msgPLI_UPDATEGANI`, `PlayerClientPackets.cpp:1470-1493`). If the server cannot find the
gani, it sends nothing.

### PLI_UPDATESCRIPT (158) - Update Weapon Script
**Trigger**: Client requests weapon bytecode
```
[STRING: weapon_name] // Weapon name, to end of packet (no checksum field)
```
For a known weapon with non-empty bytecode, the server replies with
`PLO_WEAPONBYTECODE2 (140)` to clients 5.07 and later, and with `PLO_WEAPONBYTECODE (132)`
`[GCHAR len][name][bytecode]` to older ones. Otherwise it sends nothing
(`msgPLI_UPDATESCRIPT`, `PlayerClientPackets.cpp:1495-1503`; `Weapon::sendByteCodeToPlayer`,
`server/src/object/Weapon.cpp:204-216`).

### PLI_UPDATECLASS (161) - Update NPC Class
**Trigger**: Client requests class bytecode
```
[GINT5: checksum]    // CRC32 of client's cached class bytecode (0 forces a resend)
[STRING: class_name] // Class name, to end of packet
```
If the CRC matches, the server sends nothing. If it differs, the server sends the class
RAWDATA-framed: `PLO_LOADSCRIPT (197)` to clients 5.07 and later, or
`PLO_CLASSBYTECODE (133)` `[GCHAR len][name][bytecode]` to older ones
(`ScriptClass::getClassPacket`, `server/src/scripting/ScriptClass.cpp:66-81`). For an
unknown class, clients 5.07 and later get a header-only `PLO_WEAPONBYTECODE2 (140)`, and
older clients get a name-only `PLO_CLASSBYTECODE`
(`msgPLI_UPDATECLASS`, `PlayerClientPackets.cpp:1505-1545`). This packet requires an NPC
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

[Encryption](encryption.md) is the reference for GEN_5. In summary:

- The login packet sets the one-byte key (`server/src/player/PlayerClient.cpp:336-340`).
- The iterator starts at `0x4A80B38`. Each 4-byte group advances it once:
  `iterator = iterator * 0x8088405 + key`. The data is XORed with the little-endian
  bytes of the iterator.
- The compression-type byte sets the limit in **4-byte groups**: 12 groups (48 bytes) for
  `0x02`, 4 groups (16 bytes) for `0x04` and `0x06`.

An earlier revision of this section gave `key = (key + iterator++) & 0xFF` and limits of
40, 4096 and 65536 bytes. Those values do not match gs2lib `CEncryption.cpp:159` and are
wrong.

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
**Trigger**: Player enters a level
```
// No additional data
```
The reference sends this packet **empty**. It is a "no (more) board data follows" marker.
The client stays on "Loading" until it gets board data, so the server sends an empty
`PLO_LEVELBOARD` in two places. It sends one first when the player has not finished
loading (a client bug workaround: the tiledef routine must run before the tiles arrive).
It sends one at the end of level entry when it sent no board this time because the client's
cache was current (`server/src/player/PlayerClient.cpp:1448-1452`, `:1493-1496`;
`server/src/player/PlayerClientOriginal.cpp:136`, `:167`). The tiles arrive as
**PLO_BOARDPACKET (101)**, announced by a **PLO_RAWDATA (100)** length packet.
A batched-changes form (style 2 in `server/src/level/Level.cpp:503-514`) would put board
changes inside this packet, but its use is commented out (the style stays 1 or 3,
`Level.cpp:495-499`). The server never sends that form.

### PLO_LEVELLINK (1) - Level Link/Warp

> ⚠️ **THE TRAP** ⚠️
>
> This packet does NOT use a length-prefixed GSTRING. Multiple client implementations
> have made this mistake. The string runs to the end of the packet; the only newline is the
> packet terminator (`server/src/level/Level.cpp:165`).
> If you read the first byte as a length, you will read 'l' from "level.nw".
> You will compute length = 108 - 32 = 76 and consume half the next packet. Do not do this.
>
> See [String Types: The PLO_LEVELLINK Trap](strings.md#the-plo_levellink-trap-) for details.

**Trigger**: Level entry, one packet per link. The modern-generation server sends links
only when it has no NPC-server, or the `clientsidelinks` option is set, or the level is a
sub-level of a big map (`server/src/player/PlayerClient.cpp:1478-1482`). In both generations
the links go out only inside the branch that sends the board: not when the client's cache is
current or the level was already entered this session (`PlayerClient.cpp:1457-1482`;
`PlayerClientOriginal.cpp:141-156`). The original-generation path sends them without the
NPC-server condition, but only in that branch.
```
[STRING: link_data] // Read-to-end string (NOT a GSTRING!)
```
**String Type**: Read to end of packet (NOT length-prefixed).

**Link Data Format**: "destlevel x y width height destx desty"
- destlevel: Target level name
- x, y: Link area position (tiles, 0-63)
- width, height: Link area size (tiles)
- destx, desty: Destination position (can be "playerx"/"playery" or numeric)

The server builds the string as `"{dest} {x} {y} {w} {h} {destx} {desty}"`
(`server/src/level/LevelLink.cpp:71-74`). `x`, `y`, `w` and `h` are numbers;
`destx` and `desty` are kept as strings. A client parses the last six space-separated
tokens as the numeric fields (`x y w h destx desty`); everything before them is the level
name, which may contain spaces (`server/src/level/LevelLink.cpp:82-98`).

**Important Server Behavior**:
- The client handles the warp when it walks into the link area.
- Special values: "playerx"/"playery" mean "keep player's current position" (a stored `-1` is sent as `playerx`/`playery`)

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
sent to a player on a non-gmap level, or replayed to a player entering a level whose style
is `PLO_BOARDMODIFY` (clients before 2.1, or non-gmap clients before 4.0211; see
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
getPropsForSingleLevel` (`server/src/level/LevelBoardChange.cpp:73-81`) builds the layered
and unlayered forms for server, script and respawn changes (`LevelBoardChange.cpp:57`) and
for the level-entry replay (`server/src/level/Level.cpp:525-528`). The relay of a player's
own edit is different: `msgPLI_BOARDMODIFY` forwards the client's raw bytes
(`<< (pPacket.text() + 1)`) to the other players
(`server/src/player/packets/PlayerClientPackets.cpp:127-128`). On a gmap that relay is not
`PLO_BOARDMODIFY`: it is `PLO_BOARDMODIFY2` with the sender's `mapX` and `mapY` prefixed,
sent to the nearby segments (`PlayerClientPackets.cpp:129-133`). A plain player edit never
sets the layer prefix.

**Source**: `server/src/level/LevelBoardChange.cpp:73-81` (build), `Level::alterBoard`
(`server/src/level/Level.cpp:1610`, tiles read via `readGShort()`).

### PLO_BOARDMODIFY2 (186) - Board Modification (GMAP / Map-Position Form)
**Trigger**: Board change on a gmap (sent to the nearby segments,
`server/src/level/LevelBoardChange.cpp:60`), or replayed to a player entering a level. It is
the default replay form for clients 2.1 and later on a gmap, and for non-gmap clients from
4.0211 (`server/src/level/Level.cpp:490-499`; clients before 2.1, or non-gmap clients
before 4.0211, get `PLO_BOARDMODIFY` instead). See
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
**Layer-prefixed variant**: when the change's layer is not 0, `{mapX}{mapY}{layer+64}{x}{y}{w}{h}{tiles}`
is built, with the `layer + 64` byte after `mapY` (`server/src/level/LevelBoardChange.cpp:85-95`).

**Source**: `LevelBoardChange::getPropsForMapClassic` (`server/src/level/LevelBoardChange.cpp:83-96`).
`mapX`/`mapY` are always present, even for non-gmap levels (where they resolve to `0,0`),
because `LevelBoardChange` objects always carry an explicit `MapPosition` (the function
returns an empty string without one, `LevelBoardChange.cpp:88-89`). A commented-out
`getPropsForMapNewMain()` sibling (`LevelBoardChange.cpp:98-105`) exists in source but is
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
[GSHORT: player_id]  // Player who placed bomb (0 when the server placed it)
[GCHAR: x]           // X position, half-tiles (pixel / 8; tile * 2)
[GCHAR: y]           // Y position, half-tiles
[GCHAR: power]       // Bomb power
[GCHAR: timer]       // Time to explosion
```
The server-built form is `server/src/level/Level.cpp:2098`. The relay of a client's bomb
prepends the sender id to the client body (`server/src/player/packets/PlayerClientPackets.cpp:237`).

### PLO_BOMBDEL (12) - Bomb Removed
**Trigger**: Bomb explodes or is removed
```
[GCHAR: x]           // X position, half-tiles
[GCHAR: y]           // Y position, half-tiles
```
There is **no** player id. The server builds `>> x >> y` (`server/src/level/Level.cpp:2138`),
relays the client's `PLI_BOMBDEL` body unchanged (`PlayerClientPackets.cpp:248`), and uses the
same two bytes to roll back a refused bomb (`PlayerClientPackets.cpp:233`).

### PLO_TOALL (13) - Chat Message
**Trigger**: Player sends public chat
```
[GSHORT: player_id]  // Sender player ID
[GCHAR: msg_len]     // Message length
[message]            // msg_len bytes
```
The server writes `>> (short)m_id >> (char)message.length() << message`
(`server/src/player/Player.cpp:1782`). Unlike the inbound packet, this form is truly
length-prefixed, but the length is that of the message after the inbound truncation quirk
described under PLI_TOALL.

### PLO_PLAYERWARP (14) - Player Warp
**Trigger**: Player warps to new location
```
[GCHAR: x]           // New X position, half-tiles (pixel / 8; tile * 2)
[GCHAR: y]           // New Y position, half-tiles
[STRING: level_name] // New level name
```
`x` and `y` are `PropertyTileCoordinate` values: the server writes `pixel / 8` as one
GCHAR and replaces 223 with 224. The source comment says 223 would overflow into the
newline, but its wire byte is 255; 234 is the value that gives `0x0A` and it is not remapped
(`server/src/utilities/PropertySerializers.cpp:473-485`, sent at
`server/src/player/PlayerClient.cpp:1263`).

### PLO_WARPFAILED (15) - Warp Failed
**Trigger**: Player warp attempt fails
```
[STRING: level_name] // The level that could not be loaded
```
The server writes `<< levelName` (`server/src/player/PlayerClient.cpp:1211`;
`PlayerClientOriginal.cpp:87`), and `<< level->levelName` from `enterLevel`
(`server/src/player/PlayerClient.cpp:1294`).

### PLO_DISCMESSAGE (16) - Disconnect Message
**Trigger**: The server disconnects the player
```
[STRING: reason]     // Disconnect reason
```

### PLO_HORSEADD (17) - Horse Added
**Trigger**: The server spawns a horse
```
[GCHAR: x]           // X position, half-tiles
[GCHAR: y]           // Y position, half-tiles
[GCHAR: dir_bush]    // (bushes << 2) | direction
[STRING: image]      // Horse image
```
There is no player id. The server-built form is `LevelHorse::getPacket`
(`server/include/level/LevelHorse.h:30-35`, sent at `server/src/level/Level.cpp:2367`).
The relay forwards the client's `PLI_HORSEADD` body unchanged
(`PlayerClientPackets.cpp:261`).

### PLO_HORSEDEL (18) - Horse Removed
**Trigger**: The server destroys a horse
```
[GCHAR: x]           // X position, half-tiles
[GCHAR: y]           // Y position, half-tiles
```
There is no player id (`server/src/level/Level.cpp:2390`;
`server/src/player/packets/PlayerClientPackets.cpp:279`).

### PLO_ARROWADD (19) - Arrow Added
**Trigger**: Player fires arrow
```
[GUSHORT: player_id] // Player who fired
[GCHAR: x]           // Starting X position, half-tiles
[GCHAR: y]           // Starting Y position, half-tiles
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
[GCHAR: x]           // X position, half-tiles
[GCHAR: y]           // Y position, half-tiles
```
The server writes `pixel / 8` (`server/src/level/Level.cpp:2480`) and `tile * 2` for the
rollback of a refused drop (`server/src/player/packets/PlayerClientPackets.cpp:354`).

### PLO_NPCMOVED (24) - NPC Moved (Level Change)
**Trigger**: An NPC warps to a different level. The server sends it to **all** players
(`PLTYPE_ANYPLAYER`), not only to those in the old level.
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[GCHAR: x / 8]        // NPC's OLD position in the level it's leaving, in half-tiles
[GCHAR: y / 8]        // (captured BEFORE removal from the old level)
[STRING: new_level]   // The NEW level name being warped to, to end of packet
```
> The previous version of this document incorrectly specified only a bare NPC id.
> The packet carries the NPC's old position and the destination level name.

**Source**: the level-change routine in `server/src/object/NPC.cpp:205-210`:
```cpp
>> (int)id >> (char)(localPosition.x() / 8) >> (char)(localPosition.y() / 8) << destinationLevel->levelName
```
Here, `localPosition` is the position in the level that the NPC leaves. The server captures
it after removing the NPC from the old level and before it sets the new one.

### PLO_SIGNATURE (25) - Player Signature
**Trigger**: The server sends it once during login, before the server-mode packets
(`server/src/player/Player.cpp:746`)
```
[GCHAR: signature]   // Always 73 (0x49): "more than eight players will be playing"
```

**What the original clients do with the byte** (2.17 to 2.31): `1` makes the client quit; `0`
makes it quit unless it is connected to the loopback address; every other value, the
reference's 73 included, is ignored. So a server must never send 0 or 1 here
([`version-profiles/plo-layouts-217-231.tsv`](https://github.com/squirelworks/Graal_analysis/blob/main/version-profiles/plo-layouts-217-231.tsv)).

### PLO_NPCSETSCRIPT (26) - NPC Set Script
**Trigger**: Not sent by the reference server. The enum comment gives the layout and
says the packet existed in clients 1.31 to 2.03, where it hot-swapped an NPC's script
(gs2lib `IEnums.h:195`). The server notes the same range
(`server/src/object/NPC.cpp:948`).
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[STRING: script]     // New NPC script
```

### PLO_BADDYHURT (27) - Baddy Hurt
**Trigger**: A client reports hitting a baddy. The server relays it to the level leader
only, not to the whole level (`server/src/player/packets/PlayerClientPackets.cpp:530-540`).
```
[GCHAR: baddy_id]    // Baddy identifier
[GCHAR: hurt_dx]     // Knockback X (midpoint 64)
[GCHAR: hurt_dy]     // Knockback Y (midpoint 64)
[GCHAR: damage]      // Damage in half-hearts
```
The server forwards the client's `PLI_BADDYHURT` body (`pPacket.text() + 1`) without
reading it. The field names come from the commented-out reads at
`PlayerClientPackets.cpp:535-538`.

### PLO_FLAGSET (28) - Flag Set
**Trigger**: Server or player sets a flag
```
[STRING: flag_data]  // "flag_name=value" format
```

### PLO_NPCDEL (29) - NPC Deleted
**Trigger**: The server removes an NPC from the level
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
```
The server writes `>> (int)` (`server/src/Server.cpp:1637`).

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

### PLO_SHOWIMGPLAYER (32) - Show Image
**Trigger**: Player displays image. The server relays the client's `PLI_SHOWIMGPLAYER` body to the
nearby players (`server/src/player/packets/PlayerClientPackets.cpp:816`).
```
[GSHORT: player_id]  // Player showing image
[IMAGE_DATA...]      // The client's showimg body, unchanged
```
The NPC form of this packet is `PLO_SHOWIMGNPC (166)`.

### PLO_NPCWEAPONADD (33) - NPC Weapon Added
**Trigger**: Player gains a weapon (login, or a script gives it)
```
[GCHAR: name_len]    // Weapon name length
[STRING: name]       // Weapon name
[GCHAR: 0]           // NPCProp::IMAGE, the prop id
[GCHAR: image_len]   // Image name length
[STRING: image]      // Weapon image
// then, one of:
[GCHAR: 1][GSHORT: script_len][script]       // NPCProp::SCRIPT: a classic weapon, no bytecode
[GCHAR: 74][GSHORT: classes_len][classes]    // NPCProp::CLASS: bytecode weapons; omitted with no classes
```
The packet is a weapon name followed by an NPC-prop stream. There is no weapon-type or
script-type byte. A weapon without bytecode sends its script when the client is 5.07 or
older. A weapon with bytecode on a modern-generation server sends the joined class list
(`server/src/object/Weapon.cpp:176-190`). A second packet then tells the client how to
load the code: `PLO_LOADSCRIPT (197)` for clients 5.07 and later, `PLO_WEAPONHASH (193)`
for older clients (`Weapon.cpp:194-199`). The client fetches the code with
`PLI_UPDATESCRIPT (158)`; the answer is `PLO_WEAPONBYTECODE2 (140)` or `PLO_WEAPONBYTECODE (132)`.
A default weapon (`PLO_DEFAULTWEAPON (43)`) skips all of this.

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
[GSHORT: player_id]  // Player who caused explosion (0 when the server caused it)
[GCHAR: radius]      // Explosion radius
[GCHAR: x]           // X position, half-tiles
[GCHAR: y]           // Y position, half-tiles
[GCHAR: power]       // Explosion power
```
(`server/src/level/Level.cpp:2224`; the relay of a client's explosion is
`server/src/player/packets/PlayerClientPackets.cpp:855`.)

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
**Trigger**: A force pushes the player. The reference server never sends it
(it appears only in the packet-name list, `server/src/player/Player.cpp:112`).
```
[GCHAR: dx]          // dx * 0.0625 - 4.0 tiles, so -2.0 to 2.0 in 1/16-tile steps
[GCHAR: dy]          // same encoding
```
The layout is from the enum comment (gs2lib `IEnums.h:207`).

### PLO_LEVELMODTIME (39) - Level Modification Time
**Trigger**: The server sends it unsolicited on every level entry, after the board and
chests, so the client can cache the level (`server/src/player/PlayerClient.cpp:1499`;
`PlayerClientOriginal.cpp:162`, only when it sent the board)
```
[GINT5: mod_time]    // Level modification timestamp
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

### PLO_STARTMESSAGE (41) - Start Message
**Trigger**: Sent once at login with the server's start message
(`server/src/player/PlayerClient.cpp:519`). The enum comment says 6.037 does not handle it.
```
[STRING: message]    // Server start message, to end of packet
```

### PLO_NEWWORLDTIME (42) - New World Time
**Trigger**: The server broadcasts the world time to all players every 5 seconds
(`server/src/Server.Init.cpp:183`)
```
[GINT4: time]        // New-world time, 4 bytes (CString::writeGInt4)
```

### PLO_DEFAULTWEAPON (43) - Default Weapon
**Trigger**: Player gains default weapon
```
[GCHAR: weapon_type] // LevelItemType id of the default weapon (0-24, see the PLO_ITEMADD table)
```
(`server/src/object/Weapon.cpp:171`.)

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
[GSHORT: player_id]  // Player who hit (0 for an NPC source)
[GCHAR: power]       // Hit power
[GCHAR: x]           // X position, half-tiles (tile * 2)
[GCHAR: y]           // Y position, half-tiles
[GINT3: npc_id]      // NPC ID, only when an NPC caused the hit (3 bytes)
```
(`server/src/Server.cpp:1949` for the player form, `:1955` for the NPC form.)

### PLO_STAFFGUILDS (47) - Staff Guilds
**Trigger**: Server sends staff guild information
```
[STRING: guild_data] // Staff guild information
```

### PLO_TRIGGERACTION (48) - Trigger Action
**Trigger**: The server runs a trigger action for a level, or a player sends one
```
[GSHORT: player_id]  // Sending player (0 when the server or an NPC sent it)
[GINT3: npc_id]      // Source NPC
[GCHAR: x]           // X position, pixel / 8
[GCHAR: y]           // Y position, pixel / 8
[STRINGLIST: action,params...]   // CSV: the action name, a comma, then the parameters
```
The enum comment gives the same layout (gs2lib `IEnums.h:217`). The server and NPC form is
built in `server/src/Server.cpp:1996` and `:2006`. When a **player** triggers an action,
the server relays it to the other players in the level with `>> (short)m_id` followed by the
client's `PLI_TRIGGERACTION` body unchanged (`PlayerClientPackets.cpp:1311`). That body
starts with the same GINT3 npc, GCHAR x and GCHAR y (`PlayerClientPackets.cpp:1056-1057`), so
every form carries all five fields. It does that
only when the `sendplayertriggers` option is on (the default).

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

### PLO_NPCSERVERADDR (79) - NPC-Server Address
**Trigger**: Sent to an RC login that holds the NPC-control right, when the server has an
NPC-server (`NPCServer::sendNCLoginToPlayer`, `server/src/npcserver/NPCServer.cpp:133`).
```
[GSHORT: npcserver_id] // Player id of the NPC-server account
[STRING: address]      // "<ip>,<port>", to end of packet
```
The address is the NPC-server host, or the player's own IP when the player connects from the
NPC-server's machine. The enum comment says 5.07 and later clients do not handle it
(gs2lib `IEnums.h:248`).

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
**Trigger**: Raw binary data transfer. The file queue emits it only for clients on the
GEN_5 and older encryption generations. For GEN_6 the raw packet goes out with no
announcement and no trailing newline (gs2lib `CFileQueue.cpp:94-96`, `:102-103`).
```
[GINT3: data_length] // Length of the raw packet, including its trailing \n
[RAW_DATA...]        // Raw binary data
```
The length is `packet.length() + 1`: the raw packet (type byte included) plus the newline the
queue appends to every packet for GEN_5 and older (gs2lib `CFileQueue.cpp:96`, `:102`).

### PLO_BOARDPACKET (101) - Full Board (8192 bytes)
**Trigger**: Player enters a level — the full tile board is sent here.
```
[8192 bytes tile_data]   // 64×64 tiles, 2 bytes per tile (little-endian)
```
The server sends this **raw 8192-byte board dump** as raw data. It sends the dump
immediately after a **PLO_RAWDATA (100)** packet that announces the byte count. A client
usually receives a level's tiles this way, not through PLO_LEVELBOARD. The file queue puts
this packet in the "normal" buffer and every other raw packet (files, layers, bytecode) in
the file buffer (gs2lib `CFileQueue.cpp:65`). The tiles are written in the server's byte
order, which is little-endian on x86 (`server/include/level/LevelTiles.h:134-145`).

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
> **Double-strip trap** (pyReborn's parser experience; not checked against the reference
> client): if the framing layer already strips the trailing `\n`, do **not** strip it a second
> time when parsing the file body, or files ending in `0x0A` come out truncated.
>
> **Pre-2.1 client variant:** This variant has no `modtime` field. It uses
> `[GCHAR name_len][name][data]` (`server/src/player/Player.cpp:638-641`). The queue still
> appends the trailing newline, so the RAWDATA length is only smaller by the 5 modtime bytes.
>
> **Pre-2.14 clients** do not get the large-file sequence. The server sends the whole file in
> one `PLO_FILE`, and it refuses with a failure message any file over 64000 bytes
> (`server/src/player/Player.cpp:614-621`, `:635`).

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
**Trigger**: Additional level layer data, sent after the board on level entry. Sent as a raw
packet (`PLO_RAWDATA` framing, see above).
```
[BYTE: layer]        // Layer index, a raw byte (not +32)
[BYTE: 0]            // x, raw
[BYTE: 0]            // y, raw
[BYTE: 64]           // width, raw
[BYTE: 64]           // height, raw
[4096 x 2 bytes]     // tiles, 2 bytes each, same layout as PLO_BOARDPACKET
```
The four header fields after the layer are raw bytes written with `<<`, not GCHARs
(`server/src/level/Level.cpp:132-137`).

### PLO_NPCBYTECODE (131) - NPC Bytecode
**Trigger**: Sent automatically alongside `PLO_NPCPROPS` when the NPC has compiled GS2
bytecode. The gate is the **server generation** (`Server.Generation == MODERN`), not a
client version. It goes out as a single raw packet, so the file queue adds the
`PLO_RAWDATA (100)` announcement for GEN_5 and older clients (see PLO_RAWDATA).
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[BYTECODE...]        // Raw compiled GS2 bytecode, to end of packet
```
**Source**: `Level::sendNPCToPlayer` (`server/src/level/Level.cpp:1475-1481`):
```cpp
if (m_server->Generation == ServerGeneration::MODERN && !npc->getScript().getClientByteCode().empty())
{
    CString byteCodePacket = CString() >> (char)PLO_NPCBYTECODE >> (int)npc->id;
    byteCodePacket.write(/* raw bytecode */);
    player->sendRawPacket(byteCodePacket);
}
```
(`>> (int)` is `writeGInt`, a **3-byte** GINT3.) These implementations
validate the bytes: pyReborn `parse_npc_bytecode` (`packets.py`) and
`game_tester/tier5_tests.py:test_npc_bytecode_synthetic`.

### PLO_WEAPONBYTECODE (132) - Weapon Bytecode (before 5.07)
**Trigger**: Response to `PLI_UPDATESCRIPT (158)` for a client older than 5.07. Clients 5.07
and later get `PLO_WEAPONBYTECODE2 (140)` instead. Sent as a raw packet.
```
[GCHAR: name_len]    // Weapon name length
[name]               // Weapon name
[BYTECODE...]        // Compiled GS2 bytecode, to end of packet
```
**Source**: `Weapon::sendByteCodeToPlayer` (`server/src/object/Weapon.cpp:212-214`). The enum
comment says to send the weapon first (gs2lib `IEnums.h:268`).

### PLO_CLASSBYTECODE (133) - Class Bytecode (before 5.07)
**Trigger**: Response to `PLI_UPDATECLASS (161)` for a client older than 5.07. Clients 5.07
and later get `PLO_LOADSCRIPT (197)`. Sent as a raw packet.
```
[GCHAR: name_len]    // Class name length
[name]               // Class name
[BYTECODE...]        // Compiled GS2 bytecode, to end of packet (empty for an unknown class)
```
**Source**: `ScriptClass::getClassPacket` (`server/src/scripting/ScriptClass.cpp:76-77`). For a
class the server does not have, it sends the name with no bytecode
(`server/src/player/packets/PlayerClientPackets.cpp:1537-1540`).

`PLO_WEAPONHASH (193)`, the pre-5.07 counterpart of the `PLO_LOADSCRIPT` weapon form, is in
the table at the end of this page.

### PLO_GANISCRIPT (134) - GANI Bytecode
**Trigger**: Response to `PLI_UPDATEGANI (157)` when the client's CRC32 differs from the
server's current gani bytecode. Sent as a plain packet, not through `PLO_RAWDATA` framing.
```
[GCHAR: name_len]    // Gani name length
[gani_name]          // WITHOUT the .gani suffix
[BYTECODE...]        // Compiled gani-script bytecode, to end of packet
```
**Source**: `GameAni::getBytecodePacket` (`server/src/animation/GameAni.cpp:114-126`). The
server strips a trailing `.gani` from the stored name before sending. It sends the bytecode
with `sendPacket` (`msgPLI_UPDATEGANI`, `server/src/player/packets/PlayerClientPackets.cpp:1488`).
It is always followed by a `PLO_LOADGANI (195)` load command, sent regardless of whether the
bytecode itself was sent again (`PlayerClientPackets.cpp:1470-1493`).

### PLO_WEAPONBYTECODE2 (140) - Weapon Bytecode
**Trigger**: Response to `PLI_UPDATESCRIPT (158)` (on-demand weapon-bytecode fetch) for
clients **5.07 and later** (older clients get `PLO_WEAPONBYTECODE (132)`), and also the
server's fallback answer to a `PLI_UPDATECLASS` for a **nonexistent** class from a 5.07 or
later client. The fallback has only a header and empty bytecode. This is a deliberate
workaround. The weapon form is sent as a raw packet.
```
[GSHORT: header_len] // Length of the header CSV
[header CSV]         // "weapon,<name>,1,<desKey>"  (quoted-CSV; no CRC in THIS header)
[BYTECODE...]        // Compiled GS2 bytecode, to end of packet (MAY be empty)
```
**Source**: `Weapon::sendByteCodeToPlayer` (`server/src/object/Weapon.cpp:207-215`). The
header CSV is Reborn quoted-CSV (`toCSV`): `weapon,<name>,1,<desKey>` where `<desKey>` is a
64-bit script hash packed as two GINT5s (`Weapon.cpp:346-349`). This is `m_header`
**without** the CRC32. The server sends the CRC-bearing variant (`m_headerWithCRC`,
`Weapon.cpp:367-370`) in `PLO_LOADSCRIPT (197)` instead. The unknown-class fallback
(`msgPLI_UPDATECLASS`, `server/src/player/packets/PlayerClientPackets.cpp:1524-1535`) sends a
`class,<name>,1,<10 spaces>,<5 spaces>` header with **empty bytecode**, as a plain packet.
The code comments it "should technically be PLO_LOADSCRIPT" but the client breaks
`player.join()` scripts if a missing class arrives that way. Parsers must accept an empty
bytecode tail. A client older than 5.07 gets `PLO_CLASSBYTECODE (133)` with the name only.

### PLO_NPCDEL2 (150) - NPC Delete v2
**Trigger**: NPC removed from specific level
```
[GCHAR: level_len]   // Level name length
[STRING: level_name] // Level name
[GINT3: npc_id]      // NPC identifier
```

### PLO_HIDENPCS (151) - Hide NPCs
**Trigger**: NPCs should be hidden. The reference server never sends it. The enum comment
says it "might delete all npcs with an id under 1000" (gs2lib `IEnums.h:273`).
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
its `PLO_MOVE2 (189)` counterpart below. Built by `getMoveQueuePacketData` as `move1`
(`server/src/object/NPC.cpp:540-548`), sent at `NPC.cpp:564-565` and `:588-591`. The enum
has a maintainer comment: `// Unhandled by 6.037.` (gs2lib `IEnums.h:286`).
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
// then the whole move queue, one record per queued move:
[GCHAR: x]           // pixel / 8, level-local half-tiles
[GCHAR: y]
[GCHAR: dx]          // delta / 8 + 100
[GCHAR: dy]          // delta / 8 + 100
[GSHORT: time]       // remaining duration in 0.05 s ticks
[GCHAR: options]     // Movement option flags
```

### PLO_SHOWIMGNPC (166) - NPC Show Image
**Trigger**: A script changes an NPC's showimg state, or a player enters a level
(`NPCServer.cpp`, `server/src/npcserver/NPCServer.cpp:691-751`; the level-entry form is
`NPC::getShowImagesPacket`, `server/src/object/NPC.cpp:268-281`).
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[GCHAR: index + 10]  // Showimg slot; the server accepts indexes 0-199
[PROP_DATA...]       // showimg property pairs: [GCHAR: prop_id][value] ...
```
Index 9 is special: it makes the client erase all of the NPC's showimgs, and the
level-entry form starts with it (`NPC.cpp:274`). The property ids are listed in the enum
comment (gs2lib `IEnums.h:287`: 0 image, 1 x, 2 y, 3 layer, 4 image part, 5 and 6 particle
data, 7 angle, 8 particle). The server serializes them in
`ShowImg::getAllPropsPacket`. The per-property encodings are not derived here.

### PLO_GHOSTMODE (170) - Ghost Mode
**Trigger**: Player enters/exits ghost mode. The reference server never sends it and the
enum gives no layout (gs2lib `IEnums.h:291`), so the body below is **unverified**.
```
[GCHAR: ghost_state] // Unverified: 1=enter ghost, 0=exit ghost
```

### PLO_BIGMAP (171) - Big Map Data
**Trigger**: Sent at login to clients 2.1 and later when the `bigmap` option is set to
four comma-separated tokens (`server/src/player/PlayerClient.cpp:495-501`), and by the
GS1 `setmap` command (`server/src/scripting/gs1/GS1Commands.cpp:2630`). Same layout as
`PLO_MINIMAP`. The enum comment says 6.037 does not handle it.
```
[STRING: map_text]   // "imgfile,levelsfile,x,y" per the GS1 command, decimal text, to end of packet
```
The server does not reorder the tokens: the login path relays the option's four trimmed tokens
in the order written, and the GS1 command sends `imgfile,levelsfile,x,y` in that order. See
the token-order note under PLO_MINIMAP.

### PLO_MINIMAP (172) - Minimap Data
**Trigger**: Sent at login to clients 2.1 and later when the `minimap` option is set to four
comma-separated tokens (`server/src/player/PlayerClient.cpp:504-512`), and by the GS1
`setminimap` command (`server/src/scripting/gs1/GS1Commands.cpp:2650`).
```
[STRING: map_text]   // "imgfile,levelsfile,x,y": four trimmed tokens joined by commas
```
The x and y tokens are decimal text, not GCHARs. The enum comment's example is
`zodiacminimap.txt,zodiacworldminimap3.png,10,10` (gs2lib `IEnums.h:293`). That example puts the
`.txt` file first, which conflicts with the `imgfile,levelsfile` order of the GS1
`setminimap` command (`server/src/scripting/gs1/GS1Commands.cpp:2650`). The server relays the
option text in the order written (`PlayerClient.cpp:504-512`), so the order a client sees is
whatever the operator configured; the reference does not settle which one is right.

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
`IEnums.h` has this comment: `// Unhandled by 6.037.`

`ShootPacketWrapper::constructShootV1()`
(`GServer-v2/server/src/player/Player.cpp:239-254`) builds the body:
```
[GSHORT: owner_id]
[GINT3: source]      // NPC id, or 0 for a player shot
[GCHAR: x]           // (pixel_x % 1024) / 8 = level-local half-tiles
[GCHAR: y]           // (pixel_y % 1024) / 8
[GCHAR: z]           // pixel_z / 16 + 50
[GCHAR: angle]
[GCHAR: z_angle]
[GCHAR: power]
[GCHAR: gani_len][gani]
[GCHAR: param_len][shoot_params]
```

### PLO_KINGDOMSMODE (176) - Server Mode: Kingdoms
**Trigger**: The server option `servermode = kingdoms`. `Player::sendLogin`
sends it right after `PLO_SIGNATURE` (`Player.cpp:746-752`, origin/beta4), to
every login type (client, RC and NC) with no client-version test. It comes
before `PLO_HASNPCSERVER`, `PLO_ONLINEMODE` and the first `PLO_PLAYERPROPS`.
```
// No additional data
```
Wire bytes: `D0 0A`.

Older sources call packet 176 `PLO_DISABLECLASSICMODE` or `PLO_FULLSTOP`.
Neither name describes what the reference sends. Nothing sends a
classic-mode-disable or full-stop packet. A client must not freeze input on 176.

### PLO_NEWWORLDMODE (177) - Server Mode: New World
**Trigger**: The server option `servermode = newworld`, sent at the same place
as 176 (`Player.cpp:751-752`). The two are exclusive: an `if` / `else if`
chooses at most one, and `servermode = normal` (the default) sends neither.
`servermode` is read once at startup (`Server.cpp:196-200`).
```
// No additional data
```
Wire bytes: `D1 0A`.

New-world mode also widens `PLPROP_COLORS` from 5 to 8 bytes
(`PropertySerializers.h:793-796`). Older sources call packet 177
`PLO_FULLSTOP2` (stop input and hide the HUD); the reference does not do that.

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
`CString.cpp:1220-1227`), and field 0 repeats the server name.
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
**Trigger**: Sent once at login to clients 2.1 and later
(`server/src/player/PlayerClient.cpp:514-516`). `sendRPGMessage` sends it again later with the
text as a quoted CSV, split at `#b` (`server/src/player/PlayerClient.cpp:1746-1751`)
```
[CSV: text...]       // Two quoted strings: "Welcome to <server name>.","<vendor> <app> programmed by <credits>."
```

### PLO_STATUSLIST (180) - Status List
**Trigger**: Sent at login to clients 2.1 and later with the server's status-list options
(`server/src/player/PlayerClient.cpp:529-536`) and at RC login (`server/src/player/PlayerRC.cpp:264`)
```
[STRING: statuses]   // The status names joined with "," and NOT quoted, to end of packet
```

### PLO_LISTPROCESSES (182) - List Processes
**Trigger**: Request client process list. The reference server does not send it: the send
is commented out because it crashes Windows v6 clients (`server/src/player/PlayerClient.cpp:538-543`).
```
// No additional data
```

### PLO_BOARDHEIGHTS (185) - Board Height Layer
**Trigger**: The server sends this packet when it delivers a gmap segment with height
overrides to a player. It sends nothing for a non-gmap level, or for a segment without
overrides (`server/src/level/Level.cpp:437-441`, called at
`server/src/player/PlayerClient.cpp:1464`).
```
[GCHAR: mapX]         // GMAP segment column
[GCHAR: mapY]         // GMAP segment row
[GCHAR: blockX]       // Height-block origin X (server always sends 0)
[GCHAR: blockY]       // Height-block origin Y (server always sends 0)
[GCHAR: blockW]       // Height-block width (server always sends 8)
[GCHAR: blockH]       // Height-block height (server always sends 8)
[(blockW+1)*(blockH+1) entries, row-major (index = y*9+x for the default 8x8 block):]
  [GCHAR: whole + 50]  // Integer height part, biased by +50
  [GCHAR: frac * 128]  // Fractional height part, scaled by 128
```
**Source**: `SubLevel::sendBoardHeightsToPlayer` (`server/src/level/Level.cpp:437-481`). The block
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
[GINT3: npc_id]      // NPC identifier (3 bytes)
// then the whole move queue, one record per queued move:
[GSHORT: pos_x]       // Current X, X2/Y2-style pixel-coord encoding (see below)
[GSHORT: pos_y]       // Current Y, same encoding
[GSHORT: dx]           // X delta to the destination, same encoding
[GSHORT: dy]           // Y delta to the destination, same encoding
[GSHORT: time_50ms]   // REMAINING duration (duration - elapsed), in 0.05s ticks
[GCHAR: options]      // Movement option flags
```
Each `GSHORT` coordinate/delta field uses the same encoding as player `X2`/`Y2` properties
(`PropertyPixelCoordinate::serialize`, `server/src/utilities/PropertySerializers.cpp:399-405`):
`value = (abs(pixels) << 1) | (negative ? 1 : 0)`. See
[Data Types: X2/Y2 Encoding](data-types.md#x2y2-encoding-the-weird-one) for the decode.

**Source**: `NPC::getMoveQueuePacketData` (`server/src/object/NPC.cpp:505-553`, the
`result.second` form, lines 528-538), sent via `NPC::sendMoveQueueToLevel` to the nearby
players of version 2.3 or later (`NPC.cpp:578-587`), and to a single player on level entry
(`NPC::sendMoveQueueToPlayer`, `NPC.cpp:555-567`).

### PLO_SERVERLISTCONNECTED (190) - Server Connected to the List Server
**Trigger**: Sent at login when the server is connected to the list server, before
`PLO_RESETCLIENT` (`server/src/player/PlayerClient.cpp:487-489`). It is also sent to
connected players when the list-server link comes up, except NC and NPC-server accounts
(`server/src/ServerList.cpp:358-370`, the skip at `:365`). RC login sends it too
(`server/src/player/PlayerRC.cpp:252`).
```
// No additional data
```
The enum comment says the client then logs in to IRC and requests ban types, PM guilds,
PM servers, global PMs and buddy tracking (gs2lib `IEnums.h:311`).

### PLO_SHOOT2 (191) - Shoot Projectile (v2, >= CLVER_5_07)
**Trigger**: Projectile broadcast to clients at or above `CLVER_5_07`. See
[Version-Gated Behavior](version-gated-behavior.md#projectiles-plo_shoot-vs-plo_shoot2).
`IEnums.h` has this comment: "Valid message in 5.07 and 6.037. The code it uses is unique."

`ShootPacketWrapper::constructShootV2()`
(`GServer-v2/server/src/player/Player.cpp:256-273`) builds the body:
```
[GSHORT: owner_id]
[GSHORT: pixel_x]    // plain GSHORT
[GSHORT: pixel_y]
[GSHORT: pixel_z]
[BYTE: offset_x + 32]
[BYTE: offset_y + 32]
[GCHAR: angle]
[GCHAR: z_angle]
[GCHAR: power]
[GCHAR: gravity]     // see the gravity units table under PLI_SHOOT2
[GSHORT: gani_len][gani]
[GCHAR: param_len][shoot_params]
```

> ⚠️ The 5.0.0.7 client reads x/y/z and gravity in a different form. See
> [Client-side SHOOT2 layout](#client-side-shoot2-layout). With the server body, a static
> read predicts positions at half value (an odd value flips the sign) and gravity at 4×
> the intended value for gani names under 128 bytes. No lab test confirms this yet.

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
> (gs2lib `IEnums.h:316`). The trailing stringlist currently carries only the `SETBACKTO`
> directive but is a general quoted-CSV list.

**Source**: `msgPLI_UPDATEGANI` (`server/src/player/packets/PlayerClientPackets.cpp:1491`):
```cpp
sendPacket(CString() >> (char)PLO_LOADGANI >> (char)gani.length() << gani << "\"SETBACKTO " << findAni->getSetBackTo() << "\"");
```

### PLO_LOADSCRIPT (197) - Load Script (TWO payload forms)
**Trigger**: (a) weapon-header announcement during weapon registration, for clients 5.07
and later on a modern-generation server. (b) class-bytecode delivery in response to
`PLI_UPDATECLASS (161)` for clients 5.07 and later, through `PLO_RAWDATA` framing. Older
clients get `PLO_WEAPONHASH (193)` for (a) and `PLO_CLASSBYTECODE (133)` for (b).

**Form 1 — weapon announcement** (`Weapon::registerWeaponWithPlayer`, `server/src/object/Weapon.cpp:194-199`):
```
[header CSV]         // RAW, no length prefix, no bytecode — to end of packet
                     // "weapon,<name>,1,<desKey>,<crc32>"  (m_headerWithCRC)
```

**Form 2 — class bytecode** (`ScriptClass::getClassPacket`, `server/src/scripting/ScriptClass.cpp:66-77`; sent raw, `server/src/player/packets/PlayerClientPackets.cpp:1520`):
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
(two GINT5s = 64-bit hash),crc32 (GINT5)` per the gs2lib `IEnums.h:317` comment and
`Weapon.cpp:355-370` / `ScriptClass.cpp:44-55` header construction.

Ids 104, 108, 109, 168, 181, 193 and 198 are in the table in the next section.

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

The GEN_5 cipher, the iterator and limit tables, and the bundle processing order are in
[Encryption](encryption.md). [Encryption Details (ENCRYPT_GEN_5)](#encryption-details-encrypt_gen_5)
above is the short summary. The packets in this file are the payload of that framing: the
compression-type byte of a bundle is not encrypted, and the server compresses first, then
encrypts, then prefixes the length and type (gs2lib `CFileQueue.cpp:230-262`).

This document describes the core packet structures that the Reborn protocol uses.
Implementations must use these exact formats for compatibility with existing servers
and clients.
