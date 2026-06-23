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

### GINT (GINT3): Three Bytes, Same Energy

Extends the pattern to 3 bytes. Often called **GINT3** to disambiguate from GINT4/GINT5.
This is what the GServer `CString` `operator>>(int)` / `readGInt()` produce — used for
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
> mask the top byte to 7 bits — it clamps it to **223** (`if (val[0] > 223) val[0] = 223`),
> exactly like GSHORT. So the real encodable max is `223 << 14 + 223 << 7 + 223 = 3,682,399`,
> not `2^21 − 1`. For values ≤ 2,097,151 the bytes are identical either way, which is why
> the bug rarely bites — but a strict 7-bit-mask encoder will truncate large rupee/online
> counts.

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

A 4-byte G-type (`CString` `readGInt4`). Same byte-shift scheme, top byte clamped to 223.
Encodable max `≈ 471,347,295`. Decode bias is `0x4081020`. Rare on the wire but part of
the type system, so a complete codec should implement it.

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
| GSHORT | 2 bytes | 28,767 | `(b1 << 7) + b2 - 0x1020` |
| GINT / GINT3 | 3 bytes | 3,682,399 | `((b1 << 7) + b2 << 7) + b3 - 0x81020` |
| GINT4 | 4 bytes | 471,347,295 | byte-shift, bias `0x4081020` |
| GINT5 | 5 bytes | 4,294,967,295 | 7-bit unpack, subtract 32 each |

> **Naming note:** GServer's `CString` exposes `writeGInt`/`readGInt` for the **3-byte**
> type. Throughout this documentation "GINT" and "GINT3" are the same thing.

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

### Colors (5 or 8 bytes)

Player colors are consecutive GCHARs:

```
[coat][sleeves][shoes][belt][skin]   (classic / old-world: 5 bytes)
+ [sword][shield][unused]            (new-world: 8 bytes total)
Each byte: color index (+ 32 for encoding)
```

> The count is **generation-dependent, not version-string dependent**: the server emits
> 8 colour bytes in new-world mode (`isNewWorldMode()`) and 5 in classic mode. The reborn
> stack targets v6.037 (new-world) → **8 bytes**. A parser hard-coded to 5 will desync the
> rest of the property block against a modern server.

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
