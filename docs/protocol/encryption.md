# Encryption and Packet Processing

This section covers how packets are encrypted, compressed, and bundled in the Reborn protocol. The word "encryption" is used loosely here—this is obfuscation, not cryptographic security.

## The Packet Lifecycle

Understanding the full journey of a packet is crucial. Here's what happens:

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

The protocol supports multiple "generations" of encryption. Each subsequent generation was presumably meant to be more secure. The results are... mixed.

| Generation | Encryption | Compression | Status |
|------------|------------|-------------|--------|
| GEN_1 (0) | None | None | Ancient history |
| GEN_2 (1) | None | Zlib | **Live: NC clients + listserver** |
| GEN_3 (2) | Single byte XOR | Zlib | Legacy |
| GEN_4 (3) | Partial XOR | BZ2 | Less legacy |
| **GEN_5 (4)** | **Partial XOR** | **Multi** | **Current standard** |

### GEN_3 vs GEN_5: Order of Operations

This is a critical difference that has confused implementers:

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

GEN_5 encrypts the *compressed bundle*. GEN_3 encrypts the *decompressed packets*. Getting this wrong means nothing works.

## ENCRYPT_GEN_2: The NC / Listserver Format

GEN_2 is not just "ancient history" — it is the **live** encryption for two current
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

GEN_5 uses a Linear Congruential Generator (LCG) to produce a key stream, then XORs each byte. It's not cryptographically secure—it's obfuscation to discourage casual packet sniffing.

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

The iterator is advanced using an LCG with multiplier `0x8088405` every 4 bytes. Each of the 4 bytes of the 32-bit iterator is used to XOR one byte of data.

### Encryption Limits

Here's the quirk: encryption is only applied to the first N iterations. Each iteration processes 4 bytes. Beyond that, it's plaintext.

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

Why these specific limits? The theory is that compressing data makes the first bytes more "random" and thus harder to analyze, so you don't need to encrypt the whole thing. In practice, this means if your packet is larger than the limit, part of it is unencrypted.

### Compression Types

```cpp
#define COMPRESS_UNCOMPRESSED  0x02  // No compression
#define COMPRESS_ZLIB          0x04  // Zlib (deflate)
#define COMPRESS_BZ2           0x06  // Bzip2
```

Why 0x02, 0x04, 0x06 instead of 0, 1, 2? Probably to avoid having 0x00 bytes in the stream, maintaining the protocol's allergy to low-value bytes.

## The Magic Constants

### Iterator Starting Values

Each encryption generation has a starting value for the iterator. These values are not cryptographically significant—they're just arbitrary starting points.

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

Note: GEN_3, GEN_4, and GEN_5 all use the same iterator start value (0x4A80B38). The difference is in the algorithm—GEN_3 uses single-byte insertion, while GEN_4/5 use the LCG-based XOR method.

These values were presumably chosen by someone in the early 2000s. The rationale is lost. If you get them wrong, your packets are garbage. Get them right, and don't ask questions.

### The Key

The encryption key is typically set during the login handshake. Both client and server must agree on the same key. The key is a single byte (0-255), which is... not a lot of key space.

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
