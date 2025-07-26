# Encryption Details

This section provides detailed information about the Reborn protocol encryption system, focusing on the ENCRYPT_GEN_5 implementation.

## Encryption Generations

| Generation | Encryption | Compression | Description |
|------------|------------|-------------|-------------|
| GEN_1 (0) | None | None | Plain text protocol |
| GEN_2 (1) | None | Zlib | Compression only |
| GEN_3 (2) | Single byte | Zlib | Basic obfuscation |
| GEN_4 (3) | Partial | BZ2 | Secure compression |
| GEN_5 (4) | Partial | Multi | Current standard |

## ENCRYPT_GEN_5 Implementation

### Key Stream Generation

The GEN_5 encryption uses a simple XOR-based stream cipher:

```cpp
class CEncryption {
    uint8_t m_key;           // Current encryption key
    uint32_t m_iterator;     // Iterator for key generation  
    int32_t m_limit;         // Encryption byte limit
    
    static const uint32_t ITERATOR_START[6] = {
        0, 0, 0x4A80B38, 0x481C622, 0x481C6A2, 0x12345678
    };
};

void decrypt(CString& buffer) {
    for (int i = 0; i < m_limit && i < buffer.length(); i++) {
        buffer[i] ^= (m_key + m_iterator++);
        m_iterator &= 0xFF;
    }
}
```

### Encryption Limits

Encryption is applied only to the first N bytes based on compression type:

| Compression Type | Limit | Bytes Encrypted |
|------------------|-------|-----------------|
| UNCOMPRESSED (0x02) | 40 | 40 bytes |
| ZLIB (0x04) | 4096 | 4096 bytes |
| BZ2 (0x06) | 65536 | 65536 bytes |

### Compression Integration

The compression type affects both compression algorithm and encryption limits:

```cpp
void limitFromType(uint8_t type) {
    switch(type) {
        case COMPRESS_UNCOMPRESSED: limit = 40; break;
        case COMPRESS_ZLIB: limit = 4096; break;
        case COMPRESS_BZ2: limit = 65536; break;
    }
}
```

## Packet Bundle Processing

### Outgoing (Client → Server)

```
1. Create packet bundle with individual packets
2. Compress bundle using specified method  
3. Prepend compression type byte
4. Encrypt first N bytes (based on compression type)
5. Send with 2-byte length prefix
```

### Incoming (Server → Client)

```
1. Read 2-byte length prefix
2. Read bundle data
3. Extract compression type (first byte)
4. Decrypt first N bytes using key stream
5. Decompress using specified method
6. Parse individual packets (newline-separated)
```

## Implementation Examples

### C++ Implementation

```cpp
void encrypt(CString& data) {
    for (int i = 0; i < limit && i < data.length(); i++) {
        data[i] ^= (key + iterator++);
        iterator &= 0xFF;
    }
}
```

### Python Implementation

```python
def decrypt(self, data: bytes, limit: int = -1) -> bytes:
    result = bytearray(data)
    
    # Apply limit
    bytes_to_decrypt = len(data) if limit < 0 else min(len(data), limit)
    
    for i in range(bytes_to_decrypt):
        result[i] ^= (self.key + self.iterator) & 0xFF
        self.iterator = (self.iterator + 1) & 0xFF
        
    return bytes(result)
```

### JavaScript Implementation

```javascript
function decrypt(data, key, iterator, limit) {
    const result = new Uint8Array(data);
    const bytesToDecrypt = limit < 0 ? data.length : Math.min(data.length, limit);
    
    for (let i = 0; i < bytesToDecrypt; i++) {
        result[i] ^= (key + iterator) & 0xFF;
        iterator = (iterator + 1) & 0xFF;
    }
    
    return { data: result, iterator: iterator };
}
```

## Security Considerations

1. **Limited Scope**: Only first N bytes are encrypted
2. **Simple Algorithm**: Basic XOR with incrementing key
3. **Predictable**: Iterator increment is linear
4. **Compression Dependency**: Security varies by compression type

The encryption is designed for obfuscation rather than cryptographic security, suitable for game protocol protection but not sensitive data.

## Common Implementation Errors

1. **Wrong Iterator Start**: Must use `0x4A80B38` for GEN_5
2. **Complex Key Generation**: Should be simple `key + iterator++`
3. **Incorrect Limits**: Must respect compression-type-based byte limits
4. **Endianness Issues**: Ensure proper byte order in multi-byte operations

These details ensure proper encryption compatibility with official Reborn servers and clients.