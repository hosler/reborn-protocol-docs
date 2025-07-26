# Protocol Conformance Guidelines

This section provides guidelines for implementing Reborn protocol conformance and ensuring compatibility with existing servers and clients.

## Conformance Levels

### Level 1: Basic Compatibility (Minimum)
- Correct packet ID enumeration
- Proper bundle structure handling
- Basic G-type encoding/decoding
- Core gameplay packets (movement, chat, items)
- GEN_5 encryption support

### Level 2: Standard Compatibility (Recommended)
- All Level 1 requirements
- Complete player property system
- File transfer support
- Level board handling
- GMAP navigation support
- Raw data packet processing

### Level 3: Full Compatibility (Complete)
- All Level 2 requirements  
- RC (Remote Control) administration packets
- NC (NPC Control) content management
- Advanced packet types (SHOOT2, BOARDLAYER)
- Script/bytecode handling
- Complete server management features

## Critical Requirements

### 1. Encryption Algorithm
**MUST** use the exact GEN_5 encryption implementation:

```cpp
void decrypt(uint8_t* buffer, int length, uint8_t key, uint32_t& iterator, int limit) {
    int bytes_to_decrypt = (limit < 0) ? length : min(length, limit);
    
    for (int i = 0; i < bytes_to_decrypt; i++) {
        buffer[i] ^= (key + iterator) & 0xFF;
        iterator = (iterator + 1) & 0xFF;
    }
}
```

**Common Errors to Avoid**:
- Complex multiplier operations
- Wrong iterator initialization  
- Incorrect byte limits

### 2. G-Type Encoding
**MUST** implement exact bit operations:

```cpp
// GSHORT encoding
uint16_t encodeGShort(uint16_t value) {
    uint8_t byte1 = ((value >> 6) & 0x3F) + 32;
    uint8_t byte2 = (value & 0x3F) + 32;
    return (byte1 << 8) | byte2;
}
```

### 3. Packet Bundle Processing
**MUST** follow exact order:
1. Read 2-byte length prefix
2. Extract compression type
3. Decrypt with compression-based limits
4. Decompress using appropriate algorithm
5. Parse newline-separated packets

## Testing Requirements

### Unit Tests
```python
def test_gshort_encoding():
    # Test boundary values
    assert encode_gshort(0) == b'\x20\x20'      # 32,32
    assert encode_gshort(63) == b'\x20\x5f'     # 32,95  
    assert encode_gshort(4095) == b'\x5f\x5f'   # 95,95
    
def test_encryption_limits():
    # Test compression-based limits
    assert get_encryption_limit(UNCOMPRESSED) == 40
    assert get_encryption_limit(ZLIB) == 4096
    assert get_encryption_limit(BZ2) == 65536
```

### Integration Tests
- Connect to reference server
- Send/receive standard packet sequences  
- Verify encryption/decryption roundtrip
- Test file transfer operations
- Validate GMAP navigation

### Compatibility Tests
- Test against multiple server versions
- Verify client version detection
- Check backward compatibility
- Test error handling with malformed packets

## Validation Checklist

### ✅ Packet Structure
- [ ] Correct packet ID enumeration
- [ ] Proper bundle length handling
- [ ] Newline packet separation
- [ ] Raw data packet processing

### ✅ Encryption
- [ ] GEN_5 algorithm implementation  
- [ ] Correct iterator initialization (0x4A80B38)
- [ ] Proper encryption limits by compression type
- [ ] XOR with simple key increment

### ✅ Data Types
- [ ] GCHAR: value + 32
- [ ] GSHORT: bit-shift encoding  
- [ ] GINT: 3-byte variable encoding
- [ ] GSTRING: length-prefixed strings

### ✅ Core Functionality
- [ ] Player movement and properties
- [ ] Chat and messaging
- [ ] Item and inventory handling
- [ ] Level navigation
- [ ] File transfer

### ✅ Advanced Features
- [ ] GMAP support
- [ ] Script/bytecode handling
- [ ] Administration (RC) packets
- [ ] Content management (NC) packets

## Performance Guidelines

### Memory Usage
- Minimize packet buffer allocation
- Reuse encryption state objects
- Cache decoded player properties
- Implement efficient string handling

### Network Efficiency
- Batch small packets when possible
- Use appropriate compression types
- Implement proper flow control
- Handle connection timeouts gracefully

### Processing Speed
- Optimize hot-path packet handlers
- Use lookup tables for packet routing
- Minimize string encoding/decoding
- Implement efficient raw data processing

## Security Considerations

### Protocol Security
- Validate all incoming packet data
- Implement proper bounds checking
- Handle malformed packets gracefully
- Rate-limit packet processing

### Implementation Security
- Avoid buffer overflows in string handling
- Validate file transfer operations  
- Implement proper access controls
- Use secure random number generation

## Documentation Requirements

### API Documentation
- Document all public packet handling APIs
- Provide encoding/decoding examples
- Include error handling guidelines
- Specify version compatibility

### Integration Documentation  
- Provide setup and configuration guides
- Document common integration patterns
- Include troubleshooting information
- Provide migration guides

## Certification Process

### Self-Certification
1. Complete validation checklist
2. Run full test suite
3. Test against reference implementation
4. Document any deviations

### Community Certification
1. Submit implementation for review
2. Provide test results and documentation
3. Address feedback and issues
4. Maintain ongoing compatibility

Following these guidelines ensures robust, compatible Reborn protocol implementations that work reliably with the broader ecosystem of servers and clients.