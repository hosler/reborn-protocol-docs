# UDP Peer Channel

Reported, not verified against the reference: classic clients (2.05 and 3.04 were
studied) also send some level traffic **directly to each other over UDP**. The
game server never sees these datagrams. GServer-v2 does not implement this channel. Its
only part in it is relaying two player properties. This page describes the channel so that
a client can take part in it, or turn it off safely.

**Source**: squirelworks' client-analysis notes, `protocol/udp-p2p.md`. The evidence is a
static read of the Windows 2.05 rev 2 client, lab captures of two and three 2.05 clients,
and a lab capture of two Linux 3.04 clients. The layouts below are reported there and not
verified against the reference; the server side (the two relayed properties) is checked
against GServer-v2 beta4.

## Setup

- At connect, the client binds a UDP socket. It uses the `fixedudpport` setting if
  `fixedport` is set. Otherwise it uses an ephemeral port. The `noudp` setting turns the
  channel off. A 2.22 default of `noudp=true` is also reported, but no 2.22 client is among the builds
  listed above.
- The client sends its port to the server as `UDPPORT` (player prop 31, GINT3). The server
  relays it to the other players.
- A peer address is `IPADDR` (prop 30, GINT5 holding a 32-bit address) plus `UDPPORT`
  (prop 31). Both arrive in `PLO_OTHERPLPROPS`.
- The reference server stores the client's `UDPPORT` (`PlayerProps.cpp:833-841` at
  GServer-v2 beta4) and relays both props to nearby players at login
  (`loginPropsClientOthers`, `PlayerProps.h:160`) and whenever `UDPPORT` changes
  (`clientPropsSharedLocal`, `PlayerProps.h:217`). `IPADDR` is the address the server sees
  on the client's TCP connection (`PlayerClient.cpp:290-294`); a client cannot set it
  (`PlayerProps.cpp:829-831`). Widths: [player properties](packet-structures.md).

## Datagram format

```
[BYTE: seq][GCHAR: udp_id][fields...]     // whole datagram XOR key
```

- `seq` is per sender-recipient pair, starts at 0 and wraps at 256. A receiver drops a
  duplicate `seq`.
- The whole datagram is XORed with one key byte: **`recipient_id XOR 1`** (low byte). A
  three-player capture confirms this. Every datagram to player 2 used key 3, to player 3
  key 2, and to player 4 key 5, whatever the sender.
- There is no zlib, no length prefix and no GEN_3 insertion.
- Fields use the same G-types as TCP.
- A receiver accepts a datagram only from the address and port of a known player.

## Routing

Reported: a level-local action goes **over UDP only** when every other player in the level
has a UDP port; otherwise the client sends it over UDP to the peers that have a port, and
over TCP to the server. In the lab, clients also kept sending `PLI_PLAYERPROPS` X/Y/sprite
over TCP while UDP was active, which this rule does not explain. The full rule that selects
TCP was not worked out.

## UDP ids

These ids are the channel's own numbers. They do not match the PLI or PLO ids. Reported
from the 2.05 static read and captures; not verified against the reference.

| Id | Meaning | Body |
|---|---|---|
| 0 | Movement | X×2, Y×2, SPRITE, STATUS, CARRYSPRITE, then one GCHAR that matches the first letter of the current gani (`W` walk, `I` idle, `S` sword were seen). Sent about every 100 ms while the player moves |
| 10 / 11 | Bomb add / delete | as the TCP packets |
| 12 / 13 | Arrow add / fire spy | as the TCP packets |
| 14 | Explosion | as the TCP packet |
| 15 | Show image | index, x, y, name length, name. 3.04 also sends a 1-byte form (`9`) about every 5 s |
| 16 / 17 | Horse add / delete | as the TCP packets |
| 18 | Throw carried | as the TCP packet |
| 19 / 20 | Item add / delete | as the TCP packets |
| 21 | Hit from GS1 `hitplayer`, sent only to the victim | `GCHAR((dx+4)*16)`, `GCHAR((dy+4)*16)`, `GCHAR(half_hearts)`. dx/dy are clamped to −4..4 |
| 22 | Chat | text, at most 253 bytes |
| 23 | Level name only | raw name. The receiver applies it as prop 20 (CURLEVEL). No 2.05 sender was found |
| 24 | Entered level | `GCHAR(x*2)`, `GCHAR(y*2)`, raw level name. Sent to peers in the 3×3 gmap area. Applied as props 15, 16 and 20 |
| 25 | Hit objects | as the TCP packet |
| 26 | Trigger action | as the TCP packet. 3.04 sends a mouse click this way (NPC id 0, x×2, y×2, `leftmouse`), over UDP only |
| 28 | Shot (5.0.0.7) | the `PLI_SHOOT (40)` body (layout: [Client-side SHOOT2 layout](packet-structures.md#client-side-shoot2-layout); `PLI_SHOOT = 40` at gs2lib `IEnums.h:72`) |
| 30 | Shot v2 (5.0.0.7 receives) | the `PLO_SHOOT2 (191)` body without the player id (layout: [Client-side SHOOT2 layout](packet-structures.md#client-side-shoot2-layout); `PLO_SHOOT2 = 191` at gs2lib `IEnums.h:312`) |

## What this means for an implementation

These points follow from the routing rule above. No lab test checked them.

- A client that sets a nonzero `UDPPORT` must answer these datagrams. If it does not, other
  classic clients in the same level can send some actions over UDP only, and the client
  never sees them.
- A client that does not implement the channel should send `UDPPORT` 0 or leave it out.
  Then its peers fall back to TCP through the server. The mobile engine does this: it
  sends `UDPPORT` as three blank bytes, value 0
  (`Preagonal/FourPlay/quattroplay/src/TPlayer.cpp:3255-3257`).
- A server that wants all traffic to go through it can leave out `IPADDR` and `UDPPORT` in
  `PLO_OTHERPLPROPS`.
- `PLO_PLAYERNOUDP (181)` is an unused toggle that the reference never sends; see
  [packet structures](packet-structures.md).
