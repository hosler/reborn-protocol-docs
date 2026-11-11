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
// From PlayerClientPackets.cpp:52-61
HandlePacketResult PlayerClient::msgPLI_LEVELWARP(CString& pPacket)
{
    std::optional<time_t> modTime;

    if (pPacket[0] - 32 == PLI_LEVELWARPMOD)
        modTime = static_cast<time_t>(pPacket.readGUInt5());

    const LocalPixelPosition pos = {static_cast<int16_t>(pPacket.readGChar() * 8), static_cast<int16_t>(pPacket.readGChar() * 8)};
    const CString newLevelC = pPacket.readString("");  // Read to end!
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
- `PLI_LEVELWARPMOD (30)` is the same packet with a `[GUINT5 modtime]` prefix before the
  coordinates (`:56-57`). The handler has **no permission check**. A name ending in `.gmap`
  forces a warp to that gmap (`:65-69`). A level that is a segment of a gmap gets its static
  data sent first and is then warped to (`:74-83`). If every attempt fails, the server
  re-warps the player to the level it is already in, and as a last resort to the
  `unstickmelevel` / `unstickmex` / `unstickmey` location (`:92-104`).

### PLO_LEVELNAME (6)
```cpp
// Server sends the (sub-)level name first (PlayerClient.cpp:1446)
sendPacket(CString() >> (char)PLO_LEVELNAME << staticLevelData->levelName);
// ... and after the level data, the name the player is "in" (PlayerClient.cpp:1504)
sendPacket(CString() >> (char)PLO_LEVELNAME << getLevelName());
```
On a GMAP the first packet carries the segment name and the last one carries the GMAP name
(`getLevelName()` returns the `Level`'s `levelName`, which is the gmap name, `PlayerClient.cpp:1155-1162`).
The original-protocol path sends the segment name only the first time
(`PlayerClientOriginal.cpp:149-153`).
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
// Server sends board packet (Level.cpp:114-117, 397-400)
CString retVal;
retVal.writeGChar(PLO_BOARDPACKET);
tiles.writeLayerToPacket(0, retVal);
player->sendRawPacket(retVal);

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

2. **GMAP Mode**: When on a GMAP, the segment name is sent first and the GMAP name last (see
   [PLO_LEVELNAME](#plo_levelname-6) above). Segment info comes from GMAP file parsing.

3. **Version Differences**: Some behaviors change based on client version (e.g., GANI format, encryption type).

## Quick Reference Table

See [String Types](strings.md) for the packet-by-packet string forms, and
[Data Types](data-types.md) for the width rules behind the property payloads.

## Board Change Replay Is Not GMAP-Exclusive

`SubLevel::sendBoardChangesToPlayer` (`server/src/level/Level.cpp:483-530`) replays a level's accumulated
board-change history to any player (re)entering it, via `PLO_BOARDMODIFY2` (map coords
`0,0` for non-gmap levels, since `LevelBoardChange` objects always carry an explicit
`MapPosition{partX, partY}` even for single-part levels, see `Level.cpp:1743`) or
`PLO_BOARDMODIFY`, depending on client version (see
[Version-Gated Behavior](version-gated-behavior.md#board-changes-two-different-code-paths-only-one-is-live)
for the exact style/version table). This runs for **both gmap and non-gmap levels**.
`PlayerClient::sendDynamicLevelData` (`server/src/player/PlayerClient.cpp:
1523-1528`) calls it unconditionally:

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
109-135`) applies the edit to the level, then broadcasts it to **other** players only:

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
`PlayerClient.cpp:1493-1496` (mirrored at `PlayerClientOriginal.cpp:136,167`):

```cpp
// The client will get stuck on "Loading" until it gets board data.
// So, if we did not send any data, send an empty packet so the client knows it can move on.
if (!sentBoard)
    sendPacket(CString() >> (char)PLO_LEVELBOARD);
```

The payload-carrying path is unreachable dead code in `Level.cpp:503-515`: a `style == 2`
branch that batches all pending board changes into a single `PLO_LEVELBOARD` packet, but
`style` (see [Version-Gated Behavior](version-gated-behavior.md#level-entry-replay-path-sublevel-sendboardchangestoplayer-version-check-is-live))
is only ever assigned `1` or `3`, never `2`:

```cpp
// The batched board changes seem to be sent when the player enters a level that it has cached.
// TODO(refactor): The current level sending implementation doesn't easily allow us to use this right now,
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

The server sends the full 64×64 board dump in a different way. It sends `PLO_BOARDPACKET (101)`
as a raw packet (`sendRawPacket`, `Level.cpp:114-117`, `:397-400`; see
[Packet Structures](packet-structures.md#plo_boardpacket-101---full-board-8192-bytes)), not
through `PLO_LEVELBOARD` at all. The `PLO_RAWDATA (100)` wrapper in front of it exists only
when the output encryption generation is 5 or lower (gs2lib `CFileQueue.cpp:94-96`). Generation
6 sends no wrapper. Board layers above 0 follow as separate packets (`Level.cpp:120-125`,
`:403-415`).

The empty `PLO_LEVELBOARD` is not sent only for the `!sentBoard` case. The modern path also
sends one up front when the player has not finished loading (`!m_loaded`,
`PlayerClient.cpp:1448-1452`), as a client workaround. The original-protocol path sends one
when the player has already seen the level or the client's cache is current
(`PlayerClientOriginal.cpp:132-137`, `:164-168`).

## GS1 Player Commands Silently No-Op in `timeout` Handlers

The GS1 commands `freezeplayer2`, `unfreezeplayer`, and `say2` (and other player-targeted
commands built the same way, e.g. `sendpm`) resolve their target player by walking the
script *source stack* for the nearest `PLAYER`-typed source
(`GS1Visitor::findNearestScriptObjectSourceFromStack`, `server/src/scripting/gs1/GS1Visitor.cpp:
277-285`):

```cpp
// fn_freezeplayer2 (GS1Commands.cpp:1313-1321); say2 at :2138, unfreezeplayer at :3666
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
frozen forever. This was observed with our own pyReborn `game_tester` tier-3 freeze/say2
cycle, which is a local observation and not a reference citation. A plain timeout is queued
with an NPC source (`server/src/npcserver/NPCServer.cpp:182`). A script resumed from a
`sleep` restores the source stack it saved (`GS1Visitor.cpp:713-721`), so a sleep
continuation can keep its PLAYER source. The server also runs a timeout event last in an NPC's
event batch (`server/src/scripting/Script.cpp:286`, `:325-336`). Workaround: run the unfreeze/say from a player-sourced event, or route through
a flag the client watches.

## Raw-Framed Client Uploads Keep a Trailing Newline

`IPacketHandler::parsePacketsFromBundle` (`server/include/network/IPacketHandler.h:309-328`) contains a strip for
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
the built-in NPC server is loaded, which `serverside` controls and which is off in the shipped
`serveroptions.txt`; see [Server-Side Behavior](serverside-behavior.md)). Two that surprise client implementers:

- **The server refuses client NPC mutation when it owns NPCs.**
  `msgPLI_NPCPROPS` and `msgPLI_NPCDEL` immediately return without applying the
  request when `hasNPCServer()` is true
  (`server/src/player/packets/PlayerClientPackets.cpp:189-193` and
  `:783-787`). `msgPLI_PUTNPC` refuses the same way (`:754-758`). A client must treat server-owned NPC state as authoritative.

- **The handler does not relay `PLI_BOMBADD` between clients.** Without an NPC server the
  handler relays `PLO_BOMBADD` to the rest of the level part. With one, the handler hands
  the bomb to the server-side bomb engine (`level->addBombFromClient(...)`), and **it does
  not broadcast any `PLO_BOMBADD` to other clients**: other players see the explosion
  effects only via the NPC-server's own output (`msgPLI_BOMBADD`,
  `PlayerClientPackets.cpp:215-242`, and on failure the server even bounces a
  `PLO_BOMBDEL` back to the *sender*). Do not write a client test
  that expects bomb relay on a `serverside = true` server.
- **Clients cannot set `server.*` flags.** `msgPLI_FLAGSET`/`msgPLI_FLAGDEL` route
  `server.`-prefixed names to the server flag list **only** `if (!m_server->hasNPCServer())`
  (`PlayerClientPackets.cpp:659-669` and `:702-711`). With an NPC server, a client's
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
(`server/src/player/PlayerProps.cpp:423-448`, `case PlayerProp::MESSAGE`). Consequently, changing
non-empty chat to the empty string is still a change and fires the player-chat
event. Re-sending the already-empty value does not.

## Weapon Bytecode Delivery Crashes: Fixed Upstream

The login-time crashes that GS2 weapon delivery once had (`Script::getClientByteCode()` throwing
`bad_any_cast`, and `registerWeaponWithPlayer` sending an unbuilt header) are gone on
`origin/beta4`: `Script::getClientByteCode()` uses the non-throwing pointer
`std::any_cast` and returns an empty bytecode on a miss (`server/src/scripting/Script.cpp:246-256`),
and `Weapon::registerWeaponWithPlayer` was rewritten (see
[GS2 Bytecode Delivery Rule](version-gated-behavior.md#gs2-bytecode-delivery-rule)). This was
checked by reading the source, not by running a server.

## Sources of Truth

The `GServer-v2/dependencies/gs2lib/` directory in a checkout is **stale**. Git tracks nothing
under `dependencies/` at `origin/beta4` (`git ls-tree origin/beta4 dependencies/` is empty), so
it is an untracked leftover that carries its own `.git` and `.gitmodules`, and it is **not wired
into the CMake build at all**. Never cite it.

CMake `FetchContent` pulls the authoritative copy at configure time
(`server/CMakeLists.txt:267-273`):

```cmake
FetchContent_Declare(gs2lib
	GIT_REPOSITORY https://xtjoeytx@bitbucket.org/xtjoeytx/gs2lib.git
	GIT_SHALLOW    ON
	GIT_TAG        35056f83c856091eacab50853876bfa9fa6f6967
	#URL "${PROJECT_SOURCE_DIR}/../gs2lib"
)
```

pinned to commit `35056f83c856091eacab50853876bfa9fa6f6967` (bitbucket
`xtjoeytx/gs2lib`, pin updated by upstream commit 344a0252), checked out under
`GServer-v2/build/dependencies/fc/gs2lib-src/`. All
enum values, `IUtil.cpp` version tables, and `CEncryption` internals cited across this
documentation set come from that path.
