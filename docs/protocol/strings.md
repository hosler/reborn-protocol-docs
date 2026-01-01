# String Types: A Tragedy in Three Acts

The Reborn protocol has three different ways to encode strings. They are not interchangeable. They are sometimes given the same name. This has caused pain.

## The Three Types at a Glance

| Type | Format | Max Length | Terminator | Also Known As |
|------|--------|------------|------------|---------------|
| Regular String | Raw bytes to packet end | Packet size | None (or null) | "string", "read to end" |
| Length-Prefixed | [GCHAR length][data] | 223 chars | None | "GSTRING", "gstring" |
| Newline-Terminated | Raw bytes until 0x0A | Line length | Newline (0x0A) | Also "gstring" (confusingly) |

## Type 1: Regular String (Read Until You Can't)

The simplest and most chaotic option. No length prefix, no terminator—just read bytes until the packet ends.

**Characteristics**:
- Reads ALL remaining bytes in the packet
- No length indicator
- Packet boundary is the only delimiter
- Server *sometimes* adds a null byte at the end (for fun, presumably)

**Used in**:
- PLI_LEVELWARP (level name after X, Y coordinates)
- PLO_LEVELNAME (entire packet is the level name)
- PLO_FILESENDFAILED (filename)
- Many other "last field in packet" situations

**Implementation**:
```python
# Read remaining bytes
def read_string_to_end(packet, current_position):
    return packet[current_position:]

# Or if using CString-style API
level_name = packet.readString("")  # Empty delimiter = read to end
```

**The Null Byte Situation**:

The server often (but not always) appends a null byte (0x00) to these strings. This is inconsistent enough to be annoying but consistent enough that you need to handle it:

```python
# Strip trailing nulls when reading
level_name = packet[pos:].rstrip(b'\x00').decode('latin-1')
```

## Type 2: GSTRING (The Polite One)

A well-behaved, length-prefixed string. The first byte (GCHAR-encoded) tells you exactly how many bytes follow.

**Format**:
```
[GCHAR: length][string_data]
```

**Characteristics**:
- First byte is length, encoded as GCHAR (so subtract 32)
- Maximum length: 223 characters (GCHAR max value)
- No terminator needed
- Actually predictable

**Used in**:
- Player properties (nickname, gani, headimage, etc.)
- NPC properties
- Most "sane" packet fields

**Implementation**:
```python
def read_gstring(packet, pos):
    length = packet[pos] - 32  # GCHAR decode
    string_data = packet[pos+1 : pos+1+length]
    return string_data.decode('latin-1'), pos + 1 + length

def write_gstring(string_data):
    encoded = string_data.encode('latin-1')
    length = len(encoded)
    if length > 223:
        raise ValueError("GSTRING max length is 223")
    return bytes([length + 32]) + encoded
```

## Type 3: Newline-Terminated (The Impostor)

Reads bytes until it hits a newline character (0x0A). The newline is consumed but not included in the result.

**Format**:
```
[string_data][0x0A]
```

**Characteristics**:
- Reads until newline (0x0A)
- Newline is consumed but not returned
- No length prefix
- Confusingly ALSO called "gstring" in some GServer code

**Used in**:
- PLO_LEVELLINK data
- Some internal packet handlers
- Multi-line data parsing

**Implementation**:
```python
def read_until_newline(packet, pos):
    end = packet.find(b'\n', pos)
    if end == -1:
        end = len(packet)  # No newline found, read to end
    return packet[pos:end].decode('latin-1'), end + 1
```

---

## The PLO_LEVELLINK Trap 🪤

This deserves its own section because multiple client implementations have gotten it wrong.

**The Trap**: PLO_LEVELLINK (packet ID 1) looks like it should use a length-prefixed GSTRING. It does not. It uses a raw newline-terminated string.

**What the Server Sends**:
```
[0x21]level.nw 10 20 1 1 30 40\n
  │                           └── Newline terminator
  └── Packet ID (1 + 32 = 33 = 0x21)
```

**What People Expect**:
```
[0x21][0x3D]level.nw 10 20 1 1 30 40
  │     │
  │     └── Length byte (they think)
  └── Packet ID
```

**What Goes Wrong**:

If you try to read the first byte after the packet ID as a length, you'll read 'l' (ASCII 108) minus 32 = 76. Then you'll try to read 76 bytes of "string data" and your parser will consume half the next packet.

**The Fix**:

```python
# WRONG
def handle_levellink(packet):
    length = packet[0] - 32  # NO! This reads 'l' of "level.nw"
    data = packet[1:1+length]

# RIGHT
def handle_levellink(packet):
    # Read until newline, no length prefix
    end = packet.find(b'\n')
    data = packet[:end].decode('latin-1')
    # data = "level.nw 10 20 1 1 30 40"
```

**Why This Happens**:

Level link data is stored in `.nw` level files as plain text lines. The server reads these lines and sends them with minimal processing. Adding a length prefix would require extra work, and apparently that was a bridge too far in the late 90s.

---

## The Naming Confusion

The term "gstring" is used inconsistently across codebases:

| Context | "gstring" Means |
|---------|-----------------|
| GServer CString class | Length-prefixed (GCHAR + data) |
| Some packet handlers | Newline-terminated |
| PyReborn packet_parser | Length-prefixed |
| PyReborn packet_handler | Newline-terminated |
| This documentation | We try to be specific |

**Recommendation**: When documenting or discussing, use these explicit terms:
- "Length-prefixed string" or "GSTRING"
- "Newline-terminated string"
- "Read-to-end string" or "regular string"

Avoid just saying "gstring" without context.

---

## Quick Reference by Packet

| Packet | String Type | Field |
|--------|-------------|-------|
| PLI_LEVELWARP | Read-to-end | Level name (after X, Y) |
| PLI_TOALL | Read-to-end | Chat message |
| PLO_LEVELNAME | Read-to-end | Level name (entire payload) |
| PLO_LEVELLINK | Newline-terminated | Link data |
| PLO_FILESENDFAILED | Read-to-end | Filename |
| PLO_TOALL | Read-to-end | Chat message (after player ID) |
| Player props (nickname, etc.) | Length-prefixed | Various string properties |
| NPC props | Length-prefixed | Various string properties |

---

## Character Encoding

All strings in the Reborn protocol use **Latin-1** (ISO-8859-1) encoding. Not UTF-8. Not ASCII. Latin-1.

This matters because:
- Bytes 128-255 are valid characters
- One byte = one character (no multi-byte sequences)
- You can safely treat string length as byte length

```python
# Correct
text = data.decode('latin-1')

# Incorrect (will fail on bytes > 127)
text = data.decode('ascii')

# Incorrect (will misinterpret high bytes)
text = data.decode('utf-8')
```

---

## Common Pitfalls Summary

1. **PLO_LEVELLINK is NOT length-prefixed** — It's newline-terminated. Multiple implementations have made this mistake.

2. **"gstring" means different things** — Always check the specific packet documentation.

3. **Read-to-end strings may have null bytes** — The server inconsistently appends them. Handle gracefully.

4. **Length-prefixed max is 223** — GCHAR encoding limits the length byte to 223.

5. **Use Latin-1, not UTF-8** — The protocol predates widespread UTF-8 adoption.
