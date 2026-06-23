# RC & NC Admin Sub-Protocols

Beyond the game client, GServer-v2 speaks two administrative sub-protocols over the same
TCP transport:

- **RC (Remote Control)** — server administration: accounts, server options, flags, player
  rights, file browser, kick/warp/ban.
- **NC (NPC Control)** — content management: NPCs, classes, weapons, level scripts.

Both reuse the G-type encoding and bundle framing, but they differ in **login type byte**
and, critically, in **encryption generation**.

## Login Type Byte Is a Bit Index

The first login byte is a *bit index*, sent GCHAR-encoded (`value + 32`). The server
computes `m_type = (1 << readGChar())`:

| Connection | Login byte | Resulting PLTYPE | Encryption |
|------------|-----------|------------------|------------|
| Game client | 0 | `PLTYPE_CLIENT` (1<<0) | GEN_5 |
| Legacy RC | 1 | `PLTYPE_RC` (1<<1) | **GEN_2** |
| NC | 3 | `PLTYPE_NC` (1<<3) | **GEN_2** |
| RC2 (modern) | 6 | `PLTYPE_RC2` (1<<6) | GEN_5 |

pyReborn's `RCClient` sends type **6** (RC2 → GEN_5); `NCClient` sends type **3**
(NC → GEN_2).

## NC Login: ENCRYPT_GEN_2

This is the part most implementations get wrong. NC negotiates **ENCRYPT_GEN_2**, which is a
different wire format than the client's GEN_5:

- **Framing**: `[uint16 big-endian length][zlib bundle]`. The zlib bundle holds one or more
  `\n`-terminated `[id+32][body]` packets.
- **No per-packet encryption** — GEN_2's encrypt/decrypt is a no-op.
- **No compression-type byte** — there is no `0x02/0x04/0x06` prefix; the whole bundle is
  always zlib.
- **The login packet OMITS the encryption-key byte.** The server reads the key byte only
  when `gen > ENCRYPT_GEN_3`; GEN_2 < GEN_3, so it is skipped. The NC login body is:
  `gchar(type=3)` + 8-byte version + `gchar(len)+account` + `gchar(len)+password` + identity
  string — **no key byte**.
- NC logins never receive `PLO_PLAYERPROPS`. The first server packet is typically
  `PLO_SIGNATURE (25)`; a client should latch "authenticated" on the first packet received.
- NC eligibility is gated server-side on the `PLPERM_NPCCONTROL` right.

RC2, by contrast, stays on **GEN_5** (with the per-packet key byte and compression-type
byte, exactly like a game client).

## Three Text-Escaping Schemes (Don't Confuse Them)

| Scheme | Where | Mechanism |
|--------|-------|-----------|
| `\xa7` (0xA7) substitution | weapon **code** (RC/NC weapon add/get); admin-message header/body separator | newline ⇄ `\xa7` |
| **gtokenize** (`CString::gtokenize`/`guntokenize`) | NPC and class **scripts** sent client→server | one source line per comma token; complex lines quoted with doubled `"`/`\` |
| **Graal quoted-CSV** (`toCSV`) | server→client lists (options, folders, rights folders, weapon/level lists, NPC var dumps) | comma-separated, each element optionally quoted |

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
| PLI_RC_ACCOUNTADD | 70 | `gchar(len)+acc` + `gchar(len)+pass` + `gchar(len)+email` (+ optional banned/onlyLoad/adminlvl gchars) |
| PLI_RC_ACCOUNTDEL | 71 | raw account |
| PLI_RC_ACCOUNTLISTGET | 72 | `gchar(len)+nameMask` + `gchar(len)+conditions` (empty → `*`) |
| PLI_RC_PLAYERPROPSGET2 | 73 | `gshort(playerId)` |
| PLI_RC_PLAYERPROPSGET3 | 74 | `gchar(len)+account` |
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

### RC — PLO (server → client)

| Name | ID | Wire body |
|------|----|-----------|
| PLO_RC_ADMINMESSAGE | 35 | `"Admin <acct>"` + `\xa7` + message |
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
| PLO_RC_ACCOUNTGET | 73 | `gstring(name)` + `gstring(password=empty)` + `gstring(email)` + `gchar(banned)` + `gchar(loadOnly)` + `gchar(adminLevel)` + `gstring(folders)` + `gstring(banLength)` + `gstring(banReason)` |
| PLO_RC_CHAT | 74 | raw chat/status string |
| PLO_RC_SERVEROPTIONSGET | 76 | quoted-CSV of serveroptions.txt lines |
| PLO_RC_FOLDERCONFIGGET | 77 | quoted-CSV of foldersconfig.txt lines |
| PLO_RC_MAXUPLOADFILESIZE | 103 | `gint5` upload-size limit in bytes |

### `getPropsForRCPacket()` blob (inside PLO_RC_PLAYERPROPSGET, after `gshort(id)`)

1. `gchar(len) + account name`
2. `gchar(4) + "main"` (world name, hardcoded)
3. `gstring(propsBlob)` — `gchar(len)` then a standard player-props packet
4. `gshort(flagCount)` then ×count `gchar(len)+flag`
5. `gshort(chestCount)` then ×count `gchar(level.len + 2) + gchar(chestX) + gchar(chestY) + levelName`
6. `gchar(weaponCount)` then ×count `gchar(len)+weaponName`

### RC login sequence (server → client, in order)

`PLO_CLEARWEAPONS (194)` → `PLO_RC_CHAT (74)` motd lines → server-list-connected →
"New RC" broadcast → `PLO_STAFFGUILDS (47)` → `PLO_STATUSLIST (180)` →
`PLO_RC_MAXUPLOADFILESIZE (103)` → player-prop exchange for everyone online →
"Currently online" chat. (If the account has `PLPERM_NPCCONTROL` and an npc-server is up,
`PLO_NPCSERVERADDR (79)` is also sent.)

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
| PLO_NC_NPCADD | 158 | `gint3(id)` + repeated `[gchar(propId)][gchar(len)][str]`; propId 50=NAME, 51=TYPE, 52=CURLEVEL |
| PLO_NC_NPCDELETE | 159 | `gint3(id)` |
| PLO_NC_NPCSCRIPT | 160 | `gint3(id)` + `toCSV(script, "\n")` |
| PLO_NC_NPCFLAGS | 161 | `gint3(id)` + `toCSV(flagList)` |
| PLO_NC_CLASSGET | 162 | `gchar(len)+className` + `toCSV(script)` |
| PLO_NC_CLASSADD | 163 | raw class name |
| PLO_NC_LEVELDUMP | 164 | gtokenized multi-line level NPC var dump |
| PLO_NC_WEAPONLISTGET | 167 | repeated `gchar(len)+weaponName` (non-default weapons) |
| PLO_NC_CLASSDELETE | 188 | raw class name |
| PLO_NC_WEAPONGET | 192 | (≥ NCVER_2_1) `gchar(len)+name` + `gchar(len)+image` + script (`\n`→`\xa7`) |

> **Note on "Unhandled by 5.07+":** several RC/NC PLO ids are flagged that way in
> `IEnums.h`. That comment refers to the stock *client*; gserver still emits them and
> pyReborn's RC/NC clients parse them. They are live on 6.037.

---

## Enabling the NPC-Server

The GS2/GS1 npc-server (which makes the NC NPC/class management PLOs meaningful) needs **no
V8**: it loads when `serverside = true`. Side effect: with `serverside = true` the server
stops pushing signs/links to game clients unless `clientsidesigns = true` and
`clientsidelinks = true` are also set. See [Server-Side Behavior](serverside-behavior.md).
