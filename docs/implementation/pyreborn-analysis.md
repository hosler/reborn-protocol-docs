# PyReborn Protocol Conformance Analysis

## Overview

This document analyzes how well PyReborn's implementation conforms to the
documented Graal Reborn protocol, comparing it against the GServer-v2 source.

> **Architecture note:** Encryption, the Gen5 codec, the framing/`PacketBuffer`,
> and the `PacketReader`/`PacketBuilder` G-type helpers now live in the shared
> **`reborn-protocol`** library (`reborn_protocol/{encryption,codec,constants}.py`),
> which both PyReborn and pygserver import. Earlier versions of this document
> cited these in `pyreborn/protocol.py` / `pyreborn/packets.py`; those file:line
> references are stale and have been corrected below.

## Overall Conformance: **EXCELLENT**

PyReborn implements the core Graal protocol correctly and matches GServer-v2.
The previously-listed missing handlers have largely been implemented (see
[PyReborn Implementation Gaps](pyreborn-gaps.md)).

## ✅ Correctly Implemented Areas

### 1. Packet Enumeration — match

Packet IDs and property numbers come from the shared `reborn_protocol.constants`
module (`PLI`, `PLO`, `PLPROP`), not a local `enums.py`. The client-to-server,
server-to-client, and property enumerations match the protocol.

### 2. Bundle Structure — correct

```python
# reborn_protocol/codec.py — PacketBuffer.get_packets()
length = struct.unpack('>H', bytes(self._buffer[:2]))[0]
```

- Correct `[UINT16: packet_size][BUNDLE]` framing
- **Big-endian** length prefix (`>H`)

### 3. GEN_5 Compression Integration — correct

The compression type byte (`0x02` uncompressed / `0x04` zlib / `0x06` bz2) is
read first, then the remainder is decrypted/decompressed
(`reborn_protocol/codec.py` `Gen5Codec.recv_packet`).

### 4. Encryption Algorithm — correct

**GServer-v2 (`CEncryption.cpp`)**:
```cpp
m_iterator *= 0x8088405;
m_iterator += m_key;
```

**reborn-protocol (`reborn_protocol/encryption.py`)**:
```python
self.iterator = (self.iterator * self.multiplier + self.key) & 0xFFFFFFFF
# MULTIPLIER = 0x8088405, INITIAL_ITERATOR = 0x4A80B38
```

Same LCG with multiplier `0x8088405` and iterator start `0x4A80B38`.

### 5. Encryption Limits — correct

**GServer-v2 (`CEncryption.cpp`, `limitFromType`)**:
```cpp
static int limits[] = { 0x02, 0x0C, 0x04, 0x04, 0x06, 0x04 };
```

**reborn-protocol (`reborn_protocol/encryption.py`, `limit_from_type`)**:
```python
UNCOMPRESSED (0x02) -> 0x0C   # 12 iterations
ZLIB        (0x04) -> 0x04   # 4 iterations
BZ2         (0x06) -> 0x04   # 4 iterations
```

These are iteration counts (each iteration encrypts 4 bytes), not byte counts.

### 6. G-Type Encoding — correct

The `gchar`/`gshort`/`gint3`/`gint5` read/write helpers live in
`reborn_protocol.codec` (`PacketReader`/`PacketBuilder`) and are imported by
PyReborn — they are no longer redefined inline.

```python
# reborn_protocol/codec.py — PacketReader.read_gshort()
b1 = self.data[self.pos] - 32
b2 = self.data[self.pos + 1] - 32
return (b1 << 7) + b2
```

### 7. Player Properties — naming deviation only

PyReborn uses a `PLPROP_` prefix vs the documented `PlayerProp::` namespace.
Functionally equivalent. Note the GATTRIB property range (37–74) is
**non-contiguous** — see [Packet Structures](../protocol/packet-structures.md).

## 🚫 Remaining Gaps

### 1. NC content management — partial/unverified
`nc_client.py` exists; the breadth of NPC/class management coverage is not
verified. (RC administration is now fully handled in `rc_client.py`.)

### 2. Inbound enhanced packets — partial
- The client sends `PLI_SHOOT2`; inbound `PLO_SHOOT2` handling is unverified.
- `PLO_GANISCRIPT` / `PLO_NPCBYTECODE` handling is limited/unverified.

(`PLO_MINIMAP`, `PLO_GHOSTMODE`, `PLO_RPGWINDOW`, and `PLO_BOARDLAYER` are now
handled — see the gaps doc.)

## 🔧 Code Quality Observations

### Duplicate PacketReader
`pyreborn/packets.py` now imports the shared `PacketReader` from
`reborn-protocol`; only `pyreborn/listserver.py` still defines its own. The
remaining duplication is between `listserver.py` and the shared library.

## 📊 Conformance By Area

| Area | Conformance | Notes |
|------|-------------|-------|
| Packet IDs | High | From shared `reborn_protocol.constants` |
| Bundle Structure | Correct | Big-endian `>H` framing |
| Compression | Correct | uncompressed / zlib / bz2 |
| Encryption | Correct | Matches GServer-v2 (shared lib) |
| G-Type Encoding | Correct | Shared `PacketReader`/`PacketBuilder` |
| Client Packets | High | RC sends + most PLI implemented |
| Server Packets | High | Sign/explosion/hitobjects/board-layer/minimap/bigmap/ghostmode/rpgwindow handled |
| Player Properties | High | GATTRIB stored; non-contiguous numbering handled |
| File Transfer | Implemented | request/get/has-file + PLO_FILE/RAWDATA/FILESENDFAILED |

## 📝 Summary

PyReborn provides an excellent implementation of the Graal Reborn protocol. The
core protocol (encryption, encoding, framing) is provided by the shared
`reborn-protocol` library and matches GServer-v2. Remaining gaps are narrow
(NC management, a few inbound enhanced packets), not core-protocol issues.

For the gap list, see [PyReborn Implementation Gaps](pyreborn-gaps.md).

## 📋 History

### PLO_LEVELLINK Packet Structure
Real-world testing established that PLO_LEVELLINK is a raw newline-terminated
string, **not** a GSTRING. Fixed in the parser and documented in
[Level Link Implementation](../protocol/level-link-implementation.md).

### Shared protocol library
Encryption, codec, and G-type helpers were extracted from PyReborn into the
shared `reborn-protocol` package so pygserver and PyReborn share one
implementation. File:line citations in older docs that point into
`pyreborn/protocol.py` or `pyreborn/packets.py` for these primitives are
out of date.
