# GS2 GUI control surface — core-5 audit

Spec fragment for `reborn-protocol-docs/docs/implementation/gs2-name-surface.md`
("GUI controls (sampled)" section). Closes `GuiWindowCtrl`, `GuiButtonCtrl`,
`GuiButtonBaseCtrl`, `GuiTextEditCtrl`, `GuiTextCtrl`.

Oracle root: `/home/hosler/Projects/opengraal2/Preagonal/FourPlay/quattroplay/`
(paths below are relative to it unless prefixed). Diff target:
`/home/hosler/Projects/opengraal2/pyReborn/pyreborn/game/gs2_gui.py`.

Every `file:line` below was opened and read. Where a body was not recovered or
not read, it says so instead of asserting semantics.

---

## 0. Method/property lookup is case-INSENSITIVE — value comparisons are not

`THashList::getHashcode` folds `A-Z` to lower case while hashing
(`src/THashList.cpp:307-310`), and every property/func table is stored in that
hash list. So `canClose`, `canclose`, `setSelection`, `alwaysOnTop` all resolve.
The corpus relies on this: it writes `buttonType`, `groupNum`, `maxLength`,
`clientRelative` in camel case throughout.

This matters because it is **asymmetric**: see finding C1 (`buttontype`'s
*value* is compared with `memcmp`, case-sensitively).

Child-replaces-parent is confirmed at `src/TProperties.cpp:117-128`
(`getObjectEncoded` → `removeObjectEncoded` → `addObjectEncoded` per child
entry, after `Assign(parentProperties, …)` at `:112`).

## 0b. Table-entry counts (declared array sizes, all literal)

| Class | props | funcs | parent | ctor |
| --- | ---: | ---: | --- | --- |
| `GuiWindowCtrl` | 16 (`0x10`) | 4 | `GuiControl` | `src/gui/GuiWindowCtrlProperties.cpp:227` |
| `GuiButtonCtrl` | 1 | 1 | `GuiButtonBaseCtrl` | `src/gui/GuiButtonCtrlProperties.cpp:45` |
| `GuiButtonBaseCtrl` | 4 | 2 | `GuiControl` | `src/gui/GuiButtonBaseCtrlProperties.cpp:129` |
| `GuiTextEditCtrl` | 7 | 2 (+1 **global**) | `GuiTextCtrl` | `src/gui/GuiTextEditCtrlProperties.cpp:57` |
| `GuiTextCtrl` | 2 | 2 | `GuiControl` | `src/gui/GuiTextCtrlProperties.cpp:78` |

**41 own entries total**, plus one global function that lives in
`GuiTextEditCtrl.cpp` (§4.4).

**Parent chains verified clean of both chain-modifying mechanisms.** Neither
`propertyStrings` (the *removal* list — `removeObjectEncoded`,
`src/TProperties.cpp:147`) nor `addPropertyObject` (real delegation, walked by
`TGraalVar::getProperty`) is used by any of the five classes here or by
`GuiControl`: a whole-tree grep finds them only in
`src/gui/GuiShowImgCtrlProperties.cpp:80-84` (which deletes
`red,green,blue,alpha,mode,style,rotation` from what it would inherit),
`src/gui/GuiShowImgCtrl.cpp:83`, `src/gui/GuiContextMenuCtrl.cpp:158` and
`src/gui/GuiPopUpMenuCtrl.cpp:93`. So for these five, "inherited" really does
mean inherited and the §0c `GuiControl` surface is granted in full.

> **Brief-vs-code conflict, reported not guessed:** the task sheet said
> `GuiButtonBaseCtrl` has "17 table entries". Its tables are `propDefs[0x4]`
> and `funcDefs[0x2]` — **6**, and no corpus file names the type at all
> (0 files; its subclasses account for 45). I audited what the file says.

**Every setter in all five tables is non-null: there is not one read-only
property in the core five.** The `nullptr`-setter hazard lives entirely in the
inherited `GuiControl` table, which has exactly two: `awake`
(`src/gui/GuiControlProperties.cpp:651`) and `parent` (`:683`).

## 0a. Oracle scope: FourPlay's silence is NOT proof of absence

FourPlay/quattroplay decompiles a **smaller client binary** than the one
Login's content targets. Cross-checking the Era macOS client's symbol dump
(`Preagonal/graal-revlib-osx/docs/symbol_dump.log`) against FourPlay's
`src/gui/` shows **43 Era `Gui*` translation units vs 29 in FourPlay**.

For this audit the news is mostly good and partly bad:

- **Good:** all five of my classes exist as translation units in *both* builds
  (`_GLOBAL__sub_I_GuiWindowCtrl.cpp` at `symbol_dump.log:4905`,
  `GuiTextEditCtrl.cpp` at `:4443`, plus `GuiButtonCtrl.cpp`,
  `GuiButtonBaseCtrl.cpp`, `GuiTextCtrl.cpp`). They are in the intersection, so
  the coverage risk here is about *members*, not about whole classes going
  missing the way `GuiTabCtrl`/`GuiTreeViewCtrl` do.
- **Bad, and it lands inside my text family:** **`GuiAccountPasswordCtrl` and
  `GuiMLTextEditCtrl` exist in Era and are absent from FourPlay entirely** — no
  source file, no header, no `TObjectCreator` entry (a whole-tree grep for
  `AccountPassword`/`MLTextEdit` under `src/` and `include/` returns nothing).
  **9 corpus files `new GuiAccountPasswordCtrl(…)`** — it is Login's actual
  password field (`graal-loginserver/weapons/weapon-Rescripted_IRC_Login2.txt:235`,
  `weapon-Rescripted_IRC_Login2001.txt:414`). See §6.

The Era dump cannot settle *member* questions: it is a symbol list with
obfuscated identifiers, and property names live in `.data` string literals, not
in symbols. So it can prove a class exists and can never prove a property name
does or doesn't. §5 is written with that limit in mind.

## 0c. Inherited `GuiControl` surface (already audited; recorded for the chain)

`GuiControlProperties::propDefs[0x37]` = **55** properties
(`src/gui/GuiControlProperties.cpp:646-702`), `funcDefs[0x1c]` = **28** methods
(`:864-893`). Two details from re-reading it that the previous wave did not
record and that bite the classes below:

- **`minsize` is a pure alias of `minextent`** — identical getter *and* setter
  pointers (`:681` vs `:682`).
- **`canmove`, `resizewidth`, `resizeheight` are declared on `GuiControl`
  too**, backed by `m_guiControl_unknown47/52/53`
  (`:91-99`, `:437-455`). `GuiWindowCtrl` redeclares all three against
  *different* storage — see C2.

---

## 1. Counter-intuitive findings (lead with these)

**C1. `buttontype`'s value comparison is case-SENSITIVE, and an unknown value
is silently ignored.** The setter loops the three literals
`"PushButton"/"ToggleButton"/"RadioButton"`
(`src/gui/GuiButtonBaseCtrlProperties.cpp:5-9, 16-26`) using `TString`
`operator==`, which is `memcmp` after a length check
(`src/TString.cpp:849-859`). No match ⇒ **the loop just ends; the old value
stands and nothing is reported.** So `buttontype = "pushbutton"` is a no-op
while the *name* `buttonType` resolves fine (§0). The corpus always writes the
exact-case forms (`weapon-Rescripted_Serverlist.txt:1018` etc.), so a
case-insensitive implementation is harmless in practice but a
case-sensitive-with-silent-reject one is what the reference does.

**C2. `canmove` / `resizewidth` / `resizeheight` mean different things on a
window than on any other control.** `GuiWindowCtrl` declares its own
`m_canMove`, `m_resizeWidth`, `m_resizeHeight` fields
(`include/gui/GuiWindowCtrl.h:30-32`) and redeclares all three property names
against them (`src/gui/GuiWindowCtrlProperties.cpp:203-205, 16-44`). Child wins
(§0), so on a window `GuiControl`'s copies become **unreachable from script**.
Only the window's `m_canMove` gates title-bar dragging
(`src/gui/GuiWindowCtrl.cpp:272-276`).

**C3. `maximized = true` twice UNMAXIMIZES. Same for `minimized`, and for the
`maximize()`/`minimize()` methods.** The setters call
`maximizeWindow()`/`minimizeWindow()` on a truthy write
(`GuiWindowCtrlProperties.cpp:137-156`), and those functions **restore** when
the window is already in that state (`GuiWindowCtrl.cpp:169-173`, `:151-155`).
They are toggles, not idempotent setters. `restore()` is the only idempotent
one.

**C4. `close()` ignores `canclose`.** `canclose` only gates the title-bar
button hit-tests (`GuiWindowCtrl.cpp:253-258, 312-316`); the script method goes
straight to `closeWindow()` (`GuiWindowCtrlProperties.cpp:181-184`). And
`closeWindow()` does **not** close when `closequery` is set — it fires
`onCloseQuery` and returns, leaving the window visible
(`GuiWindowCtrl.cpp:136-142`). With `destroyonhide` it hides *and* destroys the
script variable (`:144-146`).

**C5. `maxchars` silently truncates every write to `.text`, on labels *and*
edit fields, and it defaults to 255.** `GuiTextCtrl::initObject` sets it to 255
(`src/gui/GuiTextCtrl.cpp:27`); `setText` clips with `subString(0, maxchars)`
when the incoming text is longer (`:178-184`). `setText` is virtual
(`include/gui/GuiTextCtrl.h:22`) and `GuiTextEditCtrl` overrides it by
delegating back through `setTextKeepCursor` → `GuiTextCtrl::setText`
(`src/gui/GuiTextEditCtrl.cpp:1072-1079`), so the clip applies to text edits
too. `maxchars <= 0` disables it.

**C6. `password` and `inputtype` are the same storage under two names — but
*not* a table-level alias.** `getPasswordText()` is literally
`m_inputType == "password"` (`GuiTextEditCtrl.cpp:319`) and
`setPasswordText(false)` writes `"default"`, **not** the previous input type
(`:309-316`). So `pass = true; pass = false` destroys a custom `inputtype`.
A pointer-equality alias sweep (the technique that found `head`/`headimg`)
misses this one: the four function pointers are all distinct
(`GuiTextEditCtrlProperties.cpp:39-45`).

**C7. `.text = x` and `.settext(x)` differ on a text edit.** The `text`
property setter additionally zeroes the two selection anchors
(`GuiTextEditCtrlProperties.cpp:31-36`); the inherited `settext` method
(`GuiTextCtrlProperties.cpp:30-33`, not redeclared by the edit control) reaches
the same virtual `setText` but leaves the selection intact.

**C8. `setselection(a, b)` with `b < a` zeroes BOTH ends — it does not swap
them** (`GuiTextEditCtrl.cpp:216-220`). It also clamps `a < 0 → 0`, `b > len →
len`, and moves the cursor to `b` (`:209-224`). **Our `_m_setselection` swaps
(`gs2_gui.py:1910`) — that is a behavioural WRONG, see §6.**

**C9. `undo()` is a toggle (undo/redo), not a stack pop.** It swaps the live
text/selection with the single saved slot (`GuiTextEditCtrl.cpp:103-118`), so
calling it twice returns to where you started.

**C10. `historysize` evicts from opposite ends depending on how you shrink it.**
Overflow during normal use drops the **oldest** entry (`Delete(0)`,
`GuiTextEditCtrl.cpp:257`); assigning a smaller `historysize` drops the
**newest** ones (`Delete(length-1)`, `:280`). Default is 0
(`:341`), and `updateHistory` only early-outs when it is **negative** (`:238`).

**C11. `seticonsize(w,h)` creates a script-visible child object named `icon`.**
It allocates a `TDrawingPanel` named `"icon"`
(`src/gui/GuiButtonCtrl.cpp:324-326`; the first ctor arg is the object name,
`src/TDrawingPanel.cpp:34`) and registers it in the button's `vars` hash
(`GuiButtonCtrl.cpp:348-350`), which is exactly the named-member store consulted
during member resolution (`src/TGraalVar.cpp:935-937`). So `seticonsize` is the
*constructor* for `button.icon`, and `w`/`h` are clamped to `[0,64]`; `w<=0`,
`h==0` or `h<0` **destroys** the panel instead (`:308-320, 358-383`). Our
implementation already answers `button.icon` lazily
(`gs2_gui.py:971-976`) — this confirms that guess against the oracle.

**C12. A radio button's exclusivity is enforced only on user activation, never
on a script write.** `setChecked` just stores + repaints
(`src/gui/GuiButtonBaseCtrl.cpp:42-46`). The sibling sweep that clears other
`buttontype==RadioButton` controls with the same `groupnum` lives in
`onAction()` (`:68-90`), which runs from mouse-up / Enter / Space / hotkey
(`:151-152`, `:232-237`). `btn.checked = true;` from script leaves every
sibling checked.

**C13. `&` in a button's text is a hot-key marker,** and `&`/`_` are excluded
from being hot keys themselves (`GuiButtonBaseCtrl.cpp:196-224`). The
`text[markerIndex + 2]` at `:221` **looks like an off-by-one and is not**:
`TString::indexOf` is 0-based (`src/TString.cpp:702-711`) while
`TString::operator[]` is **1-based** (`:689-698`), so `+2` is the character
directly after the `&`. Verified against the assembly
(`asm/gui/GuiButtonBaseCtrl/_ZN17GuiButtonBaseCtrl8isHotKeyERK7TString.s_decomped`,
`lea 0x2(%rax),%esi` into `_ZN7TStringixEi`) — the C++ transcription is
faithful. Comparison is `equalsIgnoreCase`.

**C14. `GuiWindowCtrl` has NO assembly backing in this checkout.** `find asm -iname '*GuiWindowCtrl*'`
and `grep -rl GuiWindowCtrl asm/` both return nothing, while every other class
here has an `asm/gui/<Class>/` directory. The class is real (script-creatable,
`TObjectCreator("GuiWindowCtrl", …)` at `src/TInitStatics.cpp:5564`), but
`src/gui/GuiWindowCtrl.cpp` is stylistically a hand-written reimplementation
(anonymous-namespace `pointInRect` helper, `= default`, `override`, no
`/* Class::method() */` Ghidra banners — contrast `GuiButtonCtrl.cpp:38, 63, 88`).
**Treat §2's behaviour as strong-but-unverifiable and the table (§2 props/funcs)
as authoritative.** Concretely, `resizewidth`, `resizeheight`, `edgesnap`,
`cancollapse`, `tile` and `buttonoffset` are *stored and never read* anywhere in
the recovered body — plausible for a decompilation gap, but I cannot rule out
that edge-drag resizing simply is not modelled here.

**C15. Six names the corpus writes on these controls are registered NOWHERE in
the reference.** See §5 — `maxlength` (13 files) and `clientrelative`
(16 files) are the big ones.

---

## 2. `GuiWindowCtrl` — chain: GuiWindowCtrl → GuiControl → TGraalVar

Table: `src/gui/GuiWindowCtrlProperties.cpp:201-225`. All 16 properties are
read/write. Bodies are at `:6-179` in the same file and were all read.

| Property | T | R/W | Semantics (read) | Scripts |
| --- | --- | --- | --- | ---: |
| `text` | s | RW | Title-bar text; setter repaints. **Default `"New Window"`**, not `""` (`GuiWindowCtrl.cpp:71`) — a T1-class seeded string. | 22 |
| `canclose` | b | RW | Show/enable the close button; setter re-runs `positionButtons()` + repaint (`:51-56`). Does **not** gate `close()` (C4). | 15 |
| `canmaximize` | b | RW | ditto for the maximize button (`:75-80`). | 14 |
| `canminimize` | b | RW | ditto for the minimize button (`:63-68`). | 13 |
| `canmove` | b | RW | Title-bar drag; window-local field, shadows `GuiControl.canmove` (C2). | 9 |
| `tile` | b | RW | Stored + repaint (`:163-167`); no reader in the recovered body. | 5 |
| `destroyonhide` | b | RW | `closeWindow()` destroys the script variable after hiding (`GuiWindowCtrl.cpp:145-146`). | 4 |
| `closequery` | b | RW | `closeWindow()` fires `onCloseQuery` and does **not** hide (C4). | 2 |
| `maximized` | b | RW | Read: current state. Write: toggle (C3). | 2 |
| `minimized` | b | RW | Read: current state. Write: toggle (C3). | 0 |
| `resizewidth` | b | RW | Stored; **no reader in the recovered body** (C14). Shadows `GuiControl.resizewidth`. | 0 |
| `resizeheight` | b | RW | Stored; same caveat. | 0 |
| `cancollapse` | b | RW | Stored; no reader. Default `false` (`GuiWindowCtrl.cpp:45`). | 0 |
| `edgesnap` | b | RW | Stored; no reader. Default `true` (`:49`). | 0 |
| `closecommand` | s | RW | Stored string; no consumer in the recovered body. | 0 |
| `buttonoffset` | s | RW | `TPoint` as a string; setter re-runs `positionButtons()` + repaint (`:174-179`). Default `"0 3"` (`:64`). | 0 |

Methods (`:220-225`), all `'v'`, all zero-arg params `""`:
`close` (C4), `minimize` (toggle), `maximize` (toggle), `restore`.
**Zero corpus call sites for any of the four** (a `.close(`/`.minimize(`/…
sweep over all six corpora found none).

Constructor defaults worth copying (`GuiWindowCtrl.cpp:34-76`): extent
`100 × 200`, `minExtent = (50, titleHeight)`, **`titleHeight = 24`**,
`buttonOffset = (0,3)`, buttons `16×16` laid right-to-left in 18 px steps from
`extent.x - buttonOffset.x - 18` (`:99-132`), `standardBounds = (0,0,100,200)`,
`resizeMargin = 5.0`, `canClose/canMinimize/canMaximize/canMove/edgeSnap = true`,
`canCollapse/canDock/closeQuery/destroyOnHide/tile = false`.
`resize()` clamps the extent up to `minExtent` and re-runs `positionButtons()`
(`:331-341`).

Events fired: `onCloseQuery`, `onMinimize`, `onMaximize`, `onRestore` (all
zero-arg), plus `onMouseDragged` while the title bar drags
(`:139, 163, 182, 197, 289`).

`m_canDock` exists as a field (`GuiWindowCtrl.h:37`) with **no** registered
property name.

## 3. The button family

### 3.1 `GuiButtonBaseCtrl` — chain: → GuiControl → TGraalVar

Table `src/gui/GuiButtonBaseCtrlProperties.cpp:68-126`, bodies `:11-66`.
`GuiCheckBoxCtrl` and `GuiRadioCtrl` add **nothing at all** — both
`*Properties.cpp` files are a bare constructor
(`src/gui/GuiCheckBoxCtrlProperties.cpp:3-5`,
`src/gui/GuiRadioCtrlProperties.cpp:3-5`) — so this table *is* the whole
checkbox/radio/button-specific surface.

| Property | T | R/W | Semantics | Scripts |
| --- | --- | --- | --- | ---: |
| `text` | s | RW | Button caption; setter repaints (`GuiButtonBaseCtrl.cpp:48-52`). May embed a `&` hot-key marker (C13). | 22 |
| `checked` | b | RW | Toggle/radio state; setter repaints only, **no group exclusivity** (C12). | 9 |
| `groupnum` | i | RW | Radio group id, default **-1** (`:33`). Only consulted in `onAction`'s sibling sweep. | 8 |
| `buttontype` | s | RW | `"PushButton"`(0, default) / `"ToggleButton"`(1) / `"RadioButton"`(2). Case-sensitive, silent reject (C1). | 2 |

Methods (`:107-126`): `gettext() -> 's'`, params `""`; `settext(s) -> 'v'`,
params `"s"`. Both are thin wrappers over the same `get/setText`.
**Zero corpus call sites for either.**

Behaviour an implementer needs (`GuiButtonBaseCtrl.cpp`): `onAction` no-ops when
`active` is false (`:61-62`); ToggleButton flips `checked` (`:64-67`);
RadioButton sets itself and clears same-`groupnum` RadioButton siblings
(`:68-90`) — real scripts know exclusivity is click-only and clear siblings by
hand (`graal-loginserver/weapons/weapon-Rescripted_IRC_Login2.txt:48-49`);
then `GuiControl::onAction()` fires the `onAction` event
(`src/gui/GuiControl.cpp:284-292`). Activation sources: mouse-up while pressed
(`:151-152`), Enter (`0x0d`) or Space (`0x20`) on key-up (`:232-237`), and the
hot-key accelerator (`:296-311`). Arrow keys tab between controls (`:271-285`).

### 3.2 `GuiButtonCtrl` — chain: → GuiButtonBaseCtrl → GuiControl → TGraalVar

Table `src/gui/GuiButtonCtrlProperties.cpp:20-42`.

| Member | T | params | R/W | Semantics | Scripts |
| --- | --- | --- | --- | --- | ---: |
| `stylesection` | s | — | RW | Style-sheet section name; empty ⇒ `"Buttons"` (`GuiButtonCtrl.cpp:191-195`). A value starting `"Taskbar.Button"` picks render mode 6 instead of 5 (`:201-205`). If the button's *text* is empty and the lower-cased section contains `"startbutton"`, the drawn label becomes `"Start"` (`:159-166`). | 5 |
| `seticonsize` | v | `"ii"` | — | See C11. | 0 |

Constructor default extent is **140 × 30** (`GuiButtonCtrl.cpp:57-58`).
Icon layout, for reference: with text, the icon is drawn at `x + iconWidth + 2`
and the text inset by `iconWidth + 4`; without text the icon is centred
(`:259-279`). A pressed button shifts its content by `(+1,+1)` (`:253-257`).

## 4. The text family

### 4.1 `GuiTextCtrl` — chain: → GuiControl → TGraalVar

Table `src/gui/GuiTextCtrlProperties.cpp:35-75`.

| Member | T | params | R/W | Semantics | Scripts |
| --- | --- | --- | --- | --- | ---: |
| `text` | s | — | RW | See C5 (truncation) and below. | 21 |
| `maxchars` | i | — | RW | Character cap, **default 255** (`GuiTextCtrl.cpp:27`). Raw field read/write, no validation. | 2 |
| `gettext` | s | `""` | — | `getText()`. | 0 |
| `settext` | v | `"s"` | — | `setText()`. Virtual ⇒ dispatches to `GuiTextEditCtrl::setText` on an edit control. | 0 |

`setText` semantics (`GuiTextCtrl.cpp:170-199`), all four steps matter:
1. **Early-out when the text is unchanged** — no event, no repaint (`:172-176`).
2. Clip to `maxchars` (C5).
3. Fire `onTextChanged` **on the control**, one `'s'` param = the *clipped*
   text (`:190-193`).
4. `updateTextSize()` then repaint. `updateTextSize` **resizes the control** when
   the profile has `autosizewidth` / `autosizeheight`: width from
   `profile->getTextWidth(text)` (+2 px if the font style contains `'i'`), height
   `getTextHeight() + 4` (`:208-246`). Also re-runs on `onWake` (`:249-256`).
   So on an autosizing profile, assigning `.text` changes `.width`/`.height`.

### 4.2 `GuiTextEditCtrl` — chain: → GuiTextCtrl → GuiControl → TGraalVar

Table `src/gui/GuiTextEditCtrlProperties.cpp:38-46`, bodies `:5-36`.
Note it inherits `maxchars`, `gettext`, `settext` from `GuiTextCtrl` and
redeclares only `text`.

| Property | T | R/W | Semantics | Scripts |
| --- | --- | --- | --- | ---: |
| `text` | s | RW | `setText` (cursor → end, `GuiTextEditCtrl.cpp:1072-1076`) **plus** clearing both selection anchors (C7). | 21 |
| `password` | b | RW | Derived from `inputtype` (C6). | 16 |
| `historysize` | i | RW | Recall-buffer size; setter is `setHistorySize` (C10), no-op if unchanged (`:272-273`). Getter is the raw field. Default 0 (`:341`). | 13 |
| `tabcomplete` | b | RW | Raw field, default `false` (`:331`). No consumer in the parts of the body I read (`:1-135`, `:205-364`, `:770-795`, `:1040-1082`) — **not asserted either way**. | 5 |
| `inputtype` | s | RW | **Default `"default"`** (`:337`) — another seeded string. Setter no-ops if unchanged, else repaints (`:290-297`). Its recovered use is the mobile virtual keyboard: `openVirtualKeyboard(text, inputType)` (`:776`). | 0 |
| `showcursor` | b | RW | Raw field, default `true` (`:347`). | 0 |
| `deniedsound` | s | RW | Raw string field; **no consumer in the parts I read** — recorded as type + R/W only. | 0 |

Methods (`:52-55`):

| Method | ret | params | Semantics | Scripts |
| --- | --- | --- | --- | ---: |
| `setselection` | v | `"ii"` | C8. | **5** |
| `undo` | v | `""` | C9. | 0 |

`setselection` is the only method in this whole audit the corpus actually
calls: `ChatBar.setSelection(` / `ChatBar3D.setSelection(` in 5 files.

Constructor defaults (`:322-350`): selection `(0,0)`, cursor `0`,
`inputType="default"`, `showcursor=true`, `tabcomplete=false`, `historysize=0`.
`onLoseFirstResponder` pushes the current text into the history (`:1063-1069`).

**Unrecovered:** `GuiTextEditCtrl` declares no `onKeyDown`
(`include/gui/GuiTextEditCtrl.h` has only `setText`/`setTextKeepCursor` in the
virtual set) and none exists in `asm/gui/GuiTextEditCtrl/`. **When Enter fires
`onAction` on a text edit is therefore not established by this checkout.** The
one path that provably fires it is §4.4.

### 4.3 Events on the text family

`onTextChanged` (control, 1 string param) — §4.1.
`onAction` (control, 1 string param) — only via `setEditedText(text, true)`
(`GuiTextEditCtrl.cpp:96-97`).
`onTextEditStart` — fired on the **universe**, not the control, with one `'o'`
param = the control, on mouse-down (`:779-784`). A global handler, easy to miss.

### 4.4 A GLOBAL function hiding in a control's file

`GuiTextEditCtrl.cpp:14-23` defines `funcDefs[0x1]` =
`{"adventure_settextedittext", 'v', params "os"}`, and it is installed with
`addFuncs(nullptr, …)` — i.e. onto the **global** name surface
(`src/TInitStatics.cpp:5500`), not onto the class. It calls
`setEditedText(text, true)`: set text (through the truncating `setText`), push
to history, fire `onAction` on the control, and drop first-responder
(`:89-100`). It is the programmatic "commit as if the user pressed Enter".
0 corpus uses; listed because a per-class table walk structurally cannot find it
and the previous wave's global-function count did not attribute it.

---

## 5. Bottom-up: what the corpora actually write

Method: for each control class, every `new Gui<X>(…) { … }` construction block
in `Preagonal/graal-{lttp,loginserver,loginserver-dev,loginserver-mobile,
bomber-gs2,gta}` was parsed and its top-level `name =` assignments tallied by
distinct file (`weapon_bytecode/` excluded — those are compiled duplicates of
the same scripts and inflate every count by ~4×).

Ranked, own-table members only (inherited `GuiControl` geometry/`profile`
dominate everything and are already implemented):

- **`GuiWindowCtrl` (22 files):** `text` 22, `canclose` 15, `canmaximize` 14,
  `canminimize` 13, `canmove` 9, `tile` 5, `destroyonhide` 4, `closequery` 2,
  `maximized` 2. The other 7 properties and all 4 methods: **zero**.
- **`GuiButtonCtrl` (22):** `text` 22, `stylesection` 5, `groupnum` 2,
  `buttontype` 2. `seticonsize` never called (but `icon.drawimage*` is used in
  construction blocks — our lazy `icon` covers it).
- **`GuiTextCtrl` (21):** `text` 21, `maxchars` **0**.
- **`GuiTextEditCtrl` (21):** `text` 21 (6 in construction blocks),
  `password` 16, `historysize` 13, `tabcomplete` 5, `setselection` 5.
  `inputtype`, `showcursor`, `deniedsound`, `undo`: **zero**.
- **`GuiCheckBoxCtrl` (11) / `GuiRadioCtrl` (6):** only `text` and `groupnum`
  (6 files) from the base table.

### Names scripts write that FourPlay does not register

Checked case-insensitively across the whole of FourPlay's `src/` and
`include/`. **Read this table as "absent from FourPlay", not "absent from the
real client"** (§0a): the Era build has 14 more GUI classes and its symbol dump
cannot confirm or refute a property name. Where a stronger argument than
FourPlay's silence exists, the Verdict column says so — the durable one is
**write-only**: a name no script ever reads back is inert no matter which
client registers it.

| Name | Files | Verdict |
| --- | ---: | --- |
| `clientrelative` | 16 (window blocks) | Absent from FourPlay. **Write-only** — always `= true`, always beside the real `clientextent`, and a `.clientrelative` read sweep over all six corpora returns **0 hits**. Inert either way. |
| `maxlength` | 13 (8 text, 5 edit) | Absent from FourPlay; the FourPlay name is `maxchars`. **Behaviour-identical either way**: every corpus write is `255`, which is `maxchars`' own default (`GuiTextCtrl.cpp:27`), so whichever name the Era build registers, the resulting cap is 255. |
| `isexternal` | 10 (window blocks) | Registered in FourPlay, but on **`TServerPlayer`** (`src/TServerPlayerProperties.cpp:501`), not on any GUI class. **Write-only on windows**: the only `.isexternal` reads in the corpora are `GraalShop.isexternal` (5), a different object. |
| `helptag` | 2+2 | Absent from FourPlay; write-only in the corpora. Torque leftover. |
| `command` / `altcommand` | 2 / 2 | Absent from FourPlay's GUI classes; write-only in the corpora. |
| `editable` | 2 (edit blocks) | Absent from FourPlay; write-only. A plausible Era-only text-edit property — if any capture ever shows a read-only edit field, look here first. |
| `title` | 1 (window) | Absent from FourPlay; the window's title is `text`. Write-only. |
| `horzsizing` | 3 (window) | Typo for `horizsizing`. Corpus bug; falls through in the reference too. |
| `normalbitmap`, `mouseoverbitmap`, `pressedbitmap` | 2 each, on **`GuiButtonCtrl`** | Registered on `GuiBitmapButtonCtrl` (`src/gui/GuiBitmapButtonCtrlProperties.cpp:42, 51, 60`), whose chain is `→ GuiButtonBaseCtrl`, **not** through `GuiButtonCtrl`. Set on a plain button they are inert. |
| `parsetags` | 1 (button) | Registered on `GuiMLTextCtrl` (`src/gui/GuiMLTextCtrlProperties.cpp:314`). Inert on a button. |

None of these is evidence that I read the wrong table: each is absent from a
case-insensitive whole-source grep of FourPlay, and each is **write-only in the
corpora**, so none can change a script's behaviour through a read. The
actionable consequence for us is only about the existence gate (§6): claiming
them is harmless, not claiming them loses a write nothing reads.

---

## 6. Diff vs `pyReborn/pyreborn/game/gs2_gui.py`

Our `GuiControl._TORQUE_PROPS` is an *existence gate*: a construction-block
field only lands on the control if `has()` claims the name
(`gs2_gui.py:841-863`). So "MISSING" below means the write is silently lost.

### `GuiWindowCtrl` (`gs2_gui.py:1427-1538`)

| Member | Status | Note |
| --- | --- | --- |
| `text` | IMPLEMENTED | but default is `""`; reference seeds `"New Window"`. |
| `canclose` `canminimize` `canmaximize` `canmove` `closequery` `destroyonhide` | IMPLEMENTED | explicit get/set at `:1454-1467`; button layout at `:1469-1480` matches the oracle's 18 px right-to-left walk exactly. |
| `tile` | IMPLEMENTED (stored) | claimed in `_TORQUE_PROPS` (`:862`), inert — matches the reference's recovered body. |
| `maximized` `minimized` | **MISSING** | our fields exist (`:1450-1451`) but are not in `get`/`set`/`_TORQUE_PROPS`, so `win.maximized = true` is lost and the read is 0.0. 2 corpus files write `maximized`. Implement as the C3 toggle. |
| `resizewidth` `resizeheight` `cancollapse` `edgesnap` `closecommand` `buttonoffset` | MISSING | 0 corpus uses; store-only is enough. |
| `close` `minimize` `maximize` `restore` | **MISSING as script methods** | the Python methods exist (`close_window`/`minimize_window`/…) but are not in `_METHOD_NAMES`, so a script call returns 0.0. 0 corpus uses — low priority, cheap to wire. |
| `TITLE_H = 22` (`:1436`) | **WRONG vs oracle (24)** | Do **not** change it blind: the docstring at `:1430-1433` says 22 was derived from Login's own `y = -22` panel math, which is live-verified. Flagging the conflict only; it needs a render check, not an edit. |
| default extent `240×160` (`:1440`) | WRONG | reference is `100×200`, and `minExtent = (50, 24)` with the resize clamp (`GuiWindowCtrl.cpp:331-337`) is not modelled. |
| `maximize_window` (`:1507-1521`) | correct shape | matches `maximizeWindow` incl. the parent-size fallback. |

### `GuiButtonCtrl` / the button family (`gs2_gui.py:1591-1665`, `2014-2084`)

| Member | Status | Note |
| --- | --- | --- |
| `text` | IMPLEMENTED | base class. |
| `stylesection` | IMPLEMENTED (stored + used) | `:1608`, `:4200`; the `"startbutton"` → `"Start"` fallback at `:1605-1614` matches `GuiButtonCtrl.cpp:159-166`. |
| `checked` `groupnum` `buttontype` | **MISSING on `GuiButtonCtrl`** | we put `checked` on `GuiCheckBoxCtrl` only (`:2020-2035`); the oracle puts all three on `GuiButtonBaseCtrl`, i.e. also on `GuiButtonCtrl` **and** `GuiBitmapButtonCtrl`. `groupnum`/`buttontype` are absent everywhere. 8 and 2 corpus files respectively. |
| radio exclusivity (`:4072-4081`) | PARTIAL | we key it on `isinstance(…, GuiRadioCtrl)`; the oracle keys it on `buttontype == RadioButton` **and** equal `groupnum` (`GuiButtonBaseCtrl.cpp:82-87`). Our version also ignores `groupnum` entirely, so two independent radio groups in one parent would cross-clear. |
| `value` alias (`:2020`) | **EXTENSION** | `"value"` is registered nowhere under `src/gui/`. Harmless, but it is ours, not the reference's. |
| `gettext` `settext` | IMPLEMENTED | in `GuiControl._METHOD_NAMES` (`:869`). |
| `seticonsize` | IMPLEMENTED | `:866`; `icon` object at `:971-976` — oracle-confirmed (C11). Our clamp is not `[0,64]` and we never destroy the panel on `w<=0`. |
| default extent `100×24` (`:1600`) | WRONG | reference `140×30`. |

### `GuiTextCtrl` (`gs2_gui.py:1668-1691`)

| Member | Status |
| --- | --- |
| `text` | IMPLEMENTED |
| `maxchars` | **MISSING** (0 corpus uses, but it is what makes C5 observable) |
| truncation to 255 on `.text` writes | **MISSING** |
| unchanged-text early-out | MISSING |
| `onTextChanged` event | **MISSING** — I found no `ontextchanged` anywhere in `gs2_gui.py`. |
| autosize-on-set-text | MISSING for `GuiTextCtrl` (modelled only for `GuiMLTextCtrl`, `:1694-1699`) |
| default extent `100×16` (`:1675`) | no oracle default to compare — `GuiTextCtrl::initObject` sets none. |

### `GuiTextEditCtrl` (`gs2_gui.py:1885-1946`)

| Member | Status | Note |
| --- | --- | --- |
| `text` | IMPLEMENTED | but does not clear the selection on assignment (C7) and does not truncate (C5). |
| `setselection` | **WRONG** | `:1904-1911` clamps then **swaps** when `end < start`; the reference **zeroes both** (C8). A script doing `setSelection(5, 2)` gets a 2..5 selection from us and an empty one from the reference — and `take_selection()` (`:1916-1924`) would then delete text the reference would not. |
| `getselection` | **EXTENSION** | not in any reference table. Not in the corpus either. |
| `historysize` `tabcomplete` | claimed-but-inert (`_TORQUE_PROPS`, `:855`) | acceptable; 13 and 5 corpus files write them and nothing reads them back. |
| `password` | **MISSING as a property** | not in `_TORQUE_PROPS`, so under existence-gating `password = true;` in a construction block is **lost** — 16 corpus files write it, 8 of them inside a `new GuiTextEditCtrl{}` block. Masking today comes only from our `GuiAccountPasswordCtrl` subclass (`:1949-1953`), which covers the *other* 9 files but not these. Highest-usage real gap in this audit. |
| `GuiAccountPasswordCtrl` (`:1949`) | **IMPLEMENTED, and oracle-backed after all** | I was about to record it as our invention. It is a **real Era class** (`symbol_dump.log`, `GuiAccountPasswordCtrl.cpp`) that FourPlay lacks entirely, and Login `new`s it in 9 files. Keep it; its FourPlay-absence is a coverage gap, not an extension. Same for our `GuiMLTextEditCtrl` (`:1965`). |
| `inputtype` `showcursor` `deniedsound` `undo` | MISSING | 0 corpus uses each. |
| `max_len = 256` (`:1897`) | WRONG-ish | the reference's cap is the script-visible `maxchars`, default **255**, and it clips programmatic writes too; ours is a fixed 256 that only limits typing (`:4308`). |
| `clientrelative` `isexternal` `helptag` in `_TORQUE_PROPS` (`:849-853`) | **DIVERGENCE** | we claim three names the reference does not register, so those writes land on our control and fall through to temps/`this` in the reference. Nothing reads them back in any corpus, so it is currently unobservable — but it is a deliberate-extension note, not parity. |

### Ranked fix list (by distinct corpus files × observability)

1. `GuiTextEditCtrl.password` as a real property (16 files, currently dropped).
2. `checked` / `groupnum` / `buttontype` onto a shared `GuiButtonBaseCtrl`
   layer under `GuiButtonCtrl`, `GuiCheckBoxCtrl`, `GuiRadioCtrl`,
   `GuiBitmapButtonCtrl` (9 / 8 / 2 files), and rekey the radio sweep on
   `buttontype` + `groupnum`.
3. `setselection`'s inverted-range rule (5 files call it, on the chat bar).
4. `maxchars` + the 255-char truncation + `onTextChanged` on `GuiTextCtrl`
   (0 direct writes, but it changes what every `.text` write does).
5. `maximized`/`minimized` as toggling properties, and the four window methods.
6. Window `text` default `"New Window"`; button extent `140×30`; window extent
   `100×200` + `minExtent` clamp. Leave `TITLE_H` alone pending a render check.

## 7. Not determined

- `GuiWindowCtrl` has no assembly in this checkout (C14), so nothing in §2's
  *behaviour* column is asm-verified. The property/method **table** is.
- Whether `tabcomplete` and `deniedsound` are consumed at all: their consumers,
  if any, are in the parts of `GuiTextEditCtrl.cpp` I did not read
  (`:136-204`, `:365-745`, `:796-1039`).
- The Enter → `onAction` path on a text edit (§4.2): no `onKeyDown` exists on
  the class in either `src/` or `asm/`. Given §0a this may simply be Era-only
  code; do not conclude the reference lacks the behaviour.
- Whether `GuiAccountPasswordCtrl` adds or removes members relative to
  `GuiTextEditCtrl` (it could use `propertyStrings` to *delete* inherited ones,
  §0b). Unanswerable from FourPlay, which does not contain the class; would
  need the Era binary's data section, not its symbol dump.
- Whether `resizewidth`/`resizeheight`/`edgesnap` drive edge-drag resizing: the
  fields `m_resizeEdge`, `m_resizeMargin`, `m_mouseResizeWidth/Height` are
  initialised (`GuiWindowCtrl.cpp:59-63`) and never read in the recovered file.

## 8. 2026-07-26 implementation round (text family + engine events)

- **`onTextChanged` (§4.1 step 3) is implemented** on `GuiTextCtrl`'s text
  setter (pyReborn `gs2_gui/basic_controls.py`): unchanged-text early-out,
  clip first, then the event with the clipped text — one path for script
  `.text =`, `settext()` and typed input, matching the virtual dispatch
  (C5). Corpus weight was under-counted by the §5 construction-block
  method: `catchevent(..., "onTextChanged", ...)` routes ~15 fields in the
  staff sprite editor (`weapon-Staff_GraalShop.txt:519` ff.) and Login's
  events pane hangs a dotted handler
  (`gbf/bytecode/login/_Serverlist_Events.gs2bc.gs2:1190`,
  `Serverlist_EventOptions_Teams.onTextChanged(newtext)`).
- **C7 implemented**: the `text` PROPERTY setter zeroes both selection
  anchors on `GuiTextEditCtrl`; the inherited `settext()` method does not.
- **`onResize` is real; only the canvas-level dispatch is routed.**
  `GuiControl::resize` fires `onResize("ii", newW, newH)` on every control
  whose extent changed (`src/gui/GuiControl.cpp:2615-2618`; `onMove(x, y)`
  at `:2611` likewise). Login hangs the chat-bar resize off the canvas's
  fixed names (`function GraalControl.onResize(newwidth, newheight)`,
  `weapon-Rescripted_Serverlist.txt:2634`, `GraalControl3D` `:2735`) —
  dispatched across the weapon VMs on canvas resize. The PER-CONTROL event
  is deliberately NOT fired: the reference fires it from every resize path
  (script width/height writes included), and Login's `Serverlist_*Window.
  onResize` handlers (`:3027-3059`) resize each other — firing them from
  only the canvas-sizing sweep (a state the reference never sees) was
  live-tested on 2026-07-26 and collapsed `Serverlist_Map`. All-or-nothing;
  see the `_apply_sizing` comment in `gs2_gui/manager.py`.
- **Engine handlers checked against the six corpora**: `onReceiveText` was
  already routed (gs2_client PLO_SERVERTEXT); `onLogMessage` exists in one
  weapon (`weapon-Rescripted_-F2LogWindow.txt:92`) but is NOT routed — the
  headless client has no engine log channel to feed it; deliberate gap.
  `onInitServerWarp` / `onHandleServerWarp`: **zero corpus hits** — a
  census claim refuted by grep; nothing to route.
- **`makevar` is NOT a builtin.** `makevar("temp.creds." @ x)` compiles to
  `OP_CONV_TO_STRING; OP_MAKEVAR` with no Call op (gs2test-verified). The
  gap was dotted-name deref: the VM's `_lookup` now walks `a.b.c` (head
  through the scope chain, rest through members) when the flat name
  resolves nothing. Read-only, matching the corpus use
  (`weapon-LoginScreen.txt:341`).
- **Mobile-corpus builtins**: `_(s)` (localization wrapper,
  `weapon-Mobile_Login.txt:176`) answers identity; `char(n)` answers the
  chr (`weapon-LoginScreen.txt:341`); both are Era/mobile names absent from
  FourPlay — semantics from usage, flagged as such in the handlers.
  `des_decrypt` and `initializeiphonedisplay` joined the POLICY-INERT stub
  set (`gs2_client.py stubbed`): the mobile credential cache round-trips
  account+password through `des_encrypt`/`des_decrypt`
  (`weapon-Mobile_Login.txt:325-336`), and this client keeps that whole
  surface inert. `Quattro::DebugTools::*` calls (bomber
  `weapon-System.txt:49-52`) were already covered by the
  `quattro::debugtools::` prefix stub.
