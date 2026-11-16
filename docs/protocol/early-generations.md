# Before GEN_3: the 1998 Relay and the 1999 GServer

The reference server's oldest client constants are the `GSERV` tokens of 1.21 to 1.32 (see
[Versions and Encryption](versions-encryption.md)). This page describes what those clients,
and the clients before them, actually put on the wire. It is for anyone who wants to serve
or study the oldest builds; nothing here is needed for 2.x and later.

All of it comes from static analysis of the shipped executables and a few lab captures,
written up in squirelworks' public client-analysis notes:
[`protocol/relay-1998.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/relay-1998.md) and [`protocol/gserv-1999.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/gserv-1999.md). It is not verified
against the reference server, which has no code for the relay at all.

## The two eras side by side

| | 1998 relay (1st Graal beta to 1.1.9) | 1999 GServer (1.21 to 1.39) |
|---|---|---|
| Server | A lobby that forwards lines between partners; no game logic | GServer: accounts, levels, NPCs, flags, weapons |
| Framing | Text lines ending in `\n`, no length | `u16` big-endian length, then a zlib stream |
| Message ids | One letter (`D` plus a type letter for game data) | `chr(id + 32)` as the first byte of each message |
| Identity | A server-given 8-character id; the nickname travels as data | Account and password at login |
| Levels | Fetched over plain HTTP/1.0 by a separate small client | Sent by the GServer |
| Encryption | None | None (the DES code in these clients is for local files only) |

## The 1998 relay

Every message is one text line; the first character is the command. The read buffer is
1 KB. A captured 1.1.9 client opens **two** connections to the same port: one in a fixed
game room and one that follows the current level.

**Lobby lines.** Client to server: `N<game>#<name>` joins a game (the clients always send the
name `def` and send the real nickname later as data), `P<id>` asks to pair with a player or
accepts, `C` leaves the party, `-` leaves the available list, `D<data>` relays data to the
party. Server to client: `I<id8>` your id (`0000` plus a 4-digit counter), `+<id8>` a player is
in the same game, `-<id8>` a player left, `P<id8>` the partnership is confirmed (the client
then pushes its whole state), `C<id8>` the partner left, `D<data>` relayed data. From 15th
Graal on, the 1.1.9 server also sends `NR` or `NL` after `N`; with `NL` the client starts in
`onlinestartlocal.graal`.

**Game names.** The name sent with `N` keeps incompatible builds apart: `Zelda2` (1st, 2nd),
`Graal` (3rd, 4th), `Graal2` (4th alpha), `Graal3` (5th), `Graal4` (6th), `Graal5` (7th to 9th),
`Graal6` (10th to 12th), `Graal7` (13th), `Graal8` (14th, 15th, 1.1, 1.1.9). On a level the client
builds the name from `G<n>` plus the level's location instead, so each level is its own room
and players only meet on the same level with a compatible build.

**`D` payloads** are `D <sid:2> <type:1> <payload>`. The server does not stamp the sender, so
`sid` is the sender's own id as two base-128 characters (`(c0 − 32) × 128 + (c1 − 32)`).
Numbers use the same `+32` one-character form as the later GCHAR; coordinates are half
tiles; knockback and fine offsets use `(c − 96) / 16`, the same as the later hurt packets.
The types, with the build that added them:

| Type | Payload | Meaning |
|---|---|---|
| `A` | x, y, dir/flags, kind, one more byte | Arrow fired |
| `B` | x, y, `w·8 + h`, then w·h tiles as two base-128 chars each | Board modify |
| `C` | text | Chat line |
| `D` | one char per object id | Listed baddies or NPCs are dead |
| `E` / `G` | x, y, item index | Item laid down / picked up |
| `F` | x, y, a, b | Bomb laid |
| `H` | object id, dx, dy, damage | Baddy hurt |
| `I` | none | The player left the level |
| `L` | level name | Current level |
| `M` | repeated 6-byte records: id, x, y, sprite, `dir·4 + mode`, state | Baddy movement batch |
| `N` | text | Nickname |
| `O` | carried object id | Carry object |
| `P` | x, y, sprite | Position and animation, every 100 ms while moving; sprite = `frame·4 + dir` |
| `Q` | NPC id | `playertouchsme` (2nd Graal on) |
| `S` | count, colour indices | Sprite colours |
| `T` | 10 chars, base 128, little end first | Login time; the earliest peer becomes level leader |
| `U` | x, y, kind, id | Baddy spawned (4th alpha on) |
| `W` | sprite | Throw the carried object |
| `X` | target id | Hit aimed at one player (4th alpha on) |
| `Y` | sword, shield, power | Sword and shield change (4th alpha on) |
| `0` to `4` | various | Horse, bush and fireball actions (7th on) |
| `5` to `7` | none | Pose flags (8th / 9th on) |
| `8` | registration key | Duplicate-key check (15th on) |

Several of these live on as numbered packets with the same meaning in 1.21: board modify,
bomb, item, horse and throw.

## The 1999 GServer (1.21 to 1.32)

**Framing.** Messages queue as `chr(id + 32) + data + "\n"`. On flush the whole buffer is
deflated (zlib 1.0.4) and written as `[len_hi][len_lo][zlib stream]`. There is no size
threshold: every flush is compressed. Id 100 (`PLO_RAWDATA`) already exists and switches the
reader to a byte count for file data. This is GEN_2's framing with no cipher.

**Login.** The first message is a normal id-0 line: a type byte (`' '` = player; the 1.x
GServers take `'!'` as RemoteControl), the 8-byte `GSERVnnn` token, then the account and the
password, each as a GSTRING. It is the gen-3 login shape without the key byte. The connect
dialog defaults to `guest` / `guest`.

| Client | Token |
|---|---|
| 1.21, RemoteControl 1.21 | `GSERV007` |
| RemoteControl 1.28, RemoteControl 1.3 | `GSERV011` |
| 1.28 beta 2 | `GSERV013` |
| 1.3 test | `GSERV014` |
| 1.31 | `GSERV016` |
| 1.32 | `GSERV018` |

These tokens are protocol revisions, not dates; the dated `GNW` tokens start with 1.33. The
period GServers compare the token against a fixed list and refuse anything outside it,
newer tokens included, with `PLO_DISCMESSAGE (16)`. The 1.3 GServer, for example, answers
`GSERV016` with "You need at least Graal version 1.3 to play on this server."

**Login reply.** A lab capture of the 1.3 GServer after a good login: 9 (own props), 28 (flags,
only if the account has any), 14 (warp), 100 then a separate frame with 101 and the board,
6 (level name), 1 (links), 5 (signs), 39 (level modification time), 3 (NPC props with scripts),
and 10. The 1.28 GServer sends the same sequence without 39.

**Ids handled.** The server-to-client numbering of 2.x is already in place in 1.21:

| Client | Server-to-client ids handled | Player props parsed | NPC props |
|---|---|---|---|
| 1.21 | 0 to 34 except 30, plus 100 | 0–24 | 0–17 |
| 1.28 beta 2 | 0 to 38, plus 100 | 0–31 | 0–32 |
| 1.3 test | 0 to 39, plus 100 | 0–32 | 0–34 |
| 1.31 | 0 to 40, plus 100 | 0–32 | 0–34 |
| 1.32 | 0 to 41, plus 100 | 0–33 | 0–34 |

Baddy props are 0 to 10 in all of them. Prop numbers only grow at the end, so a decoder can
use the later tables and stop at the build's last id.

**UDP.** 1.28 beta 2 is the first build with a UDP peer socket: single, uncompressed,
unframed messages straight to another player. A walking 1.28 beta 2 client sent id 0
(props 15 to 19) to the other player every 100 ms, while the server got only the changed
props over TCP. 1.31 adds the `noudp=` and `fixedudpport=` config keys.
