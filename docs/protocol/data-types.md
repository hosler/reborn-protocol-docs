# Data Types Reference

This section specifies all data types that the Reborn protocol uses. It also explains the reasons for their design.

## The +32 Obsession: Why Everything Adds 32

Almost every value in this protocol has 32 added to it before transmission. The following history explains this design.

The Reborn protocol was designed in the late 1990s, when:
- Binary protocols made some network administrators nervous
- Debug logs looked nicer with printable characters
- Certain naive firewalls were suspicious of bytes below 32

Adding 32 to every byte puts the result in the printable ASCII range (32-255). As a result, packet dumps contain mostly readable characters. The space character (32) becomes the new zero.

This design was not necessary in 2025. However, every implementation uses it as part of the legacy protocol.

## Primitive Types (The Normal Ones)

These basic types have the expected behavior:

| Type | Size | Range | Description |
|------|------|-------|-------------|
| BYTE | 1 byte | 0-255 | Unsigned 8-bit integer |
| CHAR | 1 byte | -128 to 127 | Signed 8-bit integer |
| SHORT | 2 bytes | 0-65535 | Unsigned 16-bit, little-endian |
| INT | 4 bytes | 0-4294967295 | Unsigned 32-bit, little-endian |
| STRING | Variable | N/A | See [String Types](strings.md) |

## G-Types: The Reborn-Encoded Types

All G-types add 32 to keep transmitted values in the printable ASCII range. The protocol uses these types throughout.

### GCHAR: The Simple One

GCHAR uses the basic G-encoding rule. Add 32.

```
Encoding: byte = value + 32
Decoding: value = byte - 32
Range: 0-223 (bytes 32-255)
```

**Examples**:
| Value | Encoded Byte | ASCII |
|-------|-------------|-------|
| 0 | 32 | (space) |
| 50 | 82 | 'R' |
| 65 | 97 | 'a' |
| 223 | 255 | 'ÿ' |

```python
# Python
def encode_gchar(value): return (value + 32) & 0xFF
def decode_gchar(byte): return (byte - 32) & 0xFF
```

### GSHORT: Where It Gets Weird

A GSHORT is 2 bytes. Do not split a 16-bit number into two bytes and add 32 to each.

Instead, GSHORT uses **7-bit encoding**: each byte carries 7 bits of data (not 8), with the +32 bias applied.

```
Bit layout:
┌─────────────────────────────────────────────────────┐
│ Byte 1: [ 0 | d₁₃ d₁₂ d₁₁ d₁₀ d₉ d₈ d₇ ] + 32     │
│ Byte 2: [ 0 | d₆  d₅  d₄  d₃  d₂ d₁ d₀ ] + 32     │
└─────────────────────────────────────────────────────┘
Total data bits: 14 (7 + 7)
Maximum value: 2^14 - 1 = 16383... but see below
```

**The Actual Implementation** (from GServer-v2):

```cpp
// Encoding
unsigned short t = min(value, 28767);  // Capped at 28767, not 16383
unsigned char val[2];
val[0] = t >> 7;
if (val[0] > 223) val[0] = 223;        // Can't exceed 223 after +32
val[1] = t - (val[0] << 7);            // Remainder goes in byte 2
val[0] += 32;
val[1] += 32;

// Decoding
return (byte1 << 7) + byte2 - 0x1020;
```

**Why 0x1020?** It is `(32 << 7) + 32 = 4128`. This operation removes the +32 bias from both bytes.

**Why 28767?** The cap of 28767 (not 16383) comes from the encoding: `223 << 7 = 28544`, plus up to 223 in the second byte gives 28767.

```python
# Python implementation
def encode_gshort(value):
    t = min(value, 28767)
    val0 = t >> 7
    if val0 > 223:
        val0 = 223
    val1 = t - (val0 << 7)
    return bytes([val0 + 32, val1 + 32])

def decode_gshort(data):
    return (data[0] << 7) + data[1] - 0x1020
```

#### Canonical Maximum Versus the Server Clamp

The cap of 28767 makes a non-canonical encoding. For values 28672-28767 the high byte is
already at 223, so the low byte carries 128-223 instead of a 7-bit group. The decode
formula still gives the right value. The reference client caps at the canonical maximum
instead: its GSHORT writers clamp the encoded value to `0x6fff` (`223 << 7 | 127` =
**28671**; `Preagonal/FourPlay/quattroplay/src/TPlayer.cpp` `netSigned14`, `TClient.cpp`,
`TShowImg.cpp`). An encoder that must interoperate with clients should not exceed 28671.
A decoder should accept a low byte above `0x9F` (127 + 32). The same stop at 28671 is
reported for the 5.x and 6.x Windows clients in squirelworks' client-analysis notes
(`protocol/shoot-5007.md`, static read); not verified against the reference.

### GINT (GINT3): Three Bytes, Same Energy

GINT extends the pattern to 3 bytes. Documentation often calls it **GINT3** to distinguish it from GINT4 and GINT5.
This is what the GServer `CString` `operator>>(int)` / `readGInt()` produce. The protocol uses it for
3-byte numeric props (RUPEES, CARRYNPC, KILLS, etc.), NPC ids, and the `PLO_RAWDATA`
length field.

```
Bit layout (high byte carries the top of the value):
┌───────────────────────────────────────────────────────────┐
│ Byte 1: [ value >> 14 ] + 32   (top byte, clamped to 223)  │
│ Byte 2: [ (value >> 7) & 0x7F ] + 32                       │
│ Byte 3: [  value       & 0x7F ] + 32                       │
└───────────────────────────────────────────────────────────┘
```

> ⚠️ **Don't say "21 bits / max 2,097,151."** The reference `CString` does **not**
> mask the top byte to 7 bits. It clamps it to **223** (`if (val[0] > 223) val[0] = 223`),
> exactly like GSHORT. So the real encodable max is `223 << 14 + 223 << 7 + 223 = 3,682,399`,
> not `2^21 − 1`. For values ≤ 2,097,151 the bytes are identical either way, which is why
> this error rarely occurs. However, a strict 7-bit-mask encoder truncates large rupee or online
> counts.

The same applies here. The canonical maximum, with every group 7 bits, is
`223 << 14 | 0x3FFF` = **3,670,015**. The reference client caps its raw-data length at
exactly that value (`Preagonal/FourPlay/quattroplay/src/TGraalConnection.cpp` sendData
RAWDATA clamp to `0x37ffff`; `TPlayer.cpp` `netUnsigned21`). The same cap is reported for
the v7 client in squirelworks' client-analysis notes (its v7 framing and packet-tables
file, static read); not verified against the reference. Values from 3,670,016 to 3,682,399 need a lower group above 127: the middle
group overflows first (3,670,016 encodes as 223, 128, 0), and the low group too from
3,682,304 (223, 223, 128) upward.

```python
# Decode: the GSHORT trick extended one more byte (combined +32 bias removal)
def decode_gint3(data):
    # 0x81020 = combined +32 bias for 3 bytes = ((32<<7)+32 << 7) + 32
    return (((data[0] << 7) + data[1]) << 7) + data[2] - 0x81020
    # equivalently: ((data[0]-32)<<14) + ((data[1]-32)<<7) + (data[2]-32)

def encode_gint3(value):
    t = min(value, 3682399)
    b0 = t >> 14
    if b0 > 223: b0 = 223
    rem = t - (b0 << 14)
    b1 = rem >> 7
    b2 = rem - (b1 << 7)
    return bytes([b0 + 32, b1 + 32, b2 + 32])
```

### GINT4: Four Bytes

A 4-byte G-type (`CString` `readGInt4`) uses the same byte-shift scheme. The encoder clamps the top byte to 223.
The maximum encodable value is `≈ 471,347,295`. The decode bias is `0x4081020`.
The wire protocol rarely uses this type, but a complete codec should implement it.

### GINT5: For When You Need Bigger Numbers

Five bytes for large values like timestamps and file sizes (`operator>>(long long)` /
`readGInt5`).

```
Size: 5 bytes
Carries: a full 32-bit value (the reference encoder clamps the top nibble to 15)
Maximum value: 4,294,967,295  (NOT 2^35 − 1)
Common use: Unix timestamps, file sizes, file modtimes, adminRights bitmask
```

> ⚠️ The frequently-quoted "35-bit / 34 billion" max is wrong. `CString::writeGInt5`
> caps the value at `0xFFFFFFFF` (the top of the 5 bytes is clamped to 15), so GINT5
> transports a 32-bit value across 5 bytes.

```python
def encode_gint5(value):
    value = min(value, 0xFFFFFFFF)
    result = bytearray(5)
    for i in range(4, -1, -1):
        result[4-i] = ((value >> (i * 7)) & 0x7F) + 32
    return bytes(result)

def decode_gint5(data):
    value = 0
    for i in range(5):
        value = (value << 7) | ((data[i] - 32) & 0x7F)
    return value
```

### Quick Reference Table

| Type | Size | Max Value | Decode Formula |
|------|------|-----------|----------------|
| GCHAR | 1 byte | 223 | `byte - 32` |
| GUCHAR | 1 byte | 223 | `byte - 32` |
| GSHORT | 2 bytes | 28,767 (canonical 28,671) | `(b1 << 7) + b2 - 0x1020` |
| GUSHORT | 2 bytes | 28,767 | same as `GSHORT` |
| GINT / GINT3 | 3 bytes | 3,682,399 (canonical 3,670,015) | `((b1 << 7) + b2 << 7) + b3 - 0x81020` |
| GINT4 | 4 bytes | 471,347,295 | byte-shift, bias `0x4081020` |
| GINT5 / GUINT5 | 5 bytes | 4,294,967,295 | 7-bit unpack, subtract 32 each |

> **Naming note:** GServer's `CString` exposes `writeGInt`/`readGInt` for the **3-byte**
> type. Throughout this documentation "GINT" and "GINT3" are the same thing.

## Coordinates: A Field Guide

The coordinate system uses the following units.

### The Unit Hierarchy

```
1 tile = 16 pixels
1 half-tile = 8 pixels
1 level = 64×64 tiles = 1024×1024 pixels
```

### Where Each Unit Is Used

| Context | Unit | Encoding | Range | Notes |
|---------|------|----------|-------|-------|
| Board/tile position | Tiles | GCHAR | 0-63 | The 64×64 level grid |
| Bombs, arrows, items | Half-tiles | GCHAR | 0-127 | Twice the precision |
| Player movement (X/Y) | Half-tiles | GCHAR | 0-127 | Standard movement |
| Precise position (X2/Y2) | Pixels | GSHORT | Variable | High precision, can be negative |
| GMAP world coords | Tiles + grid offset | Various | See GMAP docs | It's a whole thing |

### X2/Y2 Encoding: The Weird One

Player properties 78 (X2) and 79 (Y2) encode positive and negative pixel positions. GMAPs can contain negative positions.

The encoding puts a sign bit in the least significant bit:

```
Encoding:
  encoded = (abs(pixels) << 1) | (1 if negative else 0)

Decoding:
  pixels = encoded >> 1
  if encoded & 1: pixels = -pixels
```

**Examples**:
| Pixels | Encoded (decimal) | Binary |
|--------|-------------------|--------|
| +160 | 320 | 101000000 |
| -160 | 321 | 101000001 |
| +0 | 0 | 0 |
| -1 | 3 | 11 |

The protocol does not use signed integers because each encoded byte must be ≥32. Signed representations would violate this requirement.

```python
def decode_x2y2(gshort_value):
    pixels = gshort_value >> 1
    if gshort_value & 1:
        pixels = -pixels
    return pixels / 16.0  # Convert to tiles
```

### Coordinate Frames in GMAPs

The wire format often uses **local segment coordinates** even when the client is on a GMAP.

| Frame | Meaning | Common use |
|-------|---------|------------|
| Local | Position inside the current 64×64 segment | `PLO_PLAYERPROPS` X/Y and X2/Y2 |
| World | Position across the full GMAP | client-side reconstruction |
| Segment | GMAP grid column/row | `GMAPLEVELX` / `GMAPLEVELY` |

Conversions:

```text
world_x = local_x + gmaplevelx * 64
world_y = local_y + gmaplevely * 64

grid = floor(world / 64)
local = world % 64
```

`X2/Y2/Z2` use the signed pixel packing above. The NPC equivalents use the same GSHORT
encoding.

The one-byte player/NPC `X` and `Y` properties are signed half-tile coordinates, not
ordinary unsigned GCHARs. After removing the +32 wire bias, values `216..255` are
interpreted as signed 8-bit values (`-40..-1`) before division by two. This is the
`PropertyTileCoordinate::deserialize` contract
(`GServer-v2/server/src/utilities/PropertySerializers.cpp:420-429`).

## Player Property Data Types

### Colors (5 or 8 bytes)

Player colors are consecutive GCHARs:

```
[skin][coat][sleeves][shoes][belt]   (classic / old-world: 5 bytes)
+ [pullover][pants][border]          (new-world: 8 bytes total)
Each byte: color index (+ 32 for encoding)
```

> The count is **server-policy-dependent, not client-version-dependent**. The reference
> server's `PropertyColors::getColorCount()` asks `Server::isNewWorldMode()` and returns
> either 8 or 5 (`GServer-v2/server/src/utilities/PropertySerializers.cpp:628-632`).
> Therefore, a receiver cannot derive the width from the handshake, and no particular
> default is normative. A configurable server chooses one width for the world.
>
> A client that does not know the policy can parse with its preferred width, require the
> property stream to consume cleanly in ascending-ID order, and retry once with the other
> width if the first interpretation overruns, leaves bytes, or produces an invalid/decreasing
> next ID. Never merge partial results from the failed attempt.

### Status Flags (Bitfield)

```
Format: GCHAR (8-bit bitfield, after -32)
Bit 0 (0x01): PAUSED
Bit 1 (0x02): HIDDEN
Bit 2 (0x04): MALE
Bit 3 (0x08): DEAD
Bit 4 (0x10): ALLOWWEAPONS
Bit 5 (0x20): HIDESWORD
Bit 6 (0x40): HASSPIN
```

### Alignment Points

```
Format: GCHAR
Range: 0-100
Values: 0 = evil, 20 = neutral, 100 = good
```

### Other Common Player Encodings

| Field | Encoding | Notes |
|-------|----------|-------|
| `STATUS` | GCHAR bitfield | `PAUSED`, `HIDDEN`, `MALE`, `DEAD`, `ALLOWWEAPONS`, `HIDESWORD`, `HASSPIN` |
| `COLORS` | 5 or 8 GCHARs | Width is selected by server-wide new-world mode, not handshake version |
| `X2`, `Y2`, `Z2` | GSHORT | Signed pixel values packed with the low-bit sign flag |
| `ONLINESECS` | GINT3 | 3-byte online time counter |
| `ONLINESECS2` | GINT5 | 5-byte online time counter |
| `IPADDR` | GINT5 | Packed integer, not raw octets |
| `TEXTCODEPAGE` | GINT3 | 3-byte code page value |

## NPC Property Data Types

NPCs use a separate property enum and several width quirks that are easy to misread. The
full semantic table is in [NPC Properties](npc-properties.md). This section gives the
wire widths.

| ID(s) | Field | Encoding | Notes |
|-------|-------|----------|-------|
| 0 | IMAGE | GCHAR length + string | Length-prefixed image name |
| 1 | SCRIPT | GSHORT length + raw bytes | Modern servers may send length 0 |
| 2-3 | X/Y | GCHAR | Tile coordinates encoded as Reborn chars |
| 4 | POWER | GCHAR | Hit points in half-hearts |
| 5 | RUPEES | GINT3 | 3-byte value, not a direction byte |
| 6-7 | ARROWS/BOMBS | GCHAR | Single-byte counts |
| 8-9 | GLOVEPOWER/BOMBPOWER | GCHAR | Single-byte powers |
| 10-11 | SWORDIMAGE/SHIELDIMAGE | Variable | Power+image forms, **not plain strings** |
| 12 | GANI | GCHAR length + string | Animation name |
| 13-14 | VISFLAGS/BLOCKFLAGS | GCHAR bitfields | Packed flags |
| 15 | MESSAGE | GCHAR length + string | Chat text |
| 16 | HURTDXDY | 2 GCHARs | Packed x/y knockback offsets |
| 17 | ID | GINT3 | NPC identifier |
| 18 | SPRITE | GCHAR | Sprite + direction packed into one byte |
| 19 | COLORS | 5 or 8 GCHARs | Same generation split as player colors |
| 20-22 | NICKNAME/HORSEIMAGE/HEADIMAGE | Variable | `HEADIMAGE` uses the preset-id threshold of 100 |
| 23-32 | SAVE0-SAVE9 | GCHAR | Single-byte save slots |
| 33 | ALIGNMENT | GCHAR | AP value |
| 34 | IMAGEPART | GSHORT/GSHORT/GCHAR/GCHAR | Fixed 6-byte rectangle |
| 35 | BODYIMAGE | GCHAR length + string | Body image filename |
| 36-40 | GATTRIB1-5 | GCHAR length + string | Custom strings |
| 41-43 | GMAPLEVELX/Y, Z | GCHAR | GMAP segment and Z offset |
| 44-47 | GATTRIB6-9 | GCHAR length + string | Custom strings |
| 48 | UNKNOWN48 | (void) | No payload |
| 49-51 | SCRIPTER, NAME, TYPE | GCHAR length + string | `canSendProp()` filters these from game clients |
| 52 | CURLEVEL | GCHAR length + string | Sent to game clients. `NPC::warp()` sets it on every level change |
| 53-73 | GATTRIB10-30 | GCHAR length + string | Custom strings |
| 74 | CLASS | GSHORT length + string | Long string |
| 75-77 | X2/Y2/Z2 | GSHORT | Signed pixel coordinates |

See [NPC Properties](npc-properties.md) for the meaning of each field and the server-side
exceptions.

## Common Packet Field Patterns

The packet documentation uses these patterns repeatedly.

| Pattern | Meaning | Notes |
|---------|---------|-------|
| Read-to-end string | Raw bytes until packet end | Used for `PLI_LEVELWARP`, `PLO_LEVELNAME`, `PLO_FILESENDFAILED`, and similar fields |
| Newline-terminated string | Raw bytes until `0x0A` | Used by `PLO_LEVELLINK` and some server-side text payloads |
| GCHAR length + string | Length-prefixed string | Maximum 223 bytes |
| GINT3 length | 3-byte count | Used for raw-data packet lengths and several counters |
| GINT5 length | 5-byte count | Used for timestamps, file sizes, and large counters |
| Packed coordinate byte | Reborn char with unit-specific scaling | Common for tile, half-tile, and pixel fields |

## Time Types

### Modification Time (GINT5)

A Unix timestamp uses 5 bytes to avoid the 32-bit timestamp limit in 2038.

### Online Time (GINT)

This type records seconds online. A 3-byte value gives approximately 24 days before overflow.

## Implementation Guidelines

### Byte Order

- All multi-byte primitives (SHORT, INT) use **little-endian** before any G-encoding
- G-encoded types have their own byte order defined by the 7-bit packing

### Validation

- Always validate ranges after decoding (especially GCHAR: 0-223)
- Handle underflow gracefully (bytes < 32 are malformed)
- Reject malformed packets silently. Do not stop the program.

### Cross-Language Reference

**JavaScript**:
```javascript
function decodeGShort(data) {
    return (data[0] << 7) + data[1] - 0x1020;
}

function encodeGShort(value) {
    const t = Math.min(value, 28767);
    let val0 = t >> 7;
    if (val0 > 223) val0 = 223;
    const val1 = t - (val0 << 7);
    return new Uint8Array([val0 + 32, val1 + 32]);
}
```

**C++** (from GServer-v2):
```cpp
unsigned short readGShort() {
    unsigned char val[2];
    read((char*)val, 2);
    return (val[0] << 7) + val[1] - 0x1020;
}
```
