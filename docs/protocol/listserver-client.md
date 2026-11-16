# List-Server Client Protocol

[Client Versions & Encryption](versions-encryption.md#production-list-server-gen-5-transition)
describes how a modern list-server session switches from GEN_2 to GEN_5. This page gives
the packet ids, the server-list layout, and the older login forms that each client
generation uses.

**Sources**: the open list server `graal-serverlist`
(`graal-serverlist/server/src/PlayerConnection.cpp`,
`graal-serverlist/server/src/ServerConnection.cpp`), the recorded live session
`pyReborn/tests/fixtures/listserver_session_live.json`, and squirelworks' client-analysis
notes, `protocol/listserver.md`. Those notes have static reads of the 2.05, 2.17, 2.22 and
2.31 clients and lab captures of real 2.00, 2.05, 2.17 and 2.22 list sessions. Statements
about what a client sends are reported there and not verified against the reference unless
a `graal-serverlist` line is cited.

## Client to list server

The three version packets 4, 5 and 7 are also listed with the reference layout in
[Client Versions & Encryption](versions-encryption.md#production-list-server-gen-5-transition).

| Id | Name | Body |
|---:|---|---|
| 0 | `V1VER` | rest = version string, for example `newmain` |
| 1 | `SERVERLIST` | GCHAR length + account, GCHAR length + password |
| 4 | `V2VER` | `GUCHAR key` + 8-byte version string. The reference switches both directions to GEN_4 (bzip2 body, partial XOR) and treats the client as 2.17-2.21 (`graal-serverlist/server/src/PlayerConnection.cpp:286-298`). Its source comment says no client that sends it is known |
| 5 | `V2SERVERLISTRC` | `GCHAR key` + 8-byte version string. GEN_5 both directions; the client gets every server (`graal-serverlist/server/src/PlayerConnection.cpp:300-310`). The reference ties it to RC1 (`graal-serverlist/server/src/ClientType.cpp:10`) |
| 7 | `V2ENCRYPTKEYCL` | `GUCHAR key` + 8-byte token + client type to end of packet, for example `GNW30123newmain`. A client type of `newmain` gets the 2.22 to 3.x list; any other string (for example `rc2`) gets every server (`graal-serverlist/server/src/PlayerConnection.cpp:312-325`) |

## List server to client

| Id | Name | Body |
|---:|---|---|
| 0 | `SVRLIST` | `GCHAR count`. Then for each server: `GCHAR 8` (field count) and 8 GCHAR-length strings: type prefix + name, language, description, url, version, player count, ip, port |
| 1 | — | not used |
| 2 | `STATUS` | text; `\r` is a line break |
| 3 | `SITEURL` | url |
| 4 | `ERROR` | text; the connection then closes |
| 5 | `UPGURL` | donation or upgrade url |

The type prefix on the server name comes from the server's HQ level: `3 ` 3D, `P ` gold,
`H ` bronze (hosted), `U ` hidden, and nothing for the middle level (HQ level 2, `Classic`
in the reference; `graal-serverlist/server/src/ServerConnection.cpp:306-327`,
`graal-serverlist/server/include/ServerHQ.h:17-23`). The reference omits the prefix at
every level for a connection that never sent a version packet (client type `Version1`, 1.41
to early 2.00; `ServerConnection.cpp:308-309`). A 2.17 client sends id 0 and so gets the
prefix (`PlayerConnection.cpp:233-248`). Reported, not verified against the reference: a
3.x-6.x client treats a name that starts with `3 ` as a 3D server.

## Login forms by client generation

Client rows are reported from squirelworks' notes and not verified against the reference,
except where a `graal-serverlist` line or the recorded session is cited.

| Client | First message | Framing |
|---|---|---|
| 2.00, 2.05 | id 0 `newmain`, with no account | plain zlib (`u16be` length + zlib), no cipher, both directions |
| 2.17 | id 0 `newmain`, then id 1 account + password, **in one frame** | plain zlib, no cipher, both directions |
| 2.2 (`V2VER`) | id 4 key + `newmain` (reported; no 2.2 client is among the builds read, and the reference knows no client that sends id 4) | bzip2 body, partial XOR (4 groups) |
| 2.22, 2.31 | id 7 key + `GNW30123newmain`, then id 1 | first frame plain zlib; every later frame GEN_5 with that key (`graal-serverlist/server/src/PlayerConnection.cpp:312-325`; recorded session `pyReborn/tests/fixtures/listserver_session_live.json`: plain zlib init frame, GEN_5 `0x04` reply frames) |
| 3.04, 3.153 | id 7 key + `G3D30123newmain` (list-server token, reported; not the game-login token in versions-encryption.md; the C# RC client sends `G3D30123rc2` the same way, `Preagonal/Preagonal.RemoteControl/RemoteControl/Connections/ListServer/ListServerConnection.cs:36`), then id 1 in the same frame | as 2.22 |

Lab notes:

- **2.05** opens the list window and sends id 0 `newmain` at once. A server that answers
  with id 0 fills the list (reported; the reference list server sends nothing for id 0,
  `graal-serverlist/server/src/PlayerConnection.cpp:233-248`, and sends the list on connect
  only to clients on its old-client port, `graal-serverlist/server/src/ListServer.cpp:192-199`).
  The client does not wait for id 1. It closes the socket about
  two seconds after it gets the list.
- **2.17** gets two plain zlib frames. Frame 1 is id 0 (the list). Frame 2 holds ids 2, 3
  and 5. Then the client closes the connection.
- **2.22** answers fully in GEN_5 after the first frame, with the same ids 0, 2, 3 and 5.

From 4.x on there is no list-server protocol
(`graal-serverlist/server/src/ClientType.cpp:9`). The client logs in to a game server
reported to be named `Login` with an ordinary game login. That server sends the list as
scripted GUI. See squirelworks' client-analysis notes, `protocol/login-tokens-3x-7x.md`.
