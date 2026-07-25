# GS2 bytecode and client runtime

This page records bytecode and runtime behavior implemented by
`reborn-protocol` and hosted by `pyReborn`. The source references and named
regression tests are the evidence for each rule.

## What reaches the client

Source is split at its client-side delimiter. The server compiles its portion
for its own engine and separately compiles the client portion sent as
bytecode. The client VM therefore never receives or executes server-side
code.

`GServer-v2/server/src/scripting/Script.cpp`, `Script::setSource()` and
`Script::compileScript()`, implement the split. Weapon and class delivery use
`getClientByteCode()` in `server/src/object/Weapon.cpp` and
`server/src/scripting/ScriptClass.cpp`. The receiving entry point is
`pyReborn/pyreborn/gs2_client.py`, `ClientGS2.load_bytecode()`.

## Container format

A container is a sequence of segments. Each begins with a plain big-endian
unsigned 32-bit identifier and unsigned 32-bit payload length. These fields
do **not** use the protocol's usual offset-by-32 packed-number encoding.

| Segment | ID | Payload |
| --- | ---: | --- |
| GS1 flags | 1 | One big-endian 32-bit flag word |
| Function table | 2 | Repeated big-endian 32-bit instruction index and NUL-terminated name |
| String table | 3 | Repeated NUL-terminated strings |
| Bytecode | 4 | Opcode and operand-record stream |

Compiler output may have a newline after the final segment, outside its
declared length. The parser preserves unknown segments.

Function and jump targets are **instruction indices**, not byte offsets. An
opcode advances the index once; its operand bytes do not.

Evidence:

- `reborn_protocol/gs2/container.py`, `parse_container()`
- `reborn_protocol/gs2/disasm.py`, `decode()`
- `tests/test_gs2_disasm.py`,
  `test_register_ops_consume_signed_operand()` and
  `test_baseline_decodes_cleanly()`

## Operand records

Operands are optional typed records in the instruction stream, not fixed
fields embedded in particular instructions. A marker encountered in opcode
position belongs to the preceding instruction and is never executed. If
several records follow one instruction, the last supplies the operand value.

| Marker | Data | Interpretation |
| --- | --- | --- |
| `0xF0` | 1 byte | Unsigned index |
| `0xF1` | 2 bytes, big-endian | Unsigned index |
| `0xF2` | 4 bytes, big-endian | Unsigned index |
| `0xF3` | 1 byte | Signed number |
| `0xF4` | 2 bytes, big-endian | Signed number |
| `0xF5` | 4 bytes, big-endian | Signed number |
| `0xF6` | NUL-terminated ASCII | Floating-point text |

The preceding opcode supplies the value's purpose: string-table index,
literal, register number, or jump target. When an instruction normally
associated with an operand has no record, its operand is the initial zero.
Real content uses that omission, so the next opcode must remain an opcode.

Evidence:

- `reborn_protocol/gs2/disasm.py`, `_parse_typed_operand()` and `decode()`
- `reborn_protocol/gs2/opcodes.py`, `OPERAND_OPS`, `NUMBER_OPS`, `INDEX_OPS`
- `tests/test_gs2_disasm.py`,
  `test_set_index_without_typed_marker_keeps_implicit_zero_operand()`,
  `test_or_without_typed_marker_keeps_implicit_zero_operand()`, and
  `test_marker_byte_is_never_an_instruction()`

## Reverse-engineered register opcodes

The open-source compiler does not emit opcodes 45–47. Captured
official-compiler output and the official interpreter establish:

| Number | Name | Behavior |
| ---: | --- | --- |
| 45 | `OP_REG_STORE` | Copy the stack top to a numbered register without popping |
| 46 | `OP_REG_LOAD` | Push a copy of a numbered register |
| 47 | `OP_CONV_TO_PROPERTY` | Convert the stack top in place to a property reference |

Store and load carry a signed operand. Leaving them out of the operand table
makes the record bytes appear to be opcodes and desynchronizes decoding.
Accepted register indices are 0 through `0x3FF`. Registers are held per frame
so a nested call does not overwrite its caller's expression cache.

Evidence:

- `reborn_protocol/gs2/opcodes.py`, opcodes 45–47 and `OPERAND_OPS`
- `reborn_protocol/gs2/vm.py`, `_op_reg_store()`, `_op_reg_load()`, and
  `_op_conv_to_property()`
- `tests/test_gs2_disasm.py`, `test_register_ops_consume_signed_operand()`
- `tests/test_gs2_vm.py`, the “expression-cache registers” tests

## Arrays

Array indices use:

```text
floor(numeric_value + 0.0001)
```

This is not truncation. It matters for negative values and calculations that
land just below an integer. Array initialization and resizing clamp requested
lengths to 0 through 10,000 cells.

Multi-dimensional access is exactly two-dimensional. Although the compiler
emits one `OP_ARRAY_MULTIDIM` for any expression with more than one index,
the runtime consumes exactly two. A three-index expression leaves the
original array on the stack and treats the first index as the base. This
matches the official runtime and is retained for compatibility.

Evidence:

- `reborn_protocol/gs2/vm.py`, `array_index()`, `array_size()`,
  `MAX_ARRAY_SIZE`, `_op_array_multidim()`, and
  `_op_array_multidim_assign()`
- `tests/test_gs2_array_semantics.py`,
  `test_array_index_is_epsilon_floor_not_truncation()`,
  `test_array_size_clamps_to_the_official_ceiling()`, and
  `test_op_array_multidim_pops_exactly_two_indices()`

## Strings, scope, and writes

`starts` and `ends` compare without regard to case. Thus
`"Login".starts("login")` is true.

Inside nested `with` blocks, `this` resolves to the innermost target that is
not the player object. A player target is skipped while searching outward.
`thiso` remains the script's original object.

Unqualified reads and writes inside `with` search from innermost to outermost,
but a target participates only when `has()` says the name exists. A missing
name falls through to temps, the script object, or globals instead of creating
an arbitrary member on the `with` target. This existence gate applies to
unqualified scope resolution. An explicit `obj.name = value` reference writes
that member directly.

Evidence:

- `reborn_protocol/gs2/vm.py`, `_op_obj_starts()`, `_op_obj_ends()`,
  `_current_this()`, `_lookup()`, and `_assign_name()`
- `tests/test_gs2_vm.py`, `test_starts_ends_are_case_insensitive()`,
  `test_this_rebinds_to_innermost_with_target()`,
  `test_this_rebinding_skips_player_target()`, and
  `test_with_assignment_only_writes_object_that_has_name()`

## Anonymous function assignments

An anonymous function expression assigned to a member is not stored as a
function value in bytecode. The compiler:

1. hoists the body into a public script function with a generated name;
2. emits a read of `this.<generated-name>`; and
3. assigns that read's result to the destination member.

The VM recognizes a missing member named in its function table and returns a
`GS2ScriptFunction`. A real stored member wins over this fallback. Because a
construction block can rebind `this`, this also assigns event handlers such
as `onAction` to the control under construction.

Evidence:

- `reborn_protocol/gs2/vm.py`, `_ScriptFnRef`, `script_function()`, and
  `_op_member_access()`
- `tests/test_gs2_script_functions.py`,
  `test_lambda_bytecode_calls_reach_the_hoisted_functions()`,
  `test_this_read_of_generated_name_yields_a_callable()`,
  `test_stored_member_value_wins_over_the_function_fallback()`, and
  `test_fallback_follows_with_block_this_rebinding()`

## Cooperative sleep and resumption

Client event dispatch uses `GS2VM.iter_call()`. A positive `OP_SLEEP` delay
yields to the client scheduler. The generator retains the program counter,
operand stack, arguments, temporary members, `with` stack, and register file.
Nested calls use `yield from`, so the whole call chain suspends.

`ClientGS2.process_coroutines()` subtracts elapsed frame time and resumes a
generator when its delay expires. New events for a suspended script queue
until the active event finishes. The instruction budget resets after a
positive sleep.

The synchronous `GS2VM.call()` interface cannot expose a yield. In that mode
`_op_sleep()` delegates timing to `GS2Host.sleep()` and continues.

Evidence:

- `reborn_protocol/gs2/vm.py`, `_execute()`, `_gcall_script()`,
  `iter_call()`, and `_op_sleep()`
- `pyReborn/pyreborn/gs2_client.py`, `ClientGS2._drive()` and
  `ClientGS2.process_coroutines()`
- `tests/test_gs2_sleep_resume.py`, which verifies retained state, nested
  suspension, synchronous fallback, and budget reset

## Host calls, coverage, and inert policy

Language operations run in the VM, while client integration crosses a host
boundary. A **host call** is a global function or object method offered to
`GS2Host.call_builtin()` with normalized arguments and an optional target.
Object lookup, construction, shared globals, and synchronous sleep are also
host services.

`GS2ClientHost` handles GS2 behavior first, then delegates compatible calls
to the GS1 client host. `NOT_HANDLED` means neither layer owns a call. The VM
records the missing name, logs it once, and returns a neutral numeric value
so one unsupported call does not terminate the event.

`GS2VM.coverage_report()` returns implemented and observed opcodes, observed
but unimplemented opcodes, skipped execution counts, handled host-call
counts, and missing host-call counts. `coverage_summary()` renders the
actionable subset. Call `reset_coverage()` before an isolated measurement
because accounting is aggregated across VM instances.

Some calls are accepted and deliberately inert. This is policy, not backlog.
Server-provided scripts may not read, change, derive, or transmit credentials;
initiate arbitrary network destinations or remote-control sessions; open
external applications; synthesize input; expose stable device identity; or
take over platform-owned connection and patching flows. Polling calls receive
safe completion constants where needed to terminate; other inert calls
receive a neutral value.

Evidence:

- `reborn_protocol/gs2/vm.py`, `GS2Host`, `_call_target()`,
  `coverage_report()`, and `coverage_summary()`
- `pyReborn/pyreborn/gs2_client.py`, `GS2ClientHost.call_builtin()`,
  `host_surface()`, `stubbed`, and `_PATCHER_STUB_VALUES`
- `pyReborn/pyreborn/game/gs2_gui.py`, whose GUI objects and methods are part
  of the host surface even when calls bypass `call_builtin()`
