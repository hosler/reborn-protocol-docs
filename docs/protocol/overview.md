# Protocol Overview

The Reborn protocol is a binary packet-based protocol used for communication between Reborn clients and servers. This section provides an overview of the protocol architecture and core concepts.

## Protocol Architecture

### Connection Types

The Reborn protocol supports multiple connection types:

- **Game Clients** - Standard players connecting to play
- **RC (Remote Control)** - Administrative connections for server management  
- **NC (NPC Control)** - Content management connections for NPCs and scripting
- **NPC-Server** - Dedicated NPC scripting server connections

### Packet Bundle Structure

All communication uses packet bundles with this structure:

```
[UINT16: packet_size][PACKET_BUNDLE_DATA]
```

Where:
- `packet_size`: Size of bundle data in bytes (little-endian)
- `PACKET_BUNDLE_DATA`: Encrypted/compressed packet bundle

### Encryption Generations

The protocol supports multiple encryption generations:

- **GEN_1**: No encryption, no compression
- **GEN_2**: No encryption, zlib compression  
- **GEN_3**: Single byte insertion, zlib compression
- **GEN_4**: Partial encryption, bz2 compression
- **GEN_5**: Partial encryption, multiple compression options (recommended)

## GEN_5 Protocol (Recommended)

### Bundle Processing

1. **Bundle Structure**: `[UINT8: compression_type][ENCRYPTED_COMPRESSED_DATA]`
2. **Compression Types**:
   - `0x02`: Uncompressed
   - `0x04`: Zlib compressed
   - `0x06`: Bzip2 compressed

3. **Processing Order**:
   - **Outgoing**: Compress → Encrypt → Send
   - **Incoming**: Receive → Decrypt → Decompress

### Individual Packets

Within bundles, packets are newline-separated:

```
[UINT8: packet_id][PACKET_DATA]\n
```

Special case for raw data:
```
[UINT8: PLI_RAWDATA][UINT32: data_length]
[RAW_DATA_BYTES]
```

## Data Encoding

### Reborn-Specific Types (G-Types)

The protocol uses specialized encoding for efficient transmission:

- **GCHAR**: `char + 32` (ensures printable ASCII)
- **GSHORT**: 7-bit shift encoding with +32 bias (2 bytes, max 28767)
- **GINT**: 3-byte encoding for medium values
- **GINT5**: 5-byte encoding for large values/timestamps

### String Encoding

- **GSTRING**: `[GCHAR: length][string_data]` - Length-prefixed string
- **Regular String**: Null or delimiter-terminated string

## Coordinate System

- **Tiles**: 64×64 grid (0-63)
- **Half-tiles**: 128×128 grid (0-127) for precise positioning
- **Pixels**: Half-tiles × 16 for screen coordinates

## Implementation Notes

1. **Byte Order**: Little-endian before G-encoding
2. **String Encoding**: Latin-1 character set
3. **Error Handling**: Invalid packets should be ignored
4. **Version Compatibility**: Some packets vary by client version

This overview provides the foundation for understanding the detailed packet specifications in the following sections.