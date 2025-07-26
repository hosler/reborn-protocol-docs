# Usage Examples

This section provides practical examples of implementing the Reborn protocol in various programming languages.

## Basic Client Connection

### Python Example

```python
import socket
import struct
import zlib

class RebornClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.encryption_key = 123  # Set during login
        self.iterator = 0x4A80B38   # GEN_5 initial value
        
    def connect(self):
        """Connect to Reborn server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        
    def send_packet(self, packet_id, data=b''):
        """Send a packet with GEN_5 encryption"""
        # Build packet
        packet = bytes([packet_id + 32]) + data + b'\n'
        
        # Compress (use zlib for packets > 55 bytes)
        if len(packet) > 55:
            compression_type = 0x04  # ZLIB
            compressed = zlib.compress(packet)
            encrypt_limit = 4096
        else:
            compression_type = 0x02  # UNCOMPRESSED
            compressed = packet
            encrypt_limit = 40
            
        # Encrypt first N bytes
        encrypted = self.encrypt(compressed, encrypt_limit)
        
        # Send with length prefix
        bundle = bytes([compression_type]) + encrypted
        length_data = struct.pack('<H', len(bundle))
        self.socket.send(length_data + bundle)
        
    def encrypt(self, data, limit):
        """GEN_5 encryption"""
        result = bytearray(data)
        bytes_to_encrypt = min(len(data), limit)
        
        for i in range(bytes_to_encrypt):
            result[i] ^= (self.encryption_key + self.iterator) & 0xFF
            self.iterator = (self.iterator + 1) & 0xFF
            
        return bytes(result)
        
    def send_login(self, username, password):
        """Send login packet"""
        login_data = f"{username}\n{password}\n"
        self.send_packet(0, login_data.encode('latin-1'))  # PLI_LEVELWARP for login
        
    def send_chat(self, message):
        """Send chat message"""
        self.send_packet(6, message.encode('latin-1'))  # PLI_TOALL
        
    def send_movement(self, x, y):
        """Send player movement"""
        # Build player props packet with position
        props = bytearray()
        props.append(15 + 32)  # PLPROP_X
        props.append(int(x/2) + 32)  # Half-pixel coordinates
        props.append(16 + 32)  # PLPROP_Y  
        props.append(int(y/2) + 32)
        
        self.send_packet(2, bytes(props))  # PLI_PLAYERPROPS

# Usage
client = RebornClient("localhost", 14900)
client.connect()
client.send_login("username", "password")
client.send_chat("Hello, world!")
client.send_movement(32, 48)  # Move to tile (2, 3)
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
        
        // Compress and encrypt
        let bundle;
        if (packet.length > 55) {
            // Use zlib compression (would need pako library)
            const compressed = pako.deflate(packet);
            const encrypted = this.encrypt(compressed, 4096);
            bundle = new Uint8Array(1 + encrypted.length);
            bundle[0] = 0x04; // ZLIB
            bundle.set(encrypted, 1);
        } else {
            const encrypted = this.encrypt(packet, 40);
            bundle = new Uint8Array(1 + encrypted.length);
            bundle[0] = 0x02; // UNCOMPRESSED
            bundle.set(encrypted, 1);
        }
        
        // Send with length prefix
        const lengthData = new Uint8Array(2);
        new DataView(lengthData.buffer).setUint16(0, bundle.length, true);
        
        const fullPacket = new Uint8Array(lengthData.length + bundle.length);
        fullPacket.set(lengthData);
        fullPacket.set(bundle, lengthData.length);
        
        this.ws.send(fullPacket);
    }
    
    encrypt(data, limit) {
        const result = new Uint8Array(data);
        const bytesToEncrypt = Math.min(data.length, limit);
        
        for (let i = 0; i < bytesToEncrypt; i++) {
            result[i] ^= (this.encryptionKey + this.iterator) & 0xFF;
            this.iterator = (this.iterator + 1) & 0xFF;
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
        
        if (packet.size() > 55) {
            compressionType = 0x04; // ZLIB
            encryptLimit = 4096;
            // Would use zlib here: compressed = zlibCompress(packet);
            compressed = packet; // Simplified
        } else {
            compressionType = 0x02; // UNCOMPRESSED
            encryptLimit = 40;
            compressed = packet;
        }
        
        // Encrypt
        encrypt(compressed.data(), compressed.size(), encryptLimit);
        
        // Send bundle
        std::vector<uint8_t> bundle;
        bundle.push_back(compressionType);
        bundle.insert(bundle.end(), compressed.begin(), compressed.end());
        
        // Add length prefix and send
        uint16_t length = bundle.size();
        // Send length (little-endian) + bundle
        sendToSocket(reinterpret_cast<uint8_t*>(&length), 2);
        sendToSocket(bundle.data(), bundle.size());
    }
    
    void encrypt(uint8_t* data, size_t length, int limit) {
        size_t bytesToEncrypt = std::min(length, static_cast<size_t>(limit));
        
        for (size_t i = 0; i < bytesToEncrypt; i++) {
            data[i] ^= (encryptionKey + iterator) & 0xFF;
            iterator = (iterator + 1) & 0xFF;
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
assert encode_gshort(28767) == b'\xff\x7f'  # 28767 -> 255,127 (max)
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

```python
class PlayerProperties:
    def __init__(self):
        self.properties = {}
        
    def set_property(self, prop_id, value):
        """Set a player property"""
        self.properties[prop_id] = value
        
    def build_props_packet(self):
        """Build PLI_PLAYERPROPS packet data"""
        data = bytearray()
        
        for prop_id, value in self.properties.items():
            data.append(prop_id + 32)  # Property ID
            
            if prop_id in [0, 10, 11, 12, 20, 21, 34, 35]:  # String properties
                # GSTRING encoding
                str_data = str(value).encode('latin-1')
                data.append(min(len(str_data), 223) + 32)
                data.extend(str_data[:223])
                
            elif prop_id in [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 18, 19]:  # Byte properties
                # GCHAR encoding
                data.append(int(value) + 32)
                
            elif prop_id in [14, 27, 28, 29]:  # Short properties
                # GSHORT encoding (7-bit shift)
                val = min(int(value), 28767)
                val0 = val >> 7
                if val0 > 223:
                    val0 = 223
                val1 = val - (val0 << 7)
                data.append(val0 + 32)
                data.append(val1 + 32)
                
        return bytes(data)

# Usage
props = PlayerProperties()
props.set_property(0, "PlayerName")      # NICKNAME
props.set_property(15, 64)               # X position
props.set_property(16, 96)               # Y position
props.set_property(12, "Hello!")         # CHAT

packet_data = props.build_props_packet()
```

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

These examples demonstrate the core concepts needed to implement a compatible Reborn protocol client or server in any programming language.