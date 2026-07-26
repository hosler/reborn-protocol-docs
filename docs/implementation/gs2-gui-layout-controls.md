# GS2 GUI control surface — layout/styling wave

Spec fragment for `reborn-protocol-docs/docs/implementation/gs2-name-surface.md`,
"GUI controls" subsection. Closes six of the 21 unaudited control classes:
`GuiScrollCtrl`, `GuiControlProfile`, `GuiMLTextCtrl`, `GuiBitmapCtrl`,
`GuiBitmapButtonCtrl`, `GuiArrayCtrl`.

Oracle: `Preagonal/FourPlay/quattroplay/`. Every `file:line` below is a line
that was opened and read. Where the decompiled C++ was checked against
`asm/**/*.s_decomped`, the asm file is named. Where a body was **not** read,
the entry says so and asserts type/flags only.

Corpus for the bottom-up half: `Preagonal/graal-{lttp,loginserver,
loginserver-dev,loginserver-mobile,bomber-gs2,gta}` ("the corpora"). Counts are
**distinct files**.

Diff target: `pyReborn/pyreborn/game/gs2_gui.py` (read, not edited).

> **Counting method — read this before trusting any number below.** GUI
> properties are overwhelmingly written **bare inside construction blocks**
> (`new GuiBitmapCtrl("X") { tile = true; }`), not dotted. A first pass here
> counted only the dotted form (`\.<name>\b`) and reported 0 files for
> `normalbitmap`, `wordwrap`, `checked` and a dozen others that are in heavy
> use. Every count in this document is now
> `grep -rliE "(^|[[:space:].;{])<name>[[:space:]]*=[^=]"` — assignment sites,
> bare or dotted. Where a name is also a common script-local (`this.scrollpos`),
> the sites were read individually and the contaminated count is called out.

---

## 0a. Oracle-coverage caveat, and the two inheritance mechanisms

**FourPlay is authoritative for what it contains; its silence is not proof of
absence.** `Preagonal/graal-revlib-osx/docs/symbol_dump.log` — the macOS Era
client — lists **42** `Gui*` translation units via its
`_GLOBAL__sub_I_<file>.cpp` static-init symbols, against 24 `Gui*` classes in
FourPlay.

For this wave that caveat is **narrow but not empty**:

- All six of my classes exist in the Era build too — `GuiControlProfile.cpp`
  (`symbol_dump.log:2302`), `GuiArrayCtrl.cpp` (`:2758`),
  `GuiBitmapButtonCtrl.cpp` (`:2806`), `GuiBitmapCtrl.cpp` (`:2839`),
  `GuiMLTextCtrl.cpp` (`:3621`), `GuiScrollCtrl.cpp` (`:4014`). So none of them
  is a FourPlay-only artifact.
- But that dump carries **no member symbols** for them. Its C++ symbols are
  obfuscated (`_ZN15VEry_tOP_SEcReT…`, `symbol_dump.log:1-25`) and the only
  `Gui*` entries are the per-TU static-init symbols listed above. There is not
  even a separate `Gui*Properties.cpp` TU in that build. **It cannot confirm or
  deny a single property name**, so it could not be used to close the one real
  absence this wave found (§1.21).

**`TProperties::propertyStrings` — the removal list — does not touch any of my
six classes.** `TProperties::compileProperties`
(`src/TProperties.cpp:96-162`) assigns the parent's compiled table first
(`:108-113`), then for each own entry removes any inherited same-name entry and
re-adds the child's (`:117-129`) — child wins — and *then* walks
`propertyStrings`, deleting each named property outright (`:132-161`). Across
the whole `src/gui/` tree `propertyStrings` is populated in exactly one file:
`GuiShowImgCtrlProperties.cpp:80-84`, which drops
`red,green,blue,alpha,mode,style,rotation`. None of `GuiScrollCtrl`,
`GuiControlProfile`, `GuiMLTextCtrl`, `GuiBitmapCtrl`, `GuiBitmapButtonCtrl`,
`GuiArrayCtrl` or `GuiButtonBaseCtrl` uses it, so the parent-chain grants in
§0 are **not pruned** and the inheritance diffs below stand as written.

**`TGraalVar::addPropertyObject` — real delegation — likewise does not touch any
of my six.** Across `src/gui/` it is called in exactly three places:
`GuiContextMenuCtrl.cpp:158` (delegates to its text-list child),
`GuiShowImgCtrl.cpp:83`, `GuiPopUpMenuCtrl.cpp:93`. `GuiScrollCtrl` in
particular does **not** delegate to its scrollbars — checked specifically
because the brief flagged it — so there is no split-read/write aliasing to
model on any class in this wave.

---

## 0. Table sizes, asm-verified

| Class | Parent (`TProperties(type,parent)` ctor) | props | funcs | asm confirmation |
| --- | --- | ---: | ---: | --- |
| `GuiArrayCtrl` | `GuiControl` (`src/gui/GuiArrayCtrlProperties.cpp:30`) | 1 | 0 | `asm/TProperties/_ZN22GuiArrayCtrlPropertiesC1Ev.s_decomped` (`$0x1,%edx`, single `addProps`, no `addFuncs`) |
| `GuiBitmapCtrl` | `GuiControl` (`GuiBitmapCtrlProperties.cpp:137`) | 5 | 2 | `_ZN23GuiBitmapCtrlPropertiesC1Ev.s_decomped` (`$0x5`, `$0x2`) |
| `GuiBitmapButtonCtrl` | **`GuiButtonBaseCtrl`** (`GuiBitmapButtonCtrlProperties.cpp:83`) | 3 | 1 | `_ZN29GuiBitmapButtonCtrlPropertiesC1Ev.s_decomped` (`$0x3`, `$0x1`) |
| `GuiButtonBaseCtrl` (in that chain) | `GuiControl` (`GuiButtonBaseCtrlProperties.cpp:129`) | 4 | 2 | not checked |
| `GuiScrollCtrl` | `GuiControl` (`GuiScrollCtrlProperties.cpp:168`) | 8 | 5 | `_ZN23GuiScrollCtrlPropertiesC1Ev.s_decomped` (`$0x8`, `$0x5`) |
| `GuiMLTextCtrl` | `GuiControl` (`GuiMLTextCtrlProperties.cpp:349`) | 13 | 24 | `_ZN23GuiMLTextCtrlPropertiesC1Ev.s_decomped` (`$0xd`, `$0x18`) |
| `GuiControlProfile` | **`TGraalVar`** (`GuiControlProfileProperties.cpp:616`) | 49 | 3 | no ctor `.s_decomped` in `asm/TProperties/` (only D0/D1/D2) — count is from the C++ array bound `propDefs[0x31]` (`:549`) plus a literal count of entries `:550-598`, which agree |

`GuiControl` itself (already audited by the previous wave) is 55 props
(`GuiControlProperties.cpp:646`, entries `:647-701`) and 28 funcs (`:864`,
entries `:865-892`), parent `TGraalVar` (`:895`).

**New own-table entries added by this wave: 108** (49+3 profile, 13+24 ML,
8+5 scroll, 5+2 bitmap, 3+1 bitmapbutton, 1+0 array), plus the 4+2
`GuiButtonBaseCtrl` entries that the bitmap-button chain drags in.

---

## 1. COUNTER-INTUITIVE FINDINGS (read these first)

### 1.1 `border` is a style ENUM, not a pixel thickness — and we treat it as a width

`GuiControlProfile.border` is `'i'` and selects a border *renderer*:
`TGUIRender::renderBorder` switches on it (`src/TGUIRender.cpp:59`) —
`1` = flat 1px in `bordercolor` (`:61-63`), `2` = raised bevel using
`bordercolorna` for the light edges (`:65-90`), `3` = sunken bevel that pulls
its inner lines from `fillcolor` (`:92-124`), `4` = the opposite bevel using
`bordercolor` (`:126-150`), **`default: return`** (`:152-153`) — i.e. `0` and
`5` draw nothing here.

`5` is the *skinned* mode, handled by the caller instead:
`GuiControl::onRender` gates on `border > 0` (`src/gui/GuiControl.cpp:3387`)
and for `== 5` fetches `getStyle()` and calls
`TGUIRender::renderStyleButton(rectangle, style, "", 5, state, false)`
(`:3389-3406`), with `state` derived from `m_active`/`isFirstResponder()`
(`:3394-3400`). The pixel thickness is a **separate** property,
`borderthickness`, default `1` (`src/gui/GuiControlProfile.cpp:190`), and it is
what `GuiScrollCtrl` measures with (`src/gui/GuiScrollCtrl.cpp:119-133`,
`getChildrenFitHeight`). `opaque` (not `border`) is what gates the fill
(`GuiControl.cpp:3384-3385`).

Corpus (`border = <n>` literals): `1`×35, `0`×24, `3`×12, **`5`×10**, `4`×4;
`borderthickness = 1`×4. So the skinned mode is in live use.

**We get this wrong.** `_profile_from_fields` does
`bw = max(0, min(3, int(to_num(fields.get("border")))))`
(`gs2_gui.py:312-313`) and passes it as `border_width`, drawn as a solid
rectangle outline. `border = 5` → we draw a 3px solid border where the
reference draws the style bitmap; `border = 4` → same; `border = 2/3` → we draw
a flat 2/3px line where the reference draws a 1px bevel. `borderthickness` is
not read at all (`_STYLE_FIELDS`, `:249-253`).

### 1.2 `justify` and `align` are the same slot — and the corpus uses the one we ignore

`GuiControlProfileProperties.cpp:582` registers `justify` with **the identical
getter and setter pointers** as `align` (`:550`):
`propfun_guicontrolprofile_align_r` / `_w`. The stored value is an index into
`AlignmentArr` = `{"left","center","right"}` (`:543-547`), matched by
`propfun_guicontrolprofile_align_w` (`:11-21`).

Corpus: `justify` appears in **5** files (23 `justify = "center"` assignments);
`align` in **1**. Our `_STYLE_FIELDS` (`gs2_gui.py:249-253`) contains `align`
and **not** `justify`, and `_profile_from_fields` reads only
`fields.get("align", "left")` (`:324`) — so every `justify = "center"` in the
Login/IRC content is silently dropped.

### 1.3 `wrap` is an alias of `tile` on `GuiBitmapCtrl`

`GuiBitmapCtrlProperties.cpp:104-112` registers `wrap` with
`propfun_guibitmapctrl_tile_r`/`_w` — the same pointers as `tile` (`:95-103`).
One field, two names. (`GuiScrollCtrl` also has a `tile` (`GuiScrollCtrlProperties.cpp:154`)
but it is a different, unrelated field — `m_guiScrollCtrl_unknown23`, plain
bool, no invalidate: `:82-90`.)

### 1.4 `GuiBitmapButtonCtrl` is NOT a `GuiBitmapCtrl`

Its parent is `GuiButtonBaseCtrl` (`GuiBitmapButtonCtrlProperties.cpp:83`), so
it has **none** of `bitmap`, `bitmaprectangle`, `fullbitmap`, `tile`, `wrap`.
Its three bitmaps are `normalbitmap` / `mouseoverbitmap` / `pressedbitmap`
(`:40-67`), all routed through `setBitmap(name, slot)` with slots 0/1/2
(`:10-33`).

And **`setbitmap` has two incompatible signatures** depending on the class:
`GuiBitmapCtrl.setbitmap(s)` (`GuiBitmapCtrlProperties.cpp:116-124`,
body `:52-55`) vs `GuiBitmapButtonCtrl.setbitmap(s,i)`
(`GuiBitmapButtonCtrlProperties.cpp:70-80`, body `:35-38`).

**We get this wrong**: `gs2_gui.py:2138` declares
`class GuiBitmapButtonCtrl(GuiButtonCtrl)` and gives it a single `bitmap`
property (`:2145-2160`); `normalbitmap`/`mouseoverbitmap`/`pressedbitmap` are
unclaimed (corpus usage of all three is 0, so this is low-priority — but the
hover/press faces will never differ).

### 1.5 `reflow()` is a no-op unless a profile resolves — and the C++ decompilation gets the guard wrong

`reflow` is registered on `GuiMLTextCtrl` only, `'v'`, params `""`
(`GuiMLTextCtrlProperties.cpp:334`; trampoline `:233-236`). The previous wave's
placement of it on `GuiMLTextCtrl` rather than `GuiTextListCtrl` is
**confirmed**.

Its body (`src/gui/GuiMLTextCtrl.cpp:1586-1607`) reads, in the C++:

1. `if (!m_awake) return;`
2. `if (htmlPage == nullptr) return;`
3. `if (m_tooltipProfile != nullptr) { htmlPage->setStyle(getStyle()); htmlPage->setLineSpacingPixels(m_tooltipProfile->linespacing); }`
4. `htmlPage->setParseTags(m_parseTags && !unknown11, m_allowedTags);`
5. `htmlPage->reflow(); reflowResize(false);`

The asm (`asm/gui/GuiMLTextCtrl/_ZN13GuiMLTextCtrl6reflowEv.s_decomped`)
**disagrees on 2 and 3**:

- Guard 1 is real: `cmpb $0x0,0x116(%rdi); jne +0x10; ret` — and
  `include/gui/GuiControl.h:267` static-asserts `offsetof(GuiControl, m_awake) == 0x116`
  (field declared `:190`). Confirmed.
- There is **no** null test of `htmlPage` (field `0x228`) anywhere in the
  function.
- What actually happens is the standard profile resolution: it tests
  `m_tooltipProfile` (`cmpq $0x0,0x80(%rbx)`; `GuiControl.h:242` asserts
  `offsetof(m_tooltipProfile) == 0x80`) and, when null, falls back to
  `dynamicCastVar(GuiControlProfile_properties, m_profile->readObject())`
  (`m_profile` at `0x78`, `GuiControl.h:241`). **If neither resolves, the
  function returns immediately** — `pop %rbx; ret` — without calling
  `THTMLPage::reflow` or `reflowResize`. The same resolution runs a second time
  for `setLineSpacingPixels` (offset `0x160` = `linespacing`).

So: **`reflow()` on a control with no resolvable `GuiControlProfile` does
nothing at all.** Given §1.9 (`initObject` seeds every profile from a global),
this is one more way a missing profile makes the UI not render rather than
render unstyled.

`reflow` also **resizes the control** — it is not a pure layout pass.
`reflowResize` (`GuiMLTextCtrl.cpp:1609-1648`) computes
`height = htmlPage->m_maxHeight`, `width = m_maxWidth + 1` when word-wrap is
off (or when called with `pUpdateParent`) else the current extent
(`:1615-1621`); when the page draws a background and the parent is a
`GuiScrollCtrl` it stretches the height up to
`GuiScrollCtrl::getChildrenFitHeight() - bounds.point.y` (`:1623-1632`); then
calls `resize()` (`:1634-1635`) and fires **`onReflow(width, height)`**
(`:1642-1644`, arg spec `"ii"`) with the page's max extents. The asm agrees on
the shape (virtual `call *%rax` for resize, then `TString << "onReflow"`,
then `invokeEvent`, then `isFirstResponder`/`ensureCursorOnScreen`:
`asm/gui/GuiMLTextCtrl/_ZN13GuiMLTextCtrl12reflowResizeEb.s_decomped`
lines 28-53).

**We get this partly wrong.** `gs2_gui.py:1714-1720` implements `_m_reflow` as
a cache invalidation returning `0.0`. It never resizes and never fires
`onReflow`. Our ML control *does* autosize its height at draw time
(`:1797-1798`), so the visible effect is close; the missing `onReflow` event is
the real gap (no corpus handler found — see §7).

### 1.6 `scrollTo` fires `onScrolled` BEFORE storing the new position, and is a no-op with no children

`GuiScrollCtrl::scrollTo` (`src/gui/GuiScrollCtrl.cpp:909-943`):

- `if (this->m_controls->mArraySize <= 0) return;` — **an empty scroll control
  cannot be scrolled at all**, not even to 0.
- clamps x to `unknown11 - unknown9` and y to `unknown12 - unknown10`, then to
  `>= 0`;
- if either changed, invokes `onScrolled` with `"iiii"` = `(newX, newY,
  newX-oldX, newY-oldY)` **and only then** writes the fields.

The write-after-event ordering is asm-confirmed:
`asm/gui/GuiScrollCtrl/_ZN13GuiScrollCtrl8scrollToEii.s_decomped` shows
`call _ZN9TGraalVar11invokeEventERK7TStringPKcz@plt`, then `TString::clear`,
then `mov %ebp,0x1fc(%rbx); mov %r12d,0x200(%rbx)`, then `calcThumbs`.
So a script's `onScrolled` handler that reads `.scrollpos` sees the **pre-scroll**
value; the deltas it was handed are the only fresh data.

`scrollDelta(x,y)` is `scrollTo(x + cur.x, y + cur.y)` (`:945-948`).

### 1.7 `scrolltotop`/`scrolltobottom` reset the HORIZONTAL scroll to 0

`GuiScrollCtrlProperties.cpp:139-142` — `scrolltobottom` is
`scrollTo(0, 0x7fffffff)`; `:144-147` — `scrolltotop` is `scrollTo(0, 0)`.
Neither preserves x. (`GuiMLTextCtrl` registers its own `scrolltobottom` /
`scrolltotop` (`GuiMLTextCtrlProperties.cpp:336`, `:338`) which delegate to
`GuiMLTextCtrl::scrollToBottom`/`ScrollToTop` — different bodies, not read.)

### 1.8 Enum-valued property setters are CASE-SENSITIVE, and silently no-op on a miss

`writeScrollbarMode` (`GuiScrollCtrlProperties.cpp:23-34`) compares the written
string against `{"alwaysOn","alwaysOff","dynamic"}` (`:8-12`) with `TString`
`operator==`, which is `memcmp` after a length check — **byte-exact, no case
folding** (`src/TString.cpp:867-878`, and the `TString`/`TString` form
`:849-860`). On no match the function returns `false`, the mode is unchanged
**and `computeSizes()` is not called** (`:65-69`, `:97-101`).

Same shape on `GuiButtonBaseCtrl.buttontype`
(`GuiButtonBaseCtrlProperties.cpp:16-26`, table `{"PushButton","ToggleButton","RadioButton"}`
`:5-9`) and on `GuiControlProfile.align`/`justify`
(`GuiControlProfileProperties.cpp:11-21`, all-lowercase table `:543-547`).

This is the opposite of the GS2 VM's `==`, which we implement case-insensitively.
Do not "helpfully" case-fold these setters.

Corpus values are all written against the exact spelling —
`hScrollBar = "alwaysOff"`×33, `"dynamic"`×10, `hscrollbar = "alwaysOff"`×3,
`vScrollBar = "dynamic"`×28, `"alwaysOff"`×13, `"alwaysOn"`×2,
`vscrollbar = "dynamic"`×2, `buttonType = "PushButton"`×12,
`justify = "center"`×23. (Note the *property name* is written in mixed case
too; name lookup case-folding was not audited here.)

### 1.9 Every new `GuiControlProfile` is seeded from the global `GuiDefaultProfile`

`GuiControlProfile::initObject` (`src/gui/GuiControlProfile.cpp:184-221`) ends
by looking up the universe global literally named `"GuiDefaultProfile"`
(`:214-219`) and calling `copyProfileFrom` on it (`:220`). So a profile's
starting values are not the constructor's — they are whatever the running
content last set on `GuiDefaultProfile`. Corpus: `GuiDefaultProfile` appears in
8 files, 52 references, including 10 `new GuiDefaultProfile(` derivations.

We model this: `_BUILTIN_PROFILE_FIELDS["guidefaultprofile"]`
(`gs2_gui.py:162-165`) and `_DEFAULT_PROFILE_NAME` (`:147`). But our seed is a
static dict, not the live object, so a script that *mutates*
`GuiDefaultProfile` after startup does not affect profiles created later — in
the reference it does (for profiles created after the mutation). No corpus case
observed.

### 1.10 There are TWO profile-copy paths with DIFFERENT coverage

- `GuiControlProfile::copyProfileFrom` (`GuiControlProfile.cpp:224-278`) — the
  native one, used by `initObject` (§1.9) and by the copy constructor (`:91`).
  It copies a hard-coded field list. Reading it against the 49-entry table,
  it **omits five registered properties**: `mouseoverselected`,
  `fontstylecontrolwords`, `fontstyleidentifiers`, `fontstylestrings`,
  `fontstylenumbers`.
- `TGraalVar::copyFrom` (`src/TGraalVar.cpp:2203-2333`) — the script-visible
  one, used by profile *derivation* (§1.11). It iterates the source's
  registered `TScriptProperty` table (`:2265-2268`), skips entries with no
  getter (`:2269-2270`), and for each name the target also registers **with a
  setter** (`:2278-2281`) does a typed get/set (`:2282-2305`). So it copies
  **all 49**, including the five above, and skips read-only ones.

Two copy paths, two different results, for the same conceptual operation.

### 1.11 Derivation (`new <ParentProfile>("Name")`) works because `GuiControlProfile` is the ONE GUI class that opts into `TGraalVar::copyFrom`

`TProperties::bool1` defaults to `false` (`src/TProperties.cpp:80`) and is set
`true` in exactly one GUI table: `GuiControlProfileProperties`'s constructor
(`GuiControlProfileProperties.cpp:618`). Twenty-plus `TGraalVar` mutators are
gated on `m_graalVar_unknown4 && !properties->bool1` — e.g. `copyFrom`
(`TGraalVar.cpp:2208-2214`), `loadString` (`:514-515`). Every `Gui*Ctrl` sets
`m_graalVar_unknown4 = true` in its `initObject` (e.g.
`GuiBitmapCtrl::initObject`, `src/gui/GuiBitmapCtrl.cpp:44`), and none of them
sets `bool1` — so **`someControl.copyFrom(other)` is a silent no-op, while
`someProfile.copyFrom(otherProfile)` is a full property copy.**

The `new` opcode (`src/TScriptMachine.cpp:1027-1191`) is what joins these: when
the class name is not a registered `TObjectCreator`, it resolves the name as a
*variable*, takes that object's `getVarType()` and looks up the creator for
**that** type instead (`:1072-1083`), creates the object (`:1118`), and then
calls `local_a0->copyFrom(this_00)` with the resolved parent (`:1156`). That is
the whole of "profile derivation": `new IRC_TextProfile("X")` → creates a
`GuiControlProfile` → `copyFrom(IRC_TextProfile)`.

Corpus derivations (top): `new GuiControlProfile(`×36, `new IRC_TextProfile(`×20,
`new IRC_TextListProfile(`×15, `new IRC_WindowProfile(`×10,
`new IRC_WindowLeftProfile(`×10, `new IRC_TreeViewProfile(`×10,
`new GuiTextEditProfile(`×10, `new GuiDefaultProfile(`×10,
`new GuiBlueTransScrollProfile(`×10, plus ~15 more at ×5.

**Our rule is a name heuristic, not the oracle's rule.**
`make_control` (`gs2_gui.py:3545-3563`) treats an unknown class as a profile
iff `classname.lower().endswith("profile")` (`:3548`). Every derivation in the
corpora happens to end in `Profile`, so this is correct *in practice*; it would
diverge for a profile whose name does not, and it would also (wrongly) make a
profile out of a non-profile object whose name does.

### 1.12 `GuiControlProfile`'s parent is `TGraalVar`, not `GuiControl`

`GuiControlProfileProperties.cpp:616`. A profile therefore has **no** `bounds`,
`extent`, `visible`, `x`/`y`/`width`/`height`, `addcontrol`, `resize`, `show`,
`profile`, … Reading `someProfile.width` in the reference resolves nothing and
yields Number `0.0`.

We model it as `class GuiControlProfile(GuiControl)` (`gs2_gui.py:3489`) with
`has()` returning `True` for everything (`:3515-3516`), so
`someProfile.width` answers `100.0` (the `GuiControl.__init__` default,
`:892`). Deliberate — the blanket `has()` is what makes existence-gated
construction-block writes land (documented `:3500-3505`) — but it is a
divergence, and `width`/`height`/`visible` specifically now answer a plausible
non-zero number instead of nothing.

### 1.13 `GuiMLTextCtrl.alpha` SHADOWS `GuiControl.alpha`

Both are `'f'`. `GuiControl.alpha` (`GuiControlProperties.cpp:649`) reads
`m_guiControl_unknown15` and writes via `setAlpha` (`:30-38`). `GuiMLTextCtrl`
redeclares it (`GuiMLTextCtrlProperties.cpp:307`) onto
`htmlPage->m_alpha` / `htmlPage->setAlpha` (`:23-31`). Child wins, so on an ML
control `alpha` is the **HTML page** alpha, not the control's.

(No corpus impact: all 12 files that write `.alpha` write it on
`tilelayers[n]`, `findimg(n)` or `player` — none on a GUI control.)

### 1.14 `GuiMLTextCtrl.text` and `.plaintext` are different views of one buffer

`plaintext` returns the raw buffer (`GuiMLTextCtrlProperties.cpp:113-118`);
`text` returns `insertEscapes(plaintext)` (`:125-128`) and its setter stores
`escapeEscapes(value)` (`:130-134`). `gettext`/`settext` (`:228-231`, `:295-298`)
are aliases of the `text` accessors, i.e. they escape too. `escapeEscapes` /
`insertEscapes` are declared at `:9-10` and defined elsewhere (**bodies not
read** — the escaping alphabet is undetermined).

### 1.15 `disallowedtags` is computed, not stored

Its getter (`:53-65`) walks `THTMLDefinitions::getTagNameList()` and returns
every tag *not* in `m_allowedTags` — so it is the complement of `allowedtags`
(`:12-15`), recomputed on each read, and the two properties are one piece of
state. Both are CSV (`GetCommaText2`).

### 1.16 `findtext`'s int argument is a FLAG MASK, not a start position

`findtext(s, i)` calls `findTextAt(s, 0, i)` (`:167-170`) — the int lands in
`pFlags`, not `pPosition`. In `findTextAt`
(`src/gui/GuiMLTextCtrl.cpp:243-347`): bit 0 = wrap-around search
(`:257`, `:259-260`), bit 1 = case-**sensitive** (`:258`), i.e. the default
`0` is a case-INSENSITIVE non-wrapping search. When `parsetags` is on it skips
over `<...>` spans (`:286-302`). Returns `-1` on any of: null/empty needle
(`:245-250`), `pPosition` out of range, needle longer than the text
(`:252-254`).

`findtextat(s,i,i)` (`:172-175`) is `(needle, position, flags)` — the middle
argument is the position. `replacetext(s,s,i)` (`:238-241`, body
`GuiMLTextCtrl.cpp:349-390`) masks the caller's flags down to `pFlags & 2`
(`:360`), i.e. **it always searches non-wrapping** and only honours the
case-sensitivity bit, and it **caps at 1000 replacements** (`:387-388`).

### 1.17 `getselectedposition` / `getselectedlength` return `-1`, not 0, when nothing is selected

`GuiMLTextCtrlProperties.cpp:200-206` and `:208-214`. `getselectedlength` is
`end - start`. Since an unanswered name in our host resolves to Number `0.0`,
a stub returning `0` reads as "a zero-length selection exists at offset 0"
rather than "no selection".

### 1.18 `getcolumnandlineofposition` returns a STRING, not a pair

`'s'`, params `"i"` (`:332`). The body (`:216-226`) builds a two-element
`TStringList` of `column` then `line` and returns `GetCommaText2()` — so
`"<column>,<line>"`, column first.

### 1.19 `allowmultipleselections = false` destroys the existing multi-selection

`GuiArrayCtrlProperties.cpp:11-23`: on a `false` write it loops
`while (selectedCells->mArraySize > 1)` deleting from the **tail**, keeping the
first selected cell. The list is `TList*` of `TPoint` selected cells
(`include/gui/GuiArrayCtrl.h:63`, populated at
`src/gui/GuiArrayCtrl.cpp:97`, `:426`, `:431`). So the write is not a mode flag
— it mutates state.

### 1.20 `GuiControlProfile`'s constructor seeds the font-colour alpha OUT OF RANGE

`fontcolor`'s four floats are stored on a 0..1 scale — the setter multiplies by
`0.003921569` (=1/255) (`GuiControlProfileProperties.cpp:219-226`) and the
getter multiplies back by 255 (`:207-217`). But the constructor stores
`m_guiControlProfile_unknown11 = 255.0` (`src/gui/GuiControlProfile.cpp:17`,
`:46`, `:74`), where the sibling colour triples seed their alpha to `1.0`
(`shadowcolor` `:205`, `gradientcolor` `:209`).

This *looked* like a decompilation artifact, so it was checked:
`asm/gui/GuiControlProfile/_ZN17GuiControlProfileC2ERK7TString.s_decomped`
line 29 is `movl $0x437f0000,0xd8(%rbx)` — `0x437f0000` is `255.0f` — and
`include/gui/GuiControlProfile.h:124` static-asserts
`offsetof(m_guiControlProfile_unknown11) == 0xd8`. **The decompilation is
faithful; the reference really does seed 255.0.** Read back before anything
overwrites it, `fontcolor`'s alpha byte is `(uint8_t)(int)(255.0*255.0+0.5)` =
`(uint8_t)65025` = `1`. In practice `initObject`'s `copyProfileFrom` (§1.9)
overwrites all four from `GuiDefaultProfile` (`GuiControlProfile.cpp:246-247`),
so this only bites when no `GuiDefaultProfile` global exists.

Do not "fix" this to 1.0 in an implementation without a live capture.

### 1.21 Real content sets FIVE profile fields FourPlay's table does not register

Sweeping every bare assignment inside a `new <…>Profile(…) { … }` block across
the corpora and diffing against the 49-entry table, all but five names match.
The exceptions, in one genuine profile block —
`graal-loginserver-mobile/weapons/weapon-Mobile_Serverlist.txt:40-58`,
`new GuiControlProfile("GR_Serverlist_ButtonProfile") { … }`:

| Name | Site | Assessment |
| --- | --- | --- |
| `bordercolorsel` | `:49` | **Plausibly a real Era-build property.** FourPlay registers `fontcolorsel` (`GuiControlProfileProperties.cpp:571`) plus `bordercolor`/`bordercolorhl`/`bordercolorna` (`:556-558`) — the `*sel` slot is missing from the border family only. |
| `fillcolorsel` | `:52` | Same shape: `fillcolor`/`fillcolorhl`/`fillcolorna` exist (`:563-565`), `fillcolorsel` does not. |
| `normalbitmap`, `mouseoverbitmap` | `:57` (`normalbitmap = mouseoverbitmap = "-";`) | **Probably a content bug, not a missing property.** Both are unambiguously `GuiBitmapButtonCtrl` properties in FourPlay (`GuiBitmapButtonCtrlProperties.cpp:40-67`), on a class whose parent chain does not include `GuiControlProfile`. |
| `pressedbitmap` | `:58` | ditto |

`alpha` also appears 3 times in 3 files inside profile blocks; `GuiControlProfile`
has no `alpha` (only `transparency`, `:598`), while `GuiControl` and
`GuiMLTextCtrl` both do — same likely-misplaced-write shape.

**Undetermined, and it must stay that way with the oracles on hand.** Either
(a) the Era/Mobile build's `GuiControlProfile` table is larger than FourPlay's,
or (b) these writes land as ordinary dynamic vars on the profile object — which
is legal, a profile is a `TGraalVar` (§1.12) — and are simply inert.
`symbol_dump.log` cannot distinguish them (§0a). Do **not** record these as
absent from the reference, and do not implement them on the strength of one
file. Flag for a live capture.

The good news for the styling surface: **every other name real content sets on a
profile is in FourPlay's 49.** Full sweep result, by assignment count / distinct
files — `fontsize` 78/8, `textshadow` 72/8, `fontstyle` 64/8, `fonttype` 63/8,
`fillcolor` 62/16, `bitmap` 53/11, `shadowcolor` 52/8, `opaque` 40/19,
`align` 30/5, `border` 21/8, `fontcolorlink` 20/5, `fontcolorlinkhl` 20/5,
`transparency` 19/13, `fontcolor` 19/10, `fillcolorhl` 13/8, `shadowoffset`
12/8, `modal` 7/7, `overridestylefont` 5/5, `textoffset` 5/5, `fillcolorna`
5/5, `autosizewidth` 5/5, `focusonshow` 5/5, `tab` 5/3, `justify` 3/3,
`bordercolor` 3/3, `bordercolorhl` 3/3, `fontcolorhl` 3/3, `fontcolorsel` 3/3,
`borderthickness` 2/2. (These are *profile-block* counts and are lower than the
whole-corpus counts in §2, which also catch the same names on controls.)

---

## 2. `GuiControlProfile` — 49 properties, 3 methods

Parent: `TGraalVar` (`GuiControlProfileProperties.cpp:616`). Table `:549-599`;
funcs `:610-614`. **All 49 properties are read/write** — there is not a single
`nullptr` setter in this table. **Zero raw-address entries**: every getter and
setter in this file is a named `propfun_*` whose body is in the same file and
was read.

| # | Name | Type | R/W | Semantics (body read) |
| ---: | --- | :---: | :---: | --- |
| 1 | `align` | s | RW | index into `{"left","center","right"}` (`:543-547`); setter is exact-match, silent no-op on a miss (`:11-21`) |
| 2 | `autosizeheight` | b | RW | plain field (`:33-41`) |
| 3 | `autosizewidth` | b | RW | plain field (`:43-51`) |
| 4 | `backgroundinset` | s | RW | `TRectangle` as string via `getTRectangleString`/`getStringTRectangle` (`:53-65`); `initObject` seeds `-1,-1,-1,-1` (`GuiControlProfile.cpp:193-196`) |
| 5 | `bitmap` | s | RW | skin-sheet filename; setter is `GuiControlProfile::setBitmap` (`:67-75`), which strips the path and **appends `.png` when the name has no extension** (`GuiControlProfile.cpp:284-308`) |
| 6 | `border` | i | RW | **style enum, see §1.1** |
| 7 | `bordercolor` | s | RW | `ColorI` via `getColorString`/`getStringColor` (`:87-95`) |
| 8 | `bordercolorhl` | s | RW | `:97-105` |
| 9 | `bordercolorna` | s | RW | `:107-115`; used for the light edges of border styles 2 and 3 (`TGUIRender.cpp:78`, `:109`) |
| 10 | `borderthickness` | i | RW | pixel thickness (`:117-125`), default 1 (`GuiControlProfile.cpp:190`) |
| 11 | `boxextent` | s | RW | `TPoint` as string (`:127-135`) |
| 12 | `cankeyfocus` | b | RW | `:137-145` |
| 13 | `cursorcolor` | s | RW | `:147-155` |
| 14 | `fillcolor` | s | RW | `:157-165` |
| 15 | `fillcolorhl` | s | RW | `:167-175` |
| 16 | `fillcolorna` | s | RW | `:177-185` |
| 17 | `fillonlynonchildarea` | b | RW | `:187-195` |
| 18 | `focusonshow` | b | RW | `:197-205`, default `true` (`GuiControlProfile.cpp:197`) |
| 19 | `fontcolor` | s | RW | **four separate floats on a 0..1 scale**, packed/unpacked in the accessors (`:207-226`); see §1.20 |
| 20 | `fontcolorhl` | s | RW | stored as a `ColorI` (unlike `fontcolor`) (`:228-236`) |
| 21 | `fontcolorna` | s | RW | `:238-246` |
| 22 | `fontcolorsel` | s | RW | `:248-256` |
| 23 | `fontcolorlink` | s | RW | `:258-266` |
| 24 | `fontcolorlinkhl` | s | RW | `:268-276` |
| 25 | `fontsize` | i | RW | `m_font.m_fontSize` (`:278-283`); seeded from `TFontOptions::defaultfontsize` (`GuiControlProfile.cpp:12`, `:31`) |
| 26 | `fontstyle` | s | RW | setter re-resolves the font file: `setFontStyle` → `TFontManager::constructFontFile` (`:285-290`; `GuiControlProfile.cpp:111-115`) |
| 27 | `fontstylecontrolwords` | s | RW | opaque string field `unknown22` (`:292-303`); **not copied by `copyProfileFrom`** (§1.10) |
| 28 | `fontstyleidentifiers` | s | RW | `unknown23` (`:305-315`); not copied |
| 29 | `fontstylestrings` | s | RW | `unknown24` (`:317-323`, `:333-337`); not copied |
| 30 | `fontstylenumbers` | s | RW | `unknown25` (`:325-331`, `:340-343`); not copied |
| 31 | `fonttype` | s | RW | `setFontType` → `constructFontFile` (`:345-355`; `GuiControlProfile.cpp:117-122`); seeded from `TFontOptions::defaultfont` (`:11`) |
| 32 | `gradientcolor` | s | RW | four floats 0..1, same packing as `fontcolor` (`:357-378`) |
| 33 | `justify` | s | RW | **alias of `align`** (§1.2) |
| 34 | `linespacing` | i | RW | `:23-31`; default 2 (`GuiControlProfile.cpp:192`); consumed by `GuiMLTextCtrl::reflow` (`GuiMLTextCtrl.cpp:1597`) |
| 35 | `mouseoverselected` | b | RW | `:380-388`; **not copied by `copyProfileFrom`** |
| 36 | `modal` | b | RW | `:390-395` |
| 37 | `numbersonly` | b | RW | `:397-405` |
| 38 | `returntab` | b | RW | `:407-415` |
| 39 | `opaque` | b | RW | `:417-425`; gates `renderFill` (`GuiControl.cpp:3384-3385`) |
| 40 | `overridestylefont` | b | RW | `:427-435` |
| 41 | `shadowcolor` | s | RW | four floats 0..1 (`:437-456`) |
| 42 | `shadowoffset` | s | RW | `TPoint` string (`:458-466`); `initObject` seeds `{1,1}` (`GuiControlProfile.cpp:201`) |
| 43 | `soundbuttondown` | s | RW | `unknown40` (`:468-478`) |
| 44 | `soundbuttonover` | s | RW | `unknown41` (`:480-491`) |
| 45 | `tab` | b | RW | `:493-501` |
| 46 | `textgradient` | b | RW | `:503-511` |
| 47 | `textoffset` | s | RW | `TPoint` string (`:513-521`) |
| 48 | `textshadow` | b | RW | `:523-531` |
| 49 | `transparency` | f | RW | `:533-541`; read by `GuiBitmapCtrl::onRender` as the blit alpha, defaulting to `1.0` when no profile resolves (`GuiBitmapCtrl.cpp:130-136`) |

Methods (`:610-614`):

| Name | Params | Ret | Semantics |
| --- | --- | :---: | --- |
| `gettextwidth` | `"s"` | i | `TFontManager::getTextWidth(fonttype, fontsize, fontstyle, …)` (`:601-604`; `GuiControlProfile.cpp:152-157`) |
| `gettextheight` | `""` | i | `TFontManager::getTextHeight(...)` (`:606`; `GuiControlProfile.cpp:127-131`) |
| `preloadfont` | `""` | v | `TFontManager::preloadFont` (`:608`; `GuiControlProfile.cpp:124-125`) |

Ten string-typed names here are **T1 candidates** (unanswered → Number 0.0 →
`== "<any word>"` true): `align`, `justify`, `backgroundinset`, `bitmap`, all
six `*color*` strings, `boxextent`, `fontstyle`, the four `fontstyle*` bags,
`fonttype`, `shadowoffset`, both `soundbutton*`, `textoffset`.

### How a control reaches its profile

`GuiControl.profile` is `'o'` with `PropType == AcceptStringProperty`
(`GuiControlProperties.cpp:685`). The getter returns `m_tooltipProfile` or, when
that is null, the dynamic cast of `m_profile->readObject()` (`:411-418`); the
setter dynamic-casts and calls `setProfile`, **silently ignoring a non-profile
object** (`:420-425`). `AcceptStringProperty` means a *string* write is looked
up as a **universe global** and the resulting object handed to the setter
(`src/TAcceptStringProperty.cpp:10-17`) — so `ctrl.profile = "IRC_ButtonProfile"`
and `ctrl.profile = IRC_ButtonProfile` are the same operation, and a name that
is not a registered global assigns nothing.

`GuiTextListEntry.profile` (`src/gui/GuiTextListEntryProperties.cpp:180`) and
`GuiContextMenuCtrl`'s `profile`/`textprofile`/`scrollprofile`
(`GuiContextMenuCtrlProperties.cpp:157-159`) use the same mechanism —
`GuiContextMenuCtrl.profile` and `.scrollprofile` are the same slot (identical
pointers at `:157` and `:159`). Both classes are outside this wave; noted for
whoever takes them.

### Diff vs `gs2_gui.py`

| Member | Corpus files | Status |
| --- | ---: | --- |
| `transparency` | 19 | IMPLEMENTED (`_STYLE_FIELDS`, clamped 0..1 `:316-318`) |
| `border` | 17 | **WRONG** — treated as pixel width, clamped 0..3 (§1.1) |
| `fillcolor` | 12 | IMPLEMENTED (`:305`) |
| `opaque` | 11 | IMPLEMENTED (`:319`) |
| `fontsize` | 10 | IMPLEMENTED, clamped 9..28 (`:314-315`) |
| `fontcolor` | 9 | IMPLEMENTED (`:306`) |
| `bitmap` | 8 | IMPLEMENTED (skin sheet, `:325`); `.png` auto-suffix not modelled |
| `tab` | 8 | MISSING (retained on the object, not consulted) |
| `fontstyle` | 7 | IMPLEMENTED, `"b"` substring → bold only (`:323`) |
| `modal` | 6 | MISSING |
| `justify` | **5** | **MISSING — highest-value gap in this class** (§1.2) |
| `fontcolorhl` | 5 | MISSING |
| `fonttype` | 5 | MISSING (we always use the game font) |
| `textshadow` | 5 | IMPLEMENTED (`:327`) |
| `bordercolor` | 3 | IMPLEMENTED (`:307`) |
| `borderthickness` | 2 | MISSING |
| `fontcolorsel`, `shadowcolor`, `shadowoffset`, `textoffset` | 2 each | MISSING |
| `align`, `autosizewidth`, `fillcolorhl`, `fontcolorlink` | 1 each | `align`/`fillcolorhl` IMPLEMENTED; other two MISSING |
| the remaining 30 | 0 | not worth implementing |

---

## 3. `GuiMLTextCtrl` — 13 properties, 24 methods

Parent `GuiControl` (`GuiMLTextCtrlProperties.cpp:349`). Props `:305-319`,
funcs `:321-346`. **All 13 properties read/write; no raw-address entries** —
every accessor body is in this file and was read.

| Name | Type | R/W | Semantics |
| --- | :---: | :---: | --- |
| `allowedtags` | s | RW | CSV; getter `m_allowedTags->GetCommaText2()`, setter builds a `TStringList` and calls `setAllowedTags` (`:12-21`) |
| `alpha` | f | RW | **`htmlPage->m_alpha` / `setAlpha` — shadows `GuiControl.alpha`** (`:23-31`, §1.13) |
| `cursorposition` | i | RW | getter is the raw field, setter is `setCursorPosition` (`:33-41`) |
| `deniedsound` | s | RW | plain field (`:43-51`) |
| `disallowedtags` | s | RW | **computed complement of `allowedtags`** (`:53-71`, §1.15) |
| `htmllinks` | b | RW | plain field (`:73-81`) |
| `htmlcompatibility` | b | RW | `htmlPage->get/setHTMLCompatibility` (`:83-91`) |
| `maxchars` | i | RW | plain field (`:93-101`) |
| `parsetags` | b | RW | setter `setParseTags` (`:103-111`) |
| `plaintext` | s | RW | raw buffer (`:113-123`) |
| `text` | s | RW | escaped view of `plaintext` (`:125-134`, §1.14) |
| `urlbase` | s | RW | `htmlPage->get/setURLBase` (`:136-144`) |
| `wordwrap` | b | RW | `htmlPage->m_wordWrap` / `setWordWrap` (`:146-154`); read by `reflowResize` to decide whether the control's width is recomputed (`GuiMLTextCtrl.cpp:1618-1621`) |

Methods:

| Name | Params | Ret | Semantics |
| --- | --- | :---: | --- |
| `addtext` | `"sb"` | v | escapes, then `addText(text, len, flag)` (`:156-160`); the bool's meaning was **not** determined (`GuiMLTextCtrl::addText` at `:148-152` forwards it as `pUnknown`) |
| `deselecttext` | `""` | v | `clearSelection()` (`:162-165`) |
| `findtext` | `"si"` | i | **int is a flag mask** (§1.16) |
| `findtextat` | `"sii"` | i | `(needle, position, flags)` (`:172-175`) |
| `getcursorline` | `""` | i | `getCursorLine()` (`:177-180`) |
| `getline` | `"i"` | s | `getLine(n)` (`:182-185`); body at `GuiMLTextCtrl.cpp:602` **not read** |
| `getlinecount` | `""` | i | `getLineCount()` (`:187-190`); body not read |
| `getlines` | `""` | o | `getLines()` → `TScriptEnvironment::makeVarFromStringList(lines, true)`, list freed after (`:192-198`) |
| `getselectedposition` | `""` | i | selection start, **`-1` if none** (`:200-206`) |
| `getselectedlength` | `""` | i | `end - start`, **`-1` if none** (`:208-214`) |
| `getcolumnandlineofposition` | `"i"` | **s** | `"<column>,<line>"` (`:216-226`, §1.18) |
| `gettext` | `""` | s | alias of the `text` getter (`:228-231`) |
| `reflow` | `""` | v | §1.5 |
| `replacetext` | `"ssi"` | i | count replaced, **capped at 1000**, flags masked to `&2` (`:238-241`; `GuiMLTextCtrl.cpp:349-390`) |
| `scrolltobottom` | `""` | v | `scrollToBottom()` (`:243-246`); body at `GuiMLTextCtrl.cpp:1298` not read |
| `scrolltotag` | `"s"` | v | `scrollToTag(tag)` (`:248-251`); body at `:1311` not read |
| `scrolltotop` | `""` | v | `scrollToTop()` (`:253-256`); body at `:1283` not read |
| `scrolltoline` | `"i"` | v | `scrollToLine(n)` (`:258-261`); body at `:1356` not read |
| `scrolltoposition` | `"i"` | v | `scrollToPosition(n)` (`:263-266`); body at `:1391` not read |
| `selecttext` | `"ii"` | **b** | `selectText(position, length)` (`:268-271`); body at `:486` not read |
| `setcursorcolumnandline` | `"ii"` | v | `(column, line)` (`:273-276`); body at `:701` not read |
| `setlines` | `"o"` | v | joins the array's cells with `\n` and calls `setText` — **note it does NOT escape**, unlike `settext` (`:278-293`) |
| `settext` | `"s"` | v | alias of the `text` setter, escapes (`:295-298`) |
| `trimhorizontally` | `""` | v | `trimHorizontally()` (`:300-303`); body at `:1423` not read |

Related non-scripted behaviour worth knowing: `GuiMLTextCtrl::resize` pushes the
new extent into the HTML page (`GuiMLTextCtrl.cpp:1536-1540`), and
`onParentResized` only marks the page dirty (`:1542-1546`) — the relayout is
deferred to the next `reflow`.

### Diff vs `gs2_gui.py`

`class GuiMLTextCtrl(GuiControl)` at `gs2_gui.py:1694`.

| Member | Corpus files | Status |
| --- | ---: | --- |
| `text` | (52 across all control classes) | IMPLEMENTED as a plain attribute (`:894`); escaping (§1.14) not modelled |
| `urlbase` | 5 | IMPLEMENTED **by accident** — falls into the generic `_members` dict, so `Serverlist_EventNews.urlbase = x` then `openURL(Serverlist_EventNews.urlbase @ url)` round-trips correctly. Not claimed by `_TORQUE_PROPS`, so a *construction-block* `urlbase = ...` would fall through to a temp under the VM's existence gate |
| `reflow` | 0 in these corpora (see §7) | IMPLEMENTED as cache invalidation (`:1706`, `:1714-1720`); does not resize, does not fire `onReflow` |
| `getlines` | 1 | IMPLEMENTED (`GuiControl._METHOD_NAMES`, `:870`) |
| `setlines`, `settext`, `gettext`, `addtext`, `scrolltobottom` | 0 | IMPLEMENTED (`:869-872`) |
| `wordwrap` | **7** | **MISSING and existence-gated** — not in `_TORQUE_PROPS` (`:848-863`), so `wordwrap = true;` in a construction block never reaches the control. Note one site writes the **string** `"1"` to this `'b'` property (`graal-loginserver/weapons/weapon-StartConnectMessage.txt:110`); others write `true`/`false` |
| `htmlcompatibility` | 5 | MISSING, existence-gated |
| `maxchars` | 4 | MISSING, existence-gated |
| `parsetags` | 3 | MISSING, existence-gated — and it changes what `findtext`/`replacetext` skip (§1.16) |
| `allowedtags`, `disallowedtags`, `cursorposition`, `deniedsound`, `htmllinks`, `plaintext` | 2 each | MISSING, existence-gated |
| `alpha` | 0 on a GUI control | MISSING; all 12 corpus `.alpha` writes are on `tilelayers[n]`/`findimg(n)`/`player` (§1.13) |
| the other 19 methods | 0 | MISSING |

Corrected from the first pass, which counted dotted forms only and reported 0
for the whole property list. The eleven properties above are all written **bare
in construction blocks**, which is precisely the case the VM's existence gate
drops on the floor — so today they do not merely go unrendered, they do not even
land on the object. Claiming all thirteen names in `GuiMLTextCtrl._TORQUE_PROPS`
is a one-line fix worth doing before any of the behaviour.

The remaining substantive gap is `reflow`'s resize + `onReflow` (§1.5).

---

## 4. `GuiScrollCtrl` — 8 properties, 5 methods

Parent `GuiControl` (`GuiScrollCtrlProperties.cpp:168`). Props `:149-158`,
funcs `:160-166`. **All 8 read/write; no raw-address entries.** All accessor
bodies are in this file and were read; the `GuiScrollCtrl::` methods they call
were read for `scrollTo`/`scrollDelta`/`getChildrenFitHeight`, **not** for
`computeSizes` (`GuiScrollCtrl.cpp:135`), `calcThumbs` or `scrollRectVisible`
(`:950`).

| Name | Type | R/W | Semantics |
| --- | :---: | :---: | --- |
| `childmargin` | s | RW | `TPoint` string; the setter calls `computeSizes()` (`:37-48`). Feeds `getChildrenFitHeight` as `unknown22 * 2` (`GuiScrollCtrl.cpp:119-133`) and the client-inset calc at `:905-906` |
| `constantthumbheight` | b | RW | plain field (`:50-58`) |
| `hscrollbar` | s | RW | `{"alwaysOn","alwaysOff","dynamic"}`, **case-sensitive, silent no-op on a miss, `computeSizes()` only on a hit** (`:60-69`, §1.8) |
| `scrollpos` | s | RW | reads `"<x>,<y>"`-ish via `getTPointString`; the **setter is `scrollTo(x,y)`**, so writing it clamps, may fire `onScrolled`, and is a **no-op on a childless control** (`:71-80`, §1.6) |
| `tile` | b | RW | plain field, unrelated to `GuiBitmapCtrl.tile` (`:82-90`) |
| `vscrollbar` | s | RW | as `hscrollbar` (`:92-101`) |
| `wheelscrolllines` | i | RW | **setter ignores values `<= 0`** (`:103-112`) |
| `willfirstrespond` | b | RW | plain field (`:114-122`) |

| Method | Params | Ret | Semantics |
| --- | --- | :---: | --- |
| `scrolldelta` | `"ii"` | v | relative scroll (`:124-127`; `GuiScrollCtrl.cpp:945-948`) |
| `scrollrectvisible` | `"iiii"` | v | builds a `TRectangle` and calls `scrollRectVisible` (`:129-132`); body at `GuiScrollCtrl.cpp:950` **not read** |
| `scrollto` | `"ii"` | v | §1.6 |
| `scrolltobottom` | `""` | v | `scrollTo(0, INT_MAX)` — **resets x** (`:139-142`, §1.7) |
| `scrolltotop` | `""` | v | `scrollTo(0, 0)` — **resets x** (`:144-147`) |

### Diff vs `gs2_gui.py`

`class GuiScrollCtrl(GuiControl)` at `gs2_gui.py:1801`.

| Member | Corpus files | Status |
| --- | ---: | --- |
| `vscrollbar` / `hscrollbar` | 22 combined | PARTIAL. `vscrollbar` is claimed in `_TORQUE_PROPS` (`:854`) and honoured at draw time (`:1845-1848`, `alwaysoff` suppresses the bar); `hscrollbar` is claimed but never read — we have no horizontal bar. Our comparison is `.lower()`ed (`:1845`), so we are *more* permissive than the oracle (§1.8) — harmless, since all corpus values already match exactly |
| `childmargin` | **8** (assignment sites) | **MISSING, and existence-gated.** Not in `_TORQUE_PROPS` (`:848-863`), so a construction-block `childMargin = "0 0";` / `childmargin = {10,10};` does **not** land on the control — it falls through to a temp, per the mechanism documented at `gs2_gui.py:841-847`. Corpus forms seen: `"0 0"` (string) ×4, `{0,0}` ×2, `{10,10}` ×5, `{5,5}` ×5, `{10,0}` ×1 — note both the string and array spellings (§8.6). **Highest-value gap in this class** |
| `scrollpos` | 1 real (see note) | **WRONG.** A raw count says 5 files, but 4 of those are the script-local `this.scrollpos` (`…/weapon-Serverlist_v4.txt:179` ×3, `graal-bomber-gs2/world/bomblobby.nw:338`, `:801`). The only true control usage is `graal-loginserver-dev/weapons/weapon-Staff_GraalShop.txt:1472` (`temp.spos = GraalShop_Sprites_Scroll.scrollpos;`) and `:1542` (the restore). We do not claim the name, so the read yields whatever `_members` holds (nothing on the first pass) and the write never touches `self.scroll_y` (`:1814-1815`) — the save/restore is a silent no-op |
| `scrolldelta` | 1 | IMPLEMENTED (`:1817`, `:1829-1836`), clamps to `max_scroll_y()`; does not fire `onScrolled` |
| `scrolltobottom` | 3 | PARTIAL — in `GuiControl._METHOD_NAMES` (`:872`) but with no `_m_scrolltobottom` on `GuiScrollCtrl`; the x-reset (§1.7) is not modelled |
| `constantthumbheight` | 2 | MISSING (cosmetic), existence-gated |
| `willfirstrespond` | 2 | claimed (`:855`) but inert |
| `tile` | see `GuiBitmapCtrl` below | the corpus `tile =` sites are bitmap controls, not scroll controls |
| `scrollto`, `scrollrectvisible`, `scrolltotop`, `wheelscrolllines` | 0 | MISSING |

Also absent on our side: `onScrolled` is never fired. No corpus handler for it
was found (see §7), so this is low priority.

---

## 5. `GuiBitmapCtrl` — 5 properties, 2 methods

Parent `GuiControl` (`GuiBitmapCtrlProperties.cpp:137`). Props `:67-113`,
funcs `:115-134`. **All read/write; no raw-address entries;** all bodies read.

| Name | Type | R/W | Semantics |
| --- | :---: | :---: | --- |
| `bitmap` | s | RW | filename; setter invalidates the rect (`:6-15`) |
| `bitmaprectangle` | s | RW | source sub-rect as a `TRectangle` string; **the setter also clears `fullbitmap`** (`:17-26`) — i.e. writing a sub-rect switches the control into part-blit mode as a side effect |
| `fullbitmap` | b | RW | plain field (`:28-36`); `initObject` defaults it `true` with a `64×64` rectangle (`GuiBitmapCtrl.cpp:50-54`) |
| `tile` | b | RW | invalidates only on an actual change (`:38-50`) |
| `wrap` | b | RW | **alias of `tile`** (`:104-112`, §1.3) |

| Method | Params | Ret | Semantics |
| --- | --- | :---: | --- |
| `setbitmap` | `"s"` | v | identical to writing `bitmap` (`:52-55`) |
| `setvalue` | `"ii"` | v | sets the pair passed as the source-**offset** `TPoint` to `TGUIRender::renderBitmap(Part)ToRectangle` (`:57-65`; consumed at `GuiBitmapCtrl.cpp:144-155`); invalidates on change |

Render path, for reference: `onRender` falls back to `GuiControl::onRender` when
the bitmap name is empty (`GuiBitmapCtrl.cpp:120-124`), resolves the profile the
usual way and takes `transparency` from it, defaulting to `1.0` if none resolves
(`:130-136`), then blits the whole image or the sub-rect depending on
`m_fullBitmap` (`:142-156`). `onWake` force-sets `active` (`:63-69`).
`getWidth`/`getHeight` are `TTexture::getTextureSize` of the bitmap
(`:102-116`) — **not registered as script properties**; the script-visible
`width`/`height` are `GuiControl`'s bounds (`GuiControlProperties.cpp:700-701`).

### Diff vs `gs2_gui.py`

`class GuiBitmapCtrl(GuiControl)` at `gs2_gui.py:2085`.

| Member | Corpus files | Status |
| --- | ---: | --- |
| `bitmap` | 21 (all classes; shared with the profile property of the same name) | IMPLEMENTED (`:2090`, `:2098-2107`), and we additionally accept `image` as a synonym — **that synonym is ours, not the reference's**; no `image` property exists in any of the six tables audited here |
| `tile` | **12** | **MISSING, and existence-gated on our side is not the issue** — `tile` *is* claimed in `_TORQUE_PROPS` (`gs2_gui.py:862`), so the write lands, but nothing reads it: we always stretch-to-fit (`:2109-2118`). Real sites are Login construction blocks, e.g. `graal-loginserver/weapons/weapon-Rescripted_Serverlist.txt:988` (`tile = true;`), `:1003` (`tile = 0;`), `:1100`, `:1244`, `:1977`, `:2008`, `:2039`; `graal-loginserver/weapons/weapon-ServerListScreen.txt:1610`, `:1647`, `:1724` (`tile = false;`). Note both boolean and 0/1 spellings. The receiving class was not disambiguated per site |
| `wrap` | 0 | MISSING (alias of `tile`, §1.3 — implementing `tile` gets it free) |
| `bitmaprectangle` / `fullbitmap` | 0 | MISSING (no sub-rect blitting) |
| `setbitmap`, `setvalue` | 0 | MISSING (not in `_METHOD_NAMES`) |

---

## 6. `GuiBitmapButtonCtrl` — 3 properties, 1 method (+ its `GuiButtonBaseCtrl` parent)

Parent `GuiButtonBaseCtrl` (`GuiBitmapButtonCtrlProperties.cpp:83`), whose
parent is `GuiControl` (`GuiButtonBaseCtrlProperties.cpp:129`). §1.4 is the
headline.

Own table (`:40-67`), all `'s'` RW, all bodies read:

| Name | Semantics |
| --- | --- |
| `normalbitmap` | `setBitmap(name, 0)` (`:20-23`) |
| `mouseoverbitmap` | `setBitmap(name, 1)` (`:10-13`) |
| `pressedbitmap` | `setBitmap(name, 2)` (`:30-33`) |

Own method (`:70-80`): `setbitmap(s, i)` → `setBitmap(name, slot)` (`:35-38`) —
the slot indices above.
`GuiBitmapButtonCtrl::setBitmap` itself was **not read**.

Inherited from `GuiButtonBaseCtrl` (props `:68-105`, funcs `:107-126`), all RW:

| Name | Type | Semantics |
| --- | :---: | --- |
| `buttontype` | s | index into `{"PushButton","ToggleButton","RadioButton"}` (`:5-9`); exact-match setter, silent no-op on a miss (`:11-26`, §1.8) |
| `checked` | b | `getChecked`/`setChecked` (`:28-36`) |
| `groupnum` | i | plain field (`:38-46`) |
| `text` | s | `getText`/`setText` (`:48-56`) |
| `gettext()` / `settext(s)` | s / v | aliases of the `text` accessors (`:58-66`) |

Corpus (**corrected — the first pass counted dotted forms only and reported 0
for all three bitmap slots**): `normalbitmap` **8** files, `mouseoverbitmap`
**8**, `pressedbitmap` **8**, `checked` **10**, `groupnum` **8**, `buttontype`
**2** (`buttonType = "PushButton"` ×12). The class name `GuiBitmapButtonCtrl`
itself appears in 3 files, but the properties are set in construction blocks on
controls created elsewhere — e.g.
`graal-loginserver/weapons/weapon-Rescripted_IRC_Login2001.txt:324-326`
(`normalbitmap = "gui2001_button.png"; mouseoverbitmap = …; pressedbitmap =
"gui2001_button_pressed.png";`) and `weapon-LoginScreen.txt:382`, `:386`.

### Diff vs `gs2_gui.py`

`class GuiBitmapButtonCtrl(GuiButtonCtrl)` at `:2138`. Single `bitmap`
attribute (`:2145-2160`), drawn stretched with the text overlaid
(`:2162-2181`).

| Member | Corpus files | Status |
| --- | ---: | --- |
| `normalbitmap` | 8 | **MISSING, and existence-gated** — not in this class's `_TORQUE_PROPS` (`:2145` adds only `bitmap`/`image`), so Login's 2001-style buttons never get a face at all: the write falls through to a temp and `self.bitmap` stays `""`, taking the `img is None` path (`:2166-2170`) into the plain `GuiButtonCtrl` skin |
| `mouseoverbitmap` | 8 | MISSING (hover face) |
| `pressedbitmap` | 8 | MISSING (pressed face) |
| `checked` | 10 | MISSING |
| `groupnum` | 8 | MISSING |
| `buttontype` | 2 | MISSING |
| `bitmap` | — | **extension** — no `bitmap` property exists on this class in the reference; ours is a stand-in for `normalbitmap` |

This is a materially bigger gap than the first pass reported: the three bitmap
slots are live Login content, not dead table entries. The cheap fix is to claim
all three names, map `normalbitmap` onto the existing `self.bitmap` and use the
other two for the hover/press states the class already tracks
(`GuiControl.hovered`/`pressed`, `gs2_gui.py:907-908`).

---

## 7. `GuiArrayCtrl` — 1 property, 0 methods

Parent `GuiControl` (`GuiArrayCtrlProperties.cpp:30`). One entry:
`allowmultipleselections`, `'b'`, RW, body read (`:6-23`) — §1.19.

`GuiTextListCtrl`'s parent is `GuiArrayCtrl`
(`src/gui/GuiTextListCtrlProperties.cpp:449`), so this name is reachable on
every text list.

Corpus: the class name appears in **0** files and `allowmultipleselections` in
**0** files. `gs2_gui.py` has no `GuiArrayCtrl` at all
(`_CONTROL_CLASSES`, `:3522-3534`) and `GuiTextListCtrl` derives straight from
`GuiControl` (`:2561`). **Verdict: do not implement.** Recorded here so the
next wave does not re-derive it.

---

## 8. Undetermined / corrections to the brief

1. **The `reflow` call-count in the brief is not reproducible.** The task states
   `reflow` is "called 2636 times across 5 corpus scripts". Across the six
   corpora named in the brief it appears in **zero** files. Tree-wide (excluding
   `FourPlay/quattroplay` itself) it appears in exactly three files:
   `Preagonal/gbf/bytecode/login/_F2LogWindow.gs2bc.gs2` (1 occurrence — the
   only real call site, `:31`: `("F2LogWindow_Text" @ temp.i).reflow();`),
   `Preagonal/gbf/bytecode/weapon-Scripted_RC.svg` (3), and
   `Preagonal/FourPlay/libqplay_symbols.txt`. The *placement* of `reflow` on
   `GuiMLTextCtrl` is confirmed and the call site is consistent with it (an RC
   log window's text pane), but the frequency claim should not be carried
   forward. Whatever produced 2636 was measuring something else.
2. **No corpus handler was found for `onReflow` or `onScrolled`.** Both events
   are real (`GuiMLTextCtrl.cpp:1642-1644`; `GuiScrollCtrl.cpp:930-937`) but
   nothing in the six corpora binds them, so implementing them is speculative.
3. **Bodies deliberately not read**, so no semantics are asserted for them:
   `escapeEscapes`/`insertEscapes`; `GuiMLTextCtrl::getLine`, `getLineCount`,
   `selectText`, `setCursorColumnAndLine`, `trimHorizontally`, all five
   `scrollTo*`; `GuiScrollCtrl::computeSizes`, `calcThumbs`,
   `scrollRectVisible`; `GuiBitmapButtonCtrl::setBitmap`;
   `TGUIRender::renderStyleButton`; `getStringTPoint`/`getStringTRectangle`/
   `getStringColor` and their inverses.
3a. **The five profile fields of §1.21** (`bordercolorsel`, `fillcolorsel`,
   `normalbitmap`, `mouseoverbitmap`/`pressedbitmap`, plus `alpha`) — whether
   they are Era-build properties or inert dynamic vars is not decidable from
   FourPlay + `symbol_dump.log`. Needs a live capture.
4. **`GuiControlProfileProperties`' constructor has no `.s_decomped`** in
   `asm/TProperties/` — only D0/D1/D2. Its 49/3 counts rest on the C++ array
   bounds and a literal entry count, which agree with each other but are not
   asm-corroborated like the other five classes.
5. **Whether property-name lookup is case-folded was not determined.** The
   corpora write `childMargin`, `hScrollBar`, `buttonType`, `vScrollBar`,
   `fillColor`, `fontType` in mixed case while the tables register them
   lower-case. The *values* are demonstrably compared case-sensitively (§1.8);
   the *names* must be folded somewhere for this content to work.
   `compileProperties` decodes each name with `decodesimple` and keys it by
   `getHashcode(decodedName)` (`src/TProperties.cpp:121-123`) — **neither
   `decodesimple` nor `getHashcode` was read**, so where the folding happens is
   open. Do not assume either way.
6. **The `{10,10}` array form written to a `'s'`-typed property**
   (`childmargin`) depends on how `TScriptProperty::writeString` stringifies a
   GS2 array and how `getStringTPoint` parses it. Neither was read.
7. The five-property gap in `copyProfileFrom` (§1.10) was derived by diffing the
   copied field list (`GuiControlProfile.cpp:229-277`) against the 49-entry
   table. Both were read in full; the *consequence* (that a
   `GuiDefaultProfile`-seeded profile starts with those five at their
   constructor values) follows but was not observed live.

---

## 9. Suggested implementation order (ranked by corpus evidence)

**Step 0, and it dominates everything below: claim the names.** Every "MISSING"
entry above that is written *bare in a construction block* is not merely
unrendered — the VM's existence gate drops the write entirely, so the value
never reaches the object and cannot be recovered later. Adding these to the
relevant `_TORQUE_PROPS` sets is a handful of lines and strictly precedes any
rendering work:

- `GuiScrollCtrl`: `childmargin`, `scrollpos`, `constantthumbheight`,
  `wheelscrolllines`
- `GuiMLTextCtrl`: all 13 (`wordwrap` 7 files, `htmlcompatibility` 5,
  `maxchars` 4, `parsetags` 3, six more at 2)
- `GuiBitmapButtonCtrl`: `normalbitmap`, `mouseoverbitmap`, `pressedbitmap`
  (8 files each), `checked` (10), `groupnum` (8), `buttontype` (2)
- `GuiBitmapCtrl`: `bitmaprectangle`, `fullbitmap`, `wrap`

Then, by value:

1. **`GuiBitmapButtonCtrl`'s three bitmap slots** — 8 files each; today Login's
   2001-style buttons render with no face at all. Map `normalbitmap` onto the
   existing `self.bitmap`, wire the other two to `hovered`/`pressed`. (§6)
2. **`border` as a style enum + `borderthickness` as the width** — `border` is
   set in 17 files, 10 of those to the skinned value `5`, which we currently
   render as a 3px solid rectangle. Requires deciding what `border == 5` draws
   without a `TGUIStyle`; the honest fallback is the profile `bitmap` skin we
   already load. (§1.1)
3. **`justify` as an alias of `align`** — one line in `_STYLE_FIELDS` plus a
   read in `_profile_from_fields`; 5 files, 23 assignments, all
   `justify = "center"`. (§1.2)
4. **`childmargin`** — 8 files; accept both the `"0 0"` string and the `{10,10}`
   array spellings. (§4)
5. **`tile` on `GuiBitmapCtrl`** — 12 files; the name already lands, nothing
   reads it. Gets `wrap` free (§1.3).
6. **`wordwrap` on `GuiMLTextCtrl`** — 7 files; note the `"1"`-as-string
   spelling at `weapon-StartConnectMessage.txt:110`.
7. **`scrollpos` on `GuiScrollCtrl`** — 1 real site, but it is a save/restore
   pair that is silently a no-op today. Wire it to `scroll_x`/`scroll_y`. (§4)
8. `fontcolorhl` (5), `fonttype` (5), `modal` (7), `tab` (5), `overridestylefont`
   (5), `fillcolorna` (5), `focusonshow` (5) on profiles — cheap, each a
   `_STYLE_FIELDS` entry plus a renderer read.
9. `reflow`'s resize + `onReflow` (§1.5) — no corpus caller in these six
   corpora, so schedule only if a live capture shows an RC/log window.
10. Everything else in §2-§7 with a corpus count of 0 — leave
    registered-but-inert. `GuiArrayCtrl` in particular: do not implement (§7).

## 10. 2026-07-26 implementation round: `copyfrom` and the own-profile copy

The two profile-copy open items from §1.10/§1.11 are implemented; three
new oracle facts were established doing it, all body-read:

**(a) `copyfrom` is script-reachable on EVERY object, and two classes opt
in.** The registration is on the root object class
(`src/TGraalVarProperties.cpp:278-285`, `'v'` params `"o"`, raw address —
the body is `TGraalVar::copyFrom`, §1.10). The gate (`:2208-2214`) passes
for exactly two tables: `GuiControlProfile`
(`GuiControlProfileProperties.cpp:618`, §1.11) **and `TStaticVar`
(`TStaticVarProperties.cpp:16`)** — the second was not previously recorded,
and it is what makes `new TStaticVar()` script objects copyable. The live
`weapon-Scripted_RC` bytecode calls `.copyfrom(` six times (control-flow
graph `Preagonal/gbf/bytecode/weapon-Scripted_RC.svg`, method-call shape
`PushVariable copyfrom; AccessMember; Call`).

*Implemented:* `GS2Object.copy_from` + VM dispatch as a root-object method
(`reborn_protocol/gs2/values.py`, `vm.py _root_object_method`/
`_list_method`); the gate lives host-side — `GuiControl.copy_from` is the
reference's silent no-op, `GuiControlProfile.copy_from` re-enables it
(members copied with arrays cloned, plus our chain-root, which reproduces
the reference's all-49 registered copy under the chain model).

**(b) `useownprofile` IS a profile copyFrom.** `setUseOwnProfile(true)`
allocates an anonymous `GuiControlProfile`, `copyFrom`s the control's
current profile into it and makes it the effective profile — idempotent
while one exists; `false` destroys it and reverts
(`src/gui/GuiControl.cpp:1746-1806`). The getter is the derived read
`ownProfile != nullptr` (`GuiControlProperties.cpp:559-561`). This is what
the corpus' `useownprofile = true; profile.<field> = ...;` idiom relies on
for per-control styling — the recently-added mobile corpus writes it in 3
scripts (e.g. `graal-loginserver-mobile/weapons/weapon-Mobile_Login.txt:118`),
and it was previously UNCLAIMED, so the write (and the isolation) was
silently dropped.

**(c) Assigning `profile` drops an active own profile.**
`GuiControl::setProfile`'s own-profile branch destroys it and nulls the
slot before installing the new profile (`GuiControl.cpp:1706-1709`).

*Implemented:* `GuiControl.own_profile` +
`_set_use_own_profile` (pyReborn `gs2_gui/base.py`); the `profile` getter
now also resolves a NAME to the registered/vivified profile object (the
`AcceptStringProperty` getter always returns an object, §"How a control
reaches its profile"), so `ctrl.profile.<field> = ...` writes land on the
shared profile exactly as the reference does when no own profile exists.
Also claimed from the same table: `clipchildren` (`:660`) and
`cliptobounds` (`:662`) — store-only, 3+2 mobile-corpus scripts write them
bare.
