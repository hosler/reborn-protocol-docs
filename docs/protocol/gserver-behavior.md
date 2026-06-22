# GServer Behavior Reference

This document provides a quick reference for how GServer-v2 implements various protocol behaviors, based on analysis of the source code. This is meant to be used as a reference to avoid repeatedly searching through the GServer source.

## String Encoding

### Three Types of Strings in GServer

1. **Regular String (read to end of packet)**
   ```cpp
   CString level = packet.readString("");  // Empty delimiter = read to end
   ```
   - Used in: PLI_LEVELWARP, PLO_LEVELNAME, PLO_FILESENDFAILED
   - No length prefix, no terminator
   - Reads ALL remaining bytes in the packet
   - **NOT** null-terminated despite what some old docs say

2. **Length-Prefixed String (GSTRING)**
   ```cpp
   uint8_t length = packet.readGChar();
   std::string text = packet.read(length);
   ```
   - Used in: Player properties, NPC properties, file packets
   - First byte is length (encoded as GCHAR)
   - Maximum length: 223 characters

3. **Newline-Terminated String**
   ```cpp
   std::string text = packet.readString("\n");
   ```
   - Used in: Level links, some packet handlers
   - Reads until newline (0x0A)
   - Newline is consumed but not included

## Critical Packet Implementations

### PLI_LEVELWARP (0)
```cpp
// From PlayerClientPackets.cpp
HandlePacketResult PlayerClient::msgPLI_LEVELWARP(CString& pPacket)
{
    time_t modTime = 0;
    if (pPacket[0] - 32 == PLI_LEVELWARPMOD)
        modTime = (time_t)pPacket.readGUInt5();
    
    Position<int16_t> pos = { 
        static_cast<int16_t>(pPacket.readGChar() * 8), 
        static_cast<int16_t>(pPacket.readGChar() * 8) 
    };
    CString newLevel = pPacket.readString("");  // Read to end!
    // ...
}
```
**Format**: `[GUCHAR: x][GUCHAR: y][STRING: level_name]`
- X/Y are in tile coordinates (multiply by 8 for pixels)
- Level name reads to end of packet
- **Important**: read-to-end, **not** null-terminated (consistent with the string-type
  rules above — the packet boundary / bundle newline delimits it, there is no `\x00`)

### PLO_LEVELNAME (6)
```cpp
// Server sends level name
sendPacket(CString() >> (char)PLO_LEVELNAME << level->levelName);
// For GMAP, sends map name instead
sendPacket(CString() >> (char)PLO_LEVELNAME << map->getMapName());
```
**Format**: `[STRING: level_name]`
- Entire packet payload is the level name
- No length prefix
- **Important**: read-to-end, **not** null-terminated (no trailing `\x00`)

### PLO_PLAYERPROPS (14) / PLO_OTHERPLPROPS (15)
Player properties use a special encoding:
- Property ID (1 byte)
- Property data (varies by property)

Special cases:
- **HEADGIF**: If length < 100, it's a preset head. Otherwise length-100 is string length
- **SWORDPOWER/SHIELDPOWER**: `[length][power+30][image_string]`
- **X2/Y2**: Encoded as `(abs(pixels) << 1) | (negative ? 1 : 0)`, sent as GShort
- **GATTRIB1-30**: Flag properties with no data

### CString Operators

The GServer uses CString with special operators for packet construction:

```cpp
// >> operator adds data with Graal encoding
CString packet;
packet >> (char)PLO_LEVELNAME;  // Adds char + 32
packet << levelName;             // Appends raw string

// Reading
char packetId = packet.readGChar();  // Reads byte - 32
int value = packet.readGInt();        // Reads 3-byte Graal int
```

## Common Patterns

### Sending Packets to Players
```cpp
// To one player
player->sendPacket(packet);

// To all players in a level  
server->sendPacketToOneLevel(packet, level);

// To all players
server->sendPacketToAll(packet);
```

### File Sending
Large files are sent in chunks:
1. PLO_LARGEFILESTART - filename
2. PLO_LARGEFILESIZE - total size 
3. PLO_RAWDATA + file chunks
4. PLO_LARGEFILEEND - signals completion

### Board Modifications
Board data is always 8192 bytes (64x64 tiles, 2 bytes each):
```cpp
// Server sends board packet
sendPacket(CString() >> (char)PLO_BOARDPACKET << boardData);

// Board modifications include position and size
packet >> (char)PLO_BOARDMODIFY >> (char)x >> (char)y 
       >> (char)width >> (char)height << tileData;
```

## Coordinate Systems

### Tile vs Pixel Coordinates
- **Tiles**: 0-63 range, used for board positions
- **Pixels**: Tiles * 16, used for precise positioning
- **Wire format**: Often pixels/2 or pixels/8 depending on packet

### GMAP Coordinates
- **Local**: Position within current 64x64 segment
- **World**: `gmaplevelx * 64 + localx` (in tiles)
- **X2/Y2**: Always in pixels, can be negative (encoded with bit flag)

## Property Encoding

### Numeric Properties
- Most use GCHAR encoding (value + 32)
- Larger values use GINT (3 bytes) or GINT5 (5 bytes)
- Special offsets: Z property has +25 offset

### String Properties
- Length-prefixed with GCHAR
- Maximum 223 characters
- Common: nickname, chat, level name, guild

### Special Encodings
- **Colors**: 5 consecutive GCHARs
- **Sprite**: Encoded with direction in lower 2 bits
- **AP**: Alignment points, 100 units = full alignment

## Error Handling

### Disconnect Messages
```cpp
sendPacket(CString() >> (char)PLO_DISCMESSAGE << reason);
```
Always followed by connection termination.

### File Send Failures
```cpp
sendPacket(CString() >> (char)PLO_FILESENDFAILED << filename);
```
Filename reads to end of packet.

## Important Notes

1. **Packet Boundaries**: Each packet is self-contained. "Read to end" means read to the end of the current packet, not the stream.

2. **Null Characters**: Level names may contain nulls. The server doesn't strip them, but clients should handle them appropriately for display.

3. **GMAP Mode**: When on a GMAP, PLO_LEVELNAME sends the GMAP name, not the segment name. Segment info comes from GMAP file parsing.

4. **Version Differences**: Some behaviors change based on client version (e.g., GANI format, encryption type).

## Quick Reference Table

| Packet | String Type | Notes |
|--------|------------|-------|
| PLI_LEVELWARP | Read to end | Level name after X,Y |
| PLO_LEVELNAME | Read to end | Entire packet is name |
| PLO_LEVELLINK | Newline-terminated | Link data as single string |
| PLO_PRIVATEMESSAGE | GSTRING | Player ID, then length+message |
| PLO_FILESENDFAILED | Read to end | Filename |
| Player properties | GSTRING | Length-prefixed strings |
| NPC properties | GSTRING | Length-prefixed strings |