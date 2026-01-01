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
│  6. PREPEND LENGTH (2 bytes, little-endian)                             │
│     ┌───────────────────────────────────────────────────────────────┐  │
│     │ [len_lo][len_hi][encrypted...][plaintext...]                  │  │
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
│     [len_lo][len_hi] → length = (len_hi << 8) | len_lo                 │
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
| GEN_2 (1) | None | Zlib | Also ancient |
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

## ENCRYPT_GEN_5: The Details

### The Algorithm

GEN_5 uses an XOR stream cipher. It's not cryptographically secure—it's obfuscation to discourage casual packet sniffing.

```cpp
class Encryption {
    uint8_t key;           // Current key byte (0-255)
    uint32_t iterator;     // Counter for key generation
    int32_t limit;         // How many bytes to encrypt
};

void decrypt(uint8_t* data, size_t length) {
    size_t bytes_to_process = min(length, limit);
    for (size_t i = 0; i < bytes_to_process; i++) {
        data[i] ^= (key + iterator) & 0xFF;
        iterator++;
    }
}
```

The key stream is simply `key + iterator`, incrementing the iterator each byte. That's it. No S-boxes, no rounds, no key schedule. Just XOR with a counter.

### Encryption Limits

Here's the quirk: encryption is only applied to the first N bytes. Beyond that, it's plaintext.

| Compression Type | Byte Value | Encryption Limit | Encrypted |
|------------------|------------|------------------|-----------|
| UNCOMPRESSED | 0x02 | 40 bytes | First 40 bytes |
| ZLIB | 0x04 | 4,096 bytes | First 4KB |
| BZ2 | 0x06 | 65,536 bytes | First 64KB |

Why these specific limits? The theory is that compressing data makes the first bytes more "random" and thus harder to analyze, so you don't need to encrypt the whole thing. In practice, this means if your packet is larger than the limit, part of it is unencrypted.

For uncompressed data, only 40 bytes are encrypted. Why 40? Your guess is as good as mine.

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

| Generation | Iterator Start | In Hex | Notes |
|------------|---------------|--------|-------|
| GEN_1 | 0 | 0x0 | No encryption anyway |
| GEN_2 | 0 | 0x0 | Still no encryption |
| GEN_3 | 78,061,368 | 0x4A80B38 | Why this number? Lost to time. |
| GEN_4 | 75,924,002 | 0x481C622 | See above. |
| GEN_5 | 305,419,896 | 0x12345678 | At least this one is obviously arbitrary |

These values were presumably chosen by someone in the early 2000s. The rationale is lost. If you get them wrong, your packets are garbage. Get them right, and don't ask questions.

### The Key

The encryption key is typically set during the login handshake. Both client and server must agree on the same key. The key is a single byte (0-255), which is... not a lot of key space.

## Implementation Examples

### Python

```python
class Encryption:
    def __init__(self, generation=5):
        self.key = 0
        self.iterator = [0, 0, 0x4A80B38, 0x481C622, 0x12345678][generation]
        self.limit = 0

    def set_limit_from_compression(self, compression_type):
        limits = {0x02: 40, 0x04: 4096, 0x06: 65536}
        self.limit = limits.get(compression_type, 0)

    def decrypt(self, data):
        result = bytearray(data)
        bytes_to_process = min(len(data), self.limit)

        for i in range(bytes_to_process):
            result[i] ^= (self.key + self.iterator) & 0xFF
            self.iterator = (self.iterator + 1) & 0xFFFFFFFF

        return bytes(result)

    encrypt = decrypt  # XOR is its own inverse
```

### JavaScript

```javascript
class Encryption {
    constructor(generation = 5) {
        this.key = 0;
        this.iterator = [0, 0, 0x4A80B38, 0x481C622, 0x12345678][generation];
        this.limit = 0;
    }

    setLimitFromCompression(compressionType) {
        const limits = {0x02: 40, 0x04: 4096, 0x06: 65536};
        this.limit = limits[compressionType] || 0;
    }

    decrypt(data) {
        const result = new Uint8Array(data);
        const bytesToProcess = Math.min(data.length, this.limit);

        for (let i = 0; i < bytesToProcess; i++) {
            result[i] ^= (this.key + this.iterator) & 0xFF;
            this.iterator = (this.iterator + 1) >>> 0;  // Keep as unsigned 32-bit
        }

        return result;
    }

    encrypt(data) {
        return this.decrypt(data);  // XOR is its own inverse
    }
}
```

### C++ (from GServer-v2)

```cpp
void CEncryption::decrypt(CString& buffer) {
    int len = (m_limit < buffer.length()) ? m_limit : buffer.length();

    for (int i = 0; i < len; i++) {
        buffer[i] ^= (m_key + m_iterator++);
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

1. **Wrong iterator start**: Each generation has a specific starting value. GEN_5 uses 0x12345678.

2. **Forgetting the limit**: You must stop encrypting/decrypting after `limit` bytes.

3. **Wrong compression type handling**: The compression type byte determines the limit.

4. **Order of operations**: GEN_5 encrypts *after* compression. GEN_3 encrypts *after* decompression.

5. **Iterator overflow**: The iterator should wrap around at 32 bits (for GEN_5), but the key XOR only uses the low 8 bits.

## Full Bundle Processing Example

```python
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
