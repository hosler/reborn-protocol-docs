# RC & NC Admin Sub-Protocols

In addition to the game-client protocol, GServer-v2 uses two administrative sub-protocols
over the same TCP transport:

- **RC (Remote Control)** handles server administration: accounts, server options, flags,
  player rights, file browser, kick/warp/ban.
- **NC (NPC Control)** handles content management: NPCs, classes, weapons, level scripts.

Both sub-protocols use the G-type encoding and bundle framing. They use different **login
type bytes** and **encryption generations**.

## Login Type Byte Is a Bit Index

The first login byte is a *bit index*, sent GCHAR-encoded (`value + 32`). The server
computes `m_type = (1 << readGChar())`:

| Connection | Login byte | Resulting PLTYPE | Encryption |
|------------|-----------|------------------|------------|
| Legacy game client | 0 | `PLTYPE_CLIENT` (1<<0) | GEN_2, or GEN_3 when the version token is unknown |
| Game client 2.19–2.21, 3.0–3.01 | 4 | `PLTYPE_CLIENT2` (1<<4) | GEN_4 |
| Game client 2.22 and later | 5 | `PLTYPE_CLIENT3` (1<<5) | GEN_5 |
| Web client | 8 | `PLTYPE_WEB` (1<<8) | GEN_1 (`PlayerClient.cpp:312-315`) |
| Legacy RC | 1 | `PLTYPE_RC` (1<<1) | **GEN_2** |
| NPC-server | 2 | `PLTYPE_NPCSERVER` (1<<2) | internal connection to the server's own NPC-server (`PlayerLogin.cpp:76-77`) |
| NC | 3 | `PLTYPE_NC` (1<<3) | **GEN_2** |
| RC2 (modern) | 6 | `PLTYPE_RC2` (1<<6) | GEN_5 |

An earlier revision of this table gave the game client as login byte 0 with GEN_5. Login
byte 0 never selects GEN_5. See
[Client Versions & Encryption](versions-encryption.md#generation-selection-switch).

The GEN_2 rows for legacy RC and NC are the current source
(`GServer-v2/server/src/player/PlayerRC.cpp:146-156`,
`GServer-v2/server/src/player/PlayerNC.cpp:111-117`). The older monolithic `TPlayer`
login (`GServer-v2` `master`, `TPlayer.cpp` lines 2285-2328) selects
**GEN_3** for `PLTYPE_RC`, `PLTYPE_NC` and `PLTYPE_NPCSERVER`. NC sends no key byte in
either version.

An unknown login type has two halves, one in each layer:

1. **Dispatch rejects it.** `PlayerLogin::msgLoginPacket` computes `1 << readGChar()`
   and creates a player only for `PLTYPE_ANYCLIENT` (CLIENT, CLIENT2, CLIENT3, WEB),
   `PLTYPE_ANYRC` (RC, RC2), `PLTYPE_ANYNC` or `PLTYPE_NPCSERVER`. Any other byte, including 7
   (`PLTYPE_EXTERNAL`, which belongs to no class), logs "New login, but unknown player type"
   and returns `Failed`, which disconnects. No player is created and nothing is
   sent back (`PlayerLogin.cpp:62-82`, `PlayerLogin.cpp:51-58`).
2. **The per-class generation switch picks a cipher from the byte.** Each handler has a
   `default:` arm: `PlayerRC.cpp:152-154` (shared with `PLTYPE_RC2`, GEN_5),
   `PlayerNC.cpp:113-114` (shared with `PLTYPE_NC`, GEN_2) and `PlayerClient.cpp:308-311`
   (shared with `PLTYPE_CLIENT3`, GEN_5). Dispatch has already filtered the byte
   by then, so the only value that reaches each `default:` is the case it shares. An unknown byte never gets
   a default cipher in practice.

pyReborn's `RCClient` sends type **6** (RC2 → GEN_5). `NCClient` sends type **3**
(NC → GEN_2).

## NC Login: ENCRYPT_GEN_2

Many implementations use the wrong format for this part. NC negotiates
**ENCRYPT_GEN_2**. This wire format differs from the client's GEN_5 format:

- **Framing**: `[uint16 big-endian length][zlib bundle]`. The zlib bundle holds one or more
  `\n`-terminated `[id+32][body]` packets.
- **No per-packet encryption**: GEN_2's encrypt/decrypt is a no-op.
- **No compression-type byte**: there is no `0x02/0x04/0x06` prefix. The whole bundle is
  always zlib.
- **The login packet OMITS the encryption-key byte.** The server reads the key byte only
  when `gen > ENCRYPT_GEN_3`. GEN_2 < GEN_3, so the server skips it. The NC login body is:
  `gchar(type=3)` + 8-byte version + `gchar(len)+account` + `gchar(len)+password` + identity
  string (**no key byte**).
- NC logins never receive `PLO_PLAYERPROPS`. The first server packet is
  `PLO_SIGNATURE (25)`, a `gchar(73)` body (`Player.cpp:746`). A client should latch
  "authenticated" on the first packet received. See [NC login sequence](#nc-login-sequence).
- NC login, like RC login, is gated on the account being in the `staff` config list
  **and** matching `adminIpRange`: `Player::sendLogin` rejects when
  `!isStaff() || !isAdminIp()` (`GServer-v2/server/src/player/Player.cpp:685-695`).
  `PLPERM_NPCCONTROL` does **not** gate the connection. That right decides only
  whether an RC session is auto-offered the NPC-server address
  (`server/src/npcserver/NPCServer.cpp:125`) and whether an already-connected NC session is killed when
  the right is revoked (`server/src/player/packets/PlayerRCPackets.cpp:913-918`). An account holding the
  right but absent from `staff` is still rejected.

RC2, by contrast, stays on **GEN_5** (with the per-packet key byte and compression-type
byte, exactly like a game client).

## Text-Escaping Schemes (Don't Confuse Them)

| Scheme | Mechanism |
|--------|-----------|
| `\xa7` (0xA7) substitution | newline ⇄ `\xa7`: weapon **code** (RC/NC weapon add/get), admin-message header/body separator |
| **gtokenize / guntokenize** (gs2lib `CString.cpp:1204`, `:1251`) | one source line per comma token, complex lines quoted with doubled `"`/`\` |
| **quoted-CSV** (`string::toCSV` / `string::fromCSV`, `server/include/utilities/StringUtils.h:975-1046`) | comma-separated, each element optionally quoted |

Which packets use which is **not** symmetric. Per packet, at `origin/beta4`:

| Packet | Scheme |
|--------|--------|
| PLI_RC_SERVEROPTIONSSET (52) | `guntokenizeI()` (`PlayerRCPackets.cpp:81`) |
| PLO_RC_SERVEROPTIONSGET (76), PLO_RC_FOLDERCONFIGGET (77) | `string::toCSV` (`PlayerRCPackets.cpp:51`, `:144`) |
| PLI_RC_FOLDERCONFIGSET (54), PLI_RC_PLAYERRIGHTSSET (84) folders | `string::fromCSV` (`PlayerRCPackets.cpp:168`, `:889`) |
| PLO_RC_PLAYERRIGHTSGET (62) folders, PLO_RC_FILEBROWSER_DIRLIST (65) | `string::toCSV` (`PlayerRCPackets.cpp:827`, `:1095`) |
| PLI_NC_NPCSCRIPTSET (109) | `guntokenize()`, the only script upload that does (`PlayerNCPackets.cpp:219`) |
| PLI_NC_CLASSADD (113), PLI_NC_NPCADD (111), PLI_NC_NPCFLAGSSET (110) | `string::fromCSV` (`PlayerNCPackets.cpp:470`, `:371`, `:256`) |
| PLO_NC_NPCATTRIBUTES (157), PLO_NC_NPCSCRIPT (160), PLO_NC_NPCFLAGS (161), PLO_NC_CLASSGET (162) | `string::toCSV` (`PlayerNCPackets.cpp:57`, `:126`, `:204`, `:452`) |
| PLO_NC_LEVELDUMP (164), PLO_NC_LEVELLIST (80) | `gtokenize()` (`PlayerNCPackets.cpp:553`, `:735`) |

NPC ids are **GINT3** (3 bytes) throughout both sub-protocols.

---

## RC Packet Reference

### RC — PLI (client → server)

| Name | ID | Wire body |
|------|----|-----------|
| PLI_RC_SERVEROPTIONSGET | 51 | *(empty)* |
| PLI_RC_SERVEROPTIONSSET | 52 | quoted-CSV options blob |
| PLI_RC_FOLDERCONFIGGET | 53 | *(empty)* |
| PLI_RC_FOLDERCONFIGSET | 54 | quoted-CSV folders blob |
| PLI_RC_DISCONNECTPLAYER | 61 | `gshort(playerId)` [+ raw reason] |
| PLI_RC_UPDATELEVELS | 62 | `gshort(count)` then ×count `gchar(len)+levelName` |
| PLI_RC_ADMINMESSAGE | 63 | raw message |
| PLI_RC_PRIVADMINMESSAGE | 64 | `gshort(playerId)` + raw message |
| PLI_RC_SERVERFLAGSGET | 68 | *(empty)* |
| PLI_RC_SERVERFLAGSSET | 69 | `gshort(count)` then ×count `gchar(len)+flag[=value]` |
| PLI_RC_ACCOUNTADD | 70 | `gchar(len)+acc` + `gchar(len)+pass` + `gchar(len)+email` + `gchar(banned)` + `gchar(loadOnly)` + `gchar(adminlvl)` + `gchar(len)+adminWorlds` + `gchar(len)+banReason`, all read unconditionally; pass, adminlvl and adminWorlds are discarded, banned and banReason apply only with `PLPERM_BAN` (`PlayerRCPackets.cpp:412-429`) |
| PLI_RC_ACCOUNTDEL | 71 | raw account |
| PLI_RC_ACCOUNTLISTGET | 72 | `gchar(len)+nameMask` + `gchar(len)+conditions` (empty → `*`) |
| PLI_RC_RESPAWNSET / HORSELIFESET / APINCREMENTSET / BADDYRESPAWNSET | 55-58 | deprecated no-ops (`PlayerRCPackets.cpp:176-198`) |
| PLI_RC_PLAYERPROPSGET | 59 | deprecated no-op (`PlayerRCPackets.cpp:200-204`) |
| PLI_RC_PLAYERPROPSSET | 60 | `gshort(playerId)` + player props (`PlayerRCPackets.cpp:206-231`) |
| PLI_RC_LISTRCS / DISCONNECTRC / APPLYREASON | 65-67 | deprecated, ignored |
| PLI_RC_PLAYERPROPSGET2 | 73 | `gshort(playerId)` |
| PLI_RC_PLAYERPROPSGET3 | 74 | `gchar(len)+account` |
| PLI_RC_PLAYERPROPSRESET | 75 | raw account; resets the account and boots the player (`PlayerRCPackets.cpp:556-613`) |
| PLI_RC_PLAYERPROPSSET2 | 76 | `gchar(len)+account` + player props (`PlayerRCPackets.cpp:615-654`) |
| PLI_RC_ACCOUNTGET | 77 | raw account |
| PLI_RC_ACCOUNTSET | 78 | `gchar(len)+acc` + `gchar(len)+pass` + `gchar(len)+email` + `gchar(banned)` + `gchar(loadOnly)` + `gchar(adminlvl)` + `gchar(len)+world` + `gchar(len)+banReason` |
| PLI_RC_CHAT | 79 | raw message |
| PLI_RC_WARPPLAYER | 82 | `gshort(playerId)` + `gchar(x*2)` + `gchar(y*2)` + raw level (half-tile coords) |
| PLI_RC_PLAYERRIGHTSGET | 83 | raw account |
| PLI_RC_PLAYERRIGHTSSET | 84 | `gchar(len)+acc` + `gint5(adminRights)` + `gchar(len)+adminIp` + `gshort_len(foldersCSV)` |
| PLI_RC_PLAYERCOMMENTSGET | 85 | raw account |
| PLI_RC_PLAYERCOMMENTSSET | 86 | `gchar(len)+acc` + raw comments |
| PLI_RC_PLAYERBANGET | 87 | raw account |
| PLI_RC_PLAYERBANSET | 88 | `gchar(len)+acc` + `gchar(banned 0/1)` + raw reason |
| PLI_RC_FILEBROWSER_START | 89 | *(empty)* |
| PLI_RC_FILEBROWSER_CD | 90 | raw folder |
| PLI_RC_FILEBROWSER_END | 91 | *(empty)* |
| PLI_RC_FILEBROWSER_DOWN | 92 | raw filename |
| PLI_RC_FILEBROWSER_UP | 93 | `gchar(len)+filename` + raw file data |
| PLI_RC_FILEBROWSER_MOVE | 96 | `gchar(len)+destDir` + raw filename |
| PLI_RC_FILEBROWSER_DELETE | 97 | raw filename |
| PLI_RC_FILEBROWSER_RENAME | 98 | `gchar(len)+oldName` + `gchar(len)+newName` |
| PLI_RC_LARGEFILESTART / LARGEFILEEND | 155 / 156 | raw filename; the upload data arrives between them (`PlayerRCPackets.cpp:1523-1565`) |
| PLI_RC_FOLDERDELETE | 160 | raw folder path (`PlayerRCPackets.cpp:1567`) |
| PLI_NPCSERVERQUERY | 94 | `gshort(playerId)` + raw message. Only `"location"` is handled: it replies with `PLO_NPCSERVERADDR`. Anything else is logged. Ignored when the server has no NPC-server (`PlayerRCPackets.cpp:1590-1604`) |

### RC — PLO (server → client)

| Name | ID | Wire body |
|------|----|-----------|
| PLO_RC_ADMINMESSAGE | 35 | `"Admin <acct>:"` + `\xa7` + message (note the colon) |
| PLO_ADDPLAYER | 55 | `gshort(id)` + `gstring(account)` + raw prop tail |
| PLO_DELPLAYER | 56 | `gshort(id)` |
| PLO_RC_SERVERFLAGSGET | 61 | `gshort(count)` then ×count `gstring(flag)` |
| PLO_RC_PLAYERRIGHTSGET | 62 | `gstring(account)` + `gint5(adminRights)` + `gstring(adminIp)` + `gshort_len(foldersCSV)` |
| PLO_RC_PLAYERCOMMENTSGET | 63 | `gstring(account)` + raw comments |
| PLO_RC_PLAYERBANGET | 64 | `gstring(account)` + `gchar(banned 0/1)` + raw reason |
| PLO_RC_FILEBROWSER_DIRLIST | 65 | quoted-CSV of folder paths |
| PLO_RC_FILEBROWSER_DIR | 66 | `gstring(folder)` + repeated `space + gchar(entryLen) + [gchar(len)+name][gchar(len)+rights][gint5 size][gint5 modtime]` |
| PLO_RC_FILEBROWSER_MESSAGE | 67 | raw status text |
| PLO_RC_ACCOUNTLISTGET | 70 | repeated `gstring(accountName)` to end |
| PLO_RC_PLAYERPROPSGET | 72 | `gshort(playerId)` + `getPropsForRCPacket()` blob (below) |
| PLO_RC_ACCOUNTGET | 73 | `gstring(name)` + `gstring(password=empty)` + `gstring(email)` + `gchar(banned)` + `gchar(loadOnly)` + `gchar(adminLevel)` + `gstring(adminWorlds)` + `gstring(banLength)` + `gstring(banReason)`; adminLevel is hardcoded 0 and adminWorlds is hardcoded `"main"` (`PlayerRCPackets.cpp:681-689`) |
| PLO_RC_CHAT | 74 | raw chat/status string |
| PLO_RC_SERVEROPTIONSGET | 76 | quoted-CSV of serveroptions.txt lines |
| PLO_RC_FOLDERCONFIGGET | 77 | quoted-CSV of foldersconfig.txt lines |
| PLO_NPCSERVERADDR | 79 | `gshort(npcServerPlayerId)` + raw `"ip,port"`. The ip is the RC's own address when that equals the server's local ip, else the NPC-server host (`ns_ip`, or the list server's address for the server when `ns_ip` is `auto`; `NPCServer.cpp:65-68`). Sent only to an RC holding `PLPERM_NPCCONTROL` (`NPCServer.cpp:122-134`) |
| PLO_RC_MAXUPLOADFILESIZE | 103 | `gint5` upload-size limit in bytes |

### `getPropsForRCPacket()` blob (inside PLO_RC_PLAYERPROPSGET, after `gshort(id)`)

1. `gchar(len) + account name`
2. `gchar(4) + "main"` (world name, hardcoded)
3. `gstring(propsBlob)`: `gchar(len)` then a standard player-props packet
4. `gshort(flagCount)` then ×count `gchar(len)+flag`
5. `gshort(chestCount)` then ×count `gchar(level.len + 2) + gchar(chestX) + gchar(chestY) + levelName`
6. `gchar(weaponCount)` then ×count `gchar(len)+weaponName`

### RC login sequence (server → client, in order)

`PLO_SIGNATURE (25)` (`gchar(73)`) → `PLO_NEWWORLDMODE` or `PLO_KINGDOMSMODE` (only on
those server modes; `Player.cpp:744-752`) → `PLO_RESETCLIENT (194)` → `PLO_RC_CHAT (74)` motd lines → server-list-connected →
"New RC" broadcast → `PLO_STAFFGUILDS (47)` → `PLO_STATUSLIST (180)` →
`PLO_RC_MAXUPLOADFILESIZE (103)` → player-prop exchange for everyone online →
"Currently online" chat.

`PLO_NPCSERVERADDR (79)` is **not** part of this sequence. `PlayerRC::sendLogin`
never calls `sendNCLoginToPlayer`. To get the address, the client sends
`PLI_NPCSERVERQUERY` with message `"location"` and receives the reply
(`PlayerRCPackets.cpp:1590-1602`). The server also pushes it unsolicited to every RC
after `PLI_RC_SERVEROPTIONSSET` (`PlayerRCPackets.cpp:127`) and after a rights change that
grants `PLPERM_NPCCONTROL` to a connected RC (`PlayerRCPackets.cpp:922`). Revoking it
disconnects that account's NC session instead (`:913-918`). A client that waits for it at login waits forever.

### PLPERM rights bits and per-packet gating

`adminRights` is a bit mask (`server/include/Account.h:29-48`):

| Bit | Name | Bit | Name |
|-----|------|-----|------|
| 0x00001 | WARPTO | 0x04000 | MODIFYSTAFFACCOUNT |
| 0x00002 | WARPTOPLAYER | 0x08000 | SETSERVERFLAGS |
| 0x00004 | SUMMON | 0x10000 | SETSERVEROPTIONS |
| 0x00008 | UPDATELEVEL | 0x20000 | SETFOLDEROPTIONS |
| 0x00010 | DISCONNECT | 0x40000 | SETFOLDERRIGHTS (never checked) |
| 0x00020 | VIEWATTRIBUTES | 0x80000 | NPCCONTROL |
| 0x00040 | SETATTRIBUTES | 0x00080 | SETSELFATTRIBUTES |
| 0x00100 | RESETATTRIBUTES | 0x00200 | ADMINMSG |
| 0x00400 | SETRIGHTS | 0x00800 | BAN |
| 0x01000 | SETCOMMENTS | 0x02000 | INVISIBLE (never checked) |

Every RC handler below also rejects a connection that is not RC (`isClient()`). Gates, in
`PlayerRCPackets.cpp`: SETSERVEROPTIONS `:63`, SETFOLDEROPTIONS `:153`, DISCONNECT `:238`,
UPDATELEVEL `:266`, ADMINMSG `:285` and `:298`, SETSERVERFLAGS `:356`,
MODIFYSTAFFACCOUNT (account add, delete and set) `:405`, `:439`, `:702`, BAN
`:425` (inside ACCOUNTADD), `:732`, `:1040`, VIEWATTRIBUTES `:517`, `:545`,
RESETATTRIBUTES `:562`, SETATTRIBUTES (another player) or SETSELFATTRIBUTES (self) `:213`, `:632`,
WARPTOPLAYER `:783`, SETRIGHTS (view another account's rights, and set) `:807`, `:842`,
SETCOMMENTS `:972`. WARPTO and SUMMON gate the in-game chat commands instead
(`server/src/player/PlayerClient.cpp:961`, `:980`). NPCCONTROL gates the NPC-server address only.

Rights-set rules (`PLI_RC_PLAYERRIGHTSSET`, `PlayerRCPackets.cpp:861-880`): an RC without
MODIFYSTAFFACCOUNT cannot grant bits 0-19 that it lacks itself, and nobody can strip their own
MODIFYSTAFFACCOUNT or SETRIGHTS. An RC without MODIFYSTAFFACCOUNT cannot change the
admin-only server options (`AdminServerOptions`, `server/include/player/PlayerRC.h:27-34`;
`PlayerRCPackets.cpp:84-105`).

NC handlers check only `isNC()`. The source marks the missing rights check with
`TODO(permissions)` (`server/src/player/packets/PlayerNCPackets.cpp:221`).

---

## NC Packet Reference

NPC ids are GINT3 everywhere.

### NC — PLI (client → server)

| Name | ID | Wire body |
|------|----|-----------|
| PLI_NC_NPCGET | 103 | empty (ping) **or** `gint3(npcId)` (request attribute dump) |
| PLI_NC_NPCDELETE | 104 | `gint3(npcId)` |
| PLI_NC_NPCRESET | 105 | `gint3(npcId)` |
| PLI_NC_NPCSCRIPTGET | 106 | `gint3(npcId)` |
| PLI_NC_NPCWARP | 107 | `gint3(npcId)` + `gchar(x*2)` + `gchar(y*2)` + raw level |
| PLI_NC_NPCFLAGSGET | 108 | `gint3(npcId)` |
| PLI_NC_NPCSCRIPTSET | 109 | `gint3(npcId)` + **gtokenized** script |
| PLI_NC_NPCFLAGSSET | 110 | `gint3(npcId)` + raw CSV `flag=value` list |
| PLI_NC_NPCADD | 111 | raw CSV `name,id,type,scripter,level,x,y` (id ≥ NPCID_GEN_MANUAL) |
| PLI_NC_CLASSEDIT | 112 | raw class name |
| PLI_NC_CLASSADD | 113 | `gchar(len)+className` + **gtokenized** script |
| PLI_NC_LOCALNPCSGET | 114 | raw level name |
| PLI_NC_WEAPONLISTGET | 115 | empty |
| PLI_NC_WEAPONGET | 116 | raw weapon name |
| PLI_NC_WEAPONADD | 117 | `gchar(len)+weapon` + `gchar(len)+image` + weapon code (`\n`→`\xa7`) |
| PLI_NC_WEAPONDELETE | 118 | raw weapon name |
| PLI_NC_CLASSDELETE | 119 | raw class name |
| PLI_NC_LEVELLISTGET | 150 | empty |

### NC — PLO (server → client)

| Name | ID | Wire body |
|------|----|-----------|
| PLO_NPCWEAPONADD | 33 | legacy weapon reply (< NCVER_2_1): `gchar(len)+name` + `gchar(0)` + `gchar(imgLen)+image` + `gchar(1)` + `gshort(scriptLen)` + script (`\n`→`\xa7`) |
| PLO_NC_LEVELLIST | 80 | gtokenized level list (parse as quoted-CSV) |
| PLO_NC_NPCATTRIBUTES | 157 | `toCSV` NPC variable dump |
| PLO_NC_NPCADD | 158 | `gint3(id)` + repeated `[gchar(propId)][gchar(len)][str]`, propId 50=NAME, 51=TYPE, 52=LEVEL. Also re-sent with only the LEVEL prop when a database NPC changes level (`NPC.cpp:221`) |
| PLO_NC_NPCDELETE | 159 | `gint3(id)` |
| PLO_NC_NPCSCRIPT | 160 | `gint3(id)` + `toCSV(script, "\n")` |
| PLO_NC_NPCFLAGS | 161 | `gint3(id)` + `toCSV(flagList)` |
| PLO_NC_CLASSGET | 162 | `gchar(len)+className` + `toCSV(script)` |
| PLO_NC_CLASSADD | 163 | raw class name |
| PLO_NC_LEVELDUMP | 164 | gtokenized multi-line level NPC var dump |
| PLO_NC_WEAPONLISTGET | 167 | repeated `gchar(len)+weaponName` (non-default weapons) |
| PLO_NC_CLASSDELETE | 188 | raw class name |
| PLO_NC_WEAPONGET | 192 | (≥ NCVER_2_1) `gchar(len)+name` + `gchar(len)+image` + script (`\n`→`\xa7`) |

### NC login sequence

After the shared `Player::sendLogin` preamble (`PLO_SIGNATURE`, see above) the server
sends, when an NPC-server exists (`PlayerNC.cpp:181-222`):

1. One `PLO_NC_NPCADD (158)` per database NPC, with only NAME, TYPE and LEVEL props.
2. One `PLO_NC_CLASSADD (163)` per class, body the raw class name.
3. One `PLO_RC_CHAT (74)` `"New NC: <account>"` for each NC already connected, and the same
   line to every other NC for this login.

PLI_NC_LEVELLISTSET (151) is defined but has no NC handler (`PlayerNC.cpp:33-51`).

> **Note on "Unhandled by 5.07+":** gs2lib `IEnums.h` flags several RC/NC PLO ids that way,
> and marks some deprecated ones "Unhandled by 6.037". gserver still emits them and
> pyReborn's RC/NC clients parse them. No reference source shows whether a stock 6.037
> client handles them (unverified).

---

## Enabling the NPC-Server

The GS2/GS1 npc-server (which makes the NC NPC/class management PLOs meaningful) needs **no
V8**: it loads when `serverside = true`. Side effect: with `serverside = true` the server
stops pushing signs/links to game clients unless `clientsidesigns = true` and
`clientsidelinks = true` are also set. See [Server-Side Behavior](serverside-behavior.md).
