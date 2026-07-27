# GS1 language and interpreter

`reborn-protocol` implements the GS1 lexer, parser, value policy, and
tree-walking interpreter. Client and server repositories provide different
hosts around that shared language core.

## Era dialect

Later GS1 content mixes the classic command language with syntax conventions
also seen in GS2. Function declarations may name parameters, and calls may
pass arguments:

```text
function add(a, b) {
  this.total = a + b;
}
add(3, 4);
```

Parameters temporarily bind bare variables for the duration of the call and
restore the prior values afterward. User functions still have no value return;
a call in value position produces `0.0`.

Functions named by GS2 event convention also receive classic events:
`onTimeout`, `onPlayerEnters`, and `onActionX` match `timeout`,
`playerenters`, and `actionx` without regard to case. Classic
`if (playerenters)` blocks continue to work.

Evidence:

- `reborn_protocol/gs1/parser.py:261-275,300-353`
- `reborn_protocol/gs1/interp.py:246-280`
- `reborn-protocol/tests/test_gs1_era_newgs1.py:30-69`

`@` concatenates values as text. Assignment is right-associative across a
chain, so `a = b = false` writes both targets. The parser also accepts method
calls on references and call results. Implemented string and list methods
include `tokenize`, `pos`, `starts`, `ends`, case conversion, trimming,
length/index/slice operations, and mutating list operations such as `add`.
An unknown method is inert rather than invalidating its enclosing script.

Evidence:

- `reborn_protocol/gs1/lexer.py:43-53`
- `reborn_protocol/gs1/parser.py:300-315,520-601`
- `reborn_protocol/gs1/interp.py:832-905`
- `reborn-protocol/tests/test_gs1_era_newgs1.py:92-139`

Classic commands retain their space form, but may also use call form:
`triggeraction(0, 0, "serverside", "-System", "x")` and
`enableweapons()` parse through the command's existing typed argument
signature. Quoted call-form strings lose their quotes; whitespace separates
arguments rather than becoming string content.

`setTimer(value)` maps to assignment of the classic `timeout` variable. It
therefore uses the host's normal scheduling hook, including the rule that a
value less than or equal to `0.0001` cancels the timer.

Evidence:

- `reborn_protocol/gs1/lexer.py:773-817`
- `reborn_protocol/gs1/interp.py:246-255,808-826`
- `reborn-protocol/tests/test_gs1_era_newgs1.py:71-90,141-150`
- `Preagonal/FourPlay/quattroplay/src/TScriptSpace.cpp:121-129`

## Recovery policy

Live scripts contain harmless surplus syntax. Empty statements are ignored,
including an extra semicolon between an `if` branch and its `else`. A stray
top-level closing brace is skipped. An unclosed block at end of source is
tolerated.

Malformed input is contained to its failed statement. Recovery consumes to
that statement's semicolon, balanced block end, or end of file. If the failed
head owns a block, the entire balanced block is skipped so its body cannot be
promoted to the enclosing scope. A junk character likewise produces at most
one parse error and drops one statement; later statements still parse and
execute.

Evidence:

- `reborn_protocol/gs1/parser.py:49-77,103-132,134-160,203-222`
- `reborn_protocol/gs1/lexer.py:463-477,684-689`
- `reborn-protocol/tests/test_gs1_parser_recovery.py:69-120`
- `reborn-protocol/tests/test_gs1_parser_recovery.py:147-166,224-230`
