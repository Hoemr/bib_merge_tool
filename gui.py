"""Desktop GUI for BibTeX Merge Tool using tkinter."""

from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from typing import Any

from bibtool.deduplicate import find_duplicate_groups
from bibtool.export import export_bib, export_duplicate_report, format_entry
from bibtool.keygen import resolve_key_conflicts
from bibtool.merge import auto_merge_group, manual_merge
from bibtool.parser import parse_multiple_files
from bibtool.search import search_entries

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

@dataclass
class AppState:
    entries: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dup_groups: list[list[dict[str, Any]]] = field(default_factory=list)
    merged_entries: list[dict[str, Any]] = field(default_factory=list)
    unique_entries: list[dict[str, Any]] = field(default_factory=list)
    final_entries: list[dict[str, Any]] = field(default_factory=list)
    unresolved_groups: list[list[dict[str, Any]]] = field(default_factory=list)
    merge_decisions: dict[int, str] = field(default_factory=dict)

    def reset(self) -> None:
        self.entries.clear()
        self.warnings.clear()
        self.dup_groups.clear()
        self.merged_entries.clear()
        self.unique_entries.clear()
        self.final_entries.clear()
        self.unresolved_groups.clear()
        self.merge_decisions.clear()

    def rebuild_final(self) -> None:
        # Unique entries (no duplicates)
        out = list(self.unique_entries)
        # Merged or kept entries from resolved duplicate groups
        out.extend(self.merged_entries)
        # Unresolved (skipped) duplicate groups — keep all their entries
        for group in self.unresolved_groups:
            out.extend(group)
        # Also include entries from groups that haven't been acted on yet
        for gi, group in enumerate(self.dup_groups):
            if gi not in self.merge_decisions:
                out.extend(group)
        self.final_entries = out
        resolve_key_conflicts(self.final_entries, preserve_existing=True)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class BibMergeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BibTeX Merge Tool")
        self.root.geometry("1280x800")
        self.root.minsize(1000, 650)

        self.state = AppState()

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TButton", padding=4)
        style.configure("TLabel", padding=2)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._build_import_tab()
        self._build_duplicates_tab()
        self._build_search_tab()
        self._build_export_tab()

    # ---- helpers ----

    def _set_status(self, tab: str, text: str) -> None:
        self.status_labels[tab].config(text=text)

    # ==================================================================
    # Tab 1 — Import
    # ==================================================================

    def _build_import_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Import  ")

        self.status_labels: dict[str, ttk.Label] = {}

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Button(top, text="Select .bib Files", command=self._on_select_files).pack(side=tk.LEFT)
        ttk.Button(top, text="Parse", command=self._on_parse).pack(side=tk.LEFT, padx=(8, 0))

        self.import_status = ttk.Label(top, text="No files loaded.")
        self.import_status.pack(side=tk.LEFT, padx=(16, 0))
        self.status_labels["import"] = self.import_status

        self.file_list_var = tk.StringVar(value=[])
        self.file_listbox = tk.Listbox(tab, listvariable=self.file_list_var, height=4, font=("Consolas", 9))
        self.file_listbox.pack(fill=tk.X, padx=8, pady=4)

        self.import_log = tk.Text(tab, height=18, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.import_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._pending_files: list[str] = []

    def _on_select_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select .bib files",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if paths:
            self._pending_files = list(paths)
            self.file_list_var.set([os.path.basename(p) for p in paths])

    def _on_parse(self) -> None:
        if not self._pending_files:
            messagebox.showwarning("No files", "Please select .bib files first.")
            return

        self.state.reset()
        result = parse_multiple_files(self._pending_files)

        self.state.entries = result.entries
        self.state.warnings = result.warnings

        groups = find_duplicate_groups(result.entries)
        self.state.dup_groups = groups

        grouped_ids = {id(e) for g in groups for e in g}
        self.state.unique_entries = [e for e in result.entries if id(e) not in grouped_ids]
        self.state.merged_entries.clear()
        self.state.unresolved_groups.clear()
        self.state.merge_decisions.clear()
        self.state.rebuild_final()

        self._set_status("import", f"Parsed {len(result.entries)} entries, found {len(groups)} duplicate group(s).")

        log = self.import_log
        log.config(state=tk.NORMAL)
        log.delete("1.0", tk.END)
        log.insert(tk.END, f"Parsed {len(result.entries)} entries from {len(self._pending_files)} file(s).\n")
        if result.warnings:
            log.insert(tk.END, "\nWarnings:\n")
            for w in result.warnings:
                log.insert(tk.END, f"  - {w}\n")
        else:
            log.insert(tk.END, "No warnings.\n")
        log.config(state=tk.DISABLED)

        self._refresh_dup_tree()

    # ==================================================================
    # Tab 2 — Duplicates
    # ==================================================================

    def _build_duplicates_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Duplicates  ")

        # Top bar
        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.dup_status = ttk.Label(top, text="No duplicates loaded.")
        self.dup_status.pack(side=tk.LEFT)
        self.status_labels["dup"] = self.dup_status

        self.keep_extras_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Keep abstract/keywords", variable=self.keep_extras_var).pack(side=tk.RIGHT)
        ttk.Button(top, text="Auto-Merge All", command=self._on_auto_merge_all).pack(side=tk.RIGHT, padx=(0, 8))

        # Treeview — takes all available space
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        cols = ("group", "entries", "key1", "title1", "year1", "decision")
        self.dup_tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        for c, w, h in [
            ("group", 60, "Group"), ("entries", 50, "#"),
            ("key1", 160, "First Key"), ("title1", 400, "Title"),
            ("year1", 50, "Year"), ("decision", 100, "Status"),
        ]:
            self.dup_tree.heading(c, text=h)
            self.dup_tree.column(c, width=w, minwidth=w)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.dup_tree.yview)
        self.dup_tree.configure(yscrollcommand=scrollbar.set)
        self.dup_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.dup_tree.bind("<Double-1>", self._on_dup_double_click)

        # Bottom action bar
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Button(btn_frame, text="Compare & Merge (对比并合并)",
                   command=self._on_dup_double_click).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Auto Merge (自动合并)",
                   command=self._on_auto_merge_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btn_frame, text="Keep All (保留全部不合并)",
                   command=self._on_keep_all_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btn_frame, text="Skip (跳过)",
                   command=self._on_skip_selected).pack(side=tk.LEFT, padx=(8, 0))

    def _selected_group_index(self) -> int | None:
        sel = self.dup_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a duplicate group first.")
            return None
        return int(sel[0])

    def _on_dup_double_click(self, _event: tk.Event = None) -> None:
        gi = self._selected_group_index()
        if gi is None:
            return
        if self.state.merge_decisions.get(gi):
            return
        CompareMergeDialog(self.root, self.state, gi, self.keep_extras_var.get(), self._after_action)

    def _on_auto_merge_selected(self) -> None:
        gi = self._selected_group_index()
        if gi is None:
            return
        if self.state.merge_decisions.get(gi):
            return
        merged = auto_merge_group(self.state.dup_groups[gi], keep_extras=self.keep_extras_var.get())
        self.state.merged_entries.append(merged)
        self.state.merge_decisions[gi] = "auto-merged"
        self.state.rebuild_final()
        title = merged.get("title", "")[:60]
        messagebox.showinfo("Merged", f"Group {gi + 1} auto-merged: \"{title}\"")
        self._refresh_dup_tree()
        self._select_next_group(gi)

    def _on_keep_all_selected(self) -> None:
        gi = self._selected_group_index()
        if gi is None:
            return
        if self.state.merge_decisions.get(gi):
            return
        self.state.merged_entries.extend(self.state.dup_groups[gi])
        self.state.merge_decisions[gi] = "kept all"
        self.state.rebuild_final()
        self._refresh_dup_tree()
        self._select_next_group(gi)

    def _on_skip_selected(self) -> None:
        gi = self._selected_group_index()
        if gi is None:
            return
        if self.state.merge_decisions.get(gi):
            return
        self.state.unresolved_groups.append(self.state.dup_groups[gi])
        self.state.merge_decisions[gi] = "skipped"
        self._refresh_dup_tree()
        self._select_next_group(gi)

    def _after_action(self, group_index: int = -1, auto_next: bool = False) -> None:
        """Called after a dialog-based merge completes."""
        self.state.rebuild_final()
        self._refresh_dup_tree()
        # Find the next undecided group after the one just resolved
        next_gi = self._find_next_undecided(group_index)
        if next_gi is None:
            self._set_status("dup", "All groups resolved.")
            return
        # Select it in the tree
        iid = str(next_gi)
        self.dup_tree.selection_set(iid)
        self.dup_tree.see(iid)
        # Auto-open Compare & Merge dialog for the next group
        if auto_next:
            self.root.after(100, lambda: CompareMergeDialog(
                self.root, self.state, next_gi,
                self.keep_extras_var.get(), self._after_action))

    def _find_next_undecided(self, after_gi: int) -> int | None:
        """Return the index of the first undecided group after *after_gi*, or any remaining."""
        # Try groups after the given index
        for gi in range(after_gi + 1, len(self.state.dup_groups)):
            if not self.state.merge_decisions.get(gi):
                return gi
        # Wrap around: try from the beginning
        for gi in range(after_gi + 1):
            if not self.state.merge_decisions.get(gi):
                return gi
        return None

    def _refresh_dup_tree(self) -> None:
        tree = self.dup_tree
        tree.delete(*tree.get_children())
        for gi, group in enumerate(self.state.dup_groups):
            first = group[0]
            decision = self.state.merge_decisions.get(gi, "")
            tree.insert("", tk.END, iid=str(gi), values=(
                gi + 1,
                len(group),
                first.get("ID", ""),
                (first.get("title", ""))[:70],
                first.get("year", ""),
                decision,
            ))

    def _select_next_group(self, current_gi: int) -> None:
        """Select the next undecided group after an action."""
        iids = self.dup_tree.get_children()
        for iid in iids:
            gi = int(iid)
            if gi > current_gi and not self.state.merge_decisions.get(gi):
                self.dup_tree.selection_set(iid)
                self.dup_tree.see(iid)
                return
        # No next undecided — try any remaining
        for iid in iids:
            gi = int(iid)
            if not self.state.merge_decisions.get(gi):
                self.dup_tree.selection_set(iid)
                self.dup_tree.see(iid)
                return

    def _action_on_gi(self, gi: int, action: Callable[[int], None]) -> None:
        """Execute an action on a group, refresh, show confirmation, auto-select next."""
        if self.state.merge_decisions.get(gi):
            return
        action(gi)
        self._refresh_dup_tree()
        self._select_next_group(gi)

    def _on_auto_merge_all(self) -> None:
        groups = self.state.dup_groups
        if not groups:
            return
        keep = self.keep_extras_var.get()
        self.state.merged_entries = [auto_merge_group(g, keep_extras=keep) for g in groups]
        self.state.unresolved_groups.clear()
        self.state.merge_decisions = {i: "auto-merged" for i in range(len(groups))}
        self.state.rebuild_final()
        self._refresh_dup_tree()
        self._set_status("dup", f"Auto-merged {len(groups)} group(s). Total: {len(self.state.final_entries)} entries.")

    def _do_auto_merge(self, gi: int) -> None:
        merged = auto_merge_group(self.state.dup_groups[gi], keep_extras=self.keep_extras_var.get())
        self.state.merged_entries.append(merged)
        self.state.merge_decisions[gi] = "auto-merged"
        self.state.rebuild_final()
        title = merged.get("title", "")[:60]
        messagebox.showinfo("Merged", f"Group {gi + 1} auto-merged: \"{title}\"")

    def _do_keep_all(self, gi: int) -> None:
        self.state.merged_entries.extend(self.state.dup_groups[gi])
        self.state.merge_decisions[gi] = "kept all"
        self.state.rebuild_final()
        messagebox.showinfo("Done", f"Group {gi + 1}: kept all {len(self.state.dup_groups[gi])} entries (not merged).")

    def _do_skip(self, gi: int) -> None:
        self.state.unresolved_groups.append(self.state.dup_groups[gi])
        self.state.merge_decisions[gi] = "skipped"

    # ==================================================================
    # Tab 3 — Search
    # ==================================================================

    def _build_search_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Search  ")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(top, text="Keywords:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=50)
        search_entry.pack(side=tk.LEFT, padx=(4, 8))
        search_entry.bind("<Return>", lambda _: self._on_search())
        ttk.Button(top, text="Search", command=self._on_search).pack(side=tk.LEFT)
        ttk.Button(top, text="Show All", command=self._on_show_all).pack(side=tk.LEFT, padx=(8, 0))

        self.search_status = ttk.Label(top, text="")
        self.search_status.pack(side=tk.LEFT, padx=(16, 0))
        self.status_labels["search"] = self.search_status

        cols = ("key", "title", "author", "year", "venue", "doi", "source")
        self.search_tree = ttk.Treeview(tab, columns=cols, show="headings", height=20)
        for c, w, h in [
            ("key", 150, "Key"), ("title", 300, "Title"),
            ("author", 200, "Author"), ("year", 50, "Year"),
            ("venue", 150, "Venue"), ("doi", 150, "DOI"),
            ("source", 100, "Source"),
        ]:
            self.search_tree.heading(c, text=h)
            self.search_tree.column(c, width=w, minwidth=40)
        self.search_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.search_tree.bind("<Double-1>", self._on_search_double_click)

        self._search_results: list[dict[str, Any]] = []

    def _on_search(self) -> None:
        query = self.search_var.get()
        results = search_entries(self.state.final_entries, query)
        self._search_results = results
        self._refresh_search_tree(results)
        self._set_status("search", f"{len(results)} result(s)")

    def _on_show_all(self) -> None:
        self.search_var.set("")
        self._search_results = list(self.state.final_entries)
        self._refresh_search_tree(self._search_results)
        self._set_status("search", f"{len(self._search_results)} entries")

    def _refresh_search_tree(self, results: list[dict[str, Any]]) -> None:
        tree = self.search_tree
        tree.delete(*tree.get_children())
        for i, e in enumerate(results):
            tree.insert("", tk.END, iid=str(i), values=(
                e.get("ID", ""),
                (e.get("title", ""))[:60],
                (e.get("author", ""))[:40],
                e.get("year", ""),
                (e.get("journal", "") or e.get("booktitle", ""))[:30],
                (e.get("doi", ""))[:30],
                e.get("_source_file", ""),
            ))

    def _on_search_double_click(self, _event: tk.Event) -> None:
        sel = self.search_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        entry = self._search_results[idx]
        EntryDetailDialog(self.root, entry)

    # ==================================================================
    # Tab 4 — Export
    # ==================================================================

    def _build_export_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Export  ")

        self.export_status = ttk.Label(tab, text="No entries to export.")
        self.export_status.pack(anchor=tk.W, padx=12, pady=(12, 4))
        self.status_labels["export"] = self.export_status

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=12, pady=4)

        ttk.Button(btn_frame, text="Export master.bib", command=self._export_master).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Export search results (selected.bib)", command=self._export_selected).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Export duplicate report (.md)", command=self._export_report).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Export unresolved duplicates", command=self._export_unresolved).pack(fill=tk.X, pady=2)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _event: tk.Event) -> None:
        tab_text = self.notebook.tab(self.notebook.select(), "text").strip()
        if tab_text == "Export":
            n = len(self.state.final_entries)
            self.export_status.config(text=f"{n} entries ready for export." if n else "No entries to export.")

    def _save_to_file(self, content: str, ext: str, ftypes: list[tuple[str, str]], default_name: str, empty_msg: str, done_msg: str) -> None:
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=ftypes, initialfile=default_name)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Done", done_msg)

    def _export_master(self) -> None:
        if not self.state.final_entries:
            messagebox.showinfo("Nothing to export", "Parse files first.")
            return
        self._save_to_file(export_bib(self.state.final_entries), ".bib", [("BibTeX", "*.bib")], "master.bib", "", f"Exported {len(self.state.final_entries)} entries.")

    def _export_selected(self) -> None:
        if not self._search_results:
            messagebox.showinfo("Nothing to export", "Run a search first.")
            return
        self._save_to_file(export_bib(self._search_results), ".bib", [("BibTeX", "*.bib")], "selected.bib", "", f"Exported {len(self._search_results)} entries.")

    def _export_report(self) -> None:
        if not self.state.dup_groups:
            messagebox.showinfo("Nothing to export", "No duplicate groups.")
            return
        self._save_to_file(export_duplicate_report(self.state.dup_groups), ".md", [("Markdown", "*.md")], "duplicate_report.md", "", "Report exported.")

    def _export_unresolved(self) -> None:
        if not self.state.unresolved_groups:
            messagebox.showinfo("Nothing to export", "No unresolved duplicates.")
            return
        entries = [e for g in self.state.unresolved_groups for e in g]
        self._save_to_file(export_bib(entries), ".bib", [("BibTeX", "*.bib")], "unresolved_duplicates.bib", "", f"Exported {len(entries)} unresolved entries.")


# ---------------------------------------------------------------------------
# Compare & Merge Dialog
# ---------------------------------------------------------------------------

class CompareMergeDialog(tk.Toplevel):
    """Side-by-side comparison dialog for a duplicate group.

    Shows each entry as a column, each field as a row.
    User clicks a cell to select which entry's value to keep per field.
    """

    def __init__(
        self,
        parent: tk.Tk,
        state: AppState,
        group_index: int,
        keep_extras: bool,
        on_done: Callable[[int, bool], None],
    ) -> None:
        super().__init__(parent)
        self.title(f"Compare & Merge — Group {group_index + 1}")
        self.geometry("1100x650")
        self.minsize(800, 450)
        self.transient(parent)
        self.grab_set()

        self._state = state
        self._gi = group_index
        self._keep_extras = keep_extras
        self._on_done = on_done
        self._group = state.dup_groups[group_index]
        self._n = len(self._group)

        # Collect all field names (preserve order from first entry, then extras)
        seen: set[str] = set()
        self._fields: list[str] = []
        for entry in self._group:
            for k in entry:
                lk = k.lower()
                if lk in ("entrytype", "id", "_source_file"):
                    continue
                if lk not in seen:
                    seen.add(lk)
                    self._fields.append(lk)

        # Per-field selection: index into self._group
        self._selection: dict[str, int] = {}
        for f in self._fields:
            self._selection[f] = self._auto_pick(f)

        self._build_ui()

    def _auto_pick(self, field: str) -> int:
        """Pick the best entry index for a field (longest non-empty value)."""
        best_idx = 0
        best_val = ""
        for i, entry in enumerate(self._group):
            v = str(entry.get(field, ""))
            if v and len(v) > len(best_val):
                best_val = v
                best_idx = i
        return best_idx

    def _build_ui(self) -> None:
        # Header
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(header, text="Click a cell to select that entry's value for each field.",
                  font=("Segoe UI", 9, "italic")).pack(side=tk.LEFT)

        # Scrollable table area
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._canvas = tk.Canvas(container, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self._canvas.yview)
        hscroll = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self._canvas.xview)
        self._table_frame = ttk.Frame(self._canvas)

        self._table_frame.bind("<Configure>",
                               lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._table_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Mouse wheel scrolling — bind/unbind when mouse enters/leaves canvas area
        def _on_mousewheel(event: tk.Event) -> None:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_e: tk.Event) -> None:
            self.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(_e: tk.Event) -> None:
            self.unbind_all("<MouseWheel>")

        self._canvas.bind("<Enter>", _bind_wheel)
        self._canvas.bind("<Leave>", _unbind_wheel)
        self._table_frame.bind("<Enter>", _bind_wheel)

        self._build_table()

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        ttk.Button(btn_frame, text="Auto-Select Best (自动选择最优)",
                   command=self._auto_select_all).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Apply Merge (应用合并)",
                   command=self._apply_merge).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Cancel (取消)",
                   command=self.destroy).pack(side=tk.RIGHT, padx=(0, 8))

    def _build_table(self) -> None:
        frame = self._table_frame
        # Clear existing
        for w in frame.winfo_children():
            w.destroy()

        n = self._n
        entry_labels = []
        for i, entry in enumerate(self._group):
            label = entry.get("ID", f"Entry {i+1}")
            entry_labels.append(label)

        # Header row
        ttk.Label(frame, text="Field", font=("Segoe UI", 9, "bold"),
                  width=18, anchor="w").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        for i in range(n):
            ttk.Label(frame, text=entry_labels[i], font=("Segoe UI", 9, "bold"),
                      width=30, anchor="w").grid(row=0, column=i + 1, sticky="w", padx=4, pady=2)

        # Field rows
        self._cell_widgets: dict[str, list[tk.Label]] = {}
        for ri, field in enumerate(self._fields):
            row = ri + 1
            ttk.Label(frame, text=field, font=("Segoe UI", 9),
                      width=18, anchor="w", foreground="#333").grid(
                row=row, column=0, sticky="nw", padx=4, pady=1)

            cell_labels = []
            for ci in range(n):
                val = str(self._group[ci].get(field, ""))
                display = val[:120] + ("..." if len(val) > 120 else "")
                if not display:
                    display = "—"

                lbl = tk.Label(
                    frame, text=display, font=("Consolas", 9),
                    wraplength=280, justify="left", anchor="w",
                    padx=6, pady=3, cursor="hand2",
                    relief="groove", borderwidth=1,
                )
                lbl.grid(row=row, column=ci + 1, sticky="ew", padx=2, pady=1)
                lbl.bind("<Button-1>", lambda _e, f=field, c=ci: self._select_cell(f, c))
                cell_labels.append(lbl)

            self._cell_widgets[field] = cell_labels

        # Highlight initial selection
        for field in self._fields:
            self._highlight(field)

    def _select_cell(self, field: str, col: int) -> None:
        self._selection[field] = col
        self._highlight(field)

    def _highlight(self, field: str) -> None:
        sel = self._selection[field]
        for i, lbl in enumerate(self._cell_widgets[field]):
            if i == sel:
                lbl.config(background="#d4edda", relief="solid", borderwidth=2)
            else:
                lbl.config(background="#f8f9fa", relief="groove", borderwidth=1)

    def _auto_select_all(self) -> None:
        for field in self._fields:
            self._selection[field] = self._auto_pick(field)
            self._highlight(field)

    def _apply_merge(self) -> None:
        field_choices = {f: idx for f, idx in self._selection.items()}
        merged = manual_merge(self._group, base_index=0,
                              field_choices=field_choices,
                              keep_extras=self._keep_extras)
        self._state.merged_entries.append(merged)
        self._state.merge_decisions[self._gi] = "manual-merged"
        self.destroy()
        self._on_done(self._gi, True)


# ---------------------------------------------------------------------------
# Entry Detail Dialog
# ---------------------------------------------------------------------------

class EntryDetailDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, entry: dict[str, Any]) -> None:
        super().__init__(parent)
        self.title(entry.get("ID", "Entry"))
        self.geometry("700x500")
        self.transient(parent)

        bibtex = format_entry(entry)

        text = tk.Text(self, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        text.insert(tk.END, bibtex)
        text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="Copy to Clipboard", command=lambda: self._copy(bibtex)).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT)

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "BibTeX copied to clipboard.", parent=self)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    BibMergeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
