# GServer Behavior Reference

This document gives a quick reference to GServer-v2 protocol behavior. The information
comes from an analysis of the source code. Use this reference instead of repeated searches
of the GServer source.

## String Encoding

[String Types](strings.md) documents the string forms GServer uses. This page
only calls out the packet handlers that use them.

## Critical Packet Implementations

### PLI_LEVELWARP (0)
```cpp
// From PlayerClientPackets.cpp
HandlePacketResult PlayerClient::msgPLI_LEVELWARP(CString& pPacket)
{
    time_t modTime = 0;
    if (pPacket[0] - 32 == PLI_LEVELWARPMOD)
        modTime = (time_t)pPacket.readGUInt5();
    
    Position<int16_t> pos = { 
        static_cast<int16_t>(pPacket.readGChar() * 8), 
        static_cast<int16_t>(pPacket.readGChar() * 8) 
    };
    CString newLevel = pPacket.readString("");  // Read to end!
    // ...
}
```
**Format**: `[GUCHAR: x][GUCHAR: y][STRING: level_name]`
- X/Y use **half-tile** coordinates. The server reads them back as
  `readGChar() * 8` pixels (`PlayerClientPackets.cpp:59`), so a tile value must
  be doubled before it goes on the wire. The wire-format details for coordinate packing are in
  [Data Types](data-types.md#coordinates-a-field-guide)
- Level name reads to end of packet
- **Important**: read-to-end, **not** null-terminated

### PLO_LEVELNAME (6)
```cpp
// Server sends level name
sendPacket(CString() >> (char)PLO_LEVELNAME << level->levelName);
// For GMAP, sends map name instead
sendPacket(CString() >> (char)PLO_LEVELNAME << map->getMapName());
```
**Format**: `[STRING: level_name]`
- Entire packet payload is the level name
- No length prefix
- **Important**: read-to-end, **not** null-terminated

### PLO_PLAYERPROPS (9) / PLO_OTHERPLPROPS (8)
Player properties use a special encoding:
- Property ID (1 byte)
- Property data (varies by property)

Special cases:
- **HEADGIF (11)**: If byte < 100, it is a preset head id. Otherwise, byte-100 is the
  string length.
- **SWORDPOWER (8)**: custom image form is `[power+30][img_len][image]`.
- **SHIELDPOWER (9)**: custom image form is `[power+10][img_len][image]`.
- **X2/Y2 (78/79)**: See [Data Types](data-types.md#x2y2-encoding-the-weird-one).
- **GATTRIB1-30**: length-prefixed strings, not flag-only props.

See [Data Types](data-types.md#player-property-data-types) for the full id/width table
(props 0-83), and [NPC Properties](npc-properties.md) for the separate NPC enum.

### CString Operators

The GServer uses CString with special operators for packet construction:

```cpp
// >> operator adds data with Reborn encoding
CString packet;
packet >> (char)PLO_LEVELNAME;  // Adds char + 32
packet << levelName;             // Appends raw string

// Reading
char packetId = packet.readGChar();  // Reads byte - 32
int value = packet.readGInt();        // Reads 3-byte Reborn int
```

## Common Patterns

### Sending Packets to Players
```cpp
// To one player
player->sendPacket(packet);

// To all players in a level  
server->sendPacketToOneLevel(packet, level);

// To all players
server->sendPacketToAll(packet);
```

### File Sending
The server sends large files in chunks:
1. PLO_LARGEFILESTART - filename
2. PLO_LARGEFILESIZE - total size 
3. PLO_RAWDATA + file chunks
4. PLO_LARGEFILEEND - signals completion

### Board Modifications
Board data is always 8192 bytes (64x64 tiles, 2 bytes each):
```cpp
// Server sends board packet
sendPacket(CString() >> (char)PLO_BOARDPACKET << boardData);

// Board modifications include position and size
packet >> (char)PLO_BOARDMODIFY >> (char)x >> (char)y 
       >> (char)width >> (char)height << tileData;
```

## Coordinate Systems

Coordinate frames and the X2/Y2 packing live in [Data Types](data-types.md#coordinates-a-field-guide)
and [Data Types](data-types.md#coordinate-frames-in-gmaps).

## Property Encoding

[Data Types](data-types.md) documents the numeric widths, string forms, and special
offsets. The main implementation gotcha here is not the values
themselves, but using the wrong width for a given property.

## Error Handling

### Disconnect Messages
```cpp
sendPacket(CString() >> (char)PLO_DISCMESSAGE << reason);
```
The server always terminates the connection after this packet.

### File Send Failures
```cpp
sendPacket(CString() >> (char)PLO_FILESENDFAILED << filename);
```
The parser reads the filename to the end of the packet.

## Important Notes

1. **Packet Boundaries**: Each packet is self-contained. "Read to end" means that the
   parser reads to the end of the current packet, not the stream.

2. **GMAP Mode**: When on a GMAP, PLO_LEVELNAME sends the GMAP name, not the segment name. Segment info comes from GMAP file parsing.

3. **Version Differences**: Some behaviors change based on client version (e.g., GANI format, encryption type).

## Quick Reference Table

See [String Types](strings.md) for the packet-by-packet string forms, and
[Data Types](data-types.md) for the width rules behind the property payloads.

## Board Change Replay Is Not GMAP-Exclusive

`SubLevel::sendBoardChangesToPlayer` (`Level.cpp:481-526`) replays a level's accumulated
board-change history to any player (re)entering it, via `PLO_BOARDMODIFY2` (map coords
`0,0` for non-gmap levels, since `LevelBoardChange` objects always carry an explicit
`MapPosition{partX, partY}` even for single-part levels, see `Level.cpp:1599`) or
`PLO_BOARDMODIFY`, depending on client version (see
[Version-Gated Behavior](version-gated-behavior.md#board-changes-two-different-code-paths-only-one-is-live)
for the exact style/version table). This runs for **both gmap and non-gmap levels**.
`PlayerClient::sendDynamicLevelData` (`PlayerClient.cpp:
1492-1497`) calls it unconditionally:

```cpp
subLevel->sendBoardChangesToPlayer(self, cachedModTime);
if (!level->isGmap())
{
    level->sendHorsesToPlayer(self);
    level->sendBaddiesToPlayer(self);
}
```

The `isGmap()` check gates only the *following* horse/baddy sends, not the board-change
replay itself. A client entering a plain, non-gmap level with prior board edits still gets
them replayed via `PLO_BOARDMODIFY2`/`PLO_BOARDMODIFY`.

Note this is a **different function** from the live per-edit broadcast
(`LevelBoardChange::sendToPlayersOnLevel`), whose own version-split logic is currently dead
code. See [Version-Gated Behavior](version-gated-behavior.md#live-broadcast-path-levelboardchange-sendtoplayersonlevel-version-check-is-dead).

## PLI_BOARDMODIFY Is Not Echoed To The Sender

`PlayerClient::msgPLI_BOARDMODIFY` (`server/src/player/packets/PlayerClientPackets.cpp:
125-134`) applies the edit to the level, then broadcasts it to **other** players only:

```cpp
if (level->alterBoard(tiles, { toWholeTilePosition(globalPosition), { dim[0], dim[1] } }, this))
{
    if (!level->isGmap())
        m_server->sendPacketToOneLevelPart(CString() >> (char)PLO_BOARDMODIFY << (pPacket.text() + 1),
            getGlobalPosition(), level, { m_id });
    else
    {
        auto mapPosition = getMapPosition();
        m_server->sendPacketToNearby(CString() >> (char)PLO_BOARDMODIFY2 >> (char)mapPosition.x() >> (char)mapPosition.y()
            << (pPacket.text() + 1), getGlobalPosition(), level, { m_id });
    }
}
```

Both send calls pass `{ m_id }`, the sender's own player id, as the `exclude` set on
`sendPacketToOneLevelPart`/`sendPacketToNearby`. There is no separate `sendPacket(self, ...)`
call anywhere in this handler. **A client must apply its own board edit
optimistically when it sends the edit.** It will never receive its own `PLI_BOARDMODIFY` as a
`PLO_BOARDMODIFY`/
`PLO_BOARDMODIFY2`.

## PLO_LEVELBOARD (0) Is Effectively Dead Code

Current server code sends only an empty `PLO_LEVELBOARD`. This acknowledgment tells the
client that it can stop waiting for board data. The packet does not contain an inline tile
payload. From
`PlayerClient.cpp:1462-1465` (mirrored at `PlayerClientOriginal.cpp:140,171`):

```cpp
// The client will get stuck on "Loading" until it gets board data.
// So, if we did not send any data, send an empty packet so the client knows it can move on.
if (!sentBoard)
    sendPacket(CString() >> (char)PLO_LEVELBOARD);
```

The payload-carrying path is unreachable dead code in `Level.cpp:497-511`: a `style == 2`
branch that batches all pending board changes into a single `PLO_LEVELBOARD` packet, but
`style` (see [Version-Gated Behavior](version-gated-behavior.md#level-entry-replay-path-sublevel-sendboardchangestoplayer-version-check-is-live))
is only ever assigned `1` or `3`, never `2`:

```cpp
// The batched board changes seem to be sent when the player enters a level that it has cached.
// TODO: The current level sending implementation doesn't easily allow use to use this right now,
// so send individual changes (it won't hurt things).
if (style == 2)
{
    CString retVal;
    retVal >> (char)PLO_LEVELBOARD;
    for (const auto& change : boardChanges)
    {
        if (!time.has_value() || change.modTime >= time.value())
            retVal << change.getPropsForSingleLevel();
    }
    if (retVal.length() > 1)
        player->sendPacket(retVal);
    return;
}
```

The server sends the full 64×64 board dump in a different way. It sends raw data through
`PLO_RAWDATA (100)` + `PLO_BOARDPACKET (101)` (see
[Packet Structures](packet-structures.md#plo_boardpacket-101---full-board-8192-bytes)), not
through `PLO_LEVELBOARD` at all.

## GS1 Player Commands Silently No-Op in `timeout` Handlers

The GS1 commands `freezeplayer2`, `unfreezeplayer`, and `say2` (and other player-targeted
commands built the same way, e.g. `sendpm`) resolve their target player by walking the
script *source stack* for the nearest `PLAYER`-typed source
(`GS1Visitor::findNearestScriptObjectSourceFromStack`, `scripting/gs1/GS1Visitor.cpp:
419-427`):

```cpp
// fn_freezeplayer2 (GS1Commands.cpp:1185-1193); say2 at :1900, unfreezeplayer at :3231
if (auto source = visitor->findNearestScriptObjectSourceFromStack(ScriptObjectType::PLAYER); source.has_value())
{
    ...
    player->freezePlayer();
}
```

Player-initiated events (`playertouchsme`, `playerchats`, ...) carry a PLAYER source, so
these work there. A **`timeout` event carries no PLAYER source** (its source is the NPC
itself), so `source.has_value()` is false and the command **silently does nothing**: no
packet, no script error, no log line. A script that does `playertouchsme → freeze →
settimeout` and expects the timeout handler to `unfreezeplayer` will leave the player
frozen forever. Confirmed by live testing (pyReborn `game_tester` tier-3 freeze/say2
cycle). Workaround: run the unfreeze/say from a player-sourced event, or route through
a flag the client watches.

## Raw-Framed Client Uploads Keep a Trailing Newline

`IPacketHandler::parsePacketsFromBundle` (`IPacketHandler.h:303-318`) contains a strip for
the framing `\n` that clients append to raw-framed (`PLI_RAWDATA`-announced) packets:

```cpp
// The client and RC versions above 1.1 append a \n to the end of the packet.
// Remove it now.
//if (isClient() || (isRC() && m_versionId > RCVER_1_1))
if (RemoveNewlinesFromRawPacket)
{
    if (curPacket[curPacket.length() - 1] == '\n')
        curPacket.removeI(curPacket.length() - 1);
}
```

but the source code declares `RemoveNewlinesFromRawPacket` `= false` (`IPacketHandler.h:203`)
and **never sets it to true anywhere in the server**. The intended condition survives only
as the comment above it. (`RemoveNewlineFromFileUpload`, the sibling RC-1.1 file-upload
workaround at `:204`, is likewise never set.) Consequence: any client upload that goes
through raw framing keeps its trailing framing newline as part of the payload. An RC
text-file upload arrives one byte longer than the real file, with a spurious `0x0A` at the
end. A conforming RC client cannot fix this from its side. Server-stored files uploaded this
way are simply corrupt by one byte until the flag wiring is fixed upstream.

## Behavior Changes When an NPC Server Is Active (`hasNPCServer()`)

Several client packet handlers branch on `Server::hasNPCServer()` (true when
`serverside = true` with the built-in NPC server). Two that surprise client implementers:

- **The server refuses client NPC mutation when it owns NPCs.**
  `msgPLI_NPCPROPS` and `msgPLI_NPCDEL` immediately return without applying the
  request when `hasNPCServer()` is true
  (`GServer-v2/server/src/player/packets/PlayerClientPackets.cpp:189-193` and
  `:782-786`). A client must treat server-owned NPC state as authoritative.

- **The handler does not relay `PLI_BOMBADD` between clients.** Without an NPC server the
  handler relays `PLO_BOMBADD` to the rest of the level part. With one, the handler hands
  the bomb to the server-side bomb engine (`level->addBombFromClient(...)`), and **it does
  not broadcast any `PLO_BOMBADD` to other clients**: other players see the explosion
  effects only via the NPC-server's own output (`msgPLI_BOMBADD`,
  `PlayerClientPackets.cpp:214-241`, and on failure the server even bounces a
  `PLO_BOMBDEL` back to the *sender*). Do not write a client test
  that expects bomb relay on a `serverside = true` server.
- **Clients cannot set `server.*` flags.** `msgPLI_FLAGSET`/`msgPLI_FLAGDEL` route
  `server.`-prefixed names to the server flag list **only** `if (!m_server->hasNPCServer())`
  (`PlayerClientPackets.cpp:650-659,693-701`). With an NPC server, a client's
  `server.foo=bar` falls through, and the server stores it as an ordinary *player* flag
  instead, silently, with no error.
- **`serverr.*` and `clientr.*` are read-only only when an NPC server is running.**
  `msgPLI_FLAGSET` wraps both rejections in `if (m_server->hasNPCServer())`
  (`PlayerClientPackets.cpp:653-657`). On a `serverside = false` deployment the
  block is skipped, the later `server.` test does not match the extra `r`, and
  the name falls through to the generic `setFlag(..., SetBy::CLIENT)`. A client
  can therefore set a `clientr.*` or `serverr.*` flag that a script trusts as
  engine-controlled. `msgPLI_FLAGDEL`'s rejection **is** unconditional, so the
  two handlers disagree. Do not generalize from `FLAGDEL`.

## Chat Change Events Include Clearing

`Player::setProp` compares `CURCHAT` with the stored message before doing
anything. An unchanged value exits immediately. `Player::setProp` stores a changed value
and, when chat command processing does not consume it, queues `PLAYERCHATS`
(`GServer-v2/server/src/player/PlayerProps.cpp:354-368`). Consequently, changing
non-empty chat to the empty string is still a change and fires the player-chat
event. Re-sending the already-empty value does not.

## Known Upstream Crash: Weapon Bytecode at Login

Two related defects in the GS2-weapon delivery path, both observed during live testing
(July 2026) against the current upstream source:

1. **`Script::getClientByteCode()` terminated the server on any weapon-bytecode request.**
   Upstream `scripting/Script.cpp:193` does
   `std::any_cast<ScriptByteCode*>(m_client_script->script)`. But `script` is a
   `shared_ptr<any>` holding the bytecode **by value**, so the cast wraps the shared_ptr in
   a fresh `any` and unconditionally throws `bad_any_cast` inside a `noexcept` function →
   `std::terminate`. The local working tree carries an uncommitted fix (cast against
   `script.get()` with the non-throwing pointer overload). **Upstream remains broken** as
   of gs2emu pinned in this repo.
2. **Registering a compiled GS2 weapon at login SEGVs.** When an account's saved
   weapon list includes a bytecode-backed weapon, the login path
   (`PlayerClient::sendLogin` weapon loop → `Weapon::registerWeaponWithPlayer`,
   `PlayerClient.cpp:552`, `Weapon.cpp:267-297`) crashes the server. The **on-demand path
   works**: register the weapon name only, and let the client fetch bytecode via
   `PLI_UPDATESCRIPT (158)` → `Weapon::sendByteCodeToPlayer`. Until fixed, do not persist
   compiled-GS2 weapons onto accounts on a stock server. Grant them at runtime instead.

(The related GS1-weapon-on-MODERN-server crash (`registerWeaponWithPlayer` taking the
bytecode branch for a weapon with no compiled bytecode and sending an unbuilt
`m_headerWithCRC`) is also fixed only in the local working tree, `Weapon.cpp:275-283`.)

## Sources of Truth

The vendored `GServer-v2/dependencies/gs2lib/` copy in this repo is **stale**. It is an
orphaned git-submodule reference (`dependencies/gs2lib/.git` is a gitlink with no
`.gitmodules` registering it) and is **not wired into the CMake build at all**
(`grep`ping `server/CMakeLists.txt` for any `add_subdirectory`/path reference to it comes up
empty). Never cite it.

CMake `FetchContent` pulls the authoritative copy at configure time
(`server/CMakeLists.txt:268-278`):

```cmake
FetchContent_Declare(gs2lib
	GIT_REPOSITORY https://xtjoeytx@bitbucket.org/xtjoeytx/gs2lib.git
	GIT_SHALLOW    ON
	GIT_TAG        63b1ae96491c188905b50c6b61c8532c601a2122
	#URL "${PROJECT_SOURCE_DIR}/../gs2lib"
)
```

pinned to commit `63b1ae96491c188905b50c6b61c8532c601a2122` (bitbucket
`xtjoeytx/gs2lib`), checked out under `GServer-v2/build/dependencies/fc/gs2lib-src/`. All
enum values, `IUtil.cpp` version tables, and `CEncryption` internals cited across this
documentation set come from that path.
