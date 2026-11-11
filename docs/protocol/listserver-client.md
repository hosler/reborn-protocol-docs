# List-Server Client Protocol

[Client Versions & Encryption](versions-encryption.md#production-list-server-gen-5-transition)
describes how a modern list-server session switches from GEN_2 to GEN_5. This page gives
the packet ids, the server-list layout, and the older login forms that each client
generation uses.

**Sources**: the open list server `graal-serverlist`, and Graal_analysis
[`protocol/listserver.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/listserver.md).
That note has static reads of the 2.05, 2.17, 2.22 and 2.31 clients and lab captures of
real 2.00, 2.05, 2.17 and 2.22 list sessions.

## Client to list server

| Id | Name | Body |
|---:|---|---|
| 0 | `V1VER` | rest = version string, for example `newmain` |
| 1 | `SERVERLIST` | GCHAR length + account, GCHAR length + password |
| 4 | `V2VER` | `GCHAR key` + `newmain`. Selects the 2.2-era bzip2 mode |
| 5 | `V2SERVERLISTRC` | `GCHAR key` (RC clients) |
| 7 | `V2ENCRYPTKEYCL` | `GCHAR key` + 8-byte token + client type, for example `GNW30123newmain` |

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
`H ` bronze (hosted), `U ` hidden, and nothing for silver. Pre-2.2 clients get no prefix
for bronze. A 3.x-6.x client treats a name that starts with `3 ` as a 3D server.

## Login forms by client generation

| Client | First message | Framing |
|---|---|---|
| 2.00, 2.05 | id 0 `newmain`, with no account | plain zlib (`u16be` length + zlib), no cipher, both directions |
| 2.17 | id 0 `newmain`, then id 1 account + password, **in one frame** | plain zlib, no cipher, both directions |
| 2.2 (`V2VER`) | id 4 key + `newmain` | bzip2 body, partial XOR (4 groups) |
| 2.22, 2.31 | id 7 key + `GNW30123newmain`, then id 1 | first frame plain zlib; every later frame GEN_5 with that key |
| 3.04, 3.153 | id 7 key + `G3D30123newmain`, then id 1 in the same frame | as 2.22 |

Lab notes:

- **2.05** opens the list window and sends id 0 `newmain` at once. A server that answers
  with id 0 fills the list. The client does not wait for id 1. It closes the socket about
  two seconds after it gets the list.
- **2.17** gets two plain zlib frames. Frame 1 is id 0 (the list). Frame 2 holds ids 2, 3
  and 5. Then the client closes the connection.
- **2.22** answers fully in GEN_5 after the first frame, with the same ids 0, 2, 3 and 5.

From 4.x on there is no list-server protocol. The client logs in to a game server named
`Login` with an ordinary game login. That server sends the list as scripted GUI. See
Graal_analysis
[`protocol/login-tokens-3x-7x.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/login-tokens-3x-7x.md).
