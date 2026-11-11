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

### Why Two String Types

The protocol uses two string encodings: length-prefixed strings and read-to-end strings.
See [String Types](strings.md) for details, including the packet newline that causes
confusion.

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
| **NPC-Server** | Dedicated NPC server | Not determined | GS1/GS2 (V8 optional); the beta4 server runs it in-process (`server/src/player/PlayerNPCServer.cpp:39-42`), so no cipher selection was found |
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
  Raw Packets → Bundle → Compress → Encrypt → Type Byte → Length Prefix → Send

RECEIVING:
  Receive → Strip Length → Strip Type Byte → Decrypt → Decompress → Split → Parse
```

See [Encryption: The Packet Lifecycle](encryption.md#the-packet-lifecycle) for detailed diagrams.

## Encryption Generations

The protocol uses multiple encryption "generations":

| Gen | Encryption | Compression | Use |
|-----|------------|-------------|-----|
| GEN_1 | None | None | Web clients; first leg of server-to-listserver registration |
| GEN_2 | None | Zlib | Live: NC, legacy 1.x clients and RC, listserver bootstrap |
| GEN_3 | Single-byte insertion | Zlib | Legacy |
| GEN_4 | Weak XOR | BZ2 | Legacy |
| **GEN_5** | **Weak XOR** | **Multi** | **Current** |

Use GEN_5. "Weak XOR" supplies obfuscation, not cryptographic security.

See [Encryption Details](encryption.md) for implementation specifics.

GEN_5 compression selection is implementation-specific. The reference server uses
uncompressed/zlib/bzip2 tiers at 55 and 8192 bytes for every session; Reborn mirrors that
for game sessions and uses only uncompressed/zlib with the 55-byte boundary for list-server
sessions. The reference client uses 48 and 4096. See
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
2. Send the login packet: [GCHAR login type][key byte, if the type's generation uses one]
   [8-byte version][GUCHAR len][account][GUCHAR len][password][identity string]
   (the first packet has no PLI_* id; see Client Versions & Encryption)
3. The server sends nothing before it has parsed the login
4. Receive PLO_PLAYERPROPS with your player data
5. Receive PLO_LEVELBOARD + PLO_LEVELNAME for starting level
6. Start handling game packets
```

## Documentation Structure

| Document | Contents |
|----------|----------|
| [Data Types](data-types.md) | G-type encoding, coordinates, property types |
| [String Types](strings.md) | The two string encodings and their gotchas |
| [Encryption](encryption.md) | Packet lifecycle, encryption algorithm, magic constants |
| [Packet Structures](packet-structures.md) | Individual packet formats (PLI_* and PLO_*) |
| [GServer Behavior](gserver-behavior.md) | Server implementation notes |
| [Level Links](level-link-implementation.md) | Level warp/link system |

## Common Pitfalls

1. **Forgetting the +32**: Every numeric value has an offset of 32. Without this offset,
   the data is invalid.

2. **Wrong string type**: PLO_LEVELLINK is a read-to-end string, not a GSTRING. Multiple
   implementations have used the wrong type.

3. **GEN_5 order of operations**: Encrypt *after* compress, then add the unencrypted type
   byte. GEN_3 works on single packets instead of the compressed bundle.

4. **Partial encryption**: Only the first N bytes are encrypted (N depends on compression type).

5. **Iterator constants**: Each encryption generation has a special start value. An
   incorrect value causes all operations to fail.

## Acknowledgments

This documentation comes from an analysis of the GServer-v2 codebase and years of
implementation experience. The protocol is a product of its time, and it operates
correctly.
