# Version-Gated Server Behavior

The server does not implement one protocol. It implements several protocols. The server
uses `Player::getVersion()` to select a protocol for each connection. This value is the
resolved `CLVER_*` for that client. This page lists each GServer-v2 branch for a client
version. The live source confirms each branch. The text identifies each version split that
exists only as **commented-out/dead code**. Do not implement a comment that the server does
not run.

**Sources**: `GServer-v2/server/src/object/NPC.cpp`, `Weapon.cpp`, `Server.cpp`,
`player/packets/PlayerClientPackets.cpp`, `player/PlayerClient.cpp`, `player/Player.cpp`,
`level/LevelBoardChange.cpp`, `level/Level.cpp`, `utilities/PropertySerializers.cpp`. Enum
values come from `build/dependencies/fc/gs2lib-src/include/IUtil.h` (`CLVER_*`), and the
full version table lives at [Client Versions & Encryption](versions-encryption.md).

## NPC Movement: PLO_MOVE vs PLO_MOVE2

`NPC.cpp:440-443` (per-player send) and `:460-461` (level broadcast):

```cpp
if (player->getVersion() < CLVER_2_3)
    player->sendPacket(CString() >> (char)PLO_MOVE >> (int)id << move1);
else
    player->sendPacket(CString() >> (char)PLO_MOVE2 >> (int)id << move2);
```

```cpp
m_server->sendPacketToNearby(CString() >> (char)PLO_MOVE2 >> (int)id << queue.second,
    ..., [](const Player* player) { return player->getVersion() >= CLVER_2_3; });
m_server->sendPacketToNearby(CString() >> (char)PLO_MOVE >> (int)id << queue.first,
    ..., [](const Player* player) { return player->getVersion() < CLVER_2_3; });
```

- Below `CLVER_2_3` (< 2.3): `PLO_MOVE (165)`.
- At/above `CLVER_2_3` (>= 2.3): `PLO_MOVE2 (189)`.

Both packet builders run per level tick, filtered by version via `sendPacketToNearby`'s
predicate. The server maintains two parallel move-command queues (`queue.first`/
`queue.second`) rather than picking one packet form per NPC.

`IEnums.h` carries a maintainer comment on `PLO_MOVE` (165): `// Unhandled by 6.037. -Codr`.
Know this if you target 6.037 specifically: the server still *sends* PLO_MOVE to
pre-2.3 clients, but the comment suggests 6.037 clients (which are always >= 2.3 and thus
never receive it) do not process it if it somehow arrived.

## Projectiles: PLO_SHOOT vs PLO_SHOOT2

`Server.cpp:2283-2292`, mirrored in the inbound handlers `PlayerClientPackets.cpp:1361`
(`msgPLI_SHOOT`) and `:1392` (`msgPLI_SHOOT2`):

```cpp
CString oldPacketBuf = CString() >> (char)PLO_SHOOT  >> (short)m_id << newPacket.constructShootV1();
CString newPacketBuf = CString() >> (char)PLO_SHOOT2 >> (short)m_id << newPacket.constructShootV2();
m_server->sendPacketToNearby(oldPacketBuf, ..., [](const auto pl) { return pl->getVersion() < CLVER_5_07; });
m_server->sendPacketToNearby(newPacketBuf, ..., [](const auto pl) { return pl->getVersion() >= CLVER_5_07; });
```

- Below `CLVER_5_07` (< 5.07): `PLO_SHOOT (175)`.
- At/above `CLVER_5_07` (>= 5.07): `PLO_SHOOT2 (191)`.

`IEnums.h` comments: `PLO_SHOOT`: `// Unhandled by 6.037. -Codr`. `PLO_SHOOT2`:
`// Valid message in 5.07 and 6.037. The code it uses is unique. -Codr`. Same pattern as
PLO_MOVE: the server still constructs and sends both forms every tick regardless of whether
any connected client is old enough to need the legacy one.

## Board Changes: Two Different Code Paths, Only One Is Live

There are **two separate places** where board-change version logic exists, and they disagree.
This is a real trap for anyone reading only one of them.

### Live Broadcast Path: LevelBoardChange sendToPlayersOnLevel (Version Check Is Dead)

Function reference: `LevelBoardChange::sendToPlayersOnLevel()`.

`LevelBoardChange.cpp:51-70`. The `CLVER_4_0211` classic/newmain split is present only as a
**commented-out block**:

```cpp
void LevelBoardChange::sendToPlayersOnLevel() const
{
    // ...
    else
    {
        m_server->sendPacketToNearby(CString() >> (char)PLO_BOARDMODIFY2 << getPropsForMapClassic(),
            toPixelPosition(m_mapPosition.value(), area.position), level, {});

        /*
        // Classic mode clients don't support board updates in adjacent levels, but still need the map position.
        server->sendPacketToOneLevel(CString() >> (char)PLO_BOARDMODIFY2 << getPropsForMapClassic(),
            level, {}, [](const Player* player) { return player->getVersion() < CLVER_4_0211; });

        // Newmain and up can see nearby level board changes.
        server->sendPacketToNearby(CString() >> (char)PLO_BOARDMODIFY2 << getPropsForMapNewMain(),
            toPixelPosition(this->area.position), level, {}, [](const Player* player) { return player->getVersion() >= CLVER_4_0211; });
        */
    }
}
```

The `// ...` above elides the **non-gmap branch, which sends a different
packet**. The full function is:

```cpp
if (!level->isGmap())
    m_server->sendPacketToOneLevelPart(
        CString() >> (char)PLO_BOARDMODIFY << getPropsForSingleLevel(), {0, 0}, level);
else
{
    // the PLO_BOARDMODIFY2 branch quoted above
}
```

**Current live behavior, by level kind:**

| Level kind | Packet | Payload builder | Delivery |
|---|---|---|---|
| non-gmap | `PLO_BOARDMODIFY` | `getPropsForSingleLevel()` | `sendPacketToOneLevelPart` |
| gmap | `PLO_BOARDMODIFY2` | `getPropsForMapClassic()` | `sendPacketToNearby` |

Client version does not enter into either branch
(`GServer-v2/server/src/level/LevelBoardChange.cpp:51-58`). A client that
implements only `PLO_BOARDMODIFY2` silently drops every timed tile swap —
bridges, switches — on ordinary levels. This matches the `msgPLI_BOARDMODIFY`
split documented in [GServer Behavior](gserver-behavior.md).

`getPropsForMapNewMain()` is also commented out elsewhere in the file
(`LevelBoardChange.cpp:97-104`) and does not exist as compiled code right now. Do not
implement a client-version split here. It is not running in this server.

### Level-Entry Replay Path: SubLevel sendBoardChangesToPlayer (Version Check Is Live)

Function reference: `SubLevel::sendBoardChangesToPlayer()`.

A **different** function, `Level.cpp:481-526`, replays a level's accumulated board-change
history to a player who (re)enters it. This one's version branching is live:

```cpp
int style = 1;
if (player->getVersion() < CLVER_2_1)
    style = 3;
else if (player->getVersion() < CLVER_4_0211)
    style = mapPosition.has_value() ? 1 : 3; // 2;

for (const auto& change : boardChanges)
{
    if (style == 1)
        player->sendPacket(CString() >> (char)PLO_BOARDMODIFY2 << change.getPropsForMapClassic());
    else if (style == 3)
        player->sendPacket(CString() >> (char)PLO_BOARDMODIFY << change.getPropsForSingleLevel());
}
```

- `< CLVER_2_1`: style 3, `PLO_BOARDMODIFY (7)` per change (`getPropsForSingleLevel()`).
- `CLVER_2_1` to `< CLVER_4_0211`: style 1 if the level has a map position (is part of a
  gmap), else style 3.
- `>= CLVER_4_0211` (default `style = 1`): `PLO_BOARDMODIFY2 (186)` per change
  (`getPropsForMapClassic()`).
- Style `2` (a batched, single `PLO_LEVELBOARD (0)` packet carrying all changes) exists in
  the source, but the server never assigns it. See the dead-code note in
  [GServer Behavior Reference](gserver-behavior.md#plo_levelboard-0-is-effectively-dead-code).

`Level::sendBoardChangesToPlayer` (`Level.cpp:1290-1294`) just forwards to the current
sub-level unconditionally. This replay runs for **both gmap and non-gmap levels**, invoked
from `PlayerClient::sendDynamicLevelData` (`PlayerClient.cpp:1492-1497`), where the
`isGmap()` check gates only the *following* horse/baddy sends, not the board-change replay
itself.

## File Transfer

`Player.cpp:556-600`. Three separate version gates:

```cpp
if (fileData.size() > 32000)
    isBigFile = true;

// Clients before 2.14 didn't support large files.
if (isClient() && m_versionId < CLVER_2_14)
{
    if (m_versionId < CLVER_2_1) packetLength -= 5; // modTime isn't sent.
    if (fileData.size() > 64000)
        return sendFailure("File too large for client version");
    isBigFile = false;
}
```

- **Big-file threshold**: files **> 32000 bytes** use the `PLO_LARGEFILESTART` /
  `PLO_LARGEFILESIZE` / `PLO_FILE`-chunks / `PLO_LARGEFILEEND` sequence (see
  [Packet Structures](packet-structures.md#plo_largefilestart-68---large-file-start)).
- **`< CLVER_2_14`**: no large-file support at all. The server forces `isBigFile` false and
  **rejects files > 64000 bytes outright** (`sendFailure`).
- **`< CLVER_2_1`**: `PLO_FILE (102)` omits the 5-byte `modtime` field: shorter form,
  `[GCHAR name_len][name][data]`, no trailing newline, vs. the `>= 2.1` form
  `[GINT5 modtime][GCHAR name_len][name][data][0x0A]` (confirmed at
  `Player.cpp:584-594`: the pre-2.1 branch sends plain `PLO_FILE >> filename` with no
  `(long long)modTime`, the >=2.1 branch includes it).

## PLPROP_COLORS Width: Two Independent Switches

There are **two separate mechanisms** here, easy to conflate into one:

1. **Wire byte count**: `PropertyColors::getColorCount()`
   (`utilities/PropertySerializers.cpp:709-713`):
   ```cpp
   int PropertyColors::getColorCount() const noexcept
   {
       auto server = BabyDI::Get<Server>();
       return server->isNewWorldMode() ? 8 : 5;
   }
   ```
   This drives the actual `serialize()`/`deserialize()` loop count: **5 bytes classic, 8
   bytes new-world**. `Server::isNewWorldMode()` gates it, **a server-wide mode
   flag**, not a per-connection client-version check. Every player on a given server
   instance sees the same width. The server does not negotiate it per client.

2. **Value range clamp**: `PropertyColors::getMaxColorValue()` (`PropertySerializers.cpp:
   715-722`), a *different* setting:
   ```cpp
   size_t colorCount = CLASSICCOLORS_COUNT;
   if (server->Generation == ServerGeneration::MODERN && server->cached.enableExBodyColors.getValue())
       colorCount += HTMLCOLORS_COUNT;
   ```
   `enableexbodycolors` (`Server.h:158`, `SettingCache<bool> enableExBodyColors`) controls
   how many distinct color *values* are legal, not how many *bytes* are on the wire.

Do not gate wire-format parsing on `enableexbodycolors`. Gate it on the server's new-world
mode instead. This mode is server-wide and is not encoded in the client
handshake, so a client cannot derive the five-versus-eight-byte width from its
own version. It needs server configuration, an out-of-band session profile, or
a cautious parser policy. See [Packet Structures](packet-structures.md) for the
property stream rather than treating the handshake as a width discriminator.

## Sword and Shield Bias Forms Are Server-Generation Gates

Sword and shield properties have a compact preset form and a biased custom-image
form. Sword custom form stores `power + 30`. Shield custom form stores
`power + 10`, followed by a GUCHAR image length and image bytes
(`GServer-v2/server/src/utilities/PropertySerializers.cpp:77-164`).

For the compact preset form, the server synthesizes default filenames according
to its generation: classic mode uses `swordN.gif`/`shieldN.gif`, while modern
mode uses `swordN.png`/`shieldN.png`. Like `COLORS`, this is server behavior,
not a value derivable solely from the connecting client's version. Detailed
property layouts belong in [Packet Structures](packet-structures.md).

## Login-Time Gates in `sendLogin`

`PlayerClient::sendLogin()`, `PlayerClient.cpp:467-627`.

**(a) Proactive bigmap push** for `CLVER_2_31` or `CLVER_1_411` (`:498-507`):
```cpp
if (m_versionId == CLVER_2_31 || m_versionId == CLVER_1_411)
{
    for (const auto& map : m_server->getMapList())
    {
        if (map->isBigMap())
            msgPLI_WANTFILE(CString() << map->getMapName());
```
These two versions get every bigmap file pushed at login time, rather than requesting them
lazily like other clients.

**(b) `-gr_zlib_fix` weapon grant** for `CLVER_2_21` through `CLVER_2_31` inclusive (`:562-566`):
```cpp
if (m_versionId >= CLVER_2_21 && m_versionId <= CLVER_2_31)
{
    sendPacket(CString() >> (char)PLO_NPCWEAPONADD >> (char)12 << "-gr_zlib_fix" >> ...);
```
A synthetic client-side weapon granted automatically to paper over a zlib bug in that
version range.

**(c) `>= CLVER_2_1` gates** four separate feature packets (`:573,585,597,613`):
```cpp
if (m_versionId >= CLVER_2_1) { /* ... PLO_BIGMAP ... */ }
if (m_versionId >= CLVER_2_1) { /* ... PLO_MINIMAP ... */ }
if (m_versionId >= CLVER_2_1) sendPacket(CString() >> (char)PLO_RPGWINDOW ...);
if (m_versionId >= CLVER_2_1) { /* ... PLO_STATUSLIST ... */ }
```
Clients below 2.1 never receive `PLO_BIGMAP`, `PLO_MINIMAP`, `PLO_RPGWINDOW`, or
`PLO_STATUSLIST` at login.

**(d) Dead: `PLO_LISTPROCESSES` for `< CLVER_6_015`** (`:623-627`). Genuinely commented out:
```cpp
// Ask for processes. This causes windows v6 clients to crash
/*
if (m_versionId < CLVER_6_015)
    sendPacket(CString() >> (char)PLO_LISTPROCESSES);
*/
```
No client, of any version, currently receives `PLO_LISTPROCESSES` from `sendLogin`. The
comment explains *why* the server no longer sends it (a crash in Windows v6 clients), which is useful
context if you are ever tempted to re-enable process-list polling.

## GS2 Bytecode Delivery Rule

`Weapon.cpp:267-308`, split across two functions.

**`registerWeaponWithPlayer()`** (`:267-297`) decides GS1-source vs. bytecode-header:

```cpp
weaponPacket >> (char)PLO_NPCWEAPONADD >> (char)name.length() << name
             >> (char)NPCProp::IMAGE >> (char)image.length() << image;

// Weapons without compiled bytecode (e.g. legacy GS1 clientside scripts) must
// send their script directly, even on a MODERN server. Taking the bytecode
// branch below for such a weapon sends an unbuilt m_headerWithCRC and crashes.
if (m_script.getClientByteCode().empty())
{
    std::string script = getClientSideScript();
    weaponPacket >> (char)NPCProp::SCRIPT >> (short)script.length() << script;
    player->sendPacket(weaponPacket);
}
else
{
    auto classes = getJoinedClassesList();
    weaponPacket >> (char)NPCProp::CLASS >> (short)classes.length() << classes;
    player->sendPacket(weaponPacket);
    // Tell the client the load the script.
    player->sendPacket(CString() >> (char)PLO_LOADSCRIPT << m_headerWithCRC);
}
```

- **No compiled bytecode** (GS1-only content): `PLO_NPCWEAPONADD` includes the `SCRIPT` prop
  with the raw source inline. This is the *only* path. It runs "even on a MODERN server,"
  per the code comment, because taking the bytecode branch without built bytecode crashes.
- **Compiled bytecode exists**: `PLO_NPCWEAPONADD` includes a `CLASS` prop (not `SCRIPT`)
  listing the joined class list, followed by a separate `PLO_LOADSCRIPT (197)` packet
  carrying `m_headerWithCRC`.

**`sendByteCodeToPlayer()`** (`:299-308`) is a **separate function**, called elsewhere (not
from `registerWeaponWithPlayer`), that sends the actual compiled payload:

```cpp
void Weapon::sendByteCodeToPlayer(std::shared_ptr<Player> player) const
{
    if (const auto& bytecode = m_script.getClientByteCode(); !bytecode.empty())
    {
        // ...
        player->sendPacket(CString() >> (char)PLO_WEAPONBYTECODE2 >> (short)m_header.length() << m_header << bytecodeView);
```

So the full sequence when bytecode exists is **`PLO_NPCWEAPONADD` (with `CLASS` prop) →
`PLO_LOADSCRIPT` → `PLO_WEAPONBYTECODE2`** (the last one from a distinct call site). The
GS1 `SCRIPT` prop is never sent for bytecode-backed weapons.

### Bytecode packet family

All five packets are now byte-validated (live pyReborn parsers exercised against GServer
fixtures, `game_tester --tier5`). Full byte layouts live in
[Packet Structures](packet-structures.md#plo_npcbytecode-131---npc-bytecode). Summary:

| Packet | ID | Direction | Payload |
|---|---|---|---|
| `PLO_NPCBYTECODE` | 131 | Server → Client | `[GINT3 npc_id][bytecode]`, streamed inside `PLO_RAWDATA`, automatically for clients `>= CLVER_4_0211` with scripted NPCs (`Level.cpp:1352-1358` `sendNPCsToPlayer`) |
| `PLO_GANISCRIPT` | 134 | Server → Client | `[GCHAR name_len][gani_name][bytecode]`, name has no `.gani` suffix (`GameAni.cpp:107-122` `getBytecodePacket`), wrapped in `PLO_RAWDATA` |
| `PLO_WEAPONBYTECODE2` | 140 | Server → Client | `[GSHORT header_len][header CSV][bytecode]` (`Weapon.cpp:299-308` `sendByteCodeToPlayer`) |
| `PLO_LOADGANI` | 195 | Server → Client | `[GCHAR name_len][gani_name][stringlist]`, stringlist e.g. `"SETBACKTO idle"` (`PlayerClientPackets.cpp:1481`) |
| `PLO_LOADSCRIPT` | 197 | Server → Client | **Two payload forms**: raw header CSV (weapon announcement, `Weapon.cpp:295`) vs `[GCHAR header_len][header CSV][bytecode]` (class bytecode, `ScriptClass.cpp:66-77`), see the packet-structures entry for disambiguation |

The client-side **request** packets: `PLI_UPDATESCRIPT (158)` = `{weapon_name}` (raw, to
end). `PLI_UPDATEGANI (157)` = `{GINT5 crc32}{gani_name}`. `PLI_UPDATECLASS (161)` =
`{GINT5 crc32}{class_name}`. Handlers are at `PlayerClientPackets.cpp:1460-1533`
(`msgPLI_UPDATEGANI/UPDATESCRIPT/UPDATECLASS`). The server answers `UPDATEGANI`/
`UPDATECLASS` only when the client's CRC32 differs from the current bytecode's. Send
checksum 0 to force a fresh copy.

The Python client parses, stores, and executes this bytecode. See
[GS2 bytecode and client runtime](../implementation/gs2-engine.md) for the
container, VM semantics, host integration, and coverage reporting.
