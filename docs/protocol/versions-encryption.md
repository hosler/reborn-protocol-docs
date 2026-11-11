# Client Versions & Encryption Generation

This page answers two questions: *"what version string does a given client send?"* and
*"which encryption generation does the server select?"* For the second answer, see
[The Critical Rule](#the-critical-rule-pltype-not-version-string) below.

> For the GEN_5 cipher internals (LCG, XOR, iterator start values), see
> [Encryption and Packet Processing](encryption.md). This page covers the version table,
> generation *selection*, and per-generation wire framing. It does not rederive the GEN_5
> algorithm.

**Sources**: gs2lib at the commit that GServer-v2 beta4 pins (`35056f8`,
`server/CMakeLists.txt:270`): `IUtil.h`, `IUtil.cpp`, `CEncryption.h`, `CEncryption.cpp`
and `CFileQueue.cpp`; and GServer-v2 `origin/beta4`: `server/include/network/IPacketHandler.h`,
`server/src/player/PlayerLogin.cpp`, `server/src/player/PlayerClient.cpp`,
`server/src/player/Player.cpp`. **Not** the vendored `GServer-v2/dependencies/gs2lib/` copy
or a local `build/` checkout of gs2lib: both are other revisions, and the older vendored
copy has a stale version table.

## Full Client Version Table

The `CLVER_*` enum (gs2lib `IUtil.h:152-231`) is a plain sequential enum. The header does
not assign explicit numeric values. The Id column below is the position in that enum, which
is the index into both arrays. Each entry has two independent strings. gs2lib `IUtil.cpp`
looks up both strings by array index:

- **`clientVersions[]`** (`IUtil.cpp:51-137`) is the compact identifier that the *client*
  sends on the wire as its 8-byte version field (e.g. `"GNW03014"`, `"G3D0311C"`). Wire
  identifiers are 8 characters: the 1.x server tokens are `GSERV...`, not `SERV...`. An
  empty string means the entry has no wire token, so no client can resolve to it.
- **`clientVersionString[]`** (`IUtil.cpp:164-251`) is the human-readable display version
  (e.g. `"2.22"`, `"6.037"`).

The rows follow the reference order, which is not strictly ascending by version:
`CLVER_NW_2_02` (display `NW 2.02`) sits between `CLVER_NPCSERVER` and `CLVER_1_20`.
The reference comments label the `2.05r2` display entry `CLVER_2_05`; the enum symbol is
`CLVER_2_052`.

| Id | CLVER enum | Display version | Wire identifier |
|---|---|---|---|
| 0 | `CLVER_UNKNOWN` | *(none)* | *(none)* |
| 1 | `CLVER_NPCSERVER` | (npcserver) | *(none)* |
| 2 | `CLVER_NW_2_02` | NW 2.02 | `G2N15041` |
| 3 | `CLVER_1_20` | 1.20 | *(none)* |
| 4 | `CLVER_1_21` | 1.21 | `GSERV007` |
| 5 | `CLVER_1_25` | 1.25 | `GSERV009` |
| 6 | `CLVER_1_27` | 1.27 | `GSERV011` |
| 7 | `CLVER_1_28` | 1.28 | `GSERV013` |
| 8 | `CLVER_1_30` | 1.30 | `GSERV014` |
| 9 | `CLVER_1_31` | 1.31 | `GSERV016` |
| 10 | `CLVER_1_32` | 1.32 | `GSERV018` |
| 11 | `CLVER_1_322` | 1.32r2 | *(none)* |
| 12 | `CLVER_1_323` | 1.32r3 | *(none)* |
| 13 | `CLVER_1_324` | 1.32r4 | *(none)* |
| 14 | `CLVER_1_33` | 1.33 | `GNW20020` |
| 15 | `CLVER_1_331` | 1.33r1 | *(none)* |
| 16 | `CLVER_1_34` | 1.34 | `GNW22030` |
| 17 | `CLVER_1_341` | 1.34r1 | *(none)* |
| 18 | `CLVER_1_35` | 1.35 | `GNW13040` |
| 19 | `CLVER_1_36` | 1.36 | `GNW10050` |
| 20 | `CLVER_1_37` | 1.37 | `GNW21050` |
| 21 | `CLVER_1_371` | 1.37r1 | *(none)* |
| 22 | `CLVER_1_38` | 1.38 | `GNW22060` |
| 23 | `CLVER_1_381` | 1.38r1 | `GNW02070` |
| 24 | `CLVER_1_39` | 1.39 | `GNW07080` |
| 25 | `CLVER_1_391` | 1.39r1 | `GNW12080` |
| 26 | `CLVER_1_392` | 1.39r2 | *(none)* |
| 27 | `CLVER_1_4` | 1.40 | *(none)* |
| 28 | `CLVER_1_41` | 1.41 | *(none)* |
| 29 | `CLVER_1_411` | 1.41r1 | `GNW13110` |
| 30 | `CLVER_2_0` | 2.0 | `GNW24011` |
| 31 | `CLVER_2_01` | 2.01 | `GNW23021` |
| 32 | `CLVER_2_02` | 2.02 | `GNW15041` |
| 33 | `CLVER_2_022` | 2.02r2 | `GNW20041` |
| 34 | `CLVER_2_03` | 2.03 | `GNW06051` |
| 35 | `CLVER_2_04` | 2.04 | `GNW24061` |
| 36 | `CLVER_2_052` | 2.05r2 | `GNW03081` |
| 37 | `CLVER_2_1` | 2.1 | `GNW31101` |
| 38 | `CLVER_2_12` | 2.12 | `GNW01012` |
| 39 | `CLVER_2_13` | 2.13 | `GNW23012` |
| 40 | `CLVER_2_14` | 2.14 | `GNW30042` |
| 41 | `CLVER_2_15` | 2.15 | `GNW19052` |
| 42 | `CLVER_2_151` | 2.151 | `GNW20052` |
| 43 | `CLVER_2_16` | 2.16 | `GNW12102` |
| 44 | `CLVER_2_17` | 2.17 | `GNW22122` |
| 45 | `CLVER_2_18` | 2.18 | `GNW21033` |
| 46 | `CLVER_2_19` | 2.19 | `GNW15053` |
| 47 | `CLVER_2_2` | 2.2 | `GNW28063` |
| 48 | `CLVER_2_21` | 2.21 | `GNW01113` |
| 49 | `CLVER_2_22` | 2.22 | `GNW03014` |
| 50 | `CLVER_2_3` | 2.3 | `GNW14015` |
| 51 | `CLVER_2_31` | 2.31 | `GNW28015` |
| 52 | `CLVER_3` | 3.0 | `G3D16053` |
| 53 | `CLVER_3_01` | 3.01 | `G3D27063` |
| 54 | `CLVER_3_041` | 3.041 | `G3D03014` |
| 55 | `CLVER_4_0211` | 4.0211 | `G3D28095` |
| 56 | `CLVER_4_034` | 4.034 | `G3D09125` |
| 57 | `CLVER_4_042` | 4.042 | `G3D17026` |
| 58 | `CLVER_4_110` | 4.110 | `G3D26076` |
| 59 | `CLVER_4_208` | 4.208 | `G3D20126` |
| 60 | `CLVER_5_07` | 5.07 | `G3D22067` |
| 61 | `CLVER_5_12` | 5.12 | `G3D14097` |
| 62 | `CLVER_5_31x` | 5.31x | `G3D26090` |
| 63 | `CLVER_6_015` | 6.015 | `G3D3007A` |
| 64 | `CLVER_6_034` | 6.034/6.035 | `G3D2505C` |
| 65 | `CLVER_6_037` | 6.037 | `G3D0311C` |
| 66 | `CLVER_6_037_LINUX` | 6.037 (Linux) | `G3D0511C` |
| 67 | `CLVER_IPHONE_1_1` | iPhone 1.1 | `G3D04048` |
| 68 | `CLVER_IPHONE_1_5` | iPhone 1.5 | `G3D18010` |
| 69 | `CLVER_IPHONE_1_11` | iPhone 1.11 | `G3D29090` |
| 70 | `CLVER_IPHONE_BELOTE_1_5` | iPhone Belote 1.5 | `G3D2504D` |
| 71 | `CLVER_WORLDS` | Worlds | `G3D2204D` |
| 72 | *(no enum symbol: trailing array slot, comment `NSVER_UNKNOWN`)* | [NPC-Server] | *(none)* |
| 73 | *(no enum symbol: trailing array slot, comment `NSVER_GENERIC`)* | [NPC-Server] Generic | `GRNS0000` |
| 74 | *(no enum symbol: trailing array slot, comment `NSVER_LNXMAD`)* | [NPC-Server] lnxmad | `LNX00001` |

> The reference display string of `CLVER_WORLDS` carries the old product name of the v7
> "Worlds" client. This table writes it as "Worlds". The wire token is unchanged.
>
> The three NPC-server rows are appended to the *same* `clientVersions[]`/`clientVersionString[]`
> arrays as extra trailing slots. The headers do not declare an `NSVER_*`-prefixed
> enumerator. Only the array comments (`IUtil.cpp:134-136,247-249`) provide these names.
> Do not add an `NSVER_*` enum to a new implementation. Match the string.

Lookup is a linear string scan: `getVersionID()` (`IUtil.cpp:271-281`) matches the wire
identifier against `clientVersions[]`. `getVersionString()` (`IUtil.cpp:283-306`) resolves
the display string and dispatches between the client/RC/NC arrays by `PLTYPE_*` bitmask.

### Tokens from real clients: 2.05 and the tokens the table does not list

Static reads and lab logins of original client builds, reported in squirelworks'
client-analysis notes, show the tokens below. The builds and platforms in the second column
are those observations. They are not verified against the reference. The reference side is
the pinned gs2lib `clientVersions[]` (`src/IUtil.cpp`) and the GServer-v2 beta4 login path
(`server/src/player/PlayerClient.cpp`).

| Token | Client build (observed) | Login type | Reference table | Effect on a stock server |
|---|---|---|---|---|
| `GNW03081` | 2.05 rev 2 (Windows) | 0 | Listed: `CLVER_2_052` (`IUtil.cpp:92`, display `"2.05r2"` at `:205`) | The first 8-byte read misses (the key sits before the token), so the server falls to GEN_3, rewinds and re-reads the token, which then resolves to `CLVER_2_052` (`PlayerClient.cpp:319-344`). That is below `CLVER_2_1`, so the pre-2.1 forms apply. No default generation range includes it, so the default `allowedversions.txt` rejects it |
| `G3D15010` | 5.24r3, 5.24r4, 6.00 beta2 (Windows) | 5 | Not listed | Resolves to `CLVER_UNKNOWN`. Rejected by the default allowed-versions check (below) |
| `G3D03048` | 6.00 beta1 (Windows) | 5 | Not listed | Same |
| `G3D0108A` | 6.01r1 (Linux) | 5 | Not listed | Same |
| `G3D19026` | 4.04r2 (Linux); Windows 4.04r2 sends the listed `G3D17026` (`CLVER_4_042`) | 5 | Not listed | Same |
| `G3D27076` | 4.20r6 (Mac) | 5 | Not listed | Same |
| `G3D22126` | 4.20 (Linux, both builds); Windows 4.20r8 sends the listed `G3D20126` (`CLVER_4_208`) | 5 | Not listed | Same |

The only local corroboration for any of the six unlisted tokens is weak: a third-party
login-server config, `Preagonal/graal-loginserver/config/allowedversions.txt:36`, whitelists
`G3D22126` on its own line directly after the 4.x range that ends at `G3D20126` (4.2.0.8).
It shows the token exists in the wild, not which build or platform sends it.

**Rejection, not just "unknown".** An unlisted token gives `m_versionId = CLVER_UNKNOWN`
(0) (`getVersionID`, `IUtil.cpp:271-281`; dispatched by `Player::getVersionIDByVersion`,
`Player.cpp:1742-1751`). The server then checks the id against `allowedversions.txt`:
a range entry passes only if `first <= id <= last`, a single entry only on an exact match
(`PlayerClient.cpp:384-409`). The stock file's three generation ranges are `GNW13110`
(1.41r1), `GNW03014:GNW28015` (2.22-2.31) and `G3D14097:G3D0511C` (5.12-6.037)
(`bin/servers/default/config/allowedversions.txt:3-5`), and none of them matches id 0. So a
stock server logs `Client version not allowed` and sends `PLO_DISCMESSAGE` "Your client
version is not allowed on this server." (`PlayerClient.cpp:410-415`). The login type still
sets the generation first (type 5 gives GEN_5, `PlayerClient.cpp:308-311`), and the server
logs these logins as `[New Client (2.22+)]` (`:365-367`). The `CLVER_*` gates only see
"unknown" on a server whose allowed list admits them.

So a server must list each platform's token, not one token per version number. The
following are observations from the same notes, not verified against the reference
client. The token is a constant in each build. The client does not compute it. Every
build from 3.04 to 6.03 sends login type 5, a key byte, then its token. 2.17 still sends
login type 0 and uses GEN_3, like 2.05. The server side agrees: type 5 reads the key byte,
then the token (`PlayerClient.cpp:333-344`), and the server's own log labels put type 4 at
"2.19 - 2.21, 3 - 3.01" and type 5 at "2.22+" (`:362-367`). The 3.x tokens reuse the 2.x
date stamps: 3.04 sends `G3D03014`, which the reference lists as `CLVER_3_041`
(`IUtil.cpp:111`) and whose stamp matches 2.22's `GNW03014` (`:105`). 3.153 sends
`G3D28015` (2.31's stamp, `GNW28015` at `:107`), which the reference does not list.

Source: squirelworks' client-analysis notes (`protocol/login-tokens-3x-7x.md`,
`protocol/v5v6-lab-play.md` and `protocol/client-versions.md`).

### RC versions

Separate dedicated enum `RCVER_*` (`IUtil.h:243-246`) with its own parallel arrays
(`rcVersions[]`/`rcVersionString[]`, `IUtil.cpp:153-162,261-268`). It is **not** part of the
`CLVER_*` index space:

| RCVER enum | Display version | Wire identifier |
|---|---|---|
| `RCVER_UNKNOWN` | *(none)* | *(none)* |
| `RCVER_1_010` | 1.010 | `GSERV023` |
| `RCVER_1_1` | 1.1 | `GSERV024` |
| `RCVER_2` | 2.0 | `GSERV025` |

### NC versions

Separate dedicated enum `NCVER_*` (`IUtil.h:236-238`), own arrays (`ncVersions[]`/
`ncVersionString[]`, `IUtil.cpp:145-151,253-259`):

| NCVER enum | Display version | Wire identifier |
|---|---|---|
| `NCVER_UNKNOWN` | *(none)* | *(none)* |
| `NCVER_1_1` | 1.1 | `NCL11012` |
| `NCVER_2_1` | 2.1 | `NCL21075` |

See [RC & NC Protocols](rc-nc-protocols.md) for the login-type-byte handshake that gets a
the server uses to classify a connection as an RC, NC, or game client.

## The Critical Rule: PLTYPE, Not Version String

**The PLTYPE login-type byte selects the encryption generation before the server fully
parses the version string. The resulting CLVER does not select it.** New implementations
often incorrectly treat "2.22 = GEN_5, 6.037 = GEN_5" as a version rule. Instead, each
client build sends a login type that causes this result.

### PLTYPE byte values

From `IEnums.h:344-360` (not `IUtil.h`, which has no `PLTYPE_*` symbols):

| Constant | Value | Bit |
|---|---|---|
| `PLTYPE_AWAIT` | `0x80000000` | — |
| `PLTYPE_CLIENT` | 1 | `1<<0` |
| `PLTYPE_RC` | 2 | `1<<1` |
| `PLTYPE_NPCSERVER` | 4 | `1<<2` |
| `PLTYPE_NC` | 8 | `1<<3` |
| `PLTYPE_CLIENT2` | 16 | `1<<4` |
| `PLTYPE_CLIENT3` | 32 | `1<<5` |
| `PLTYPE_RC2` | 64 | `1<<6` |
| `PLTYPE_EXTERNAL` | 128 | `1<<7` (comment: "IRC client?") |
| `PLTYPE_WEB` | 256 | `1<<8` |

The wire byte is **not** the flag value. It is the *shift amount*. Both
`PlayerLogin::msgLoginPacket` (`server/src/player/PlayerLogin.cpp:62`) and
`PlayerClient::handleLogin` (`server/src/player/PlayerClient.cpp:297`) compute:

```cpp
m_type = (1 << pPacket.readGChar());
```

So a login-type byte of `0` (GCHAR-decoded) means `PLTYPE_CLIENT`, `4` means `PLTYPE_CLIENT2`,
`5` means `PLTYPE_CLIENT3`, `8` means `PLTYPE_WEB`, etc.

### Generation selection switch

`PlayerClient::handleLogin`, `server/src/player/PlayerClient.cpp:299-316`:

```cpp
switch (m_type)
{
    case PLTYPE_CLIENT:
        Encryption.setGen(ENCRYPT_GEN_2);
        break;
    case PLTYPE_CLIENT2:                 // 2.19 - 2.21, 3 - 3.01
        Encryption.setGen(ENCRYPT_GEN_4);
        break;
    default:
    case PLTYPE_CLIENT3:                 // 2.22+
        Encryption.setGen(ENCRYPT_GEN_5);
        break;
    case PLTYPE_WEB:
        Encryption.setGen(ENCRYPT_GEN_1);
        m_fileQueue.setCodec(ENCRYPT_GEN_1, 0);
        break;
}
```

Two things happen to an unrecognised login-type byte, in this order:

1. **The generation is chosen from the type.** In this switch (`PlayerClient.cpp:300-316`)
   `default:` shares the `PLTYPE_CLIENT3` case, so a type that matches no other case falls
   into the **GEN_5** branch. The RC and NC login handlers have the same shape
   (`PlayerRC.cpp:146-156`: `default` is RC2 and gets GEN_5; `PlayerNC.cpp:111-119`:
   `default` is NC and gets GEN_2).
2. **The login handler rejects it.** Before any of those switches run, the connection's
   first packet goes through `PlayerLogin::msgLoginPacket`
   (`server/src/player/PlayerLogin.cpp:60-98`). It builds a `PlayerClient`
   (a `PlayerClientOriginal` when the type is exactly `PLTYPE_CLIENT`), `PlayerRC`,
   `PlayerNC` or `PlayerNPCServer` only when `1 << byte` falls in `PLTYPE_ANYCLIENT`,
   `PLTYPE_ANYRC`, `PLTYPE_ANYNC` or `PLTYPE_NPCSERVER`. Any other value (including
   `PLTYPE_EXTERNAL`, which is in none of those sets) logs "New login, but unknown player
   type" and returns `Failed` (`PlayerLogin.cpp:78-83`), and the connection is
   disconnected with no reply. The `default:` labels above are therefore unreachable for
   an unknown byte: the only member of `PLTYPE_ANYCLIENT` that has no case of its own is
   `PLTYPE_CLIENT3`, and the same holds for RC2 and NC.

So the observable behavior is "disconnect". An implementation should reject unknown
types instead of relying on the GEN_5 fall-through. The older monolithic `TPlayer` login
(`master`, `TPlayer.cpp` lines 2322-2327) also disconnected an unknown type, with the
message "Your client type is unknown."

| PLTYPE | Encryption gen (initial) | Client range |
|---|---|---|
| `PLTYPE_CLIENT` | GEN_2 (downgraded to GEN_3 — see below) | Legacy 1.x clients |
| `PLTYPE_CLIENT2` | GEN_4 | 2.19 – 2.21, 3.x – 3.01 |
| `PLTYPE_CLIENT3` | GEN_5 | 2.22+ (includes 6.037) |
| `PLTYPE_WEB` | GEN_1 | Web/embed clients |

### The GEN_2 → GEN_3 downgrade

The switch above always gives `PLTYPE_CLIENT` GEN_2. Immediately after the switch
(`PlayerClient.cpp:318-331`) the server reads an 8-byte version identifier and looks it up
with `getVersionID()`. If that identifier is **not** one of the tokens in `clientVersions[]`
(i.e. it resolves to `CLVER_UNKNOWN`), the server concludes that this is a 1.41-style
client that also sends an encryption key. It resets the generation to GEN_3 and resets
the packet read cursor to offset 1:

```cpp
if (m_type == PLTYPE_CLIENT)
{
    m_version = pPacket.readChars(8);
    m_versionId = getVersionID(m_version);

    // 1.41 registers itself as PLTYPE_CLIENT, but does include an encryption key.
    if (m_versionId == CLVER_UNKNOWN)
    {
        Encryption.setGen(ENCRYPT_GEN_3);
        pPacket.setRead(1);
    }
}
```

`CString::setRead(1)` sets an absolute read position (gs2lib `CString.h`: the read cursor
becomes `pRead`, clamped to the buffer). It is not a one-byte rewind. Offset 1 is the
byte just after the login-type byte, so the whole 8-byte version that was just read is
un-read. The generic "newer clients" block below (`PlayerClient.cpp:334-345`) then
re-reads from there: first the encryption-key byte, then the 8-byte version.

## Login Packet Layout

Field order as read in `handleLogin` (`PlayerClient.cpp:297-353`):

1. **Login-type byte**. The server reads a `GCHAR` and shifts it into `PLTYPE_*` as described above.
2. **(PLTYPE_CLIENT only)** 8-byte version identifier, looked up via `getVersionID()`. May
   trigger the GEN_3 downgrade and the read-cursor reset to offset 1 described above.
3. **Encryption-key byte**. The server reads it **only when `m_versionId` is still `CLVER_UNKNOWN`** at
   this point (`PlayerClient.cpp:333-341`). This covers `PLTYPE_CLIENT2`/`CLIENT3`/`WEB`
   unconditionally (they skip step 2 entirely, so `m_versionId` is still unknown), plus the
   1.41-style `PLTYPE_CLIENT` case after the reset. In other words, for game-client logins:
   **the key byte is present whenever `m_versionId` is still `CLVER_UNKNOWN`**: GEN_3, GEN_4
   and GEN_5 logins send it, and so does `PLTYPE_WEB` (GEN_1). A `PLTYPE_CLIENT` (GEN_2) login
   whose version token resolves does not send it. Sending the key byte on an unrecognized
   version string is precisely how a 1.41-style client gets *detected* as GEN_3: unknown
   8-char string at the version slot → reset to offset 1 → re-read that position as key + version.
   ```cpp
   m_encryptionKey = (unsigned char)pPacket.readGChar();
   Encryption.reset(m_encryptionKey);
   if (Encryption.getGen() > ENCRYPT_GEN_3)
       m_fileQueue.setCodec(Encryption.getGen(), m_encryptionKey);
   ```
   Don't confuse the two conditions here: the **strictly-greater** `> ENCRYPT_GEN_3` check
   (`PlayerClient.cpp:339`) gates only the *outgoing* (server → client) `m_fileQueue`
   codec — a GEN_3 client's key is used for its client → server packets, but the server's
   replies to it are plain zlib, never encrypted (see the GEN_3 row below). The NC/RC
   login paths (`PlayerNC.cpp:120`, `PlayerRC.cpp:159`) *do* use `> ENCRYPT_GEN_3` to gate
   reading the key byte itself — which coincides in practice because NC/RC gens are only
   ever GEN_2 (no key) or GEN_5 (key); no GEN_3 NC/RC clients exist.
4. **8-byte version identifier** (again, but via `getVersionIDByVersion()` this time — which
   dispatches to `getVersionID()`/`getNCVersionID()`/`getRCVersionID()` by connection type).
5. **Account name**. A 1-byte unsigned length (`GUCHAR`) precedes that number of raw chars.
6. **Password**. It uses the same length-prefixed pattern.
7. **Identity string**. `readString("")` reads to the end of the packet. The value is comma-delimited:
   `{platform},{mobile 'dc:id2'},{md5:harddisk-id},{md5:network-id},{uname release/version},{android-id}`.
   Only the platform token is actually consumed by the server.

### The login frame itself is not GEN_5

A GEN_4 or GEN_5 client sends the login packet in a frame that is plain zlib:
`[uint16 big-endian length][zlib data]`, with **no compression-type byte and no XOR**. The
key travels inside this frame, so the frame cannot be encrypted with it. The client
switches to the generation's normal framing for every frame after the login. The same
holds for RC2 (type 6). The NC socket (type 3) never leaves this plain zlib mode.

Server side, confirmed against the reference: a new connection's `CEncryption` starts at
GEN_3 (pinned gs2lib `CEncryption.cpp:26-30`), and the GEN_3 branch of
`processPacketBundle` only inflates the bundle (`IPacketHandler.h:266-269`). The first
packet goes to `parseLoginPacket`, which reads it to the newline with no decrypt step
(`IPacketHandler.h:227-235`, `:375-395`). The generation is chosen only while that login is
handled (`PlayerLogin.cpp:60-99`, `PlayerClient.cpp:297-316`). RC2 (type 6) switches to
GEN_5 (`PlayerRC.cpp:146-156`). NC (type 3) always gets GEN_2, which is zlib only and reads
no key (`PlayerNC.cpp:111-127`, `IPacketHandler.h:260-263`).

The client side comes from static reads of the 2.22 and 2.31 clients and the Delphi
RemoteControl, and lab captures of real 2.22 sessions, reported in squirelworks'
client-analysis notes (`protocol/codec-and-framing.md`, `tools/remotecontrol.md`). This is
not verified against the reference client.

## Per-Generation Wire Framing

Two layers are involved: an **outer bundle frame** (always present, gen-independent) and a
**per-generation payload transform**.

### Outer framing (all generations)

`IPacketHandler::retrievePacketBundle` (`IPacketHandler.h:239-248`) always reads a `uint16`
bundle-size prefix before any generation-specific operation, so **inbound** framing (client
to server) always has the 2-byte length prefix. It is not GEN_2-specific. The **outbound**
(server to client) side is different: GEN_1 and GEN_6 are sent raw, with no compression and
no length prefix (gs2lib `CFileQueue.cpp:162-178`; the `default:` case shares them). GEN_2
to GEN_5 are sent as `[uint16 length][payload]`.

### Payload transform — `IPacketHandler::processPacketBundle` (`IPacketHandler.h:250-307`)

| Gen | Framing |
|---|---|
| **GEN_1** | Raw. `processPacketBundle` returns immediately — no decompression, no decrypt. |
| **GEN_2** | `bundle.zuncompress2I(usedDeflate)` only (`IPacketHandler.h:260-263`). No compression-type byte, no encryption. |
| **GEN_3** | `bundle.zuncompress2I(usedDeflate)` at the **bundle** level (`IPacketHandler.h:266-269`). The single-byte-insertion decrypt runs later, **per individual packet** after the bundle is split on newlines (`parsePacketsFromBundle`, `IPacketHandler.h:332-334`): `if (gen == GEN_3) Encryption.decrypt(curPacket);` — i.e. GEN_3 "encryption" is applied once per packet, not once per bundle. |
| **GEN_4** | `Encryption.limitFromType(COMPRESS_BZ2)` then `Encryption.decrypt(bundle)` (XOR, limited to 4 four-byte blocks = 16 bytes) applied to the **whole bundle**, *then* `bundle.bzuncompressI()`. Always BZ2 — there is no compression-type byte for GEN_4. |
| **GEN_5** | Read + strip a 1-byte compression-type indicator (`0x02`/`0x04`/`0x06`) from the front of the bundle, `limitFromType(pType)` to pick the XOR block-limit, partial XOR-decrypt, then decompress per the type byte (zlib/bz2/none). |
| **GEN_6** | Declared (`ENCRYPT_GEN_6 = 5`) but **not implemented**. On receive it falls into the same `>= ENCRYPT_GEN_5` branch as GEN_5 (no dedicated case), but `CEncryption::decrypt` treats it as a no-op, so the XOR pass is silently skipped. On send the framing is **not** GEN_5-style: the outbound queue sends GEN_6 raw, with no compression, no length prefix and no per-packet newline (gs2lib `CFileQueue.cpp:162-178`, and `:62,95-103` for the newline and `PLO_RAWDATA` rules). |

The two zlib rows use `zuncompress2I`, not `zuncompressI`. `zuncompress2` retries a body
whose Adler-32 check fails as raw DEFLATE (it strips the 2-byte header; the source comment also mentions a 4-byte trailer, which the code does not remove),
a workaround for a bug in the 2.x client's zlib (gs2lib `CString.cpp:936-959`). If that
retry also fails, the call returns an empty buffer (`CString.cpp:960-976`); there is no
fallback to treating the body as raw data. The decompression buffer defaults to 65,536
bytes (gs2lib `CString.h:170-177`). On a GEN_5 zlib bundle that needed the DEFLATE retry,
the receiver then rolls the LCG iterator back one step (`IPacketHandler.h:297-301`,
gs2lib `CEncryption.h:64-65`), because the 2.x client's iterator falls one step behind.

### GEN_3's "single byte insertion", precisely

The encrypt code in gs2lib `CEncryption.cpp` (`:109-118`) inserts a **literal `)` character
(`0x29`)** at a pseudo-random offset from the LCG iterator. The decrypt code (`:54-61`)
removes one byte at that same computed offset:

```cpp
// decrypt (CEncryption.cpp:54-61)
m_iterator *= 0x8088405;
m_iterator += m_key;
int pos = ((m_iterator & 0x0FFFF) % pBuf.length());
pBuf.removeI(pos, 1);

// encrypt (CEncryption.cpp:109-116, mirror)
// ... same iterator advance ...
return CString() << pBuf.subString(0, pos) << ")" << pBuf.subString(pos);
```

**GEN_3 is direction-asymmetric.** The insertion cipher exists only on the **client →
server** direction. The server's *outgoing* GEN_3 path (gs2lib `CFileQueue.cpp:180-203`) shares
its `case` label with GEN_2. It uses zlib compression and a length prefix, and **never calls
`encrypt()`**:

```cpp
case ENCRYPT_GEN_2:
case ENCRYPT_GEN_3:
{
    pSend.zcompressI();
    // ... length prefix + send; no out_codec.encrypt() anywhere
```

So a GEN_3 *client implementation* must:

- **Sending**: per packet (without its trailing `\n`), advance the LCG once
  (`iterator = iterator*0x8088405 + key`, seed `0x04A80B38`), insert one filler byte at
  `pos = (iterator & 0xFFFF) % (len + 1)` — the modulus is over the **post-insertion**
  length because the server computes the removal offset over the length it *receives*.
  then re-append `\n`, join packets, zlib the bundle, length-prefix. The filler must not
  be `\n` because it would split the server's newline framing. Use `)` like the reference
  encryptor.
- **Receiving**: plain zlib bundles. No decryption at all.

What a real GEN_3 client does, as reported in squirelworks' client-analysis notes (Windows
2.05 rev 2 and 2.17, static read, checked on the wire in three lab 2.05 sessions with no
mismatches; not verified against the reference):

- The key is a random 7-bit value, sent once in the login line.
- The login line itself goes out clean. Insertion starts with the **second** message,
  which can be in the same first bundle (for example `PLI_LANGUAGE`).
- The inserted byte is `((iterator >> 16) & 0x7F) + 0x20`, not `)`. That is the real
  client's behaviour; the reference encryptor's filler is `)` (gs2lib
  `CEncryption.cpp:116`). The server deletes the byte without looking at it
  (`removeI`, `CEncryption.cpp:54-61`), so any value except `\n` works.
- The insertion position can be 0. In that case the filler byte comes **before the packet
  id**. A decoder must not read the id until it has removed the filler byte.
- GEN_3 uses the same LCG step as GEN_4 and GEN_5, but only once per message.

Source: squirelworks' client-analysis notes, `protocol/codec-and-framing.md` ("Gen 3 (2.05)")
and `protocol/client-versions.md`.

This exact behavior is implemented and live-verified in
`reborn-protocol/reborn_protocol/codec.py` (`Gen3Codec`). Tests probed it against GServer with a
real 1.411 login (`game_tester/version_probe.py`).

### GEN_4, both directions

Symmetric, per gs2lib `CFileQueue.cpp:205-228` (server send) and `IPacketHandler.h:272-280`
(server receive): bundle → **bz2 compress** → partial XOR with the GEN_5 LCG keystream
(iterator seed `0x4A80B38`, `limitFromType(COMPRESS_BZ2)` = 4 iterations = first **16
bytes**, limit re-armed per bundle) → `uint16` length prefix. **No compression-type byte**
in either direction. GEN_4 always uses bz2. `Gen4Codec` implements this behavior in
`reborn-protocol/reborn_protocol/codec.py` (probed with real 2.17/2.21 logins).

### XOR limits (GEN_4/GEN_5, shared implementation)

Same LCG-driven 4-byte XOR keystream as GEN_5 (see [Encryption](encryption.md) for the
detailed algorithm). The per-compression-type block limits come from gs2lib `CEncryption.cpp:156-171`
(`limitFromType`, table `{0x02,0x0C, 0x04,0x04, 0x06,0x04}` at `:159`):

| Compression type | Byte value | XOR limit (4-byte blocks) | Bytes encrypted |
|---|---|---|---|
| `COMPRESS_UNCOMPRESSED` | `0x02` | 12 | 48 |
| `COMPRESS_ZLIB` | `0x04` | 4 | 16 |
| `COMPRESS_BZ2` | `0x06` | 4 | 16 |

`ITERATOR_START = {0U, 0U, 0x04A80B38U, 0x4A80B38U, 0x4A80B38U, 0U}` (a `static constexpr std::array`, gs2lib `CEncryption.cpp:24`) —
GEN_3, GEN_4, and GEN_5 all seed the same LCG constant (the leading zero digit on GEN_3's
entry is not numerically significant).

### Production list-server GEN_5 transition

A modern list-server exchange is:

1. Connect with the reference server initially configured for GEN_2
   (`graal-serverlist/server/src/PlayerConnection.cpp:42-43`).
2. Send `PLI_V2ENCRYPTKEYCL` as a GEN_2 frame: plain zlib, no type byte.
3. The server parses the key, eight-byte version string, and client type, then
   switches both directions to GEN_5
   (`graal-serverlist/server/src/PlayerConnection.cpp:312-323`).
4. Send the credential/server-list request as GEN_5. The reference server answers
   in GEN_5 from then on. Whether the closed production list server's first response
   bundle is already GEN_5 and begins with type `0x04` is **unverified**: the reference
   code only shows that the open server switches after parsing the initialization packet.

The open list server has two sibling initialization packets besides `PLI_V2ENCRYPTKEYCL`
(`graal-serverlist/server/src/PlayerConnection.cpp:23-25`):

| Packet | Layout | Effect |
|---|---|---|
| `PLI_V2VER` (`:286-298`) | `[GUCHAR key][8-byte version]` | GEN_4 both directions, client type `Version2` |
| `PLI_V2SERVERLISTRC` (`:300-310`) | `[GCHAR key][8-byte version]` | GEN_5 both directions, client type `AllServers` |
| `PLI_V2ENCRYPTKEYCL` (`:312-325`) | `[GUCHAR key][8-byte version][client type string to end]` | GEN_5 both directions, `Version3` only for `newmain`, otherwise `AllServers` |

`PLI_V2VER` carries a source comment that nobody knows which client uses it.

Reborn retains a plain-zlib first-response fallback because an implementation
may queue output before processing the initialization packet: at connection
creation the open reference server's output queue and input codec are still
GEN_2. The recorded production session does not use this fallback. Support for
it is interoperability with the open implementation, not evidence that
production sends a GEN_2 first response.

List-server response text uses **cp1252**, whereas game-session text uses
**latin-1**. The distinction is observable for bytes such as `0x92` (a right
single quotation mark in cp1252). This is Reborn's policy, backed only by its own tests.
The reference server treats text as opaque bytes and no list-server decode step was found in
`graal-serverlist` or the reference client, so it is **unverified** against the reference.

The version field is parsed and stored but does not select the returned server
set. The client type selects it. Exactly `newmain` selects `Version3`. Every other value
selects `AllServers` (`graal-serverlist/server/src/PlayerConnection.cpp:315-322`).
`sendServerList` filters by that bucket and suppresses an `offline`-named entry
only outside `AllServers`
(`graal-serverlist/server/src/PlayerConnection.cpp:195-218`);
`AllServers` bypasses the allowed-version mask
(`graal-serverlist/server/src/ServerConnection.cpp:252-257`).

### PLI_SET_ENC_KEY (252) / PLI_BUNDLE (253): declared, unimplemented

Both packet IDs exist in `IEnums.h:163-164` (`PLI_SET_ENC_KEY` — "Set AES / RC4 encryption
key and init vector"; `PLI_BUNDLE` — "Bundled packets contain multiple packets"), suggesting
a planned GEN_6 (AES/RC4) handshake and an explicit multi-packet-bundle wrapper. Neither has
a registered handler in `Player::GeneratePacketHandlers()` or `PlayerClient::
GeneratePacketHandlers()` — both arrays default-fill to `msgPLI_NULL` (or `nullptr`,
bubbling to `Player::msgPLI_NULL`) and never register 252/253. Sending either packet to the
current server logs `"Unknown Player Packet"` and counts against the connection's
`InvalidPackets` disconnect threshold. Treat GEN_6 as unimplemented for interop purposes.

## GEN_6 on the Wire: the 6.11 Client Handshake

The master and beta4 branches do not implement GEN_6. But the Windows 6.113 and Mac 6.111
clients do speak a newer framing, as reported in squirelworks' client-analysis notes
(`protocol/v6-login-token-explained.md`, `protocol/v611-outgoing-cipher.md` and
`protocol/v6113-list-capture.md`: static reads, one capture and offline lab replays). The
per-build facts for those two builds are not verified against the reference. The packet ids
match `PLI_SET_ENC_KEY` (252) and `PLI_BUNDLE` (253), and the same ids exist as
`PLO_SET_ENC_KEY` and `PLO_BUNDLE` (pinned gs2lib `IEnums.h:163-164`, `:319-320`).
The mechanisms below are corroborated by the decompiled reference client
(`Preagonal/FourPlay/quattroplay/src/`, a v6-era mobile engine, not the 6.11 desktop
builds) and the Kotlin headless client (`Preagonal/Preagonal.Client.Headless/`).

### The connector script decides the protocol

The 6.11 desktop builds have no built-in login token (the mobile engine that the decompiled
reference client comes from does embed a compressed connector script,
`TInitStatics.cpp:635`, `TGUIScriptLoader.cpp:31-48`). Before a 6.11 desktop build connects
to a game server, it asks an HTTP connector for `conf.gs`. The reply is a 256-byte RSA-2048
signature over the bare SHA-256 digest of the payload (no `DigestInfo` wrapper), then an
encrypted GS2 script. The client checks the signature and then runs the script as
`StartScript_Connector`. The script opens the game connection and builds the login. In the
reply that was studied (one connector reply, reported in squirelworks' client-analysis
notes), the script does this:

1. `setProtocol("EILLLT")` sets the packet header template.
2. `sendRaw("GNP1905C")` sends the 8-byte token with no header.
3. It sends one framed packet that carries a 16-byte RC4 session key, encrypted with
   `rsa_encrypt` to an RSA-2048 public key in the script.
4. `setEncryptionOut` turns on RC4 for every later byte the client sends.

A different connector reply could choose a different token, template or cipher.

### The `EILLLT` header

Each letter is one header byte:

| Letter | Field |
|---|---|
| `E` | Compression: 0 raw, 1 zlib, 2 bzip2 |
| `I` | Packet counter, one byte, +1 for each packet. Inner and outer packets share it |
| `LLL` | Big-endian length of **header plus body** (6 + body length) |
| `T` | Packet id as a raw byte, **no +32** |

There is no trailing newline.

### The first packets are 252 and 253

A 6.11 stream starts with these bytes:

| Offset | Bytes | Meaning |
|---|---|---|
| 0-7 | `GNP1905C` | Token |
| 8-13 | `01 02 00 01 17 fd` | `E`=1 (zlib), `I`=2, `LLL`=279, `T`=**0xFD (253)** |
| 14-286 | zlib data | Inflates to an inner packet: `E`=0, `I`=1, `LLL`=262, `T`=**0xFC (252)**, 256-byte body |
| 287 on | RC4 ciphertext | Plain RC4, standard key schedule, no IV, headers included |

The 0xFC body is one RSA-2048 block. The best explanation is that it carries the wrapped
session key. That is `PLI_SET_ENC_KEY` ("Set AES / RC4 encryption key and init vector").
Every outer packet the client sends after this is 0xFD, wrapping one or more inner packets.
That is `PLI_BUNDLE` ("Bundled packets contain multiple packets"). So a server for stock
6.11 clients needs the private key that matches the script's public key. Without it, the
server cannot read the client stream.

### Server-to-client direction

The capture's first server packet starts `01 02 00 01 21 fd`. The reference clients decode
this direction with the same 6-byte header (`E`, `I`, `LLL` big-endian including the
header, raw `T`), and `E` = 0 raw, 1 zlib, 2 bzip2
(`TGraalConnection.cpp:1121-1141`, bzip2 through `BZ2_bzBuffToBuffDecompress` at
`TCompression.cpp:84`; headless `packet/GPacketHeader.kt:23-32`,
`compress/GCompressionTypeV6.kt:3-6`, `net/GProtocolV6.kt:42-48`):

| `T` | Body |
|---|---|
| 0xFD (`PLO_BUNDLE`) | One or more inner packets back to back, each with its own 6-byte header and its own `E` (`GProtocolV6.kt:68-79`) |
| 0xFC (`PLO_SET_ENC_KEY`) | One RSA block. Decrypted, it is `{GCHAR cipherType}{GCHAR length}{key}{GCHAR length}{iv}`, with type 1 = RC4 and 2 = AES. The cipher applies to every later byte the server sends (`TGraalConnection.cpp:459-514`, `GProtocolV6.kt:81-99`, `:28-40`) |

So the client needs an RSA private key for this direction. The headless client embeds one
(`GProtocolV6.kt:26`). The decompiled client decrypts a private key that the script sets
and RSA-decrypts with it only if one is set (`TGraalConnection.cpp:468-476`). In the
decompiled client the ids 0xFC and 0xFD are not fixed. The script assigns the handler
roles (`TClientProperties.cpp:159-178`). The headless client hard-codes them
(`packet/types/GServerToClientPacketType.kt:7-8`).

### Upstream `feature/newprotocol`

The GServer-v2 branch `feature/newprotocol` (`c3cc0d8`, January 2026) has a partial
implementation. It detects `GNP1905C` as the first 8 bytes
(`Player.cpp` line 582 on `feature/newprotocol`). On a match it switches the
input codec and the file queue to `ENCRYPT_GEN_6`, then sends every weapon as its
`CLVER_4_0211` weapon packets plus a `PLO_NPCWEAPONSCRIPT` with its bytecode
(`Player.cpp:585-596`). It writes packets as `00`, a running counter, a
3-byte length that includes the 6 header bytes, and the raw id
(`Player.cpp:973-997`). It skips the `PLO_RAWDATA` announcements. It does not parse
anything the client sends, and it has no RC4 or RSA step. The same branch answers a
`G3D2204D` (Worlds) login only with
`PLO_SERVERWARP "Offline,Offline,127.0.0.1,14915"` (`Player.cpp` lines 2713-2715 on that branch).

### v7 (Worlds) engine builds

A static read of the v7 native engine plugin (builds 548 to 614 and later) shows the same
two framing modes in one socket object. This is reported in squirelworks' client-analysis
notes (the v7 framing and packet-table note: static read only, no live session). The build
range is not verified against the reference. The decompiled reference client has the same
two modes: the `0xFFFF` length escape (`TGraalConnection.cpp:845-863`) and the script
template with field widths capped at 4 (`:1221-1266`).

- **Mode 0, classic GEN_5**, is the default before a connector script runs. Its receive
  path reads a 2-byte big-endian length. If that length is `0xFFFF`, a further 4-byte
  length follows, so the header is 6 bytes. GEN_5 as documented here has no such escape.
- **Mode 1, script template**, starts when the script calls `setprotocol`. The letters `I`,
  `L`, `T` and `E` set the offset and width (1-4 bytes) of counter, length, id and
  compression fields. The low nibble of `E` selects raw (0), zlib (1) or bzip2 (2). A
  configured "nested" id makes the parser read the body as more framed packets. That is how
  the `PLI_BUNDLE` (253) wrapper above is unpacked.
- **Counter check.** In mode 1 a counter must equal the previous counter + 1, masked to the
  counter width. The check is skipped while the stored previous value is negative. A
  mismatch is an error.
- **Ciphers.** A type byte (`GCHAR`, 1 = RC4, 2 = AES) selects the stream cipher for
  each direction. AES is CBC and pads outbound data with `0xFF` to 16 bytes. RC4 has no IV.
