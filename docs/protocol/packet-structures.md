# Reborn Protocol v2 - Packet Structure Reference

## Overview

This document provides comprehensive documentation of the Reborn protocol packet structures based on analysis of the GServer-v2 codebase. All packet structures are documented down to the primitive level for cross-language implementation.

> **Prerequisites**: Before diving into packet structures, understand:
> - [Data Types](data-types.md) - G-type encoding (the +32 obsession)
> - [String Types](strings.md) - The three different string formats (yes, three)
> - [Encryption](encryption.md) - How packets are bundled and encrypted

## Protocol Architecture

### Packet Bundle Structure

All packets are sent within bundles with the following structure:

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

Within each bundle, packets are separated by newlines (`\n`) except for raw data packets:

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
[Data Types](data-types.md). This page stays focused on packet layouts; when a field width
matters, follow the link rather than re-deriving it here.

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
[STRING: tile_data]  // Raw tile data (2 bytes per tile)
```

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
[GUCHAR: length_power] // Length (5 bits) + Power (3 bits)
```

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
> numeric prop and desyncing every property after it. The canonical width table and the
> cross-prop quirks are documented in [Data Types](data-types.md#player-property-data-types).
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
> - otherwise → `[GCHAR: power+30][GCHAR: img_len][STRING: image]` — the **power byte comes
>   first**, biased by **+30**, then the length-prefixed image name
>
> **SHIELDPOWER** (`PropertyShieldPower`):
> - power `0` → `[GCHAR: 0]`
> - power 1-3 with **no** custom image → `[GCHAR: power]` (1 byte)
> - otherwise → `[GCHAR: power+10][GCHAR: img_len][STRING: image]` — note the bias is
>   **+10** here, not +30 like the sword
>
> Yes, the format changes based on the value. Yes, the power byte precedes the length.
> Yes, sword and shield use different biases.
**GANI (10)**: `[GCHAR: length][string]` - Animation file
**HEADIMAGE (11)**: Variable format (see below) — *also called HEADGIF in some older docs*

> ⚠️ **MAGIC NUMBER ALERT** - HEADIMAGE
>
> The first byte has a dual interpretation:
> - If byte < 100: It's a **preset head ID** (no string follows, just the ID byte)
> - If byte ≥ 100: **Subtract 100** to get the actual string length, then read that many bytes
>
> Example: Byte value 105 means "read 5 bytes of string data for the head image filename."
> Byte value 5 means "use preset head #5, no string follows."
>
> The magic number 100 was chosen because early Graal had fewer than 100 preset heads.
> This was a reasonable assumption in 1999.
**CURCHAT (12)**: `[GCHAR: length][string]` - Current chat bubble
**COLORS (13)**: `[8 bytes: color_data]` (new-world / v6.037) or `[5 bytes]` (classic) - Player colors. The reborn stack targets v6.037, so **8 bytes** here. Each byte is a palette index (+32 encoded).
**ID (14)**: `[GSHORT: player_id]` (2 bytes)
**X (15)**: `[GCHAR: x * 2]` - X position in **half-tiles** (tile = value/2). *Not* pixels/2.
**Y (16)**: `[GCHAR: y * 2]` - Y position in **half-tiles** (tile = value/2)
**SPRITE (17)**: `[GCHAR: (sprite << 2) | direction]` - direction = low 2 bits, sprite/frame = rest
**STATUS (18)**: `[GCHAR: status_flags]` - Player status bits
**CARRYSPRITE (19)**: `[GCHAR: carry_sprite]` - Carried object sprite
**CURLEVEL (20)**: `[GCHAR: length][string]` - Current level name
**HORSEGIF (21)**: `[GCHAR: length][string]` - Horse image
**HORSEBUSHES (22)**: `[GCHAR: bush_count]` - Bushes eaten by horse
**EFFECTCOLORS (23)**: Variable - `[GCHAR: first]`; if `first == 0` the prop is just that 1 byte, otherwise 5 bytes total (`first` + 4 color bytes). Visual effect colors (RGBA tint)
**CARRYNPC (24)**: `[GINT3: npc_id]` (**3 bytes**) - Carried NPC ID
**APCOUNTER (25)**: `[GSHORT: ap_time]` (**2 bytes** — not 1) - AP recovery counter
**MAGICPOINTS (26)**: `[GCHAR: mp_count]` - Magic points
**KILLSCOUNT (27)**: `[GINT3: kill_count]` (**3 bytes**) - Player kills
**DEATHSCOUNT (28)**: `[GINT3: death_count]` (**3 bytes**) - Player deaths
**ONLINESECS (29)**: `[GINT3: online_time]` (**3 bytes**) - Online time in seconds
**IPADDR (30)**: `[GINT5: ip_address]` (**5 bytes**) - IP as a packed gint5 integer, *not* 5 raw octets
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
| 83 | UNKNOWN83 | `[GINT5]` (client reads 5 bytes) |

A parser that treats 37-74 as one flat GATTRIB block will misalign every subsequent
property. Likewise, props **51** (void) and **53** (1 byte, not a string) are the two that
most often desync a naive parser.

**X2/Y2/Z2 (78/79/80)** are the high-precision pixel coordinates used on GMAPs and for
sub-tile positions. Each is a GSHORT carrying `value = (abs(pixels) << 1) | (negative ? 1 : 0)`.
Decode: `pixels = value >> 1; if (value & 1) pixels = -pixels;` then `tiles = pixels / 16`.
See [Data Types: X2/Y2 Encoding](data-types.md#x2y2-encoding-the-weird-one).

## Remote Control Packets (PLI_RC_*)

These packets are used by RC (Remote Control) clients for server administration.

> **For the complete, byte-validated RC and NC reference** — including the login handshakes,
> the GEN_2 vs GEN_5 distinction, the full PLI/PLO tables, and the `getPropsForRCPacket`
> blob layout — see [RC & NC Protocols](rc-nc-protocols.md). The entries below are a quick
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

These packets are used by NC (NPC Control) clients for NPC/content management.

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
[GUINT5: checksum]   // Local GANI checksum
[STRING: gani_name]  // GANI name (without .gani extension)
```

### PLI_UPDATESCRIPT (158) - Update Weapon Script
**Trigger**: Client requests weapon bytecode
```
[STRING: weapon_name] // Weapon name
```

### PLI_UPDATECLASS (161) - Update NPC Class
**Trigger**: Client requests class bytecode
```
[GINT5: checksum]    // Local class checksum
[STRING: class_name] // Class name
```

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
Encryption is limited based on compression type:
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

1. **Byte Order**: Multi-byte primitive encoding is summarized in [Data Types](data-types.md)
2. **String Termination**: String formats are documented in [String Types](strings.md)
3. **Coordinate System**: Coordinate frames and GMAP packing live in [Data Types](data-types.md)
4. **Error Handling**: Invalid packets should be ignored, not cause disconnection
5. **Version Compatibility**: Some packets vary by client version (check version ID)

## Server-to-Client Packets (PLO_*)

### PLO_LEVELBOARD (0) - Level Board Data
**Trigger**: Player enters level or requests level data
```
[tile_data...][\n]   // Newline-terminated inline board data
```
Inline (newline-terminated) board data. **Note**: the full 64×64 board is normally
*not* sent here. The complete 8192-byte tile dump is delivered out-of-band as
**PLO_BOARDPACKET (101)**, announced by a preceding **PLO_RAWDATA (100)** length packet.
PLO_LEVELBOARD is used for the inline/partial board representation. Each tile is a
16-bit value (2 bytes) representing the tile index.

### PLO_LEVELLINK (1) - Level Link/Warp

> ⚠️ **THE TRAP** ⚠️
>
> This packet does NOT use a length-prefixed GSTRING. Multiple client implementations
> have made this mistake. The server sends raw string data until a newline (0x0A).
> If you try to read the first byte as a length, you'll read 'l' from "level.nw",
> compute length = 108 - 32 = 76, and consume half the next packet. Don't do this.
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

> Note prop **4 (POWERIMAGE)** is a power byte followed by a length-prefixed image string —
> a common mis-parse is to read power as a bare byte and lose sync. pyReborn reliably reads
> ID/X/Y/TYPE; clients that only need the type can stop after prop 3.

### PLO_NPCPROPS (3) - NPC Properties  
**Trigger**: NPC properties change or player enters level
```
[GINT3: npc_id]      // NPC identifier (3 bytes)
[GCHAR: prop_id][payload]...   // NPC property pairs (their OWN enum, not player props)
```

> NPCs use a **distinct `NPCProp` enum** — prop 5 is RUPEES (not a direction), 17 is ID,
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
> whole-tile coords or the server won't match the chest.

### PLO_LEVELSIGN (5) - Level Sign
**Trigger**: Player enters level with signs
```
[GCHAR: tile_x]      // Sign X coordinate (WHOLE tiles, 0-63)
[GCHAR: tile_y]      // Sign Y coordinate (WHOLE tiles, 0-63)
[ENCODED_TEXT...]    // Graal sign-encoded text, to end of packet (NOT plain ASCII!)
```

> ⚠️ **The sign text is NOT plain ASCII.** It is encoded with a custom alphabet + a
> button-symbol escape table (`encodeSign`/`decodeSign` in GServer `LevelSign.cpp`). Each
> encoded byte is `alphabet_index + 32` (a GCHAR). Reading it as a raw string gives
> garbage.

**Decoding**: for each byte, `code = byte - 32`. If `code` is in the symbol code-table
(`ctab`), emit `#` followed by the mapped button symbol; otherwise emit `signAlphabet[code]`.
Literal `#K` (code 13) sequences are stripped.

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
**Trigger**: Another player modifies tiles
```
[GCHAR: start_x]     // Starting X coordinate
[GCHAR: start_y]     // Starting Y coordinate
[GCHAR: width]       // Modification width
[GCHAR: height]      // Modification height
[TILE_DATA...]       // New tile data
```

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
**Trigger**: Player is being disconnected
```
[STRING: reason]     // Disconnect reason
```

### PLO_HORSEADD (17) - Horse Added
**Trigger**: Horse is spawned
```
[GUSHORT: player_id] // Player who added horse
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
[GCHAR: dir_bush]    // Direction + bush count
[STRING: image]      // Horse image
```

### PLO_HORSEDEL (18) - Horse Removed
**Trigger**: Horse is destroyed
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
**Trigger**: Item is dropped or spawned
```
[GCHAR: x * 2]       // X position (half-tiles; tile = value/2)
[GCHAR: y * 2]       // Y position (half-tiles)
[GCHAR: item_id]     // NUMERIC LevelItemType id (0-24), NOT a length-prefixed string
```

> `item_id` is a single numeric byte, mapped through the `LevelItemType` table below — it is
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
**Trigger**: Item is picked up or destroyed
```
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
```

### PLO_NPCMOVED (24) - NPC Moved
**Trigger**: NPC changes position (hides NPC during level transitions)
```
[GUINT: npc_id]      // NPC identifier
```

### PLO_SIGNATURE (25) - Player Signature
**Trigger**: Player requests signature verification
```
[STRING: signature]  // Player signature data
```

### PLO_NPCACTION (26) - NPC Action
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
**Trigger**: NPC is removed from level
```
[GUINT: npc_id]      // NPC identifier
```

### PLO_FILESENDFAILED (30) - File Send Failed
**Trigger**: Requested file could not be sent
```
[STRING: filename]   // Failed file name
```

### PLO_FLAGDEL (31) - Flag Deleted
**Trigger**: Flag is removed
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
**Trigger**: Weapon is removed from player
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
[GSHORT: from_id]    // Sender player ID (graal short — ((b1-32)<<7)|(b2-32), NOT raw big-endian)
[CSV body...]        // toCSV: "","Private message:",<msg>   (or "Mass message:")
```

> Two gotchas: (1) `from_id` is a **GSHORT** (graal-encoded), not a raw 16-bit big-endian
> value — decoding it as `(b0<<8)|b1` gives wildly wrong ids. (2) The body is a quoted-CSV
> structure (`"<sender>","Private message:",<msg>`), not a bare message string.

### PLO_PUSHAWAY (38) - Push Away
**Trigger**: Player is pushed by force
```
[PUSH_DATA...]       // Push force and direction data
```

### PLO_LEVELMODTIME (39) - Level Modification Time
**Trigger**: Level modification time is requested
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

> **The server is a pure relay for PvP.** It forwards `PLO_HURTPLAYER` to the victim; the
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
**Trigger**: Trigger action is executed
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

> The trailing level name (e.g. `"chicken.gmap"`) is easy to miss — the server appends
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
**Trigger**: Large file transfer begins (file > 32000 bytes)
```
[STRING: filename]   // File being transferred (raw, to end of packet)
```

> The total size is **not** in this packet — it arrives separately as `PLO_LARGEFILESIZE (84)`.
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
This is the **raw 8192-byte board dump**, sent as raw data immediately after a
**PLO_RAWDATA (100)** packet that announces the byte count. This is the canonical
way a client receives a level's tiles (not PLO_LEVELBOARD).

### PLO_FILE (102) - File Data
**Trigger**: File content transfer (small files, ≤ 32000 bytes)

A file arrives as **two packets**: a `PLO_RAWDATA (100)` announcing the byte count of the
*following* packet, then the `PLO_FILE (102)` itself.

```
[GINT5: modtime]     // 5 bytes — file modification time (operator>>(long long))
[GCHAR: name_len]    // 1 byte
[name]               // name_len raw bytes
[file_data]          // raw file bytes
[0x0A]               // single trailing newline
```

> The doc previously claimed `[GCHAR file_type][GUINT5 file_size][data]` — **that is wrong**.
> There is no "file type" byte and no inline size: the size comes from the preceding
> `PLO_RAWDATA`, and a `GINT5 modtime` precedes a GCHAR-length-prefixed name.
>
> The announced `PLO_RAWDATA` length = `1 (file id byte) + 5 (modtime) + 1 + name_len +
> data_len + 1 (trailing \n)`.
>
> **Double-strip trap:** the raw-data framing layer already strips the trailing `\n`. Do
> **not** strip it a second time when parsing the file body, or files ending in `0x0A` come
> out truncated.
>
> **Pre-2.1 client variant:** no `modtime` field — `[GCHAR name_len][name][data]`, no
> trailing newline, and the RAWDATA length is correspondingly smaller.

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
**Trigger**: Compiled NPC script transfer
```
[GINT3: npc_id]      // NPC identifier
[BYTECODE_DATA...]   // Compiled script bytecode
```

### PLO_GANISCRIPT (134) - GANI Script
**Trigger**: GANI animation bytecode
```
[GANI_BYTECODE...]   // Compiled GANI script
```

### PLO_NPCWEAPONSCRIPT (140) - NPC Weapon Script
**Trigger**: Weapon script transfer
```
[GUSHORT: info_len]  // Script info length
[SCRIPT_DATA...]     // Weapon script data
```

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

### PLO_MOVE (165) - Move Command
**Trigger**: Server-initiated movement
```
[MOVEMENT_DATA...]   // Movement command data
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

### PLO_SHOOT (175) - Shoot Projectile (Server)
**Trigger**: Server-initiated projectile
```
[SHOOT_DATA...]      // Projectile data
```

### PLO_FULLSTOP (176) - Full Stop
**Trigger**: Disable client input/HUD
```
// No additional data - freezes client completely
```

### PLO_SERVERWARP (178) - Server Warp
**Trigger**: Warp to different server
```
[STRING: server_info] // Server connection info
```

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

### PLO_UPDATEPACKAGEISUPDATED (187) - Package Updated
**Trigger**: Notify client of package update
```
[STRING: filename]   // Updated file name
```

### PLO_MOVE2 (189) - Move v2
**Trigger**: Enhanced movement command
```
[GUINT: player_id]   // Player to move
[MOVEMENT_DATA...]   // Enhanced movement data
```

### PLO_SHOOT2 (191) - Shoot v2
**Trigger**: Enhanced projectile (v5.07+)
```
[ENHANCED_SHOOT...]  // Enhanced projectile data
```

### PLO_CLEARWEAPONS (194) - Clear Weapons
**Trigger**: Remove all weapons from player
```
// No additional data - clears weapon list
```

### PLO_LOADGANI (253) - Load GANI
**Trigger**: Load GANI animation
```
[GCHAR: name_len]    // GANI name length
[STRING: gani_name]  // GANI name
[STRING: setbackto]  // SETBACKTO parameter
```

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

The compression type affects both the compression algorithm and encryption limits.

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

This documentation covers the core packet structures used in the Reborn protocol. Implementation should follow these exact formats for compatibility with existing servers and clients.
