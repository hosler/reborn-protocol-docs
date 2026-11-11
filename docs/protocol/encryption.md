# Encryption and Packet Processing

This section explains how the Reborn protocol encrypts, compresses, and bundles packets. Here, "encryption" means obfuscation, not cryptographic security.

> **Which generation does a given client use?** The client version string does not directly
> select the generation. The `PLTYPE_*` login-type byte selects it, with some version-string
> downgrades and fallbacks. See
> [Client Versions & Encryption](versions-encryption.md) for the full client/RC/NC version
> table, the PLTYPE → generation selection logic, the login packet field order, and the
> per-generation bundle framing (GEN_1 through the unimplemented GEN_6). This page focuses
> on the GEN_5 cipher internals themselves.

## The Packet Lifecycle

A packet passes through the following stages:

### Sending

The diagram shows the GEN_5 send path. The reference server's queue (gs2lib
`CFileQueue.cpp:230-269`) compresses the bundle, encrypts the compressed bytes with the limit
for the chosen type, and only then puts the unencrypted type byte in front. The length
prefix is `encrypted length + 1`.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        OUTGOING PACKET FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. BUILD PACKETS                                                       │
│     ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│     │ [id][data][\n]   │  │ [id][data][\n]   │  │ [id][data][\n]   │   │
│     └──────────────────┘  └──────────────────┘  └──────────────────┘   │
│              │                    │                    │                │
│              └────────────────────┼────────────────────┘                │
│                                   ▼                                     │
│  2. BUNDLE TOGETHER                                                     │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [pkt1][\n][pkt2][\n][pkt3][\n]                                │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  3. COMPRESS (if enabled; the type is chosen here, not yet sent)        │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [compressed_data...]                                          │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  4. ENCRYPT (first N bytes of the compressed data only!)                │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [encrypted...][plaintext...]  ← N bytes encrypted, rest plain │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  5. PREPEND COMPRESSION TYPE (never encrypted)                          │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [type][encrypted...][plaintext...]                            │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  6. PREPEND LENGTH (2 bytes, big-endian, counts the type byte)          │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [len_hi][len_lo][type][encrypted...][plaintext...]            │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  7. SEND OVER SOCKET                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Receiving

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INCOMING PACKET FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. READ LENGTH PREFIX                                                  │
│     [len_hi][len_lo] → length = (len_hi << 8) | len_lo  (big-endian)   │
│                                                                         │
│  2. READ BUNDLE (length bytes)                                          │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [type][encrypted...][plaintext...]                            │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  3. EXTRACT COMPRESSION TYPE (first byte)                               │
│     type = 0x02 (none), 0x04 (zlib), or 0x06 (bz2)                     │
│                                                                         │
│  4. DECRYPT (first N bytes, based on compression type)                  │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [decrypted_data...]                                           │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  5. DECOMPRESS (if compressed)                                          │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [pkt1][\n][pkt2][\n][pkt3][\n]                                │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  6. SPLIT ON NEWLINES                                                   │
│     (except for PLI_RAWDATA packets, which specify their own length)   │
│                                                                         │
│  7. PARSE EACH PACKET                                                   │
│     First byte (minus 32) = packet ID, rest = packet data              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Encryption Generations

The protocol supports multiple encryption "generations." Each later generation changes the encryption or compression method.

| Generation | Encryption | Compression | Status |
|------------|------------|-------------|--------|
| GEN_1 (0) | None | None | Live: `PLTYPE_WEB` logins, and the first leg of the server's list-server registration |
| GEN_2 (1) | None | Zlib | **Live: NC clients, legacy 1.x game clients, legacy RC, and the list-server bootstrap** |
| GEN_3 (2) | Single-byte insertion | Zlib | Legacy |
| GEN_4 (3) | Partial XOR | BZ2 | Less legacy |
| **GEN_5 (4)** | **Partial XOR** | **Multi** | **Current standard** |

### GEN_3 vs GEN_5: Order of Operations

Implementations must apply these operations in the specified order:

**GEN_5 (Current)**:
```
Send: Compress → Encrypt compressed data → Send
Recv: Decrypt → Decompress decrypted data → Parse
```

**GEN_3 (Legacy)**:
```
Client → server:  Insert one byte into each packet → Bundle → Compress → Send
Server receives:  Decompress → Split into packets → Remove the inserted byte from each → Parse
Server → client:  Compress → Send   (no insertion at all)
```

GEN_5 encrypts the *compressed bundle*. GEN_3 transforms the individual *packets*, before
compression on the sending side and after decompression on the receiving side, and only in
the client-to-server direction. An incorrect order prevents communication.

## ENCRYPT_GEN_2: The NC / Listserver Format

GEN_2 is the **live** encryption for several connection types: **NC (NPC Control)** clients,
legacy `PLTYPE_CLIENT` (1.x) game clients (`server/src/player/PlayerClient.cpp:302-304`),
legacy `PLTYPE_RC` (`server/src/player/PlayerRC.cpp:148-151`), and the **listserver**
bootstrap. The list server starts every connection in GEN_2 and switches both directions to
GEN_5 after the first initialization packet
(`graal-serverlist/server/src/PlayerConnection.cpp:42-43,305-306,321-322`). GEN_1 is also
still reachable: `PLTYPE_WEB` clients get it (`PlayerClient.cpp:312-315`), and the game
server's own `REGISTERV3` to the list server goes out as GEN_1, then GEN_2
(`server/src/ServerList.cpp:264-266`). If you implement an NC client, you implement GEN_2.

GEN_2 is the simplest format:

```
[uint16 big-endian length][zlib-compressed bundle]
```

- **No per-packet/partial encryption.** GEN_2's encrypt/decrypt is a no-op. The "encryption"
  is purely the zlib wrapping.
- **No compression-type byte.** Unlike GEN_5, there is no leading `0x02/0x04/0x06` — the
  payload is *always* zlib. The reference receiver inflates with `zuncompress2I`, which
  retries a bad-checksum body as raw DEFLATE but does not treat the body as raw data
  (see [Zlib tolerance](#zlib-tolerance-and-iterator-rollback)).
- **The NC/RC login packet omits the encryption-key byte.** The NC and RC login handlers read
  the key byte only when `gen > ENCRYPT_GEN_3` (`server/src/player/PlayerNC.cpp:120`,
  `server/src/player/PlayerRC.cpp:159`). Since GEN_2 < GEN_3, GEN_2 NC and RC logins do
  **not** send it. The game-client path uses a different rule: it reads the key whenever the
  version token is still unknown (`PlayerClient.cpp:333-341`). See
  [Login Packet Layout](versions-encryption.md#login-packet-layout).
- The decompressed bundle is the usual `[id+32][body]\n` packet stream.

This is why an NC client cannot share the GEN_5 codec path: it must swap to a GEN_2 codec
(zlib-frame in/out, no key byte, no compression byte) before login. See
[RC & NC Protocols](rc-nc-protocols.md) for the full NC login handshake.

> RC is the other admin protocol. Modern **RC2** clients use GEN_5 (with the key byte and
> compression byte, exactly like a game client). The legacy `PLTYPE_RC`, `PLTYPE_NC` and
> `PLTYPE_CLIENT` paths use GEN_2.

## ENCRYPT_GEN_5: The Details

### The Algorithm

GEN_5 uses a Linear Congruential Generator (LCG) to produce a key stream. It then XORs each byte. This method provides obfuscation, not cryptographic security.

```cpp
class Encryption {
    uint8_t key;           // Current key byte (0-255)
    uint32_t iterator;     // LCG state (starts at 0x4A80B38 for GEN_5)
    int32_t limit;         // How many 4-byte blocks to encrypt (-1 = unlimited)
};

// From GServer-v2 CEncryption.cpp
void decrypt(uint8_t* data, size_t length) {
    const uint8_t* iter_bytes = reinterpret_cast<const uint8_t*>(&iterator);

    for (size_t i = 0; i < length; i++) {
        if (i % 4 == 0) {
            if (limit == 0) return;
            iterator = iterator * 0x8088405 + key;  // LCG step
            if (limit > 0) limit--;
        }
        data[i] ^= iter_bytes[i % 4];
    }
}
```

The algorithm advances the iterator with an LCG multiplier of `0x8088405` every 4 bytes. It uses each iterator byte to XOR one data byte.

### Encryption Limits

The algorithm encrypts only the first N iterations. Each iteration processes 4 bytes. Data after those iterations remains plaintext.

| Compression Type | Byte Value | Limit (iterations) | Bytes Encrypted |
|------------------|------------|-------------------|-----------------|
| UNCOMPRESSED | 0x02 | 0x0C (12) | 48 bytes |
| ZLIB | 0x04 | 0x04 (4) | 16 bytes |
| BZ2 | 0x06 | 0x04 (4) | 16 bytes |

These values come directly from gs2lib's `CEncryption.cpp:159`:
```cpp
static int limits[] = { 0x02, 0x0C, 0x04, 0x04, 0x06, 0x04 };
// { type, limit, type, limit, ... }
```

If a packet exceeds the limit, part of it remains unencrypted.

### Compression Types

```cpp
#define COMPRESS_UNCOMPRESSED  0x02  // No compression
#define COMPRESS_ZLIB          0x04  // Zlib (deflate)
#define COMPRESS_BZ2           0x06  // Bzip2
```

### Outbound Compression Is a Session Contract

GEN_5 does not have one universal size policy. The table below is **Reborn's** outbound
policy (the game-session column mirrors the reference server; the list-server column is
Reborn's own choice), not a reference-wide contract. The reference server and the reference
client use different thresholds, given after the table:

| Uncompressed payload size | Game session | List-server session |
|---|---|---|
| `0..55` bytes | uncompressed, type `0x02` | uncompressed, type `0x02` |
| `56..8192` bytes | zlib, type `0x04` | zlib, type `0x04` |
| `>8192` (`0x2000`) bytes | bzip2, type `0x06` | zlib, type `0x04` |

The policies agree for every size through 8192 bytes. They differ only above
this size. This is a wire contract, not only a compression optimization. The
receiver consumes the type byte and `limitFromType`/`limit_from_type` derives
the partial-XOR limit from it. Reborn records the distinction in
`reborn_protocol.encryption.CompressionPolicy`, `GAME_COMPRESSION`, and
`LIST_SERVER_COMPRESSION`.

The reference client uses different size limits from the reference server. Its send path
(`Preagonal/FourPlay/quattroplay/src/TGraalConnection.cpp:559-580`, with `minzlibbytes = 48`
and `minbzip2bytes = 4096` at `:170-171`) chooses the type for each flush of the send
buffer (`n` bytes before compression):

| `n` | Type |
|---|---|
| below `0x30` (48) | `0x02` |
| `0x30` to `0xFFF` | `0x04` zlib |
| `0x1000` (4096) and above | `0x06` bzip2, only when `allowbzip2compression` and the per-connection flag allow it; otherwise `0x04` |

The reference client has no "zlib if shorter" rule below 48 bytes: it always sends `0x02`
there. The send buffer flushes at `0x1000` bytes (`TGraalConnection.cpp:1309,1320,1338`).

The 55 and 8192 limits above are the reference server's GEN_5 send policy
(gs2lib `CFileQueue.cpp:235-245`: `> 0x2000` bzip2, `> 55` zlib), which Reborn mirrors
for game sessions; only the list-server column is Reborn's own. The open list server's own
sends go through the same `CFileQueue` thresholds, so it sends bzip2 above 8192 bytes. Any
receiver accepts all three types, so either policy works on the wire.

The following are reported in squirelworks' client-analysis notes
(`protocol/client-versions.md` and `protocol/codec-and-framing.md`; static read and lab
captures); they were not verified against the reference. The 2.22 client picks the type by
the same 48 and 4096 thresholds, but sends `0x04` below 48 bytes when the zlib output is
actually shorter. Real 2.22 sessions under Wine sent 580 `0x02` and 17 `0x04` frames. No
`0x06` frame from a client has been captured yet. The Delphi RemoteControl RC socket uses
the same per-flush choice.

The two-tier list-server rule describes how the Reborn client treats the closed production
list server. That production behavior is **unverified** against the reference: the
reference client's own thresholds are the 48 and 4096 above, and the rule is **not** a
demonstrated server-side prohibition. The open reference list server accepts `0x06`, calls
`limitFromType`, decrypts, and bzip2-decompresses it
(`graal-serverlist/server/src/PlayerConnection.cpp:137-153`). A compatible
client nevertheless should emit only uncompressed or zlib bundles for a
production list-server session unless it has separately established bzip2
support.

### Zlib tolerance and iterator rollback

A zlib bundle is inflated with gs2lib `CString::zuncompress2`. If the normal inflate reports
a data error, it strips the 2-byte zlib header and retries the rest as raw DEFLATE. Only the
header is removed from the input (`source + 2`, `length() - 2`); the "4-byte trailer" in the
source comment is not stripped, and `buffSize - 6` is the size of the output buffer. This works around a 2.x client bug that writes a bad Adler-32
checksum in some cases (gs2lib `CString.cpp:936-959`). If both attempts fail the call returns
an empty buffer (`CString.cpp:960-976`). The buffer for the inflated data defaults to 65,536
bytes (gs2lib `CString.h:170-177`).

On GEN_5 a zlib bundle that needed the DEFLATE retry makes the receiver roll the LCG
iterator back one step (`server/include/network/IPacketHandler.h:293-301`, gs2lib
`CEncryption.h:64-65`: "the client falls 1 iteration behind"). A receiver that skips the
rollback desynchronises the keystream for every later bundle.

### Outbound bundle rules (reference server)

These are the gs2lib `CFileQueue.cpp` rules for what goes into one bundle:

- The queue packs normal packets until the bundle holds 0xC000 bytes, and stops adding a
  packet that would take it past `0xF000 - 6` bytes (`:84-146`). The exception is a first
  normal packet that is already larger than that: it is added regardless (`:108-114`), and only
  the post-compression check (over `0xFFFD` bytes, or `0xFFFC` for GEN_5) drops it
  (`:186-191`, `:251-256`).
- A packet that carries raw data is announced by `PLO_RAWDATA` as
  `>> PLO_RAWDATA >> (int)(len + 1) << '\n'`, then the body, then `'\n'`, only when the
  generation is GEN_5 or lower (`:62,92-104`). On receive, `PLI_RAWDATA` sets a flag, and
  the next `GUInt` bytes are taken as one packet without newline splitting
  (`server/include/network/IPacketHandler.h:315-328,363-368`).
- After compression the data must fit in `0xFFFC` bytes for GEN_5 (the type byte takes one
  more) or `0xFFFD` bytes for GEN_2 to GEN_4. A larger bundle is dropped with an error and
  not sent (`:186-191,209-214,251-256`).

An edge case in the reference client: it scrambles `ceil(len / 4)` blocks (at most 12) for
an uncompressed (`0x02`) payload but `floor(len / 4)` blocks (at most 4) for a compressed
one (`Preagonal/FourPlay/quattroplay/src/TGraalConnection.cpp:76-92`). The server XORs
every byte up to the limit, including a partial final block (gs2lib `CEncryption.cpp:71-85`).
The two differ only for a compressed payload shorter than 16 bytes whose length is not a
multiple of 4.

## The Magic Constants

### Iterator Starting Values

Each encryption generation has an iterator start value. These arbitrary values have no cryptographic significance.

From gs2lib's `CEncryption.cpp:24`:
```cpp
static constexpr std::array ITERATOR_START = {0U, 0U, 0x04A80B38U, 0x4A80B38U, 0x4A80B38U, 0U};
```

| Generation | Enum Index | Iterator Start | In Hex | Notes |
|------------|------------|---------------|--------|-------|
| GEN_1 | 0 | 0 | 0x0 | No encryption anyway |
| GEN_2 | 1 | 0 | 0x0 | Still no encryption |
| GEN_3 | 2 | 78,121,784 | 0x4A80B38 | Why this number? Lost to time. |
| GEN_4 | 3 | 78,121,784 | 0x4A80B38 | Same as GEN_3 |
| **GEN_5** | 4 | **78,121,784** | **0x4A80B38** | **Same as GEN_3/4** |

GEN_3, GEN_4, and GEN_5 all use the same iterator start value (0x4A80B38). Their algorithms differ. GEN_3 inserts one byte, while GEN_4 and GEN_5 use the LCG-based XOR method.

The reason for these values is unknown. Incorrect values produce invalid packets. Use the specified values.

### The Key

The login handshake usually sets the encryption key. The client and the server must use the same key. The key is one byte (0-255).

## Implementation Examples

### Python (GEN_5)

```python
import struct

class Encryption:
    """GEN_5 encryption matching GServer-v2 CEncryption.cpp"""

    # Iterator starting values by generation index
    ITERATOR_START = [0, 0, 0x4A80B38, 0x4A80B38, 0x4A80B38, 0]
    # Limits by compression type: {type: iterations}
    LIMITS = {0x02: 0x0C, 0x04: 0x04, 0x06: 0x04}

    def __init__(self, generation=4):  # GEN_5 is index 4
        self.key = 0
        self.iterator = self.ITERATOR_START[generation]
        self.limit = -1  # -1 = unlimited
        self.multiplier = 0x8088405

    def set_limit_from_compression(self, compression_type):
        # The reference limitFromType leaves the limit unchanged for an unknown type
        # and reports an error (gs2lib CEncryption.cpp:156-171).
        if compression_type in self.LIMITS:
            self.limit = self.LIMITS[compression_type]

    def decrypt(self, data):
        result = bytearray(data)

        for i in range(len(data)):
            if i % 4 == 0:
                if self.limit == 0:
                    break
                self.iterator = (self.iterator * self.multiplier + self.key) & 0xFFFFFFFF
                if self.limit > 0:
                    self.limit -= 1

            # XOR with corresponding byte of 32-bit iterator (little-endian)
            iterator_bytes = struct.pack('<I', self.iterator)
            result[i] ^= iterator_bytes[i % 4]

        return bytes(result)

    encrypt = decrypt  # XOR is its own inverse
```

### JavaScript (GEN_5)

```javascript
class Encryption {
    // GEN_5 encryption matching GServer-v2 CEncryption.cpp
    static ITERATOR_START = [0, 0, 0x4A80B38, 0x4A80B38, 0x4A80B38, 0];
    static LIMITS = {0x02: 0x0C, 0x04: 0x04, 0x06: 0x04};
    static MULTIPLIER = 0x8088405;

    constructor(generation = 4) {  // GEN_5 is index 4
        this.key = 0;
        this.iterator = Encryption.ITERATOR_START[generation];
        this.limit = -1;  // -1 = unlimited
    }

    setLimitFromCompression(compressionType) {
        // The reference leaves the limit unchanged for an unknown type.
        if (compressionType in Encryption.LIMITS) {
            this.limit = Encryption.LIMITS[compressionType];
        }
    }

    decrypt(data) {
        const result = new Uint8Array(data);

        for (let i = 0; i < data.length; i++) {
            if (i % 4 === 0) {
                if (this.limit === 0) break;
                // LCG step (keep as unsigned 32-bit)
                this.iterator = Math.imul(this.iterator, Encryption.MULTIPLIER);
                this.iterator = (this.iterator + this.key) >>> 0;
                if (this.limit > 0) this.limit--;
            }

            // XOR with corresponding byte of 32-bit iterator (little-endian)
            result[i] ^= (this.iterator >>> (8 * (i % 4))) & 0xFF;
        }

        return result;
    }

    encrypt(data) {
        return this.decrypt(data);  // XOR is its own inverse
    }
}
```

### C++ (from GServer-v2 CEncryption.cpp)

```cpp
// GEN_4 and GEN_5 use the same algorithm
void CEncryption::decrypt(CString& pBuf) {
    const uint8_t* iterator = reinterpret_cast<const uint8_t*>(&m_iterator);

    for (int32_t i = 0; i < pBuf.length(); ++i) {
        if (i % 4 == 0) {
            if (m_limit == 0) return;
            m_iterator *= 0x8088405;  // LCG multiplier
            m_iterator += m_key;
            if (m_limit > 0) m_limit--;
        }

        pBuf[i] ^= iterator[i % 4];
    }
}
```

## Security Considerations

Let's be clear: this is not secure encryption. It's obfuscation.

**Weaknesses**:
1. **Single-byte key**: Only 256 possible keys
2. **Linear key stream**: The pattern `key + iterator` is trivially predictable
3. **Partial encryption**: Large packets have plaintext tails
4. **No authentication**: Packets can be modified without detection
5. **Known plaintext**: Packet IDs are predictable, enabling key recovery

**Appropriate use**: Discouraging casual packet sniffing in a legacy game protocol. Not for protecting sensitive data.

## Common Implementation Errors

1. **Wrong iterator start**: GEN_3, GEN_4, and GEN_5 all use `0x4A80B38`, not other values.

2. **Using simple increment**: GEN_4/5 use an LCG (`iterator = iterator * 0x8088405 + key`), NOT simple increment.

3. **Wrong limit interpretation**: Limits are iteration counts (each iteration = 4 bytes), not raw byte counts.

4. **Forgetting the limit check**: You must stop after `limit` iterations.

5. **Order of operations**: GEN_5 encrypts *after* compression and prepends the type byte after encrypting. GEN_3 works on individual packets, outside the compressed bundle.

6. **Wrong byte ordering**: The 32-bit iterator is accessed as little-endian bytes for XOR.

## Full Bundle Processing Example

```python
import struct
import zlib
import bz2

class Gen5Encryption:
    """GEN_5 encryption matching GServer-v2"""
    LIMITS = {0x02: 0x0C, 0x04: 0x04, 0x06: 0x04}

    def __init__(self, key=0):
        self.key = key
        self.iterator = 0x4A80B38
        self.limit = -1

    def set_limit_from_compression(self, compression_type):
        if compression_type in self.LIMITS:
            self.limit = self.LIMITS[compression_type]

    def decrypt(self, data):
        result = bytearray(data)
        for i in range(len(data)):
            if i % 4 == 0:
                if self.limit == 0:
                    break
                self.iterator = (self.iterator * 0x8088405 + self.key) & 0xFFFFFFFF
                if self.limit > 0:
                    self.limit -= 1
            iterator_bytes = struct.pack('<I', self.iterator)
            result[i] ^= iterator_bytes[i % 4]
        return bytes(result)


def process_incoming_bundle(raw_data, encryption):
    # Step 1: Extract compression type
    compression_type = raw_data[0]
    encrypted_data = raw_data[1:]

    # Step 2: Set encryption limit based on compression
    encryption.set_limit_from_compression(compression_type)

    # Step 3: Decrypt
    decrypted = encryption.decrypt(encrypted_data)

    # Step 4: Decompress
    if compression_type == 0x04:  # ZLIB
        decompressed = zlib.decompress(decrypted)
    elif compression_type == 0x06:  # BZ2
        decompressed = bz2.decompress(decrypted)
    else:  # UNCOMPRESSED
        decompressed = decrypted

    # Step 5: Split into packets
    packets = decompressed.split(b'\n')

    # Step 6: Parse each packet
    for packet in packets:
        if len(packet) == 0:
            continue
        packet_id = packet[0] - 32  # GCHAR decode
        packet_data = packet[1:]
        handle_packet(packet_id, packet_data)
```
