# Protocol Overview

The Reborn protocol is a binary packet-based protocol used for communication between Reborn clients and servers. It was designed in the late 1990s and carries the architectural decisions of that era with pride.

## Before You Begin: The Philosophy

Understanding *why* this protocol is the way it is will save you hours of confusion.

### Why Everything Adds 32

Almost every numeric value in this protocol has 32 added to it before transmission. The goal was to ensure all bytes fall within the printable ASCII range (32-255), making packet dumps more readable and allegedly helping with certain network configurations of the era.

The result is a protocol that's *technically* binary but *kinda* looks like ASCII if you squint. The space character (32) becomes the new zero. Newlines (10) are packet separators. It's almost clever.

For details, see [Data Types: The +32 Obsession](data-types.md#the-32-obsession-why-everything-adds-32).

### Why Three String Types

Because one wasn't confusing enough. See [String Types](strings.md) for the full tragedy.

### Why Partial Encryption

The encryption only covers the first N bytes of each bundle because compressed data is "random-looking" and presumably hard to analyze. Also, encrypting everything would be work.

## Protocol Architecture

### Connection Types

The Reborn protocol supports multiple connection types:

| Type | Purpose | Encryption | Notes |
|------|---------|------------|-------|
| **Game Client** | Standard players | GEN_5 | Most common |
| **RC (Remote Control)** | Server administration | GEN_5 (RC2) / GEN_2 (legacy RC) | Admin access |
| **NC (NPC Control)** | Content management | **GEN_2** | NPC scripting; no key byte |
| **NPC-Server** | Dedicated NPC server | Varies | GS1/GS2 (V8 optional) |
| **Listserver** | Server discovery | GEN_2 | Login/server list |

See [RC & NC Protocols](rc-nc-protocols.md) for the admin sub-protocol login handshakes.

### The Bundle System

All packets are sent within **bundles**. A bundle contains one or more packets and is processed as a unit.

```
┌────────────────────────────────────────────────────────┐
│                    WIRE FORMAT                          │
├────────────────────────────────────────────────────────┤
│                                                         │
│   [length][compression_type][encrypted_compressed_data] │
│      2B          1B              variable               │
│                                                         │
└────────────────────────────────────────────────────────┘

Inside the bundle (after decrypt + decompress):
┌────────────────────────────────────────────────────────┐
│ [packet_id][data][\n][packet_id][data][\n]...         │
└────────────────────────────────────────────────────────┘
```

**Key points**:
- Length prefix is 2 bytes, **big-endian** (`struct.pack('>H', len)` — high byte first)
- Compression type is 1 byte (0x02=none, 0x04=zlib, 0x06=bz2)
- Packets within a bundle are separated by newlines (0x0A)
- Each packet's first byte is the packet ID (GCHAR-encoded)

### Processing Order

For GEN_5 (the current standard):

```
SENDING:
  Raw Packets → Bundle → Compress → Encrypt → Length Prefix → Send

RECEIVING:
  Receive → Strip Length → Decrypt → Decompress → Split → Parse
```

See [Encryption: The Packet Lifecycle](encryption.md#the-packet-lifecycle) for detailed diagrams.

## Encryption Generations

The protocol has evolved through multiple "generations" of encryption:

| Gen | Encryption | Compression | Use |
|-----|------------|-------------|-----|
| GEN_1 | None | None | Ancient |
| GEN_2 | None | Zlib | Live: NC + listserver |
| GEN_3 | Weak XOR | Zlib | Legacy |
| GEN_4 | Weak XOR | BZ2 | Legacy |
| **GEN_5** | **Weak XOR** | **Multi** | **Current** |

GEN_5 is recommended. "Weak XOR" means it's obfuscation, not cryptographic security.

See [Encryption Details](encryption.md) for implementation specifics.

## Data Encoding

### G-Types (The Graal Types)

All numeric values use "G-type" encoding, which adds 32 to ensure printable ASCII:

| Type | Size | Max Value | Formula |
|------|------|-----------|---------|
| GCHAR | 1 byte | 223 | `value + 32` |
| GSHORT | 2 bytes | 28,767 | 7-bit encoding + 32 per byte |
| GINT | 3 bytes | 2,097,151 | 7-bit encoding + 32 per byte |
| GINT5 | 5 bytes | 34 billion | 7-bit encoding + 32 per byte |

See [Data Types](data-types.md) for encoding details and examples.

### String Encoding

There are **three** types of strings. This is important:

1. **Regular String**: Reads to end of packet (no prefix, no terminator)
2. **GSTRING**: Length-prefixed with GCHAR (max 223 chars)
3. **Newline-Terminated**: Reads until 0x0A

The term "gstring" is used inconsistently in various codebases. Always check the specific packet documentation.

See [String Types](strings.md) for the full breakdown.

## Coordinate System

```
1 tile = 16 pixels
1 level = 64×64 tiles = 1024×1024 pixels
```

| Context | Unit | Range |
|---------|------|-------|
| Board/tile operations | Tiles | 0-63 |
| Player movement | Half-tiles | 0-127 |
| Precise positioning | Pixels | Variable |
| GMAP world | Tiles + grid offset | See GMAP docs |

## Quick Start: Minimal Client

Here's the basic flow to connect and authenticate:

```
1. TCP connect to server:port
2. Receive server greeting (PLO_* packets with server info)
3. Send PLI_LOGIN with credentials
4. Receive PLO_PLAYERPROPS with your player data
5. Receive PLO_LEVELBOARD + PLO_LEVELNAME for starting level
6. Start handling game packets
```

## Documentation Structure

| Document | Contents |
|----------|----------|
| [Data Types](data-types.md) | G-type encoding, coordinates, property types |
| [String Types](strings.md) | The three string types and their gotchas |
| [Encryption](encryption.md) | Packet lifecycle, encryption algorithm, magic constants |
| [Packet Structures](packet-structures.md) | Individual packet formats (PLI_* and PLO_*) |
| [GServer Behavior](gserver-behavior.md) | Server implementation notes |
| [Level Links](level-link-implementation.md) | Level warp/link system |

## Common Pitfalls

1. **Forgetting the +32**: Every numeric value is offset by 32. Forgetting this means garbage data.

2. **Wrong string type**: PLO_LEVELLINK uses newline-terminated strings, not GSTRING. This has bitten multiple implementations.

3. **GEN_5 order of operations**: Encrypt *after* compress. GEN_3 did it the other way around.

4. **Partial encryption**: Only the first N bytes are encrypted (N depends on compression type).

5. **Iterator constants**: Each encryption generation has a magic starting value. Get it wrong, everything breaks.

## Acknowledgments

This documentation is based on analysis of the GServer-v2 codebase and years of implementation experience. The protocol's quirks are documented with affection—it's a product of its time, and it works.
