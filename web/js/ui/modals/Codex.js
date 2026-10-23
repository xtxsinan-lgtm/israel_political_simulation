/* Port of game/ui/controllers/CodexController.gd (+ scenes/modals/CodexOverlay.tscn) and
 * game/ui/components/CodexAutoLinker.gd.
 *
 * CodexOverlay: Control (500,120)-(1420,520) on LedgerCodexLayer, toggled by C (UIManager).
 * Godot shows a RichTextLabel 640x480 with the fixed sentence and auto links; link clicks emit
 * codex_entry_requested(meta) which nobody handles. Web intent fix: paper panel background and
 * clicking a link shows that term's entry (title + one-line definition) inside the overlay.
 */
import { el, rect, label } from "../../core/controls.js";

/* The 4 built-in CodexAutoLinker terms + one-line definitions (web addition: Godot has none). */
const BUILTIN_TERMS = [
  { id: "mahapach", title: "大转折", def: "1977年5月大选，贝京领导的利库德集团首次击败工党，结束了工党自建国以来连续29年的执政。" },
  { id: "bader_ofer", title: "巴德尔-奥弗法", def: "以色列议会分配剩余席位的方法（洪德法的变体），按得票比例分配120席，略偏向大党。" },
  { id: "histadrut", title: "以色列总工会", def: "以色列劳工总联合会，集工会、大雇主与医保机构于一身，是工党体系的经济支柱。" },
  { id: "gush_emunim", title: "古什埃穆尼姆", def: "“信仰集团”，1974年成立的宗教民族主义定居运动，推动在西岸和加沙兴建定居点。" },
];

/** CodexAutoLinker: same term order and first-match rule as the .gd; returns DOM segments. */
export class CodexAutoLinker {
  constructor(codexTerms) {
    this.terms = BUILTIN_TERMS.map((t) => ({ ...t }));
    // Godot iterates the whole codex_terms.json dict (yielding a junk term "terms");
    // the intent is the `terms` table, so read that (empty in the shipped data).
    const raw = (codexTerms && typeof codexTerms === "object" && codexTerms.terms && typeof codexTerms.terms === "object")
      ? codexTerms.terms : {};
    for (const id of Object.keys(raw).sort()) {
      const row = raw[id] && typeof raw[id] === "object" ? raw[id] : {};
      const title = String(row.title ?? row.name_zh ?? id);
      if (title !== "") this.terms.push({ id, title, def: String(row.definition ?? row.summary ?? row.def ?? row.text ?? "") });
    }
  }

  term(id) { return this.terms.find((t) => t.id === id) || null; }

  /** Segments [{text} | {text, link:id}] = inject_codex_links without the bbcode. */
  segments(rawText) {
    let segs = [{ text: String(rawText ?? "") }];
    const used = new Set();
    for (const t of this.terms) {
      if (!t.title || used.has(t.title) || !segs.some((s) => !s.link && s.text.includes(t.title))) continue;
      used.add(t.title);
      const next = [];
      for (const s of segs) {
        if (s.link || !s.text.includes(t.title)) { next.push(s); continue; }
        const parts = s.text.split(t.title);
        parts.forEach((p, i) => {
          if (p) next.push({ text: p });
          if (i < parts.length - 1) next.push({ text: t.title, link: t.id });
        });
      }
      segs = next;
    }
    return segs;
  }

  /** Fill `node` with text + <a class="codex-link"> links; onLink(id) on click. */
  render(node, rawText, onLink) {
    node.textContent = "";
    for (const s of this.segments(rawText)) {
      if (!s.link) { node.appendChild(document.createTextNode(s.text)); continue; }
      const a = el("a", "codex-link", s.text);
      a.dataset.codex = s.link;
      a.href = `codex://${s.link}`;
      a.addEventListener("click", (ev) => { ev.preventDefault(); if (onLink) onLink(s.link); });
      node.appendChild(a);
    }
    return node;
  }
}

export class CodexController {
  constructor(ctx) {
    this.ctx = ctx;
    this.linker = new CodexAutoLinker(ctx.data && ctx.data.codex_terms);
    this.query = "";
    this.visible = false;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(el("div", "codex-overlay panel"), 500, 120, 1420, 520);
    this.root.id = "CodexOverlay";
    this.root.style.display = "none";
    this.body = el("div", "codex-body rtl");
    this.entry = el("div", "codex-entry");
    this.entryTitle = label("", { size: 18, cls: "codex-entry-title" });
    this.entryDef = label("", { autowrap: true, cls: "codex-entry-def" });
    this.entry.append(this.entryTitle, this.entryDef);
    this.entry.style.display = "none";
    this.root.append(this.body, this.entry);
    layer.appendChild(this.root);
    this.showEntry("mahapach");
    this.ctx.bus.connect("codex_entry_requested", (meta) => this._onEntryRequested(meta));
  }

  setVisible(open) {
    this.visible = !!open;
    this.root.style.display = this.visible ? "" : "none";
    if (!this.visible) this.entry.style.display = "none";
  }

  /** show_entry: Godot always renders the fixed sentence; `query` remembers the entry id. */
  showEntry(entryId) {
    this.linker.render(this.body, "大转折之后，议会席位按巴德尔-奥弗法分配。", (id) => this._onMeta(id));
    this.query = entryId;
  }

  filterEntries(needle) {
    return this.linker.terms.filter((t) => needle === "" || t.title.includes(needle)).map((t) => t.id);
  }

  _onMeta(id) {
    this.ctx.bus.emit("codex_entry_requested", `codex://${id}`);
  }

  /* Web wiring of the dead signal: open the requested term inside the overlay. */
  _onEntryRequested(meta) {
    const id = String(meta || "").replace(/^codex:\/\//, "");
    const term = this.linker.term(id);
    if (!term) return; // "index" (sent by UIManager on open) keeps the sentence only
    this.query = id;
    this.entryTitle.textContent = `${term.title}  ${term.id}`;
    this.entryDef.textContent = term.def || "（暂无释义）";
    this.entry.style.display = "";
  }
}
