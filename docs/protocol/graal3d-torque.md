# Graal3D Torque Side Connection

The Graal clients from 3.04 to 5.12 are built on the Torque Game Engine (TGE 1.x). When
such a client joins a 3D server, it opens a second connection: a Torque UDP connection
next to the normal Graal TCP login. This page describes that second connection. The
5.24r3 and later clients have no 3D side.

**Sources**: Graal_analysis
[`torque/network.md`](https://github.com/squirelworks/Graal_analysis/blob/main/torque/network.md)
and
[`torque/wire-by-build.md`](https://github.com/squirelworks/Graal_analysis/blob/main/torque/wire-by-build.md).
These notes have static reads of the 3.04, 3.153, 4.04r2, 4.20r6 and 5.12 clients, and a
lab capture of the real 5.12 client that completes the handshake against a test server.

## Two connections to one host

The server list marks a 3D server with a `"3 "` prefix on its name. When the user picks
such a server, the client:

1. Removes the two-character prefix.
2. Starts the Torque side. It connects over UDP to **listed port + 1**.
3. Opens the normal Graal TCP connection to the listed port and logs in as usual. The TCP
   login is the same as for a 2D server.

So a Graal3D server is two servers on one host: a GServer on TCP port *P* and a Torque
server on UDP port *P* + 1. The client's own UDP port is random, unless the preference
`$pref::Graal::fixedport` is set. Then the client uses `fixedudpport` (default 14899).

The 3D connection lives only as long as the TCP connection. When the TCP side closes, the
client shows "You have been disconnected from the game server." and sends a Torque
disconnect (`0x26`).

## Packet framing

The framing is stock TGE 1.x `NetInterface`. All integers are little-endian. The first bit
of a datagram gives the kind:

- **1**: a data packet for an established connection (Torque's notify protocol: sequence
  numbers, acks, then events, ghost updates and moves in a `BitStream`).
- **0**: an "info" packet. The first byte is the type:

| Type | Name | Direction | Body |
|---|---|---|---|
| `0x1A` | ConnectChallengeRequest | C→S | U32 connect sequence |
| `0x1C` | ConnectChallengeReject | S→C | the Graal clients do not handle it |
| `0x1E` | ConnectChallengeResponse | S→C | U32 sequence, 4 × U32 address digest |
| `0x20` | ConnectRequest | C→S | U32 sequence, 4 × U32 digest, string class name `GameConnection`, then the connect-request fields below |
| `0x22` | ConnectReject | S→C | U32 sequence, string reason |
| `0x24` | ConnectAccept | S→C | U32 sequence, the class table (3.153 and later), U32 protocol |
| `0x26` | Disconnect | both | U32 sequence, string reason |

Types below `0x17` go to the master-server and LAN query handler.

Strings in info packets use Torque `writeString`: one flag bit (1 = Huffman coded with
Torque's fixed character-frequency tree, 0 = raw), a U8 length, then the codes or bytes.
After the type byte, an info packet is a bit stream, so the fields after the first string
are not byte-aligned.

## Connect request

`NetConnection::writeConnectRequest` writes the net class group (U32, 0 = game) and the
class CRC for that group (U32). Then `GameConnection::writeConnectRequest` writes:

| Field | 3.04 | 3.153 | 4.04r2 | 4.20r6 | 5.12 |
|---|---|---|---|---|---|
| game string | `Torque Game Engine Demo` | `Graal3D` | `Graal3D` | `Graal3D` | `Graal3D` |
| U32 current protocol | 9 | 19 | 19 | 21 | 24 |
| U32 minimum protocol | 9 | 19 | 19 | 21 | 24 |
| string join password | server password | not traced | account password | not traced | account password |
| U32 argc (≤ 16), then argc strings | script args | not traced | 2: account, nickname | not traced | 2: account, nickname |

- The join password is the account password **in clear**. Torque adds no encryption.
- The class CRC is not computed. In 4.04r2 and 5.12 the CRC table is static data
  `{0xFFFFFFFF, 0, 0, 0}` that nothing writes to. Group 0 always sends `0xFFFFFFFF`.

The 5.12 server-side reader rejects a request in these cases:

| Condition | Reason code |
|---|---|
| game string is not `Graal3D` | `CHR_GAME` |
| client current protocol < 24 | `CHR_PROTOCOL_LESS` |
| client minimum protocol > 24 | `CHR_PROTOCOL_GREATER` |
| argc > 16 | `CR_INVALID_ARGS` |

## Connect accept and the class table

In stock TGE the accept body is one U32, the server's protocol. From 3.153 on, the Graal
clients read a **class-name table** before that U32:

```
repeat while readFlag() == 1:
    U12     class type        (5.12: 0 = net object, 1 = net event)
    U12     server class id   (0..255)
    string  class name        (Huffman string, for example "NetStringEvent")
U32  protocol                 (must match the client's protocol exactly)
```

The client maps each server id to its own class with that name. Ghost and event class ids
on the wire are then the **server's** ids, sent in 12 bits. This replaces Torque's fixed
class numbering, which is why the class CRC no longer matters.

- 3.153 and 4.04r2 use three types: object, datablock and event.
- 4.20r6 and 5.12 use two types: object and event.
- 3.04 has no table (stock TGE).

An accept with an empty table (one 0 bit) and protocol 24 is enough to get a real 5.12
client to "Connection established". An accept in the stock layout, without the table bit,
is read one bit off. The client reads protocol 12 and silently rejects it.

The client accepts only its own protocol: exactly 24 for 5.12, 21 for 4.20r6, 19 for
4.04r2 and 3.153, and 9 for 3.04. Any other value gives `CHR_PROTOCOL`.

### Networked classes in 4.20r6 and 5.12

| Type | Classes |
|---|---|
| object (0) | `Camera`, `DynamicGrass`, `DynamicGrassReplicator`, `DynamicShapeReplicator`, `GameObject`, `Sky`, `Sun`, `TerrainBlock`, `WaterBlock`, `fxSunLight`. 4.20r6 also has `SimpleNetObject` and `twSurfaceReference` |
| event (1) | `BigDataChunkEvent`, `BigDataStartEvent`, `ConnectionMessageEvent`, `GhostAlwaysObjectEvent`, `NetStringEvent`, `RemoteCommandEvent`, `RequestReloadEvent` (C→S), `TerrainChunkEvent`, `TerrainRequestUpdatesEvent` (C→S). 4.20r6 also has `SimpleMessageEvent` |

`BigDataStartEvent` and `BigDataChunkEvent` are Graal additions. They carry Graal text and
scripts over the Torque connection.

## After the accept

Data packets use the stock Torque `ConnectionProtocol` header. Mission download uses the
`MissionStartPhaseN` and `MissionStartPhaseNAck` remote commands:

| Build | Phases |
|---|---|
| 3.153, 4.04r2 (stock TGE game layer) | 1 "Download Datablocks & Targets", 2 "Download Ghost Objects", 3 "Mission Lighting" |
| 5.12 | 1 "Download Ghost Objects", 2 "Mission Lighting" (no datablocks) |

In 5.12 these steps raise the GS2 event `onGraal3DLoginStep`.

The 5.12 `GameConnection` packets differ from stock TGE. The client sends no `Move`
structures. It always reports the control object's position (3 × F32) and, when it
controls that object, the object's own packet data. The server sends a U32 server time
with the control object.

## Minimum for a server

To get a real 5.12 client connected:

1. Answer `0x1A` with `0x1E`. Echo the sequence and send any digest that the server can
   check later.
2. Accept a `0x20` with class group 0, CRC `0xFFFFFFFF`, game string `Graal3D` and
   protocol 24/24. Check the join password against the account.
3. Reply `0x24` with the sequence, the class table (every object and event class the
   server will send, by name), a 0 bit, and protocol 24.
4. Keep the Graal TCP connection alive. If it closes, the client drops the 3D connection.

For 4.04r2 clients use protocol 19 and the three-type class table.
