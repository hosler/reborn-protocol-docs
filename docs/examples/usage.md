# Usage Examples

This section gives practical Reborn protocol examples in different
programming languages.

## Basic Client Connection

### Python Example

```python
from pyreborn.client import Client

client = Client("localhost", 14900, version="6.037")
if client.connect() and client.login("username", "password"):
    client.say("Hello, world!")
    # The Client facade exposes position and level as property aliases over
    # its state components.
    print(client.level, client.x, client.y)
client.disconnect()
```

For list-server framing without a socket, use the transport-neutral session:

```python
from pyreborn.listserver import ListServerSession

session = ListServerSession(
    version="G3D0311C", client_type="pyreborn", encryption_key=42
)
init_frame = session.build_init_packet()       # GEN_2 initialization frame
login_frame = session.build_login_packet("username", "password")  # GEN_5
assert init_frame and login_frame
```

### JavaScript Example

```javascript
class RebornClient {
    constructor(host, port) {
        this.host = host;
        this.port = port;
        this.ws = null;
        this.encryptionKey = 123;
        this.iterator = 0x4A80B38;
    }
    
    connect() {
        // WebSocket connection for browser usage
        this.ws = new WebSocket(`ws://${this.host}:${this.port}`);
        this.ws.binaryType = 'arraybuffer';
        
        this.ws.onmessage = (event) => {
            this.handlePacket(new Uint8Array(event.data));
        };
    }
    
    sendPacket(packetId, data = new Uint8Array()) {
        // Build packet
        const packet = new Uint8Array(1 + data.length + 1);
        packet[0] = packetId + 32;
        packet.set(data, 1);
        packet[packet.length - 1] = 10; // newline
        
        // Compress and encrypt. The encrypt limit is an ITERATION count
        // (4 bytes per iteration), not a byte count.
        let bundle;
        if (packet.length > 0x2000) {
            // Game sessions use bzip2 here (library call omitted).
            throw new Error("bzip2 compressor required for bundles >8192 bytes");
        } else if (packet.length > 55) {
            // Use zlib compression (would need pako library)
            const compressed = pako.deflate(packet);
            const encrypted = this.encrypt(compressed, 0x04); // 4 iterations
            bundle = new Uint8Array(1 + encrypted.length);
            bundle[0] = 0x04; // ZLIB
            bundle.set(encrypted, 1);
        } else {
            const encrypted = this.encrypt(packet, 0x0C);     // 12 iterations
            bundle = new Uint8Array(1 + encrypted.length);
            bundle[0] = 0x02; // UNCOMPRESSED
            bundle.set(encrypted, 1);
        }
        
        // Send with 2-byte BIG-ENDIAN length prefix (setUint16 littleEndian=false)
        const lengthData = new Uint8Array(2);
        new DataView(lengthData.buffer).setUint16(0, bundle.length, false);
        
        const fullPacket = new Uint8Array(lengthData.length + bundle.length);
        fullPacket.set(lengthData);
        fullPacket.set(bundle, lengthData.length);
        
        this.ws.send(fullPacket);
    }
    
    // GEN_5: XOR with the LCG keystream, advancing the 32-bit iterator every
    // 4 bytes. limit = number of 4-byte iterations (-1 = encrypt all).
    encrypt(data, limit) {
        const result = new Uint8Array(data);
        for (let i = 0; i < data.length; i++) {
            if (i % 4 === 0) {
                if (limit === 0) break;
                // LCG step, kept as unsigned 32-bit
                this.iterator = (Math.imul(this.iterator, 0x8088405) + this.encryptionKey) >>> 0;
                if (limit > 0) limit--;
            }
            result[i] ^= (this.iterator >>> (8 * (i % 4))) & 0xFF;
        }
        return result;
    }
    
    sendChat(message) {
        const data = new TextEncoder().encode(message);
        this.sendPacket(6, data); // PLI_TOALL
    }
}
```

### C++ Example

```cpp
#include <iostream>
#include <vector>
#include <string>
#include <cstdint>
#include <stdexcept>

class RebornClient {
private:
    uint8_t encryptionKey = 123;
    uint32_t iterator = 0x4A80B38;
    
public:
    void sendPacket(uint8_t packetId, const std::vector<uint8_t>& data = {}) {
        // Build packet
        std::vector<uint8_t> packet;
        packet.push_back(packetId + 32);
        packet.insert(packet.end(), data.begin(), data.end());
        packet.push_back('\n');
        
        // Determine compression
        uint8_t compressionType;
        int encryptLimit;
        std::vector<uint8_t> compressed;
        
        if (packet.size() > 0x2000) {
            compressionType = 0x06; // BZIP2
            encryptLimit = 0x04;    // 4 iterations
            // compressed = bzip2Compress(packet);
            throw std::runtime_error("bzip2 compressor required");
        } else if (packet.size() > 55) {
            compressionType = 0x04; // ZLIB
            encryptLimit = 0x04;    // 4 iterations
            // compressed = zlibCompress(packet);
            throw std::runtime_error("zlib compressor required");
        } else {
            compressionType = 0x02; // UNCOMPRESSED
            encryptLimit = 0x0C;    // 12 iterations
            compressed = packet;
        }
        
        // Encrypt
        encrypt(compressed.data(), compressed.size(), encryptLimit);
        
        // Send bundle
        std::vector<uint8_t> bundle;
        bundle.push_back(compressionType);
        bundle.insert(bundle.end(), compressed.begin(), compressed.end());
        
        // Add length prefix and send. The prefix is 2 bytes BIG-ENDIAN
        // (high byte first) — do NOT memcpy a host uint16_t.
        uint16_t length = bundle.size();
        uint8_t lenPrefix[2] = {
            static_cast<uint8_t>((length >> 8) & 0xFF),  // high byte first
            static_cast<uint8_t>(length & 0xFF)
        };
        sendToSocket(lenPrefix, 2);
        sendToSocket(bundle.data(), bundle.size());
    }
    
    // GEN_5: XOR with the LCG keystream, advancing the 32-bit iterator every
    // 4 bytes. `limit` is the number of 4-byte iterations (NOT a byte count);
    // -1 means encrypt everything. Using a simple increment here is the most
    // common implementation mistake — see encryption.md.
    void encrypt(uint8_t* data, size_t length, int limit) {
        for (size_t i = 0; i < length; i++) {
            if (i % 4 == 0) {
                if (limit == 0) return;
                iterator = iterator * 0x8088405u + encryptionKey;  // LCG step
                if (limit > 0) limit--;
            }
            data[i] ^= reinterpret_cast<uint8_t*>(&iterator)[i % 4];
        }
    }
    
    void sendChat(const std::string& message) {
        std::vector<uint8_t> data(message.begin(), message.end());
        sendPacket(6, data); // PLI_TOALL
    }
    
    void sendMovement(uint16_t x, uint16_t y) {
        std::vector<uint8_t> props;
        props.push_back(15 + 32); // PLPROP_X
        props.push_back((x/2) + 32);
        props.push_back(16 + 32); // PLPROP_Y
        props.push_back((y/2) + 32);
        
        sendPacket(2, props); // PLI_PLAYERPROPS
    }
    
private:
    void sendToSocket(const uint8_t* data, size_t length) {
        // Platform-specific socket send implementation
    }
};
```

## G-Type Encoding Examples

### GSHORT Encoding

```python
def encode_gshort(value):
    """Encode 16-bit value as GSHORT (7-bit shift, max 28767)"""
    t = min(value, 28767)  # GServer max value
    val0 = t >> 7
    if val0 > 223:
        val0 = 223
    val1 = t - (val0 << 7)
    return bytes([val0 + 32, val1 + 32])

def decode_gshort(data):
    """Decode GSHORT to 16-bit value"""
    return (data[0] << 7) + data[1] - 0x1020  # 0x1020 = (32 << 7) + 32

# Examples (corrected for 7-bit encoding)
assert encode_gshort(0) == b'\x20\x20'      # 0 -> 32,32
assert encode_gshort(1000) == b'\x27\x88'   # 1000 -> 39,136  
assert encode_gshort(28767) == b'\xff\xff'  # 28767 -> 255,255 (max; both bytes clamp to 223+32)
assert decode_gshort(b'\x20\x20') == 0
assert decode_gshort(b'\x27\x88') == 1000
```

### GSTRING Encoding

```python
def encode_gstring(text):
    """Encode string with length prefix"""
    data = text.encode('latin-1')
    length = min(len(data), 223)  # Max GCHAR value
    return bytes([length + 32]) + data[:length]

def decode_gstring(data):
    """Decode GSTRING"""
    if len(data) < 1:
        return ""
    length = data[0] - 32
    if length < 0 or length > len(data) - 1:
        return ""
    return data[1:1+length].decode('latin-1', errors='replace')

# Examples
assert encode_gstring("hello") == b'\x25hello'  # 5+32=37=0x25
assert decode_gstring(b'\x25hello') == "hello"
```

## Player Property Handling

Do **not** bucket property ids into "byte", "short" and "string" groups by
hand. The buckets do not exist. `RUPEESCOUNT` (3) is a 3-byte gInt, not one
byte. `ID` (14) and `KILLSCOUNT`/`DEATHSCOUNT`/`ONLINESECS` (27-29) are
multi-byte gInts, not bit-packed GSHORTs. `SWORDPOWER` (8) and `SHIELDPOWER`
(9) carry a bias plus an optional image. `X`/`Y` (15/16) are signed half-tiles.
A hand-written bucket list gets at least one of these wrong and misaligns every
property after it.

`reborn_protocol.props` owns the descriptor table. Use it:

```python
from reborn_protocol.props import PLAYER_PROPS, encode_value

def build_props_packet(props):
    """Build a PLI_PLAYERPROPS payload from {prop_id: value}."""
    data = bytearray()
    for prop_id in sorted(props):        # ascending id order is required
        desc = PLAYER_PROPS[prop_id]
        data.append(prop_id + 32)
        data.extend(encode_value(desc, props[prop_id]))
    return bytes(data)

packet_data = build_props_packet({
    0:  "PlayerName",   # NICKNAME, length-prefixed string
    3:  1250,           # RUPEESCOUNT, 3-byte gInt
    12: "Hello!",       # CURCHAT
    15: 32.0,           # X, half-tile
    16: 48.0,           # Y, half-tile
})
```

`sorted()` is not cosmetic. Property streams travel in ascending id order, and
a strict parser stops at the first descending id instead of raising an error,
so an out-of-order writer makes entities arrive half-populated with no
diagnostic.

## File Transfer Example

```python
def request_file(client, filename):
    """Request a file from server"""
    data = filename.encode('latin-1')
    client.send_packet(23, data)  # PLI_WANTFILE
    
def handle_file_packet(packet_data):
    """Handle incoming PLO_FILE packet"""
    if len(packet_data) < 6:
        return None
        
    # Read file type and size
    file_type = packet_data[0] - 32
    size_bytes = packet_data[1:6]
    
    # Decode GINT5 size
    file_size = 0
    for i in range(5):
        file_size = (file_size << 7) | ((size_bytes[i] - 32) & 0x7F)
    
    # Extract file data
    file_data = packet_data[6:6+file_size]
    
    return {
        'type': file_type,
        'size': file_size,
        'data': file_data
    }
```

These examples show the core concepts that you must use to make a compatible
Reborn protocol client or server in any programming language.
