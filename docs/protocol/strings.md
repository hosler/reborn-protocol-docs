# String Types: A Tragedy in Two Acts

The Reborn protocol has two methods to encode strings on the wire, plus a framing detail that looks like a third. The methods are not interchangeable. Some code uses the same name for different methods. This causes errors.

## The Types at a Glance

| Type | Format | Max Length | Terminator | Also Known As |
|------|--------|------------|------------|---------------|
| Regular String | Raw bytes to packet end | Packet size | None (or null) | "string", "read to end" |
| Length-Prefixed | [GCHAR length][data] | 223 chars | None | "GSTRING", "gstring" |
| "Newline-terminated" | Not a wire type | n/a | The packet's own newline | Some code calls a read-to-end string this |

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

## The Packet Newline (Not a String Type)

The reader of a packet bundle splits the stream on newline characters (0x0A). Every packet
ends with one: the server's send queue appends `'\n'` to each packet
(gs2lib `CFileQueue.cpp:101-103`), and the receiver cuts each packet with
`readString("\n")` (`server/include/network/IPacketHandler.h:330`). That newline belongs
to the packet framing. It is not a terminator that individual string fields carry.

**What this means for strings**:
- A string that the server writes as the last field of a packet is a read-to-end string
  (Type 1). The newline that follows it is the packet terminator.
- A reader that treats the string as "until newline" gets the same bytes only because the
  packet has already been cut at the newline. It is not a third wire encoding.
- Code that calls such a field "newline-terminated" (or "gstring") describes the framing,
  not the field.

**Used in**:
- PLO_LEVELLINK data (a read-to-end string, see below)
- Other packets whose last field is a read-to-end string

**Implementation** (a reader working on one already-split packet):
```python
def read_to_end(packet, pos):
    return packet[pos:].decode('latin-1')
```

---

## The PLO_LEVELLINK Trap 🪤

Multiple client implementations parse this field incorrectly.

**The Trap**: PLO_LEVELLINK (packet ID 1) looks like it should use a length-prefixed GSTRING. It does not. It is a read-to-end string with no length prefix. The server builds it as `>> (char)PLO_LEVELLINK << link.getLinkStr()` (`server/src/level/Level.cpp:165`, `server/src/level/LevelLink.cpp:71-74`) with no explicit newline. The only newline is the one that ends the packet.

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
    # Read to the end of the packet (already cut at the newline), no length prefix
    data = packet.rstrip(b'\n').decode('latin-1')
    # data = "level.nw 10 20 1 1 30 40"
```

**Why This Happens**:

The link is one space-separated text line, and the packet has no length field for it. Nothing in the reference explains the original design choice.

---

## The Naming Confusion

The term "gstring" is used inconsistently across codebases:

| Context | "gstring" Means |
|---------|-----------------|
| GServer CString class | Length-prefixed (GCHAR + data) |
| Some packet handlers | A read-to-end field, described as newline-terminated |
| PyReborn packet_parser | Length-prefixed |
| PyReborn packet_handler | A read-to-end field, described as newline-terminated |
| This documentation | We try to be specific |

**Recommendation**: When documenting or discussing, use these explicit terms:
- "Length-prefixed string" or "GSTRING"
- "Read-to-end string" or "regular string"

Do not use only "gstring" without context.

---

## Quick Reference by Packet

| Packet | String Type | Field |
|--------|-------------|-------|
| PLI_LEVELWARP | Read-to-end | Level name (after X, Y) |
| PLI_TOALL | Length byte on the wire, read-to-end by the server | Chat message. Reference quirk: `readString(readGUChar())` (`server/src/player/Player.cpp:1765`) converts the length to its decimal text (gs2lib `CString.cpp:133-138`) and uses that as a delimiter (gs2lib `CString.cpp:272-291`), so the length is never used as a length and the message is cut at the first occurrence of those digits |
| PLO_LEVELNAME | Read-to-end | Level name (entire payload) |
| PLO_LEVELLINK | Read-to-end | Link data |
| PLO_FILESENDFAILED | Read-to-end | Filename |
| PLO_TOALL | Length-prefixed | Chat message (after the GSHORT player ID; `server/src/player/Player.cpp:1782`) |
| Player props (nickname, etc.) | Length-prefixed | Various string properties |
| NPC props | Length-prefixed | Various string properties |

---

## Character Encoding

Reborn selects the text encoding by session type. This is Reborn's policy, not a
rule found in the reference. The reference server treats text as opaque bytes (it keeps a
per-account `codePage`, default 1252, set by a client property: `server/include/Account.h:72`,
`server/src/player/PlayerProps.cpp:1055-1063`), and no list-server text decoding was found
in the list-server source or the reference client. The claim that the two sessions differ
is backed only by Reborn's own tests, so treat it as **unverified** against the reference:

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

1. **PLO_LEVELLINK is NOT length-prefixed**. It is a read-to-end string. Multiple implementations have made this mistake.

2. **"gstring" means different things**. Always check the specific packet documentation.

3. **Read-to-end strings may have null bytes**. The server does not append them consistently. Accept both forms.

4. **Length-prefixed max is 223**. GCHAR encoding limits the length byte to 223.

5. **Choose encoding by session**. Game text is Latin-1. List-server text is
   cp1252. Neither is UTF-8.

6. **Do not Unicode-fold GS2 text**. Case-insensitive GS2 operations are
   ASCII-only. GS1 has its own deliberately different policy.
