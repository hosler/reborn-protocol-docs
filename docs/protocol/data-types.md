# Data Types Reference

This section provides detailed specifications for all data types used in the Reborn protocol—and explains *why* they are the way they are.

## The +32 Obsession: Why Everything Adds 32

Before we dive in, let's address the elephant in the room: almost every value in this protocol has 32 added to it before transmission. Why?

The Graal protocol was designed in the late 1990s, when:
- Binary protocols made some network administrators nervous
- Debug logs looked nicer with printable characters
- Certain naive firewalls were suspicious of bytes below 32

Adding 32 to every byte ensures the result is in the printable ASCII range (32-255). This means packet dumps are *almost* human-readable if you squint. The space character (32) becomes the new zero.

Is this still necessary in 2025? No. Is it baked into every implementation? Yes. Welcome to legacy protocols.

## Primitive Types (The Normal Ones)

These are the basic types that behave like you'd expect:

| Type | Size | Range | Description |
|------|------|-------|-------------|
| BYTE | 1 byte | 0-255 | Unsigned 8-bit integer |
| CHAR | 1 byte | -128 to 127 | Signed 8-bit integer |
| SHORT | 2 bytes | 0-65535 | Unsigned 16-bit, little-endian |
| INT | 4 bytes | 0-4294967295 | Unsigned 32-bit, little-endian |
| STRING | Variable | N/A | See [String Types](strings.md) |

## G-Types: The Reborn-Encoded Types

All G-types add 32 to ensure "printable ASCII transmission." They're used everywhere.

### GCHAR: The Simple One

The gateway drug of G-encoding. Just add 32.

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

Here's where the protocol earns its reputation. A GSHORT is 2 bytes, but you can't just split a 16-bit number into two bytes and add 32 to each. That would be too simple.

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

**Why 0x1020?** It's `(32 << 7) + 32 = 4128`. This undoes the +32 on both bytes in one operation. Clever, but not documented anywhere until now.

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

### GINT: Three Bytes, Same Energy

Extends the pattern to 3 bytes. Each carries 7 bits of data.

```
Bit layout:
┌───────────────────────────────────────────────────────────┐
│ Byte 1: [ 0 | d₂₀ d₁₉ d₁₈ d₁₇ d₁₆ d₁₅ d₁₄ ] + 32        │
│ Byte 2: [ 0 | d₁₃ d₁₂ d₁₁ d₁₀ d₉  d₈  d₇  ] + 32        │
│ Byte 3: [ 0 | d₆  d₅  d₄  d₃  d₂  d₁  d₀  ] + 32        │
└───────────────────────────────────────────────────────────┘
Total data bits: 21
Maximum value: 2,097,151
```

```python
def encode_gint(value):
    byte1 = ((value >> 14) & 0x7F) + 32
    byte2 = ((value >> 7) & 0x7F) + 32
    byte3 = (value & 0x7F) + 32
    return bytes([byte1, byte2, byte3])

def decode_gint(data):
    return ((data[0] - 32) << 14) | ((data[1] - 32) << 7) | (data[2] - 32)
```

### GINT5: For When You Need Bigger Numbers

Five bytes for large values like timestamps. Same 7-bit pattern.

```
Size: 5 bytes
Total data bits: 35
Maximum value: 34,359,738,367
Common use: Unix timestamps, file sizes
```

```python
def encode_gint5(value):
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
| GSHORT | 2 bytes | 28,767 | `(b1 << 7) + b2 - 0x1020` |
| GINT | 3 bytes | 2,097,151 | 7-bit unpack, subtract 32 each |
| GINT5 | 5 bytes | 34,359,738,367 | 7-bit unpack, subtract 32 each |

## Coordinates: A Field Guide

The coordinate system is straightforward once you understand the units.

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

Player properties 78 (X2) and 79 (Y2) encode pixel positions with support for negative values. Because negative positions are a thing in GMAPs.

The encoding stuffs a sign bit into the least significant bit:

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

Why not just use signed integers? Because every byte needs to be ≥32 after encoding, and signed representations would break that. See: The +32 Obsession.

```python
def decode_x2y2(gshort_value):
    pixels = gshort_value >> 1
    if gshort_value & 1:
        pixels = -pixels
    return pixels / 16.0  # Convert to tiles
```

## Player Property Data Types

### Colors (5 bytes)

Player colors are 5 consecutive GCHARs:

```
[coat][sleeves][shoes][belt][skin]
Each byte: color index 0-31 (+ 32 for encoding)
```

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

## Time Types

### Modification Time (GINT5)

Unix timestamp. 5 bytes because 32-bit timestamps are *so* 2038.

### Online Time (GINT)

Seconds spent online. 3 bytes gives ~24 days before overflow, which is probably fine.

## Implementation Guidelines

### Byte Order

- All multi-byte primitives (SHORT, INT) use **little-endian** before any G-encoding
- G-encoded types have their own byte order defined by the 7-bit packing

### Validation

- Always validate ranges after decoding (especially GCHAR: 0-223)
- Handle underflow gracefully (bytes < 32 are malformed)
- Reject malformed packets silently—don't crash

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
