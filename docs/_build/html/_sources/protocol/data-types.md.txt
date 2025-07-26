# Data Types Reference

This section provides detailed specifications for all data types used in the Reborn protocol.

## Primitive Types

### Basic Types

| Type | Size | Range | Description |
|------|------|-------|-------------|
| BYTE | 1 byte | 0-255 | Unsigned 8-bit integer |
| CHAR | 1 byte | -128 to 127 | Signed 8-bit integer |
| SHORT | 2 bytes | 0-65535 | Unsigned 16-bit integer |
| INT | 4 bytes | 0-4294967295 | Unsigned 32-bit integer |
| STRING | Variable | N/A | Null or delimiter terminated |

### Reborn-Encoded Types (G-Types)

All G-types add 32 to ensure printable ASCII transmission.

#### GCHAR
```
Encoding: (value + 32) & 0xFF
Range: 0-223 (after encoding: 32-255)
```

**Example**:
```cpp
// Encode
uint8_t encoded = (value + 32) & 0xFF;

// Decode  
uint8_t decoded = (encoded - 32) & 0xFF;
```

#### GSHORT  
```
Encoding: ((value >> 6) + 32) + ((value & 0x3F) + 32)
Size: 2 bytes
Range: 0-16383
```

**Example**:
```cpp
// Encode
uint8_t byte1 = ((value >> 6) & 0x3F) + 32;
uint8_t byte2 = (value & 0x3F) + 32;

// Decode
uint16_t decoded = ((byte1 - 32) << 6) | (byte2 - 32);
```

#### GINT (3-byte)
```
Encoding: 3-byte variable encoding with +32 per byte
Size: 3 bytes  
Range: 0-2097151
```

**Example**:
```cpp
// Encode
uint8_t byte1 = ((value >> 14) & 0x7F) + 32;
uint8_t byte2 = ((value >> 7) & 0x7F) + 32;  
uint8_t byte3 = (value & 0x7F) + 32;

// Decode
uint32_t decoded = ((byte1-32) << 14) | ((byte2-32) << 7) | (byte3-32);
```

#### GINT5 (5-byte)
```
Encoding: 5-byte encoding for large values/timestamps
Size: 5 bytes
Range: 0-34359738367  
```

**Example**:
```cpp
// Encode (big-endian style)
for (int i = 4; i >= 0; i--) {
    bytes[4-i] = ((value >> (i * 7)) & 0x7F) + 32;
}

// Decode
uint64_t decoded = 0;
for (int i = 0; i < 5; i++) {
    decoded = (decoded << 7) | ((bytes[i] - 32) & 0x7F);
}
```

## String Types

### GSTRING (Length-Prefixed)
```
Format: [GCHAR: length][string_data]
Maximum length: 223 characters
Encoding: Latin-1
```

**Example**:
```cpp
// Encode
packet.writeGChar(text.length());
packet.write(text.c_str(), text.length());

// Decode  
uint8_t length = packet.readGChar();
std::string text = packet.readString(length);
```

### Regular String  
```
Format: [string_data][delimiter]
Delimiter: Usually '\n' or '\0'
Encoding: Latin-1
```

## Coordinate Types

### Tile Coordinates
```
Range: 0-63 (64×64 grid)
Encoding: Usually GCHAR
Usage: Level tile positions
```

### Half-Tile Coordinates  
```
Range: 0-127 (128×128 grid)
Encoding: Usually GCHAR  
Usage: Precise object positioning
```

### Pixel Coordinates
```
Range: 0-2048 (half-tiles × 16)
Encoding: GCHAR for (pixels/2) or GSHORT for full precision
Usage: Screen/rendering coordinates
```

## Player Property Data Types

### Colors (5 bytes)
```
Format: [coat][sleeves][shoes][belt][skin]
Each byte: 0-31 color index
```

### Alignment Points  
```
Format: GCHAR
Range: 0-100
Values: 0=evil, 20=neutral, 100=good
```

### Status Flags
```
Format: GCHAR (bitfield)
Bits:
  0x01 - PAUSED
  0x02 - HIDDEN  
  0x04 - MALE
  0x08 - DEAD
  0x10 - ALLOWWEAPONS
  0x20 - HIDESWORD
  0x40 - HASSPIN
```

### ELO Rating
```
Format: [GFLOAT: rating][GFLOAT: deviation]
Size: Variable (depends on GFLOAT encoding)
Usage: Player skill rating system
```

## Time Types

### Modification Time
```
Format: GINT5
Value: Unix timestamp
Usage: File/level modification tracking
```

### Online Time
```
Format: GINT  
Value: Seconds online
Usage: Session tracking
```

## File Transfer Types

### File Size
```
Format: GINT5
Value: File size in bytes
Usage: Large file transfer size indication
```

### Checksum
```
Format: GINT5
Value: CRC32 checksum
Usage: File integrity verification
```

## NPC/Object Types

### NPC ID
```
Format: GINT
Range: 0-16777215
Usage: Unique NPC identifier
```

### Player ID  
```
Format: GSHORT
Range: 0-16383
Usage: Player identifier within server
```

### Item Type
```
Format: GCHAR
Range: 0-23
Values: See LevelItemType enum
```

## Implementation Guidelines

### Byte Order
- All multi-byte values use **little-endian** before G-encoding
- G-encoding preserves byte order within encoded format

### Validation
- Always validate ranges after decoding
- Handle overflow/underflow gracefully
- Reject malformed packets silently

### Performance
- G-types optimize for printable ASCII transmission
- Avoid unnecessary encoding/decoding in hot paths
- Cache decoded values when possible

### Cross-Language Compatibility
```python
# Python example
def encode_gshort(value):
    return bytes([((value >> 6) & 0x3F) + 32, (value & 0x3F) + 32])

def decode_gshort(data):
    return ((data[0] - 32) << 6) | (data[1] - 32)
```

```javascript
// JavaScript example  
function encodeGShort(value) {
    return new Uint8Array([
        ((value >> 6) & 0x3F) + 32,
        (value & 0x3F) + 32
    ]);
}

function decodeGShort(data) {
    return ((data[0] - 32) << 6) | (data[1] - 32);
}
```

These data type specifications ensure consistent encoding/decoding across all Reborn protocol implementations.