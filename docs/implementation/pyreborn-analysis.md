# PyReborn Protocol Conformance Analysis

## Overview

PyReborn implements the game, list-server, RC, and NC protocol families on top
of the shared `reborn-protocol` package. This page describes the current
architecture; detailed packet and property layouts remain in the protocol
reference.

## Overall conformance: high

The shared library owns framing and G-types (`reborn_protocol.codec`), GEN_3
through GEN_5 transforms (`reborn_protocol.codec` and
`reborn_protocol.encryption`), property descriptors
(`reborn_protocol.props`), and coordinate conversions
(`reborn_protocol.coords`). PyReborn therefore does not maintain private copies
of these wire primitives.

## Current client architecture

### Packet dispatch

`Client._handle_packet` is a registry lookup, not the former 1,279-line
90-branch dispatcher. The `pyreborn.handlers` package registers **92 handlers**
across seven domain modules:

- `chat`, `combat`, `entities`, `files`, `level`, `scripts`, and `session`
- `registry.handles` records packet IDs and `registry.dispatch` invokes the
  bound handler

This closes the old maintainability gap in which protocol coverage depended on
editing one large conditional.

### Client state

The former flat `Client.__init__` state is divided among components in
`pyreborn.client_state`: session, identity, world, entity, inventory, script,
file, and warp state. `client.py` installs a property-alias table for **150 of
the 156** historical attributes, preserving source compatibility for callers
such as `client.level_name` while component code uses explicit ownership.
`client.py` is now about 2,500 lines rather than the former 4,111.

### Properties and coordinates

Six independent client/server property walkers were replaced by
`reborn_protocol.props`. Its `PLAYER_PROPS`, `NPC_PROPS`, and `BADDY_PROPS`
descriptor tables drive parsing and encoding in both PyReborn and pygserver.
This closes the duplicate-parser gap and makes widths such as `COLORS` a stream
policy rather than an ad-hoc branch. See [Packet Structures](../protocol/packet-structures.md)
and [NPC Properties](../protocol/npc-properties.md) for field layouts.

`reborn_protocol.coords` now names and converts level-local tiles, GMAP/world
tiles, local pixels, global pixels, and camera coordinates. See
[GMAP Protocol](../protocol/gmap.md) for the wire-level map rules.

### List-server session

`pyreborn.listserver.ListServerSession` is transport-neutral: it owns framing,
the GEN_2 initialization fallback, the GEN_5 codec, and packet parsing.
`ListServerClient` and `WebSocketListServerClient` are adapters that only move
bytes. The module imports `Gen2Codec`, `Gen5Codec`, `PacketBuffer`,
`PacketReader`, and `LIST_SERVER_COMPRESSION` from the shared library; its old
private encryption, codec, and G-type implementations are gone.

### Script hosts

Client-side GS1 builtin dispatch uses the `_GS1_PLAYER_BUILTINS`,
`_GS1_NPC_BUILTINS`, and `_GS1_BUILTINS` registries rather than a long
conditional. The client host surface contains **414 names**.

Approximately **57 builtin names remain implemented independently in both the
client host and pygserver's server host**. This duplication is deliberate:
the two implementations sometimes embody different live behavior, and merging
them requires a human compatibility decision rather than a mechanical move.

## Server-side architecture relevant to the client

pygserver's `Player` has fallen from 1,702 lines to about 571 and now acts as a
façade over login, session, movement, entity, combat, and other services.
`pygserver.audience.AudienceService` centralizes visibility and recipient
selection. This closes the prior risk that different handlers independently
implemented “nearby players” with subtly different rules.

## Correctly implemented protocol areas

- Big-endian `uint16` bundle framing and newline-separated inner packets.
- GEN_3, GEN_4, and GEN_5 receive/send transforms.
- GEN_5 compression type bytes and per-type partial-XOR limits.
- Shared GCHAR/GSHORT/GINT and string readers/builders.
- Declarative player, NPC, and baddy property streams.
- Large-file framing, RC/NC packet families, and GS2 bytecode transport and
  execution.
- Inbound `PLO_SHOOT` and `PLO_SHOOT2` dispatch.

## Remaining limits

The remaining issues are not core framing failures:

- GEN_6 is not implemented by either PyReborn or the reference server.
- A few GS1 drawing commands and the ground-item sprite table remain incomplete.
- Corrupt level-board data falls back to an empty board without surfacing a
  diagnostic to the caller.
- List-server server-entry strings decode as cp1252, but top-level
  status/site/donation/error bodies in `build_response` still decode as
  latin-1. Bytes such as `0x92` are therefore wrong on that path.
- Roughly 57 shared builtin names await behavior-by-behavior reconciliation.

See [PyReborn Implementation Gaps](pyreborn-gaps.md) for the actionable list.
