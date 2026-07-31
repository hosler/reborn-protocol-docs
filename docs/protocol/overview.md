# Protocol Overview

Reborn clients and servers use the Reborn binary packet protocol to communicate. Its
design comes from the late 1990s and contains the architectural decisions of that era.

## Before You Begin: The Philosophy

An understanding of the protocol design helps you prevent confusion.

### Why Everything Adds 32

The sender adds 32 to almost every numeric value before transmission. This operation puts
all bytes in the printable ASCII range (32-255). It makes packet dumps easier to read. The
designers also thought that it helped with some network configurations of the era.

The result is a binary protocol that can look like ASCII. The space character (32)
represents zero. Newlines (10) separate packets.

For details, see [Data Types: The +32 Obsession](data-types.md#the-32-obsession-why-everything-adds-32).

### Why Three String Types

The protocol uses three string types. See [String Types](strings.md) for details.

### Why Partial Encryption

The encryption covers only the first N bytes of each bundle. The designers assumed that
compressed data looked random and was difficult to analyze. Full encryption also required
more work.

## Protocol Architecture

### Connection Types

The Reborn protocol supports multiple connection types:

| Type | Purpose | Encryption | Notes |
|------|---------|------------|-------|
| **Game Client** | Standard players | GEN_5 | Most common |
| **RC (Remote Control)** | Server administration | GEN_5 (RC2) / GEN_2 (legacy RC) | Admin access |
| **NC (NPC Control)** | Content management | **GEN_2** | NPC scripting; no key byte |
| **NPC-Server** | Dedicated NPC server | Varies | GS1/GS2 (V8 optional) |
| **Listserver** | Server discovery | GEN_2 init → GEN_5 session | First request switches codecs |

See [RC & NC Protocols](rc-nc-protocols.md) for the admin sub-protocol login handshakes.

### The Bundle System

The sender puts all packets in **bundles**. A bundle contains one or more packets. The
receiver processes each bundle as one unit.

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

The protocol uses multiple encryption "generations":

| Gen | Encryption | Compression | Use |
|-----|------------|-------------|-----|
| GEN_1 | None | None | Ancient |
| GEN_2 | None | Zlib | Live: NC + listserver |
| GEN_3 | Weak XOR | Zlib | Legacy |
| GEN_4 | Weak XOR | BZ2 | Legacy |
| **GEN_5** | **Weak XOR** | **Multi** | **Current** |

Use GEN_5. "Weak XOR" supplies obfuscation, not cryptographic security.

See [Encryption Details](encryption.md) for implementation specifics.

GEN_5 compression selection is session-specific. Game sessions use
uncompressed/zlib/bzip2 tiers at 55 and 8192 bytes; list-server sessions use
only uncompressed/zlib with the 55-byte boundary. See
[Outbound Compression Is a Session Contract](encryption.md#outbound-compression-is-a-session-contract).

## Data Encoding

See [Data Types](data-types.md) for the wire formats of numeric values, coordinates, and
property widths. See [String Types](strings.md) for string behavior. Packet documents show
the field layout.
`data-types.md` explains each encoded width.

## Quick Start: Minimal Client

Use this basic sequence to connect and authenticate:

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

1. **Forgetting the +32**: Every numeric value has an offset of 32. Without this offset,
   the data is invalid.

2. **Wrong string type**: PLO_LEVELLINK uses newline-terminated strings, not GSTRING.
   Multiple implementations have used the wrong type.

3. **GEN_5 order of operations**: Encrypt *after* compress. GEN_3 did it the other way around.

4. **Partial encryption**: Only the first N bytes are encrypted (N depends on compression type).

5. **Iterator constants**: Each encryption generation has a special start value. An
   incorrect value causes all operations to fail.

## Acknowledgments

This documentation comes from an analysis of the GServer-v2 codebase and years of
implementation experience. The protocol is a product of its time, and it operates
correctly.
