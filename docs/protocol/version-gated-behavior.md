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

`server/src/object/NPC.cpp:564-567` (per-player send, `sendMoveQueueToPlayer`) and `:584-591` (level broadcast, `sendMoveQueueToLevel`):

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

Both packet forms are built whenever an NPC move queue is sent
(`NPC.cpp:555-592`, `getMoveQueuePacketData`), not on a per-tick basis, and each
recipient is selected by the predicate in `sendPacketToNearby`, so a client gets exactly one
form. The server maintains two parallel move-command queues (`queue.first`/`queue.second`)
rather than picking one packet form per NPC.

`IEnums.h` carries a maintainer comment on `PLO_MOVE` (165): `// Unhandled by 6.037. -Codr`.
Know this if you target 6.037 specifically: the server still *sends* PLO_MOVE to
pre-2.3 clients, but the comment suggests 6.037 clients (which are always >= 2.3 and thus
never receive it) do not process it if it somehow arrived.

## Projectiles: PLO_SHOOT vs PLO_SHOOT2

The player-shot form is built in the inbound handlers `server/src/player/packets/PlayerClientPackets.cpp:1364-1369`
(`msgPLI_SHOOT`) and `:1397-1402` (`msgPLI_SHOOT2`):

```cpp
const CString oldPacketBuf = CString() >> (char)PLO_SHOOT  >> (short)m_id << newPacket.constructShootV1();
const CString newPacketBuf = CString() >> (char)PLO_SHOOT2 >> (short)m_id << newPacket.constructShootV2();
m_server->sendPacketToNearby(oldPacketBuf, ..., {m_id}, [](const auto pl) { return pl->getVersion() < CLVER_5_07; });
m_server->sendPacketToNearby(newPacketBuf, ..., {m_id}, [](const auto pl) { return pl->getVersion() >= CLVER_5_07; });
```

The shooter (`{m_id}`) is excluded. An NPC-server shot (`server/src/Server.cpp:2536-2546`) uses the
same pair with `(short)0` as the id and excludes `{0}`.

- Below `CLVER_5_07` (< 5.07): `PLO_SHOOT (175)`.
- At/above `CLVER_5_07` (>= 5.07): `PLO_SHOOT2 (191)`.

`IEnums.h` comments: `PLO_SHOOT`: `// Unhandled by 6.037. -Codr`. `PLO_SHOOT2`:
`// Valid message in 5.07 and 6.037. The code it uses is unique. -Codr`. Same pattern as
PLO_MOVE: the server builds both forms for every shot and filters recipients by version, so
each client gets exactly one of them.

## Board Changes: Two Different Code Paths, Only One Is Live

There are **two separate places** where board-change version logic exists, and they disagree.
This is a real trap for anyone reading only one of them.

### Live Broadcast Path: LevelBoardChange sendToPlayersOnLevel (Version Check Is Dead)

Function reference: `LevelBoardChange::sendToPlayersOnLevel()`.

`server/src/level/LevelBoardChange.cpp:52-71`. The `CLVER_4_0211` classic/newmain split is present only as a
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
(`server/src/level/LevelBoardChange.cpp:56-57`). A client that
implements only `PLO_BOARDMODIFY2` silently drops every timed tile swap —
bridges, switches — on ordinary levels. This matches the `msgPLI_BOARDMODIFY`
split documented in [GServer Behavior](gserver-behavior.md).

`getPropsForMapNewMain()` is also commented out elsewhere in the file
(`LevelBoardChange.cpp:98-105`) and does not exist as compiled code right now. Do not
implement a client-version split here. It is not running in this server.

### Level-Entry Replay Path: SubLevel sendBoardChangesToPlayer (Version Check Is Live)

Function reference: `SubLevel::sendBoardChangesToPlayer()`.

A **different** function, `server/src/level/Level.cpp:483-530`, replays a level's accumulated board-change
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

`Level::sendBoardChangesToPlayer` (`Level.cpp:1395-1398`) just forwards to the current
sub-level unconditionally. This replay runs for **both gmap and non-gmap levels**, invoked
from `PlayerClient::sendDynamicLevelData` (`server/src/player/PlayerClient.cpp:1523-1528`), where the
`isGmap()` check gates only the *following* horse/baddy sends, not the board-change replay
itself.

## File Transfer

`server/src/player/Player.cpp:610-653`. Three separate version gates:

```cpp
if (fileData.size() > 32000)
    isBigFile = true;

// Clients before 2.14 didn't support large files.
if (isClient() && m_versionId < CLVER_2_14)
{
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
  `[GCHAR name_len][name][data][0x0A]`, vs. the `>= 2.1` form
  `[GINT5 modtime][GCHAR name_len][name][data][0x0A]` (confirmed at
  `Player.cpp:638-645`: the pre-2.1 branch sends `PLO_FILE >> (char)filename.length() << filename`
  with no `(long long)fileModTime`, the >=2.1 branch includes it). The `0x0A` is not
  version-specific. It is the framing newline that gs2lib `CFileQueue.cpp` adds to every raw
  packet when the output generation is 5 or lower (`CFileQueue.cpp:61-63`, `:96`, `:102-103`),
  so both forms end in it and it is counted inside the `PLO_RAWDATA` length. The only
  difference between the two forms is the 5-byte `modtime`.

> ⚠️ **The pre-2.1 branch does not match what was observed of the 2.05 client.** The server
> side is confirmed: below `CLVER_2_1` the server sends `PLO_FILE` as
> `[id][namelen][name][data]` without the modification time (`server/src/player/Player.cpp:638-641`
> at `origin/beta4`), and it counts the trailing newline inside the `PLO_RAWDATA` length
> (gs2lib `CFileQueue.cpp:95-103`). The client side below is reported in squirelworks'
> client-analysis notes (`protocol/file-205r2-prefix-lf.md`); it was not verified against the
> reference. A static read of the original Windows 2.05 rev 2 client reports that its
> `PLO_FILE` handler behind `PLO_RAWDATA` **always** consumes five metadata bytes, then a
> GCHAR name length, the name, and the content. With N raw bytes, the content is
> N − 7 − name_length. The handler does not drop a final `0x0A` inside the raw count. So a
> newline that the server adds inside the count becomes the last byte of the saved file.
> 2.05 sends the token `GNW03081`. The pinned gs2lib lists that token as `CLVER_2_052`
> (`IUtil.cpp:92`), directly below `CLVER_2_1` in the enum, so it does not resolve to
> `CLVER_UNKNOWN` (only older gs2lib tables lack it). `CLVER_2_052` is still below
> `CLVER_2_1`, so 2.05 gets the shorter form and, as reported, reads the wrong bytes.
> In a local lab, the server was changed to send the prefix and to keep the newline out of
> the count. The unmodified 2.05r2 client then saved three of five test files byte for byte
> (no newline, one newline, binary with a newline). The empty and two-newline cases are
> still open. Clients older than 2.05 were not checked.

### Unknown tokens get the pre-2.1 file layout

Every gate above compares `m_versionId`, and `m_versionId` comes only from the login token's
position in gs2lib's `clientVersions[]`. A token that the server allows but that is not in
the table resolves to `CLVER_UNKNOWN` (0). That is below `CLVER_2_1`, so the client gets
every pre-2.1 path: no modtime, no large-file packets, and a failure for files over 64000
bytes.

The 5.24 and 6.00 beta builds show the effect. Their tokens (`G3D15010`, `G3D03048`) are not
in the table. The client always reads `PLO_FILE` as `[GINT5 modtime][GCHAR name_len][name]`.
Given the short form, it takes the name length and the first four name characters as the
modtime, and the fifth character as the name length. For `sword1.png` it reads `d` (68) as
the length, so the "name" is `1.png` plus 63 bytes of PNG data. The client then reports that
it cannot open that file for writing. When the token is added to the table, the same server
sends the modtime form and the client saves the files normally.

So a server for 5.x and 6.x clients must have every allowed token in its version table. All
5.x and 6.x entries rank above `CLVER_2_14`. The array and the `CLVER_*` enum must stay in
step: an entry added to one and not the other shifts every later version id.

### What 5.x and 6.x clients request at login

- 5.00r7 to 6.03r7 open with `basepackage.gupd`. The client sends it as
  `PLI_VERIFYWANTSEND (47)` (`GINT5 crc32` + name) when it has a cached copy for that
  server, and as `PLI_WANTFILE (23)` when it does not. The cache is per server name: a
  5.00r7 client sent 47 on the `Login` server and 23 on the next server after the warp.
- Then `PLI_UPDATEFILE (34)` for cached images and animations, for example `idle.gani`,
  `sprites.png`, `body.png`, `head0.png` and `shield1.png`.
- Then `PLI_WANTFILE (23)` for the fonts (`arial.ttf`, `arialbd.ttf`) and for
  `tiledefs<server>.txt`.

A real 5.00r7 client, with its token in the table, saved a 541,248-byte file sent as
`68`, `84`, `102` chunks (each with modtime and name) and `69` byte for byte.

Source: Graal_analysis
[`protocol/file-transfer.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/file-transfer.md).
It has the lab captures for 5.00r7, 5.24r4, 5.30r3 and 6.03r7.

## PLPROP_COLORS Width: Two Independent Switches

There are **two separate mechanisms** here, easy to conflate into one:

1. **Wire byte count**: `PropertyColors::getColorCount()`
   (`server/include/utilities/PropertySerializers.h:793-796`):
   ```cpp
   static int getColorCount() noexcept
   {
       return isNewWorldMode() ? 8 : 5;
   }
   ```
   This drives the actual `serialize()`/`deserialize()` loop count: **5 bytes classic, 8
   bytes new-world**. `Server::isNewWorldMode()` (`server/include/Server.h:578-581`, true when the server mode is
   `NEWWORLD`) gates it, **a server-wide mode
   flag**, not a per-connection client-version check. Every player on a given server
   instance sees the same width. The server does not negotiate it per client.

2. **Value range clamp**: `PropertyColors::getMaxColorValue()` (`PropertySerializers.h:
   798-804`), a *different* setting:
   ```cpp
   size_t colorCount = CLASSICCOLORS_COUNT;
   if (isModernGeneration() && exBodyColorsEnabled())
       colorCount += HTMLCOLORS_COUNT;
   ```
   `enableexbodycolors` (`server/include/Server.h:171`, default `false`, `SettingCache<bool> enableExBodyColors`) controls
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
(`server/src/utilities/PropertySerializers.cpp:96-204`).

For the compact preset form, the server synthesizes default filenames according
to its generation (`Limits::defaultImageExtension()`, `PropertySerializers.cpp:673-677`):
only the `CLASSIC` generation uses `swordN.gif`/`shieldN.gif`. The `NEWMAIN` and `MODERN`
generations both use `swordN.png`/`shieldN.png`. A custom image with no extension also
gets `.gif` appended on `CLASSIC` servers only (`:135-139`, `:199-203`). A 1.41 client may omit
the shield image after the biased power byte, and the server tolerates that (`:192-193`). Like `COLORS`, this is server behavior,
not a value derivable solely from the connecting client's version. The property id 10
(`GANI`, `BOWIMAGE` in pre-2.x) is gated the same way: a `CLASSIC` server reads it as a bow image
(preset byte `< 10`, otherwise a custom image of length `preset - 10` with `.gif` appended
when it has no extension), and every other generation reads a GCHAR-length gani name
(`PropertySerializers.cpp:240-263`). Detailed
property layouts belong in [Packet Structures](packet-structures.md).

## Login-Time Gates in `sendLogin`

`PlayerClient::sendLogin()`, `server/src/player/PlayerClient.cpp:443-545`.

**(a) Proactive bigmap push** for `CLVER_2_31` or `CLVER_1_411` (`:478-485`):
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

**(b) Removed.** Earlier GServer-v2 versions granted a synthetic `-gr_zlib_fix` weapon to
`CLVER_2_21` through `CLVER_2_31` clients. Upstream removed it (commit 240e60ac), and
`origin/beta4` has no such grant.

**(c) `>= CLVER_2_1` gates** four separate feature packets (`:495`, `:505`, `:515`, `:530`):
```cpp
if (m_versionId >= CLVER_2_1) { /* ... PLO_BIGMAP ... */ }
if (m_versionId >= CLVER_2_1) { /* ... PLO_MINIMAP ... */ }
if (m_versionId >= CLVER_2_1) sendPacket(CString() >> (char)PLO_RPGWINDOW ...);
if (m_versionId >= CLVER_2_1) { /* ... PLO_STATUSLIST ... */ }
```
Clients below 2.1 never receive `PLO_BIGMAP`, `PLO_MINIMAP`, `PLO_RPGWINDOW`, or
`PLO_STATUSLIST` at login.

**(d) Dead: `PLO_LISTPROCESSES` for `< CLVER_6_015`** (`:538-542`). Genuinely commented out:
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

`server/src/object/Weapon.cpp:167-216`, split across two functions. The rule changed
upstream in commit 410102ec: the old single "bytecode empty or not" test is gone, and the
branches now depend on the client version as well as the server generation.

**`registerWeaponWithPlayer()`** (`:167-202`) builds `PLO_NPCWEAPONADD` with the `IMAGE` prop
and then takes one of three paths (a default weapon sends only `PLO_DEFAULTWEAPON`, `:169-173`):

```cpp
// Classic weapons.
if (m_script.getClientByteCode().empty() && player->getVersion() <= CLVER_5_07)
{
    const std::string script = getClientSideScript();
    weaponPacket >> (char)NPCProp::SCRIPT >> (short)script.length() << script;
    player->sendPacket(weaponPacket);
}
// If we have bytecode, send the weapon headers.
else if (m_server->Generation == ServerGeneration::MODERN)
{
    if (const auto classes = getJoinedClassesList(); !classes.empty())
        weaponPacket >> (char)NPCProp::CLASS >> (short)classes.length() << classes;

    // Send the weapon.
    player->sendPacket(weaponPacket);

    // Tell the client the load the script.
    if (!m_headerWithCRC.empty())
    {
        if (player->getVersion() >= CLVER_5_07)
            player->sendPacket(CString() >> (char)PLO_LOADSCRIPT << m_headerWithCRC);
        else player->sendPacket(CString() >> (char)PLO_WEAPONHASH >> (long long)m_checksum << name);
    }
}
```

- **No client bytecode and client `<= CLVER_5_07`** (`:179`): `PLO_NPCWEAPONADD` carries the
  `SCRIPT` prop with the GS1 source inline. This holds on any server generation.
- **Otherwise, on a `MODERN` server** (`:186`): `PLO_NPCWEAPONADD` carries a `CLASS` prop
  (the joined class list) only when that list is non-empty (`:188`), and is sent without a
  `SCRIPT` prop. Then, if `m_headerWithCRC` is non-empty (`:195`), the client is told to load
  the script: clients `>= CLVER_5_07` get `PLO_LOADSCRIPT (197)` carrying `m_headerWithCRC`
  (`:197-198`), older clients get `PLO_WEAPONHASH (193)` as `[GINT5 checksum][weapon name]`
  (`:199`). The bytecode itself arrives later, when the client asks for it (below).
- **Everything else sends nothing**: a non-`MODERN` server with
  a client above 5.07, or a non-`MODERN` server with bytecode, matches neither branch, so
  no `PLO_NPCWEAPONADD` is sent at all.

**`sendByteCodeToPlayer()`** (`:204-216`) is a **separate function**. Its only caller is the
`PLI_UPDATESCRIPT` handler (`server/src/player/packets/PlayerClientPackets.cpp:1495-1503`),
so the client has to ask for the payload after the announcement. It sends the compiled
payload in a raw packet, again by client version:

```cpp
if (player->getVersion() >= CLVER_5_07)
    player->sendRawPacket(CString() >> (char)PLO_WEAPONBYTECODE2 >> (short)m_header.length() << m_header << bytecodeView);
else player->sendRawPacket(CString() >> (char)PLO_WEAPONBYTECODE >> (char)name.length() << name << bytecodeView);
```

- **`>= CLVER_5_07`**: `PLO_WEAPONBYTECODE2 (140)`, `[GSHORT header_len][header CSV][bytecode]`.
- **`< CLVER_5_07`**: `PLO_WEAPONBYTECODE (132)`, `[GCHAR name_len][weapon name][bytecode]`.

So the sequence for a `MODERN` server with bytecode is `PLO_NPCWEAPONADD` (`CLASS` prop) →
`PLO_LOADSCRIPT` (>= 5.07) or `PLO_WEAPONHASH` (older) → client `PLI_UPDATESCRIPT` →
`PLO_WEAPONBYTECODE2` or `PLO_WEAPONBYTECODE`. The GS1 `SCRIPT` prop is never sent for a
bytecode-backed weapon.

Classes use the same version split in `ScriptClass::getClassPacket`
(`server/src/scripting/ScriptClass.cpp:66-81`): `>= CLVER_5_07` gets `PLO_LOADSCRIPT` as
`[GCHAR header_len][header][bytecode]`, older clients get `PLO_CLASSBYTECODE (133)` as
`[GCHAR name_len][class name][bytecode]` (the "v4" form). The `PLI_UPDATECLASS` answer for a
class the server does not have is described under the request packets below.

### Bytecode packet family

The first five packets below are covered by our own pyReborn parsers and fixtures
(`game_tester --tier5`), which is a cross-check and not the reference. The version-dependent
variants (`PLO_WEAPONBYTECODE`, `PLO_CLASSBYTECODE`, `PLO_WEAPONHASH`) are listed after the
table. Full byte layouts live in
[Packet Structures](packet-structures.md#plo_npcbytecode-131---npc-bytecode). Summary:

| Packet | ID | Direction | Payload |
|---|---|---|---|
| `PLO_NPCBYTECODE` | 131 | Server → Client | `[GINT3 npc_id][bytecode]`, streamed inside `PLO_RAWDATA`, sent right after `PLO_NPCPROPS` only when the server `Generation == MODERN` and the NPC has client bytecode, with no client-version test (`server/src/level/Level.cpp:1475-1480`; changed by upstream commit 410102ec) |
| `PLO_GANISCRIPT` | 134 | Server → Client | `[GCHAR name_len][gani_name][bytecode]`, name has no `.gani` suffix (`server/src/animation/GameAni.cpp:114-126` `getBytecodePacket`), wrapped in `PLO_RAWDATA` |
| `PLO_WEAPONBYTECODE2` | 140 | Server → Client | `[GSHORT header_len][header CSV][bytecode]` (`Weapon.cpp:204-215` `sendByteCodeToPlayer`, clients `>= CLVER_5_07` only) |
| `PLO_LOADGANI` | 195 | Server → Client | `[GCHAR name_len][gani_name][stringlist]`, stringlist e.g. `"SETBACKTO idle"` (`PlayerClientPackets.cpp:1491`) |
| `PLO_LOADSCRIPT` | 197 | Server → Client | **Two payload forms**: raw header CSV (weapon announcement, `Weapon.cpp:198`) vs `[GCHAR header_len][header CSV][bytecode]` (class bytecode, `ScriptClass.cpp:66-81`), see the packet-structures entry for disambiguation |

Three more packets exist for clients below 5.07 (ids from the pinned gs2lib `IEnums.h`):
`PLO_WEAPONBYTECODE (132)` = `[GCHAR name_len][weapon name][bytecode]` (`Weapon.cpp:214`),
`PLO_CLASSBYTECODE (133)` = `[GCHAR name_len][class name][bytecode]` (`ScriptClass.cpp:77`,
`PlayerClientPackets.cpp:1540`), and `PLO_WEAPONHASH (193)` = `[GINT5 checksum][weapon name]`
(`Weapon.cpp:199`), which prompts the client to send `PLI_UPDATESCRIPT` if its copy differs.

The client-side **request** packets: `PLI_UPDATESCRIPT (158)` = `{weapon_name}` (raw, to
end). `PLI_UPDATEGANI (157)` = `{GINT5 crc32}{gani_name}`. `PLI_UPDATECLASS (161)` =
`{GINT5 crc32}{class_name}`. Handlers are at `PlayerClientPackets.cpp:1470-1545`
(`msgPLI_UPDATEGANI/UPDATESCRIPT/UPDATECLASS`). The server sends the bytecode for `UPDATEGANI`/
`UPDATECLASS` only when the client's CRC32 differs from the current bytecode's. Send
checksum 0 to force a fresh copy. Details:

- `UPDATEGANI` silently ignores an unknown gani (`:1479-1483`). For a known gani it sends
  `PLO_LOADGANI` even when the CRC matches (`:1487-1491`).
- `UPDATECLASS` does nothing when there is no NPC server (`:1511-1512`). For a class the server
  does not have, clients `>= CLVER_5_07` get an empty `PLO_WEAPONBYTECODE2` carrying only a
  class header (`:1524-1535`, deliberately not `PLO_LOADSCRIPT`, per the code comment), and
  older clients get `PLO_CLASSBYTECODE` with just the class name (`:1540`).

The Python client parses, stores, and executes this bytecode. See
[GS2 bytecode and client runtime](../implementation/gs2-engine.md) for the
container, VM semantics, host integration, and coverage reporting.
