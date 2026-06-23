# GServer Behavior Reference

This document provides a quick reference for how GServer-v2 implements various protocol behaviors, based on analysis of the source code. This is meant to be used as a reference to avoid repeatedly searching through the GServer source.

## String Encoding

The string forms used by GServer are documented in [String Types](strings.md). This page
only calls out the packet handlers that use them.

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
- X/Y are in tile coordinates; the wire-format details for coordinate packing live in
  [Data Types](data-types.md#coordinates-a-field-guide)
- Level name reads to end of packet
- **Important**: read-to-end, **not** null-terminated

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
- **Important**: read-to-end, **not** null-terminated

### PLO_PLAYERPROPS (9) / PLO_OTHERPLPROPS (8)
Player properties use a special encoding:
- Property ID (1 byte)
- Property data (varies by property)

Special cases:
- **HEADGIF (11)**: If byte < 100, it's a preset head id. Otherwise byte-100 is the string length.
- **SWORDPOWER (8)**: custom image form is `[power+30][img_len][image]`.
- **SHIELDPOWER (9)**: custom image form is `[power+10][img_len][image]`.
- **X2/Y2 (78/79)**: See [Data Types](data-types.md#x2y2-encoding-the-weird-one).
- **GATTRIB1-30**: length-prefixed strings, not flag-only props.

See [Data Types](data-types.md#player-property-data-types) for the full id/width table
(props 0-83), and [NPC Properties](npc-properties.md) for the separate NPC enum.

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

Coordinate frames and the X2/Y2 packing live in [Data Types](data-types.md#coordinates-a-field-guide)
and [Data Types](data-types.md#coordinate-frames-in-gmaps).

## Property Encoding

The numeric widths, string forms, and special offsets are documented in
[Data Types](data-types.md). The main implementation gotcha here is not the values
themselves, but using the wrong width for a given property.

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

2. **GMAP Mode**: When on a GMAP, PLO_LEVELNAME sends the GMAP name, not the segment name. Segment info comes from GMAP file parsing.

3. **Version Differences**: Some behaviors change based on client version (e.g., GANI format, encryption type).

## Quick Reference Table

See [String Types](strings.md) for the packet-by-packet string forms, and
[Data Types](data-types.md) for the width rules behind the property payloads.
