# Reborn Protocol v2 - Packet Structure Reference

## Overview

This document provides comprehensive documentation of the Reborn protocol packet structures based on analysis of the GServer-v2 codebase. All packet structures are documented down to the primitive level for cross-language implementation.

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

### Reborn-Specific Encoding (G-Types)

The protocol uses specialized encoding for efficient data transmission:

- **GCHAR**: `char + 32` (ensures printable ASCII)
- **GUCHAR**: `unsigned char + 32`
- **GSHORT**: `((value >> 6) + 32) + ((value & 0x3f) + 32)` (2 bytes)
- **GUSHORT**: Same as GSHORT but for unsigned values
- **GINT**: 3-byte encoding
- **GINT4**: 4-byte encoding  
- **GINT5/GUINT5**: 5-byte encoding for timestamps/large values

### String Encoding

- **GSTRING**: `[GCHAR: length][string_data]` - String with Graal-encoded length prefix
- **Regular String**: Null-terminated or delimiter-terminated string

## Client-to-Server Packets (PLI_*)

### PLI_LEVELWARP (0) - Level Warp Request
**Trigger**: Player moves to a different level
```
[GUCHAR: tile_x]     // X coordinate (in tiles)
[GUCHAR: tile_y]     // Y coordinate (in tiles)  
[STRING: level_name] // Target level name
```
**Variant**: PLI_LEVELWARPMOD (30) - includes modification time:
```
[GUINT5: mod_time]   // Level modification timestamp
[GUCHAR: tile_x]
[GUCHAR: tile_y]
[STRING: level_name]
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
[GUCHAR: item_type]  // Item type (0-5: various items)
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

**NICKNAME (0)**: `[GCHAR: length][string]`
**MAXPOWER (1)**: `[GCHAR: hearts * 2]` (1 heart = 2 power)
**CURPOWER (2)**: `[GCHAR: current_power]`
**RUPEESCOUNT (3)**: `[GUINT: rupee_count]`
**ARROWSCOUNT (4)**: `[GCHAR: arrow_count]`
**BOMBSCOUNT (5)**: `[GCHAR: bomb_count]`
**GLOVEPOWER (6)**: `[GCHAR: glove_power]` (0-3)
**BOMBPOWER (7)**: `[GCHAR: bomb_power]` (0-3)
**SWORDPOWER (8)**: `[GCHAR: sword_power]` (0-4)
**SHIELDPOWER (9)**: `[GCHAR: shield_power]` (0-3)
**GANI (10)**: `[GCHAR: length][string]` - Animation file
**HEADGIF (11)**: `[GCHAR: length][string]` - Head image
**CURCHAT (12)**: `[GCHAR: length][string]` - Current chat bubble
**COLORS (13)**: `[5 bytes: color_data]` - Player colors
**ID (14)**: `[GUSHORT: player_id]`
**X (15)**: `[GCHAR: pixel_x / 2]` - X position
**Y (16)**: `[GCHAR: pixel_y / 2]` - Y position
**SPRITE (17)**: `[GCHAR: sprite_index]` - Current animation frame
**STATUS (18)**: `[GCHAR: status_flags]` - Player status bits
**CARRYSPRITE (19)**: `[GCHAR: carry_sprite]` - Carried object sprite
**CURLEVEL (20)**: `[GCHAR: length][string]` - Current level name
**HORSEGIF (21)**: `[GCHAR: length][string]` - Horse image
**HORSEBUSHES (22)**: `[GCHAR: bush_count]` - Bushes eaten by horse
**EFFECTCOLORS (23)**: `[4 bytes: effect_colors]` - Visual effect colors
**CARRYNPC (24)**: `[GUINT: npc_id]` - Carried NPC ID
**APCOUNTER (25)**: `[GCHAR: ap_time]` - AP recovery counter
**MAGICPOINTS (26)**: `[GCHAR: mp_count]` - Magic points
**KILLSCOUNT (27)**: `[GUINT: kill_count]` - Player kills
**DEATHSCOUNT (28)**: `[GUINT: death_count]` - Player deaths
**ONLINESECS (29)**: `[GUINT: online_time]` - Online time in seconds
**IPADDR (30)**: `[5 bytes: ip_address]` - Player IP address
**UDPPORT (31)**: `[GUSHORT: udp_port]` - UDP port
**ALIGNMENT (32)**: `[GCHAR: ap_value]` - Alignment Points
**ADDITFLAGS (33)**: `[GCHAR: flags]` - Additional player flags
**ACCOUNTNAME (34)**: `[GCHAR: length][string]` - Account name
**BODYIMG (35)**: `[GCHAR: length][string]` - Body image
**RATING (36)**: `[GFLOAT: rating][GFLOAT: deviation]` - ELO rating
**GATTRIB1-30 (37-74)**: `[GCHAR: length][string]` - Custom attributes
**Z (45)**: `[GCHAR: (z_pos + 50)]` - Z position
**GMAPLEVELX (43)**: `[GCHAR: gmap_x]` - GMAP level X
**GMAPLEVELY (44)**: `[GCHAR: gmap_y]` - GMAP level Y

## Remote Control Packets (PLI_RC_*)

These packets are used by RC (Remote Control) clients for server administration.

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

| Type | Size | Description | Encoding |
|------|------|-------------|----------|
| GCHAR | 1 byte | Signed char + 32 | `(char)value + 32` |
| GUCHAR | 1 byte | Unsigned char + 32 | `(unsigned char)value + 32` |
| GSHORT | 2 bytes | 16-bit value | `((value >> 6) + 32) + ((value & 0x3F) + 32)` |
| GUSHORT | 2 bytes | Unsigned 16-bit | Same as GSHORT |
| GINT | 3 bytes | 24-bit value | Custom 3-byte encoding |
| GINT4 | 4 bytes | 32-bit value | Custom 4-byte encoding |
| GINT5/GUINT5 | 5 bytes | Large values/timestamps | Custom 5-byte encoding |
| GSTRING | Variable | Length-prefixed string | `[GCHAR: len][string_data]` |

## Implementation Notes

1. **Byte Order**: All multi-byte values use little-endian encoding before G-encoding
2. **String Termination**: Regular strings are null-terminated or delimiter-terminated
3. **Coordinate System**: 
   - Tiles: 64×64 grid (0-63)
   - Half-tiles: 128×128 grid (0-127) 
   - Pixels: Multiply half-tiles by 16
4. **Error Handling**: Invalid packets should be ignored, not cause disconnection
5. **Version Compatibility**: Some packets vary by client version (check version ID)

## Server-to-Client Packets (PLO_*)

### PLO_LEVELBOARD (0) - Level Board Data
**Trigger**: Player enters level or requests level data
```
[64x64 tile_data]    // 8192 bytes of tile data (2 bytes per tile)
```
Each tile is encoded as a 16-bit value representing the tile type.

### PLO_LEVELLINK (1) - Level Link/Warp
**Trigger**: Level has warp/link destinations
```
[GCHAR: dest_x]      // Destination X coordinate
[GCHAR: dest_y]      // Destination Y coordinate  
[GCHAR: new_x]       // New X position after warp
[GCHAR: new_y]       // New Y position after warp
[STRING: dest_level] // Destination level name
```

### PLO_BADDYPROPS (2) - Baddy Properties
**Trigger**: Baddy properties change or player enters level
```
[GCHAR: baddy_id]    // Baddy identifier
[BADDY_PROPS...]     // Variable baddy property data
```

### PLO_NPCPROPS (3) - NPC Properties  
**Trigger**: NPC properties change or player enters level
```
[GUINT: npc_id]      // NPC identifier
[NPC_PROPS...]       // Variable NPC property data
```

### PLO_LEVELCHEST (4) - Level Chest
**Trigger**: Player opens chest or enters level with chests
```
[GCHAR: state]       // 0=closed, 1=opened
[GCHAR: tile_x]      // Chest X coordinate
[GCHAR: tile_y]      // Chest Y coordinate
```

### PLO_LEVELSIGN (5) - Level Sign
**Trigger**: Player enters level with signs
```
[GCHAR: tile_x]      // Sign X coordinate
[GCHAR: tile_y]      // Sign Y coordinate
[STRING: sign_text]  // Sign text content
```

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
[GCHAR: tile_x]      // X position
[GCHAR: tile_y]      // Y position
[GCHAR: item_type]   // Item type (0-5)
```

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
[GUSHORT: sender_id] // Sender player ID
[STRING: message]    // Private message text
```

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
[GUSHORT: attacker_id] // Attacking player ID
[GCHAR: hurt_dx]     // Knockback X direction
[GCHAR: hurt_dy]     // Knockback Y direction
[GCHAR: power]       // Damage amount
[GUINT: npc_id]      // NPC ID (if NPC attack)
```

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
[GCHAR: pixel_x]     // X position (pixels/2)
[GCHAR: pixel_y]     // Y position (pixels/2)
[GCHAR: pixel_z]     // Z position
[GCHAR: gmap_x]      // GMAP level X
[GCHAR: gmap_y]      // GMAP level Y
```

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
**Trigger**: Large file transfer begins
```
[STRING: filename]   // File being transferred
[GUINT5: file_size]  // Total file size
```

### PLO_LARGEFILEEND (69) - Large File End
**Trigger**: Large file transfer completes
```
[STRING: filename]   // Completed file name
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

### PLO_BOARDPACKET (101) - Board Packet
**Trigger**: Special board data transfer
```
[BOARD_DATA...]      // Board-specific data
```

### PLO_FILE (102) - File Data
**Trigger**: File content transfer
```
[GCHAR: file_type]   // File type indicator
[GUINT5: file_size]  // File size
[FILE_DATA...]       // File content
```

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