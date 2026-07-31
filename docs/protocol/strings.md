# String Types: A Tragedy in Three Acts

The Reborn protocol has three methods to encode strings. The methods are not interchangeable. Some code uses the same name for different methods. This causes errors.

## The Three Types at a Glance

| Type | Format | Max Length | Terminator | Also Known As |
|------|--------|------------|------------|---------------|
| Regular String | Raw bytes to packet end | Packet size | None (or null) | "string", "read to end" |
| Length-Prefixed | [GCHAR length][data] | 223 chars | None | "GSTRING", "gstring" |
| Newline-Terminated | Raw bytes until 0x0A | Line length | Newline (0x0A) | Also "gstring" (confusingly) |

## Type 1: Regular String (Read Until You Can't)

This type has no length prefix or terminator. Read the bytes until the packet ends.

**Characteristics**:
- Reads ALL remaining bytes in the packet
- No length indicator
- Packet boundary is the only delimiter
- The server sometimes adds a null byte at the end

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

The server often appends a null byte (0x00) to these strings, but it does not always do so. A reader must accept both forms.

```python
# Strip trailing nulls when reading
level_name = packet[pos:].rstrip(b'\x00').decode('latin-1')
```

## Type 2: GSTRING (The Polite One)

A length-prefixed string starts with a GCHAR-encoded byte. This byte specifies the exact number of bytes that follow.

**Format**:
```
[GCHAR: length][string_data]
```

**Characteristics**:
- First byte is length, encoded as GCHAR (so subtract 32)
- Maximum length: 223 characters (GCHAR max value)
- No terminator needed
- The length makes the field predictable

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

The reader reads bytes until it finds a newline character (0x0A). The reader consumes the newline but does not include it in the result.

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

Multiple client implementations parse this field incorrectly.

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

If the parser treats the first byte after the packet ID as a length, it reads 'l' (ASCII 108) minus 32 = 76. The parser then reads 76 bytes of "string data" and consumes part of the next packet.

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

`.nw` level files store level link data as plain text lines. The server reads these lines and sends them with minimal processing. The original design did not add a length prefix.

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

Do not use only "gstring" without context.

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

The session type selects the text encoding. There is no single protocol-wide
decoder:

| Session | Text encoding |
| --- | --- |
| Game server | Latin-1 (ISO-8859-1) |
| List server | Windows-1252 (`cp1252`) |

This is an intentional difference between session types. Both are
single-byte encodings, but they disagree in the `0x80`–`0x9f` range. For
example, byte `0x92` is the right single quotation mark `’` in a list-server
response, while Latin-1 preserves it as the control character U+0092.
Reborn exposes the selection through `reborn_protocol/codec.py`,
`PacketReader.__init__()` and `PacketReader.read_string()`.
`pyReborn/tests/unit/test_listserver_codec.py`,
`test_list_server_text_is_cp1252_not_latin1()`, pins the `0x92` behavior.

For game-session strings, Latin-1 means:
- Bytes 128-255 are valid characters
- One byte = one character (no multi-byte sequences)
- You can safely treat string length as byte length

```python
# Game session
game_text = data.decode('latin-1')

# List-server session
list_text = data.decode('cp1252')
```

---

## Script case-insensitive comparison

Text decoding and script case folding are separate policies. GS2
case-insensitive operations fold ASCII `A` through `Z` only. The official
interpreter's `TString::startsIgnoreCase()` and `endsIgnoreCase()` call
`TString::strncasecmp()`, which is a direct wrapper around C
`::strncasecmp`
(`Preagonal/FourPlay/quattroplay/src/TString.cpp:27-30,961-972,987-998`).
Independent GS2 implementations should use an ASCII-only fold for equality,
prefix/suffix operations, and list string sorting.

Do not use Unicode `casefold()`. It maps `"ß"` to `"ss"` and changes the
length: Unicode folding therefore says `"ßabc"` starts with `"SS"`, while
the real client says false. Reborn centralizes the GS2 rule in
`reborn_protocol/gs2/values.py`, `casefold()` and `casecmp()`.

GS1 must remain separate. Reborn's GS1 `strequals`, `strcontains`, and
`startswith` builtins use Python `.lower()` and consequently over-fold some
non-ASCII text. That behavior is internally consistent and deliberately
unchanged. Do not use it to redefine GS2 semantics.

---

## Common Pitfalls Summary

1. **PLO_LEVELLINK is NOT length-prefixed**. It is newline-terminated. Multiple implementations have made this mistake.

2. **"gstring" means different things**. Always check the specific packet documentation.

3. **Read-to-end strings may have null bytes**. The server does not append them consistently. Accept both forms.

4. **Length-prefixed max is 223**. GCHAR encoding limits the length byte to 223.

5. **Choose encoding by session**. Game text is Latin-1. List-server text is
   cp1252. Neither is UTF-8.

6. **Do not Unicode-fold GS2 text**. Case-insensitive GS2 operations are
   ASCII-only. GS1 has its own deliberately different policy.
