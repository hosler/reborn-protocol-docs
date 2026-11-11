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

### Sending (Client → Server)

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
│  3. COMPRESS (if enabled)                                               │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [compressed_data...]                                          │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  4. PREPEND COMPRESSION TYPE                                            │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [type][compressed_data...]                                    │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  5. ENCRYPT (first N bytes only!)                                       │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [encrypted...][plaintext...]  ← N bytes encrypted, rest plain │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  6. PREPEND LENGTH (2 bytes, big-endian)                                │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [len_hi][len_lo][encrypted...][plaintext...]                  │  │
│     └───────────────────────────────────────────────────────────────┘  │
│                                   │                                     │
│                                   ▼                                     │
│  7. SEND OVER SOCKET                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Receiving (Server → Client)

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
| GEN_1 (0) | None | None | Ancient history |
| GEN_2 (1) | None | Zlib | **Live: NC clients + listserver** |
| GEN_3 (2) | Single byte XOR | Zlib | Legacy |
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
Send: Compress → Send
Recv: Decompress → Decrypt individual packets → Parse
```

GEN_5 encrypts the *compressed bundle*. GEN_3 encrypts the *decompressed packets*. An incorrect order prevents communication.

## ENCRYPT_GEN_2: The NC / Listserver Format

GEN_2 is the **live** encryption for two current
connection types: **NC (NPC Control)** clients and **listserver** communication. If you
implement an NC client, you implement GEN_2.

GEN_2 is the simplest format:

```
[uint16 big-endian length][zlib-compressed bundle]
```

- **No per-packet/partial encryption.** GEN_2's encrypt/decrypt is a no-op. The "encryption"
  is purely the zlib wrapping.
- **No compression-type byte.** Unlike GEN_5, there is no leading `0x02/0x04/0x06` — the
  payload is *always* zlib. (A tolerant reader may fall back to treating the body as raw if
  zlib inflation fails.)
- **The login packet omits the encryption-key byte.** The server reads the key byte only
  when `gen > ENCRYPT_GEN_3`. Since GEN_2 < GEN_3, NC/listserver logins do **not** send it.
- The decompressed bundle is the usual `[id+32][body]\n` packet stream.

This is why an NC client cannot share the GEN_5 codec path: it must swap to a GEN_2 codec
(zlib-frame in/out, no key byte, no compression byte) before login. See
[RC & NC Protocols](rc-nc-protocols.md) for the full NC login handshake.

> RC is the other admin protocol but does **not** use GEN_2: modern **RC2** clients use
> GEN_5 (with the key byte and compression byte, exactly like a game client). Only the
> legacy `PLTYPE_RC` and `PLTYPE_NC` paths use GEN_2.

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

These values come directly from GServer-v2's `CEncryption.cpp`:
```cpp
static int limits[] = { 0x02, 0x0C, 0x04, 0x04, 0x06, 0x04 };
// { type, limit, type, limit, ... }
```

The design assumes that compression makes the first bytes less predictable and more difficult to analyze. Therefore, it does not encrypt the complete packet. If a packet exceeds the limit, part of it remains unencrypted.

### Compression Types

```cpp
#define COMPRESS_UNCOMPRESSED  0x02  // No compression
#define COMPRESS_ZLIB          0x04  // Zlib (deflate)
#define COMPRESS_BZ2           0x06  // Bzip2
```

The likely reason for values 0x02, 0x04, and 0x06 is to prevent 0x00 bytes in the stream. This choice is consistent with other low-value-byte restrictions.

### Outbound Compression Is a Session Contract

GEN_5 does not have one universal size policy. Reborn uses these outbound
policies:

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

The original clients use different size limits. The 2.22 client chooses the type for each
flush of its send buffer (`n` bytes before compression):

| `n` | Type |
|---|---|
| below `0x30` (48) | `0x02`, or `0x04` when zlib output is actually shorter |
| `0x30` to `0xFFF` | `0x04` zlib |
| `0x1000` (4096) and above | `0x06` bzip2 |

The send buffer flushes at `0x1000` bytes. Real 2.22 sessions under Wine sent 580 `0x02` and
17 `0x04` frames. No `0x06` frame from a client has been captured yet. The Delphi
RemoteControl RC socket uses the same per-flush choice. So the 55 and 8192 limits above are
Reborn's own policy, not the 2.22 client's. Any receiver accepts all three
types, so either policy works on the wire. Source: Graal_analysis
[`protocol/client-versions.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/client-versions.md)
and
[`protocol/codec-and-framing.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/codec-and-framing.md)
(static read and lab captures).

The two-tier list-server rule describes the client's historical behavior
against the closed production list server; it is **not** a demonstrated
server-side prohibition. The open reference list server accepts `0x06`, calls
`limitFromType`, decrypts, and bzip2-decompresses it
(`graal-serverlist/server/src/PlayerConnection.cpp:137-153`). A compatible
client nevertheless should emit only uncompressed or zlib bundles for a
production list-server session unless it has separately established bzip2
support.

## The Magic Constants

### Iterator Starting Values

Each encryption generation has an iterator start value. These arbitrary values have no cryptographic significance.

From GServer-v2's `CEncryption.cpp`:
```cpp
const uint32_t CEncryption::ITERATOR_START[6] = {0, 0, 0x04A80B38, 0x4A80B38, 0x4A80B38, 0};
```

| Generation | Enum Index | Iterator Start | In Hex | Notes |
|------------|------------|---------------|--------|-------|
| GEN_1 | 0 | 0 | 0x0 | No encryption anyway |
| GEN_2 | 1 | 0 | 0x0 | Still no encryption |
| GEN_3 | 2 | 78,061,368 | 0x4A80B38 | Why this number? Lost to time. |
| GEN_4 | 3 | 78,061,368 | 0x4A80B38 | Same as GEN_3 |
| **GEN_5** | 4 | **78,061,368** | **0x4A80B38** | **Same as GEN_3/4** |

GEN_3, GEN_4, and GEN_5 all use the same iterator start value (0x4A80B38). Their algorithms differ. GEN_3 inserts one byte, while GEN_4 and GEN_5 use the LCG-based XOR method.

Someone selected these values in the early 2000s, but the reason is unknown. Incorrect values produce invalid packets. Use the specified values.

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
        self.limit = self.LIMITS.get(compression_type, -1)

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
        this.limit = Encryption.LIMITS[compressionType] ?? -1;
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

**Appropriate use**: Discouraging casual packet sniffing in a game protocol from 1999. Not for protecting sensitive data.

## Common Implementation Errors

1. **Wrong iterator start**: GEN_3, GEN_4, and GEN_5 all use `0x4A80B38`, not other values.

2. **Using simple increment**: GEN_4/5 use an LCG (`iterator = iterator * 0x8088405 + key`), NOT simple increment.

3. **Wrong limit interpretation**: Limits are iteration counts (each iteration = 4 bytes), not raw byte counts.

4. **Forgetting the limit check**: You must stop after `limit` iterations.

5. **Order of operations**: GEN_5 encrypts *after* compression. GEN_3 encrypts *after* decompression.

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
        self.limit = self.LIMITS.get(compression_type, -1)

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
