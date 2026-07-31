# Client Versions & Encryption Generation

This page answers two questions: *"what version string does a given client send?"* and
*"which encryption generation does the server select?"* For the second answer, see
[The Critical Rule](#the-critical-rule-pltype-not-version-string) below.

> For the GEN_5 cipher internals (LCG, XOR, iterator start values), see
> [Encryption and Packet Processing](encryption.md). This page covers the version table,
> generation *selection*, and per-generation wire framing. It does not rederive the GEN_5
> algorithm.

**Sources**: `GServer-v2/build/dependencies/fc/gs2lib-src/{include,src}/IUtil.{h,cpp}`,
`include/CEncryption.h`, `src/CEncryption.cpp`, `server/include/network/IPacketHandler.h`,
`server/src/player/PlayerClient.cpp`, `server/src/player/Player.cpp`. **Not** the vendored
`GServer-v2/dependencies/gs2lib/` copy. See the sources-of-truth callout in
[GServer Behavior Reference](gserver-behavior.md#sources-of-truth).

## Full Client Version Table

The `CLVER_*` enum (`IUtil.h:150-218`) is a plain sequential enum. The header does not
assign explicit numeric values. Each entry has two independent strings. `IUtil.cpp` looks
up both strings by array index:

- **`clientVersions[]`** (`IUtil.cpp:50-123`) is the compact identifier that the *client*
  sends on the wire as its 8-byte version field (e.g. `"GNW03014"`, `"G3D0311C"`).
- **`clientVersionString[]`** (`IUtil.cpp:142-215`) is the human-readable display version
  (e.g. `"2.22"`, `"6.037"`).

| CLVER enum | Display version | Wire identifier |
|---|---|---|
| `CLVER_UNKNOWN` | *(none)* | *(none)* |
| `CLVER_NPCSERVER` | *(none)* | *(none)* |
| `CLVER_1_25` | 1.25 | `SERV009` |
| `CLVER_1_27` | 1.27 | `SERV011` |
| `CLVER_1_28` | 1.28 | `SERV013` |
| `CLVER_1_31` | 1.31 | `SERV016` |
| `CLVER_1_32` | 1.32 | `SERV018` |
| `CLVER_1_322` | *(none)* | *(none)* |
| `CLVER_1_323` | *(none)* | *(none)* |
| `CLVER_1_324` | *(none)* | *(none)* |
| `CLVER_1_33` | 1.33 | `GNW20020` |
| `CLVER_1_331` | *(none)* | *(none)* |
| `CLVER_1_34` | 1.34 | `GNW22030` |
| `CLVER_1_341` | *(none)* | *(none)* |
| `CLVER_1_35` | 1.35 | `GNW13040` |
| `CLVER_1_36` | 1.36 | `GNW10050` |
| `CLVER_1_37` | 1.37 | `GNW21050` |
| `CLVER_1_371` | *(none)* | *(none)* |
| `CLVER_1_38` | 1.38 | `GNW22060` |
| `CLVER_1_381` | *(none)* | *(none)* |
| `CLVER_1_39` | 1.39 | `GNW07080` |
| `CLVER_1_391` | *(none)* | *(none)* |
| `CLVER_1_392` | *(none)* | *(none)* |
| `CLVER_1_4` | *(none)* | *(none)* |
| `CLVER_1_41` | *(none)* | *(none)* |
| `CLVER_1_411` | 1.41r1 | `GNW13110` |
| `CLVER_2_1` | 2.1 | `GNW31101` |
| `CLVER_2_12` | 2.12 | `GNW01012` |
| `CLVER_2_13` | 2.13 | `GNW23012` |
| `CLVER_2_14` | 2.14 | `GNW30042` |
| `CLVER_2_15` | 2.15 | `GNW19052` |
| `CLVER_2_151` | 2.151 | `GNW20052` |
| `CLVER_2_16` | 2.16 | `GNW12102` |
| `CLVER_2_17` | 2.17 | `GNW22122` |
| `CLVER_2_18` | 2.18 | `GNW21033` |
| `CLVER_2_19` | 2.19 | `GNW15053` |
| `CLVER_2_2` | 2.2 | `GNW28063` |
| `CLVER_2_21` | 2.21 | `GNW01113` |
| `CLVER_2_22` | 2.22 | `GNW03014` |
| `CLVER_2_3` | 2.3 | `GNW14015` |
| `CLVER_2_31` | 2.31 | `GNW28015` |
| `CLVER_3` | 3.0 | `G3D16053` |
| `CLVER_3_01` | 3.01 | `G3D27063` |
| `CLVER_3_041` | 3.041 | `G3D03014` |
| `CLVER_4_0211` | 4.0211 | `G3D28095` |
| `CLVER_4_034` | 4.034 | `G3D09125` |
| `CLVER_4_042` | 4.042 | `G3D17026` |
| `CLVER_4_110` | 4.110 | `G3D26076` |
| `CLVER_4_208` | 4.208 | `G3D20126` |
| `CLVER_5_07` | 5.07 | `G3D22067` |
| `CLVER_5_12` | 5.12 | `G3D14097` |
| `CLVER_5_31x` | 5.31x | `G3D26090` |
| `CLVER_6_015` | 6.015 | `G3D3007A` |
| `CLVER_6_034` | 6.034/6.035 | `G3D2505C` |
| `CLVER_6_037` | 6.037 | `G3D0311C` |
| `CLVER_6_037_LINUX` | 6.037 (Linux) | `G3D0511C` |
| `CLVER_IPHONE_1_1` | iPhone 1.1 | `G3D04048` |
| `CLVER_IPHONE_1_5` | iPhone 1.5 | `G3D18010` |
| `CLVER_IPHONE_1_11` | iPhone 1.11 | `G3D29090` |
| `CLVER_IPHONE_BELOTE_1_5` | iPhone Belote 1.5 | `G3D2504D` |
| `CLVER_WORLDS` | Graal Worlds | `G3D2204D` |
| *(no enum symbol — trailing array slot, comment `NSVER_UNKNOWN`)* | `[NPC-Server]` | *(none)* |
| *(no enum symbol — trailing array slot, comment `NSVER_GENERIC`)* | `[NPC-Server] Generic` | `GRNS0000` |
| *(no enum symbol — trailing array slot, comment `NSVER_LNXMAD`)* | `[NPC-Server] lnxmad` | `LNX00001` |

> The three NPC-server rows are appended to the *same* `clientVersions[]`/`clientVersionString[]`
> arrays as extra trailing slots. The headers do not declare an `NSVER_*`-prefixed
> enumerator. Only the array comments (`IUtil.cpp:119-121,211-213`) provide these names.
> Do not add an `NSVER_*` enum to a new implementation. Match the string.

Lookup is a linear string scan: `getVersionID()` (`IUtil.cpp:234-244`) matches the wire
identifier against `clientVersions[]`. `getVersionString()` (`IUtil.cpp:246-277`) resolves
the display string and dispatches between the client/RC/NC arrays by `PLTYPE_*` bitmask.

### RC versions

Separate dedicated enum `RCVER_*` (`IUtil.h:227-233`) with its own parallel arrays
(`rcVersions[]`/`rcVersionString[]`, `IUtil.cpp:133-140,225-232`). It is **not** part of the
`CLVER_*` index space:

| RCVER enum | Display version | Wire identifier |
|---|---|---|
| `RCVER_UNKNOWN` | *(none)* | *(none)* |
| `RCVER_1_010` | 1.010 | `GSERV023` |
| `RCVER_1_1` | 1.1 | `GSERV024` |
| `RCVER_2` | 2.0 | `GSERV025` |

### NC versions

Separate dedicated enum `NCVER_*` (`IUtil.h:220-225`), own arrays (`ncVersions[]`/
`ncVersionString[]`, `IUtil.cpp:125-131,217-223`):

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

The wire byte is **not** the flag value. It is the *shift amount*. `PlayerClient::
handleLogin` (`PlayerClient.cpp:314`) computes:

```cpp
m_type = (1 << pPacket.readGChar());
```

So a login-type byte of `0` (GCHAR-decoded) means `PLTYPE_CLIENT`, `4` means `PLTYPE_CLIENT2`,
`5` means `PLTYPE_CLIENT3`, `8` means `PLTYPE_WEB`, etc.

### Generation selection switch

`PlayerClient::handleLogin`, `PlayerClient.cpp:317-341`:

```cpp
switch (m_type)
{
    case PLTYPE_CLIENT:
        Encryption.setGen(ENCRYPT_GEN_2);
        break;
    case PLTYPE_CLIENT2:                 // 2.19 - 2.21, 3 - 3.01
        Encryption.setGen(ENCRYPT_GEN_4);
        break;
    case PLTYPE_CLIENT3:                 // 2.22+
        Encryption.setGen(ENCRYPT_GEN_5);
        break;
    case PLTYPE_WEB:
        Encryption.setGen(ENCRYPT_GEN_1);
        m_fileQueue.setCodec(ENCRYPT_GEN_1, 0);
        break;
    default:
        // disconnect: "Your client type is unknown."
        return false;
}
```

| PLTYPE | Encryption gen (initial) | Client range |
|---|---|---|
| `PLTYPE_CLIENT` | GEN_2 (downgraded to GEN_3 — see below) | Legacy v1.3x clients |
| `PLTYPE_CLIENT2` | GEN_4 | 2.19 – 2.21, 3.x – 3.01 |
| `PLTYPE_CLIENT3` | GEN_5 | 2.22+ (includes 6.037) |
| `PLTYPE_WEB` | GEN_1 | Web/embed clients |

### The GEN_2 → GEN_3 downgrade

The switch above always gives `PLTYPE_CLIENT` GEN_2. Immediately after the switch,
(`PlayerClient.cpp:343-356`) the server reads an 8-byte version identifier and looks it up
with `getVersionID()`. If that identifier is **not** one of the *old-style* SERV/GNW-prefixed
strings in `clientVersions[]` (i.e. it resolves to `CLVER_UNKNOWN`), the server concludes
the server identifies a 1.41-style client that also sends an encryption key. It resets the generation to
GEN_3, and rewinds the packet read cursor by one byte:

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

The rewind lets the generic "newer clients" block below parse the data again from one byte
earlier. The server then reads the potential second version-string byte as the encryption-key byte.

## Login Packet Layout

Field order as read in `handleLogin` (`PlayerClient.cpp:303-378`):

1. **Login-type byte**. The server reads a `GCHAR` and shifts it into `PLTYPE_*` as described above.
2. **(PLTYPE_CLIENT only)** 8-byte version identifier, looked up via `getVersionID()`. May
   trigger the GEN_3 downgrade + 1-byte rewind described above.
3. **Encryption-key byte**. The server reads it **only when `m_versionId` is still `CLVER_UNKNOWN`** at
   this point (`PlayerClient.cpp:359-361`). This covers `PLTYPE_CLIENT2`/`CLIENT3`/`WEB`
   unconditionally (they skip step 2 entirely, so `m_versionId` is still unknown), plus the
   rewound 1.41-style `PLTYPE_CLIENT` case. In other words, for game-client logins: **the
   key byte is present whenever gen ends up >= GEN_3**. GEN_1 and GEN_2 logins never send it.
   **GEN_3, GEN_4, and GEN_5 all do**. Sending the key byte on an unrecognized version
   string is precisely how a 1.41-style client gets *detected* as GEN_3: unknown 8-char
   string at the version slot → rewind → re-read that position as key + version.
   ```cpp
   m_encryptionKey = (unsigned char)pPacket.readGChar();
   Encryption.reset(m_encryptionKey);
   if (Encryption.getGen() > ENCRYPT_GEN_3)
       m_fileQueue.setCodec(Encryption.getGen(), m_encryptionKey);
   ```
   Don't confuse the two conditions here: the **strictly-greater** `> ENCRYPT_GEN_3` check
   (`PlayerClient.cpp:364`) gates only the *outgoing* (server → client) `m_fileQueue`
   codec — a GEN_3 client's key is used for its client → server packets, but the server's
   replies to it are plain zlib, never encrypted (see the GEN_3 row below). The NC/RC
   login paths (`PlayerNC.cpp:103`, `PlayerRC.cpp:151`) *do* use `> ENCRYPT_GEN_3` to gate
   reading the key byte itself — which coincides in practice because NC/RC gens are only
   ever GEN_2 (no key) or GEN_5 (key); no GEN_3 NC/RC clients exist.
4. **8-byte version identifier** (again, but via `getVersionIDByVersion()` this time — which
   dispatches to `getVersionID()`/`getNCVersionID()`/`getRCVersionID()` by connection type).
5. **Account name**. A 1-byte unsigned length (`GUCHAR`) precedes that number of raw chars.
6. **Password**. It uses the same length-prefixed pattern.
7. **Identity string**. `readString("")` reads to the end of the packet. The value is comma-delimited:
   `{platform},{mobile 'dc:id2'},{md5:harddisk-id},{md5:network-id},{uname release/version},{android-id}`.
   Only the platform token is actually consumed by the server.

## Per-Generation Wire Framing

Two layers are involved: an **outer bundle frame** (always present, gen-independent) and a
**per-generation payload transform**.

### Outer framing (all generations)

`IPacketHandler::retrievePacketBundle` (`IPacketHandler.h:239-248`) always reads a `uint16`
bundle-size prefix before any generation-specific operation. This 2-byte length prefix is
universal, not GEN_2-specific.

### Payload transform — `IPacketHandler::processPacketBundle` (`IPacketHandler.h:250-289`)

| Gen | Framing |
|---|---|
| **GEN_1** | Raw. `processPacketBundle` returns immediately — no decompression, no decrypt. |
| **GEN_2** | `bundle.zuncompressI()` only. No compression-type byte, no encryption. |
| **GEN_3** | `bundle.zuncompressI()` at the **bundle** level. The single-byte-insertion decrypt runs later, **per individual packet** after the bundle is split on newlines (`parsePacketsFromBundle`, `IPacketHandler.h:323-325`): `if (gen == GEN_3) Encryption.decrypt(curPacket);` — i.e. GEN_3 "encryption" is applied once per packet, not once per bundle. |
| **GEN_4** | `Encryption.limitFromType(COMPRESS_BZ2)` then `Encryption.decrypt(bundle)` (XOR, limited to 4 four-byte blocks = 16 bytes) applied to the **whole bundle**, *then* `bundle.bzuncompressI()`. Always BZ2 — there is no compression-type byte for GEN_4. |
| **GEN_5** | Read + strip a 1-byte compression-type indicator (`0x02`/`0x04`/`0x06`) from the front of the bundle, `limitFromType(pType)` to pick the XOR block-limit, partial XOR-decrypt, then decompress per the type byte (zlib/bz2/none). |
| **GEN_6** | Declared (`ENCRYPT_GEN_6 = 5`) but **not implemented**. Falls into the same `>= ENCRYPT_GEN_5` framing branch as GEN_5 (no dedicated case), but `CEncryption::decrypt`/`encrypt` treat it as a no-op (no case at all in `encrypt()`'s switch), so a nominal GEN_6 session would use GEN_5-style framing with the XOR pass silently skipped. |

### GEN_3's "single byte insertion", precisely

The encrypt code in `CEncryption.cpp` (`:98-107`) inserts a **literal `)` character (`0x29`)** at
a pseudo-random offset from the LCG iterator. The decrypt code (`:49-57`) removes one byte at
that same computed offset:

```cpp
// decrypt (CEncryption.cpp:49-57)
m_iterator *= 0x8088405;
m_iterator += m_key;
int pos = ((m_iterator & 0x0FFFF) % pBuf.length());
pBuf.removeI(pos, 1);

// encrypt (CEncryption.cpp:98-104, mirror)
// ... same iterator advance ...
return CString() << pBuf.subString(0, pos) << ")" << pBuf.subString(pos);
```

**GEN_3 is direction-asymmetric.** The insertion cipher exists only on the **client →
server** direction. The server's *outgoing* GEN_3 path (`CFileQueue.cpp:175-196`) shares
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

This exact behavior is implemented and live-verified in
`reborn-protocol/reborn_protocol/codec.py` (`Gen3Codec`). Tests probed it against GServer with a
real 1.411 login (`game_tester/version_probe.py`).

### GEN_4, both directions

Symmetric, per `CFileQueue.cpp:198-219` (server send) and `IPacketHandler.h:268-278`
(server receive): bundle → **bz2 compress** → partial XOR with the GEN_5 LCG keystream
(iterator seed `0x4A80B38`, `limitFromType(COMPRESS_BZ2)` = 4 iterations = first **16
bytes**, limit re-armed per bundle) → `uint16` length prefix. **No compression-type byte**
in either direction. GEN_4 always uses bz2. `Gen4Codec` implements this behavior in
`reborn-protocol/reborn_protocol/codec.py` (probed with real 2.17/2.21 logins).

### XOR limits (GEN_4/GEN_5, shared implementation)

Same LCG-driven 4-byte XOR keystream as GEN_5 (see [Encryption](encryption.md) for the
detailed algorithm). The per-compression-type block limits come from `CEncryption.cpp:145`
(`limitFromType`, table `{0x02,0x0C, 0x04,0x04, 0x06,0x04}`):

| Compression type | Byte value | XOR limit (4-byte blocks) | Bytes encrypted |
|---|---|---|---|
| `COMPRESS_UNCOMPRESSED` | `0x02` | 12 | 48 |
| `COMPRESS_ZLIB` | `0x04` | 4 | 16 |
| `COMPRESS_BZ2` | `0x06` | 4 | 16 |

`ITERATOR_START[6] = {0, 0, 0x04A80B38, 0x4A80B38, 0x4A80B38, 0}` (`CEncryption.cpp:23`) —
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
4. Send the credential/server-list request as GEN_5. Production's first
   response bundle is already GEN_5 and begins with type `0x04`.

Reborn retains a plain-zlib first-response fallback because an implementation
may queue output before processing the initialization packet: at connection
creation the open reference server's output queue and input codec are still
GEN_2. The recorded production session does not use this fallback. Support for
it is interoperability with the open implementation, not evidence that
production sends a GEN_2 first response.

List-server response text uses **cp1252**, whereas game-session text uses
**latin-1**. The distinction is observable for bytes such as `0x92` (a right
single quotation mark in cp1252).

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
