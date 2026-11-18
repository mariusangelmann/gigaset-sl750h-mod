# Main-menu / Netzdienste analysis (Ghidra decompiler)

Decompiled with `re/ghidra/DecompileList.java` against the imported R1 program.
All addresses are real CPU addresses. Status is **verified** (read from the
decompiler/disassembly) unless marked *hypothesis*.

## Globals

| Addr | Name | Meaning |
|---|---|---|
| 0x87546c | `menu_state_ptr` | pointer to the list/submenu state struct; `menu_state_get()` (0x16fdb2) returns it. **Null (0) at idle and on the main grid** — set only for list-style screens. |
| 0x875434 | `ui_state_ptr` | pointer to the UI window state struct (+4 next-handler ptr, +8 flags, +0xa event code). Also null at idle. |
| 0x875438 | (unnamed) | holds a pointer (seen = 0x8752CA) that **is** live on the main grid — the main grid's own state, distinct from the two above. |
| 0x2ae8fa | `main_menu_table` | 8 records, stride 14 (0xe). |

## main_menu_table record (stride 14)

- `+0` u32 **visibility predicate**/2 (not a select handler). `main_menu_visibility_loop` (0x16e950) calls all 8 during redraw, and the renderer calls them per item — so **patching +0 fires during drawing**, which is why the first Snake hook there did nothing useful.
- `+5` u16 subitem count.
- `+6` u32 pointer to the item's **sub-action array** (u32 entries), indexed by the subitem number — read by `FUN_0016e684`.

Item 3 = Netzdienste (predicate `main_menu_pred_netzdienste` @ 0x16f0be hard-codes index 3).

## Why the old hook never fired

`menu_state+1` is the **render iterator**, not the live cursor: the renderer
`FUN_0016e6f6` (0x16e6f6) sweeps `*(menu_state+1)` from 0 while `< 8`, calling
each item's predicate to build the visible list. The Snake hook gated on
`[menu_state]+1 == 3`, i.e. on the iterator mid-sweep, and `menu_state_ptr` is
null on the main grid anyway. Both reasons mean the gate never held.

## Select path (in progress)

The renderer `FUN_0016e6f6` returns the selected item's **action pointer**
(from `record+6`) when OK (`FUN_0011cfbc(...|0x1a)`) is active, else a default
screen handler (`0xb7986`→0x16f30c, `0xb78d1`→0x16f1a2). Those handlers
(`FUN_0016f30c`, `FUN_0016f1a2`) are UI window procs driven by `ui_state_ptr`
(+0xa event, +4 next handler). So "Netzdienste opens Netzdienste" = selecting
item 3 returns its submenu action as the next window proc.

**Open question (next step):** pin the exact instruction where the *main* item
index (not the render iterator) is read and its `record+6` action dispatched on
OK, so a hook there (gated on index == 3) can jump to the Snake launcher
instead of the Netzdienste submenu. The main-grid state lives via `[0x875438]`
→ 0x8752CA; confirm the selected-index field there live with `monitor/mon.py`
while on Netzdienste, then hook the dispatch.

## Reusable Ghidra scripts

- `re/ghidra/DecompileList.java <addr1,addr2,...> [outfile]` — decompile a list
  of functions by hex CPU address (creates a function at the address if none).
- `re/ghidra/DumpSyms.java <name1,name2>` — print addresses of named symbols.

Run against the imported project:

```bash
export GHIDRA_INSTALL_DIR=~/tools/ghidra_12.1.4_PUBLIC
export JAVA_HOME=/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" work/ghidra sl750h -process -noanalysis \
  -scriptPath re/ghidra -postScript DecompileList.java 0x16e6f6 out.c
```
