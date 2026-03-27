"""Build Orchestrator Mode Overview PowerPoint."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# ── Colours (Catppuccin Mocha) ──
BG        = RGBColor(0x1E, 0x1E, 0x2E)
TITLE_CLR = RGBColor(0x89, 0xB4, 0xFA)  # soft blue
TEXT_CLR  = RGBColor(0xCD, 0xD6, 0xF4)  # light grey
ACCENT    = RGBColor(0xA6, 0xE3, 0xA1)  # green
WARN      = RGBColor(0xFA, 0xB3, 0x87)  # peach/orange
CODE_BG   = RGBColor(0x31, 0x32, 0x44)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
DIM       = RGBColor(0x6C, 0x70, 0x86)
TBL_HDR   = RGBColor(0x45, 0x47, 0x5A)
TBL_ROW1  = RGBColor(0x2A, 0x2B, 0x3D)
TBL_ROW2  = RGBColor(0x24, 0x25, 0x35)
MAUVE     = RGBColor(0xCB, 0xA6, 0xF7)  # purple
YELLOW    = RGBColor(0xF9, 0xE2, 0xAF)
RED       = RGBColor(0xF3, 0x8B, 0xA8)
TEAL      = RGBColor(0x94, 0xE2, 0xD5)
PINK      = RGBColor(0xF5, 0xC2, 0xE7)

# ── Helpers ──

def set_bg(slide):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = BG


def add_text(slide, left, top, width, height, text, size=18, color=TEXT_CLR,
             bold=False, align=PP_ALIGN.LEFT, font_name="Cascadia Code"):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                     Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = align
    return tf


def add_para(tf, text, size=18, color=TEXT_CLR, bold=False,
             font_name="Cascadia Code", space_before=Pt(6)):
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.space_before = space_before
    return p


def add_title(slide, text):
    add_text(slide, 0.5, 0.3, 12, 0.7, text, size=32,
             color=TITLE_CLR, bold=True, font_name="Segoe UI")


def add_subtitle(slide, text, top=1.1):
    add_text(slide, 0.5, top, 12, 0.5, text, size=18,
             color=TEXT_CLR, font_name="Segoe UI")


def styled_table(slide, rows, cols, left, top, width, height,
                 col_widths=None):
    tbl_shape = slide.shapes.add_table(rows, cols,
                                       Inches(left), Inches(top),
                                       Inches(width), Inches(height))
    tbl = tbl_shape.table
    if col_widths:
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = Inches(w)
    for row_idx, row in enumerate(tbl.rows):
        for cell in row.cells:
            cell.fill.solid()
            if row_idx == 0:
                cell.fill.fore_color.rgb = TBL_HDR
            elif row_idx % 2 == 1:
                cell.fill.fore_color.rgb = TBL_ROW1
            else:
                cell.fill.fore_color.rgb = TBL_ROW2
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(14)
                p.font.color.rgb = TEXT_CLR
                p.font.name = "Cascadia Code"
    return tbl


def set_cell(tbl, r, c, text, color=TEXT_CLR, bold=False, size=14,
             align=PP_ALIGN.LEFT):
    cell = tbl.cell(r, c)
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = "Cascadia Code"
    p.alignment = align


def add_box(slide, left, top, width, height, fill_color=CODE_BG):
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    box.fill.solid()
    box.fill.fore_color.rgb = fill_color
    return box


def add_rounded_box(slide, left, top, width, height, fill_color, text,
                    text_size=16, text_color=WHITE, bold=True,
                    font_name="Segoe UI", align=PP_ALIGN.CENTER):
    """Add a rounded-rectangle shape with centered text."""
    from pptx.enum.shapes import MSO_SHAPE
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(text_size)
    p.font.color.rgb = text_color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = align
    tf.paragraphs[0].space_before = Pt(0)
    tf.paragraphs[0].space_after = Pt(0)
    return tf


def add_arrow(slide, x1, y1, x2, y2, color=DIM, width=Pt(3)):
    """Add a straight connector arrow between two points (inches)."""
    from pptx.enum.shapes import MSO_CONNECTOR_TYPE
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT,
        Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    connector.line.color.rgb = color
    connector.line.width = width
    # Add arrowhead at end
    connector.end_x = Inches(x2)
    connector.end_y = Inches(y2)
    return connector


# ══════════════════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
set_bg(s)

add_text(s, 1, 1.5, 11, 1.2,
         "Vulnhalla: Orchestrated Analysis",
         size=44, color=TITLE_CLR, bold=True, font_name="Segoe UI")
add_text(s, 1, 2.9, 11, 0.6,
         "From single-turn LLM conversations to a structured Plan \u2192 Investigate \u2192 Synthesize pipeline",
         size=22, color=TEXT_CLR, font_name="Segoe UI")
add_text(s, 1, 4.0, 11, 0.5,
         "Model: azure/gpt-5.1-codex   \u2502   Static Analysis: Coverity + CodeQL",
         size=18, color=DIM, font_name="Cascadia Code")
add_text(s, 1, 5.5, 11, 0.5,
         "Plan  \u2192  Investigate  \u2192  Synthesize",
         size=28, color=ACCENT, bold=True, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 2 — The Problem
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "The Problem: Manual Triage Doesn\u2019t Scale")

bullets = [
    ("Coverity + CodeQL generate hundreds of static-analysis findings", TEXT_CLR),
    ("Each finding requires a human to read code, trace data flow, assess guards", TEXT_CLR),
    ("Experienced security engineers spend 10\u201330 min per issue", WARN),
    ("Many findings are False Positives \u2014 valid guards exist but the tool can\u2019t see them", TEXT_CLR),
    ("Goal: LLM-powered triage that can classify TP / FP / NMD with evidence", ACCENT),
]
tf = add_text(s, 0.8, 1.3, 11.5, 0.5, "", size=20, font_name="Segoe UI")
for i, (txt, clr) in enumerate(bullets):
    p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
    p.text = "\u2022  " + txt
    p.font.size = Pt(20)
    p.font.color.rgb = clr
    p.font.name = "Segoe UI"
    p.space_before = Pt(16)

# Bottom
add_text(s, 0.8, 5.8, 11, 0.5,
         "Verdict codes:  1337 = True Positive  \u2502  1007 = False Positive  "
         "\u2502  7331 = Needs More Data",
         size=16, color=DIM, font_name="Cascadia Code")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 3 — Old Mode Architecture
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Old Mode: Single Multi-Turn Conversation")
add_subtitle(s, "LLMAnalyzer  \u2014  one long chat with the LLM making all decisions")

# Flow boxes (left column)
flow_items = [
    ("Alert + Code",          MAUVE,  1.6),
    ("4 System Messages",     TBL_HDR, 2.3),
    ("LLM Picks Tools",       WARN,   3.0),
    ("Execute \u2192 Inject Results", CODE_BG, 3.7),
    ("Check Evidence Flags",  TBL_HDR, 4.4),
    ("Verdict or Loop",       ACCENT, 5.1),
]
for (label, color, top) in flow_items:
    add_rounded_box(s, 0.8, top, 3.5, 0.55, color, label,
                    text_size=16, text_color=WHITE)

# Arrow annotations
add_text(s, 4.5, 2.85, 1, 0.5, "\u2193", size=20, color=DIM, font_name="Segoe UI")
add_text(s, 4.5, 3.55, 1, 0.5, "\u2193", size=20, color=DIM, font_name="Segoe UI")
add_text(s, 4.5, 4.25, 1, 0.5, "\u21bb loop", size=14, color=DIM, font_name="Segoe UI")

# Right column: characteristics
chars = [
    ("\u2022  LLM decides which tools to call and in what order", TEXT_CLR),
    ("\u2022  Sequential rounds \u2014 no parallelization", TEXT_CLR),
    ("\u2022  Evidence tracked via sticky flags (MECHANISM, GUARDS, EXPLOITABILITY)", TEXT_CLR),
    ("\u2022  4 system messages injected (role, workflow, status codes, tools)", TEXT_CLR),
    ("\u2022  Tools: get_function_code, get_caller_function, get_class, get_macro, get_global_var", DIM),
]
tf = add_text(s, 5.5, 1.5, 7, 0.5, "How It Works", size=22,
              color=TITLE_CLR, bold=True, font_name="Segoe UI")
for txt, clr in chars:
    add_para(tf, txt, size=17, color=clr, font_name="Segoe UI", space_before=Pt(14))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 4 — Old Mode Limitations
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Old Mode Limitations")
add_subtitle(s, "Why a single conversation with full LLM autonomy falls short")

left_items = [
    ("\u26a0  Topic Drift",
     "LLM reasoning can diverge from actual code.\n"
     "It may chase irrelevant functions for many rounds."),
    ("\u26a0  No Parallelization",
     "All tool calls are sequential \u2014 one round at a time.\n"
     "Complex cases with 3\u20134 leads serialize poorly."),
    ("\u26a0  Duplicate Tool Calls",
     "LLM may request the same function lookup twice.\n"
     "No deduplication across rounds."),
]
right_items = [
    ("\u26a0  Dead-End Loops",
     "LLM can spend many rounds on a fruitless path\n"
     "before trying a different approach."),
    ("\u26a0  Hard to Debug",
     "One big conversation log \u2014 no easy way to see\n"
     "which round introduced a wrong conclusion."),
    ("\u26a0  Guard Blindness",
     "No systematic strategy for checking call-site guards.\n"
     "Guards often missed or dismissed."),
]

for i, (title, body) in enumerate(left_items):
    top = 1.5 + i * 1.8
    tf = add_text(s, 0.8, top, 5.5, 0.5, title, size=20,
                  color=WARN, bold=True, font_name="Segoe UI")
    add_para(tf, body, size=16, color=TEXT_CLR, font_name="Segoe UI",
             space_before=Pt(8))

for i, (title, body) in enumerate(right_items):
    top = 1.5 + i * 1.8
    tf = add_text(s, 7, top, 5.5, 0.5, title, size=20,
                  color=WARN, bold=True, font_name="Segoe UI")
    add_para(tf, body, size=16, color=TEXT_CLR, font_name="Segoe UI",
             space_before=Pt(8))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 5 — Orchestrated Mode: High-Level Architecture
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Orchestrated Mode: 3-Phase Pipeline")
add_subtitle(s, "Python orchestrates \u2014 the LLM answers focused questions, not driving the process")

# Phase boxes (large, horizontal)
phase_colors = [MAUVE, TEAL, ACCENT]
phase_labels = [
    "Phase 1: PLAN\nDecompose alert into investigation leads",
    "Phase 2: INVESTIGATE\nParallel per-lead tool calling + analysis",
    "Phase 3: SYNTHESIZE\nChain findings into final verdict",
]
phase_x = [0.6, 4.8, 9.0]
for i in range(3):
    add_rounded_box(s, phase_x[i], 1.6, 3.8, 1.3, phase_colors[i],
                    phase_labels[i], text_size=16, text_color=WHITE)

# Arrows between phases
add_text(s, 4.4, 1.9, 0.5, 0.5, "\u2192", size=32, color=DIM,
         font_name="Segoe UI", align=PP_ALIGN.CENTER)
add_text(s, 8.6, 1.9, 0.5, 0.5, "\u2192", size=32, color=DIM,
         font_name="Segoe UI", align=PP_ALIGN.CENTER)

# Detail boxes below each phase
plan_details = (
    "\u2022 Reads alert + flagged code\n"
    "\u2022 Outputs JSON array of leads\n"
    "\u2022 Each lead: question, why,\n"
    "   evaluation criteria, line nums,\n"
    "   seed tools to call"
)
inv_details = (
    "\u2022 Runs each lead in parallel\n"
    "   (ThreadPoolExecutor)\n"
    "\u2022 Seed tools auto-executed\n"
    "\u2022 LLM gets +12 follow-up calls\n"
    "\u2022 Tool cache deduplicates\n"
    "\u2022 6 consecutive fails \u2192 stop"
)
syn_details = (
    "\u2022 Receives all lead findings\n"
    "\u2022 No tools \u2014 pure reasoning\n"
    "\u2022 Traces data flow source \u2192 sink\n"
    "\u2022 Assesses guard effectiveness\n"
    "\u2022 Returns verdict + evidence"
)

for i, details in enumerate([plan_details, inv_details, syn_details]):
    box = add_box(s, phase_x[i], 3.2, 3.8, 2.6)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = details
    p.font.size = Pt(14)
    p.font.color.rgb = TEXT_CLR
    p.font.name = "Cascadia Code"
    p.line_spacing = Pt(20)

# Bottom tagline
add_text(s, 0.6, 6.2, 12, 0.5,
         "Key insight: Python decides what to investigate. "
         "The LLM answers one focused question per lead.",
         size=18, color=YELLOW, bold=True, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 5b — Phase 1 Prompt: Planner
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Phase 1 Prompt \u2014 The Planner")
add_subtitle(s, "Role: \u201cExpert security researcher\u201d \u2014 security-aware because it must understand alert context")

# Left: What the prompt tells the LLM
tf_left = add_text(s, 0.6, 1.5, 5.8, 0.5,
                   "Prompt Instructions", size=22,
                   color=TITLE_CLR, bold=True, font_name="Segoe UI")
plan_points = [
    ("\u2022  Plan, don\u2019t decide", "Explicitly forbidden from reaching a verdict or presupposing answers."),
    ("\u2022  Cite line numbers", "Every question, why, and evaluate must reference specific source lines."),
    ("\u2022  Observable properties only", "Ask about return ranges, types, control flow \u2014 never infer from names."),
    ("\u2022  Self-contained leads", "Each lead answerable independently \u2014 enables parallel execution."),
    ("\u2022  Data-flow prioritization", "Focus on functions between source and sink, not downstream consumers."),
    ("\u2022  Explicit guard leads", "Separate lead for caller-side guards \u2014 don\u2019t fold into callee analysis."),
]
for title, desc in plan_points:
    add_para(tf_left, title, size=16, color=ACCENT, bold=True,
             font_name="Segoe UI", space_before=Pt(10))
    add_para(tf_left, f"   {desc}", size=14, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# Right: Design rationale
tf_right = add_text(s, 7, 1.5, 5.8, 0.5,
                    "Design Rationale", size=22,
                    color=YELLOW, bold=True, font_name="Segoe UI")
rationale_points = [
    ("Knows it\u2019s security",
     "The planner MUST understand the alert type (buffer overflow, "
     "use-after-free, etc.) to decompose it into the right questions. "
     "Without security context, it can\u2019t identify what matters."),
    ("Forbidden from concluding",
     "Separation of concerns: if the planner also reasons about verdicts, "
     "it biases the questions. Planning and judging must be decoupled."),
    ("No name-based assumptions",
     "LLMs readily assume \u201cGetSize returns a size\u201d or \u201cIsValid checks "
     "validity.\u201d The prompt forces observable questions to prevent "
     "hallucinated reasoning shortcuts."),
    ("Guard leads mandated",
     "Most FP misclassifications come from missed caller-side guards. "
     "Requiring a separate guard lead ensures the synthesizer gets "
     "explicit evidence about protections."),
]
for title, desc in rationale_points:
    add_para(tf_right, title, size=16, color=WARN, bold=True,
             font_name="Segoe UI", space_before=Pt(12))
    add_para(tf_right, f"   {desc}", size=13, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 5c — Phase 2 Prompt: Investigator
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Phase 2 Prompt \u2014 The Investigator")
add_subtitle(s, "Role: \u201cCode researcher\u201d \u2014 deliberately NOT told this is about security")

# Left: What the prompt tells the LLM
tf_left = add_text(s, 0.6, 1.5, 5.8, 0.5,
                   "Prompt Instructions", size=22,
                   color=TITLE_CLR, bold=True, font_name="Segoe UI")
inv_points = [
    ("\u2022  Answer ONE question", "Scoped to a single lead \u2014 no verdict, no security judgment."),
    ("\u2022  Check the ledger first", "PRIOR TOOL RESULTS list prevents duplicate tool calls."),
    ("\u2022  \u201cCan I answer now?\u201d", "Must ask this before every tool call \u2014 stops wasteful exploration."),
    ("\u2022  Follow delegation chains", "If a function just forwards data, look up the callee. Don\u2019t stop at pass-throughs."),
    ("\u2022  Evidence audit", "Strip assertions before responding \u2014 if removing them changes the answer, it was wrong."),
    ("\u2022  Only look up visible names", "Every tool argument must appear in code already seen. No invented names."),
]
for title, desc in inv_points:
    add_para(tf_left, title, size=16, color=TEAL, bold=True,
             font_name="Segoe UI", space_before=Pt(10))
    add_para(tf_left, f"   {desc}", size=14, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# Right: Design rationale
tf_right = add_text(s, 7, 1.5, 5.8, 0.5,
                    "Design Rationale", size=22,
                    color=YELLOW, bold=True, font_name="Segoe UI")
rationale_points = [
    ("Does NOT know it\u2019s security",
     "This is the key design choice. The investigator is told it\u2019s a "
     "\u201ccode researcher\u201d \u2014 not a security analyst. This prevents it from "
     "jumping to security conclusions or dismissing findings as "
     "\u201cprobably safe.\u201d It just reports what the code does."),
    ("Factual, not judgmental",
     "Without security framing, the LLM treats every code path equally. "
     "It won\u2019t rationalize away a missing bounds check because "
     "\u201cthe function name suggests it\u2019s safe.\u201d"),
    ("Tight tool discipline",
     "The ledger check + \u201ccan I answer now?\u201d pattern cuts tool usage "
     "dramatically. Old mode had no dedup \u2014 LLM would re-request the "
     "same function multiple times."),
    ("Assertion stripping",
     "Assertions compile to no-ops in production. LLMs treat them as "
     "real guards unless explicitly told otherwise. The evidence audit "
     "forces the investigator to remove them before concluding."),
]
for title, desc in rationale_points:
    add_para(tf_right, title, size=16, color=WARN, bold=True,
             font_name="Segoe UI", space_before=Pt(12))
    add_para(tf_right, f"   {desc}", size=13, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 5d — Phase 3 Prompt: Synthesizer
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Phase 3 Prompt \u2014 The Synthesizer")
add_subtitle(s, "Role: \u201cExpert security researcher\u201d \u2014 security context restored for the verdict")

# Left: What the prompt tells the LLM
tf_left = add_text(s, 0.6, 1.5, 5.8, 0.5,
                   "Prompt Instructions", size=22,
                   color=TITLE_CLR, bold=True, font_name="Segoe UI")
syn_points = [
    ("\u2022  Chain findings together", "Trace data flow from source to sink using evidence from all leads."),
    ("\u2022  No tools \u2014 pure reasoning", "Works only from pre-gathered evidence. Cannot request new lookups."),
    ("\u2022  Guard assessment", "List every guard: effective (runtime bound) vs. ineffective (assertion/missing)."),
    ("\u2022  Transitive assertion rule", "If a guard\u2019s limit is only bounded by an assertion, the guard itself is broken."),
    ("\u2022  Structured verdict", "Evidence Summary \u2192 Data Flow \u2192 Guard Assessment \u2192 Status Code."),
    ("\u2022  Respect investigator gaps", "\u201cCould not determine\u201d = no bound was found = value is unbounded."),
]
for title, desc in syn_points:
    add_para(tf_left, title, size=16, color=ACCENT, bold=True,
             font_name="Segoe UI", space_before=Pt(10))
    add_para(tf_left, f"   {desc}", size=14, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# Right: Design rationale
tf_right = add_text(s, 7, 1.5, 5.8, 0.5,
                    "Design Rationale", size=22,
                    color=YELLOW, bold=True, font_name="Segoe UI")
rationale_points = [
    ("Security context restored",
     "Unlike the investigator, the synthesizer needs to understand "
     "exploitability, guard effectiveness, and vulnerability classes. "
     "It\u2019s the ONLY phase that renders a security judgment."),
    ("Evidence-only reasoning",
     "No tools means no opportunity to go off-script. The synthesizer "
     "can only work with what investigators found \u2014 this prevents it "
     "from doing its own ad-hoc investigation and contradicting leads."),
    ("Structured output format",
     "Forcing Evidence Summary \u2192 Data Flow \u2192 Guard Assessment \u2192 Verdict "
     "ensures the LLM shows its work. Each step is auditable and "
     "the verdict must follow logically from the prior sections."),
    ("Absence = unbounded",
     "LLMs tend to assume safety when evidence is missing. The prompt "
     "flips this: if an investigator couldn\u2019t find a bound, the value "
     "is treated as unbounded. This prevents optimistic hallucination."),
]
for title, desc in rationale_points:
    add_para(tf_right, title, size=16, color=WARN, bold=True,
             font_name="Segoe UI", space_before=Pt(12))
    add_para(tf_right, f"   {desc}", size=13, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 6 — The Lead Concept (deeper dive)
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "The Lead Concept")
add_subtitle(s, "Each lead is a focused, self-contained investigation question")

# Example lead JSON
lead_json = (
    '{\n'
    '  "question": "What values can GetSize() return\n'
    '               when the file is empty?",\n'
    '  "why": "GetSize is used as array index at line 47.\n'
    '          Negative return → out-of-bounds access.",\n'
    '  "evaluate": "Return-value range of GetSize()",\n'
    '  "lines": [42, 47, 51],\n'
    '  "tools": [\n'
    '    {"tool": "get_function_code",\n'
    '     "args": {"name": "GetSize", "file": "file.cpp"}}\n'
    '  ]\n'
    '}'
)
box = add_box(s, 0.6, 1.5, 5.5, 4.5)
tf = box.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = lead_json
p.font.size = Pt(13)
p.font.color.rgb = ACCENT
p.font.name = "Cascadia Code"
p.line_spacing = Pt(19)

# Right: explanation
right_bullets = [
    ("question", "The single question this lead must answer", MAUVE),
    ("why", "Why it matters for the verdict", WARN),
    ("evaluate", "What observable property to extract", TEAL),
    ("lines", "Source lines the planner identified as relevant", TEXT_CLR),
    ("tools", "Seed tools \u2014 auto-called before the LLM sees the lead", ACCENT),
]
tf2 = add_text(s, 6.6, 1.5, 6, 0.5,
               "Lead Structure", size=24, color=TITLE_CLR,
               bold=True, font_name="Segoe UI")
for field, desc, clr in right_bullets:
    add_para(tf2, f"  {field}", size=18, color=clr, bold=True,
             font_name="Cascadia Code", space_before=Pt(14))
    add_para(tf2, f"    {desc}", size=16, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(4))

# Bottom note
add_text(s, 0.6, 6.3, 12, 0.5,
         "Planner generates 2\u20134 leads per alert  \u2502  "
         "Each lead runs independently with its own tool budget",
         size=16, color=DIM, font_name="Cascadia Code")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 7 — Key Differences Table
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Old Mode vs. Orchestrated Mode")

rows_data = [
    ("Aspect",             "Old Mode",                       "Orchestrated Mode"),
    ("Control Flow",       "LLM decides tools",              "Python orchestrates"),
    ("Parallelization",    "None (sequential rounds)",        "Leads run in parallel"),
    ("Tool Deduplication", "No (LLM may repeat)",             "Global cache (tool+args)"),
    ("Drift Prevention",   "High risk (LLM diverges)",        "Low (leads pre-planned)"),
    ("Dead-End Handling",  "LLM explores all paths",          "Auto-stop after 6 failures"),
    ("Debugging",          "One big conversation log",         "Versioned per-lead outputs"),
    ("Guard Discovery",    "Buried in reasoning",              "Explicit planner lead"),
    ("Replay",             "Not supported",                    "Replay lead / synthesize"),
]

tbl = styled_table(s, len(rows_data), 3, 0.6, 1.2, 12.1, 5.5,
                   col_widths=[2.8, 4.6, 4.7])
for r, (a, b, c) in enumerate(rows_data):
    if r == 0:
        set_cell(tbl, r, 0, a, color=TITLE_CLR, bold=True, size=15)
        set_cell(tbl, r, 1, b, color=TITLE_CLR, bold=True, size=15)
        set_cell(tbl, r, 2, c, color=TITLE_CLR, bold=True, size=15)
    else:
        set_cell(tbl, r, 0, a, color=YELLOW, bold=True, size=14)
        set_cell(tbl, r, 1, b, color=WARN, size=14)
        set_cell(tbl, r, 2, c, color=ACCENT, size=14)

# ══════════════════════════════════════════════════════════════════════
# SLIDE 8 — Replay & Debugging
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Replay & Debugging Capabilities")
add_subtitle(s, "Each phase produces versioned output files \u2014 re-run any phase independently")

# Output structure
output_text = (
    "output/results_orchestrated/c/{CID}/run_001/\n"
    "\u251c\u2500 1_plan_final.json       (lead definitions)\n"
    "\u251c\u2500 2_initial_code.json     (extracted source)\n"
    "\u251c\u2500 2_1_final.json          (Lead 1 findings)\n"
    "\u251c\u2500 2_2_final.json          (Lead 2 findings)\n"
    "\u251c\u2500 2_3_final.json          (Lead 3 findings)\n"
    "\u251c\u2500 3_synthesize_final.json (verdict + evidence)\n"
    "\u251c\u2500 run_summary.json        (cost, tokens, timing)\n"
    "\u2514\u2500 run_report.md           (human-readable report)"
)
box = add_box(s, 0.6, 1.5, 5.8, 3.5)
tf = box.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = output_text
p.font.size = Pt(14)
p.font.color.rgb = ACCENT
p.font.name = "Cascadia Code"
p.line_spacing = Pt(22)

# Replay modes
replay_bullets = [
    ("plan_only=True",
     "Run only the planner \u2014 inspect leads before committing to investigation"),
    ("plan_file=\u2018...\u2019",
     "Load a saved plan and re-run investigation from it (skip Phase 1)"),
    ("replay_lead=\u20181\u2019",
     "Re-investigate a single lead with new settings.\n"
     "Creates versioned output (2_1_v2_final.json) \u2014 never overwrites."),
    ("replay_synthesize=True",
     "Re-synthesize verdict from existing lead findings.\n"
     "Useful for testing synthesizer prompt changes."),
]
tf2 = add_text(s, 7, 1.5, 5.5, 0.5,
               "Replay Modes", size=24, color=TITLE_CLR,
               bold=True, font_name="Segoe UI")
for flag, desc in replay_bullets:
    add_para(tf2, f"  {flag}", size=16, color=MAUVE, bold=True,
             font_name="Cascadia Code", space_before=Pt(14))
    add_para(tf2, f"    {desc}", size=14, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(4))

add_text(s, 0.6, 6.2, 12, 0.5,
         "Replay enables surgical debugging: re-run only the phase that failed "
         "without re-running the whole pipeline.",
         size=17, color=YELLOW, bold=True, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 9 — Efficiency Gains
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Efficiency \u2014 Speed & Cost Improvements")
add_subtitle(s, "Selected CIDs comparing old-mode runs to orchestrated mode (b12 batch)")

# Efficiency table
eff_data = [
    ("CID",      "Old Duration", "New Duration", "\u0394",    "Old Cost", "New Cost", "\u0394"),
    ("27528",    "837 s",        "77 s",         "\u221291%", "$0.47",    "$0.11",    "\u221277%"),
    ("15518",    "1,686 s",      "312 s",        "\u221282%", "$0.69",    "$0.43",    "\u221238%"),
    ("19309",    "1,347 s",      "686 s",        "\u221249%", "$0.61",    "$0.49",    "\u221220%"),
]
tbl = styled_table(s, len(eff_data), 7, 0.6, 1.5, 12.1, 2.8,
                   col_widths=[1.4, 1.8, 1.8, 1.2, 1.4, 1.4, 1.2])
for r, row in enumerate(eff_data):
    for c, val in enumerate(row):
        if r == 0:
            set_cell(tbl, r, c, val, color=TITLE_CLR, bold=True, size=14)
        elif c in (3, 6):  # delta columns
            set_cell(tbl, r, c, val, color=ACCENT, bold=True, size=14)
        else:
            set_cell(tbl, r, c, val, color=TEXT_CLR, size=14)

# Phase breakdown
add_text(s, 0.6, 4.8, 5, 0.5,
         "Average Phase Duration (b12)", size=20,
         color=TITLE_CLR, bold=True, font_name="Segoe UI")

phase_data = [
    ("Phase",       "Avg Duration", "% of Total"),
    ("Plan",        "44 s",         "25%"),
    ("Investigate",  "89 s",         "52%"),
    ("Synthesize",  "35 s",         "20%"),
]
tbl2 = styled_table(s, 4, 3, 0.6, 5.3, 5, 1.6,
                    col_widths=[1.8, 1.6, 1.6])
for r, row in enumerate(phase_data):
    for c, val in enumerate(row):
        if r == 0:
            set_cell(tbl2, r, c, val, color=TITLE_CLR, bold=True, size=13)
        else:
            clr = [MAUVE, TEAL, ACCENT][r-1] if c == 0 else TEXT_CLR
            set_cell(tbl2, r, c, val, color=clr, bold=(c == 0), size=13)

# Right: metrics
tf = add_text(s, 7, 4.8, 5.5, 0.5,
              "b12 Batch Metrics", size=20,
              color=TITLE_CLR, bold=True, font_name="Segoe UI")
metrics = [
    ("Avg cost per CID:",   "$0.19"),
    ("Tool hit rate:",       "90% (140/155)"),
    ("Avg leads per CID:",  "3.1  (range 2\u20134)"),
    ("Total tokens:",        "977,532"),
    ("Avg tokens per CID:", "~51k"),
]
for label, val in metrics:
    add_para(tf, f"  {label}  {val}", size=16, color=TEXT_CLR,
             font_name="Cascadia Code", space_before=Pt(10))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 10 — Accuracy Results
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Accuracy \u2014 Batch b12 Results")
add_subtitle(s, "19 CIDs analyzed  \u2502  compared against human expert ground truth")

# Main accuracy box
add_rounded_box(s, 1, 1.8, 3.5, 2.5, RGBColor(0x2A, 0x2B, 0x3D),
                "88.2%\nAccuracy\n(15/17 agree with human)",
                text_size=28, text_color=ACCENT, bold=True)

# Breakdown
breakdown = [
    ("15 CIDs", "Correct \u2014 agree with human verdict", ACCENT),
    ("2 CIDs", "Disagreement \u2014 LLM vs. human differ", WARN),
    ("2 CIDs", "NMD \u2014 insufficient data to decide", DIM),
]
tf = add_text(s, 5, 1.8, 7, 0.5, "Breakdown", size=22,
              color=TITLE_CLR, bold=True, font_name="Segoe UI")
for count, desc, clr in breakdown:
    add_para(tf, f"  {count}  \u2014  {desc}", size=18, color=clr,
             font_name="Segoe UI", space_before=Pt(14))

# Disagreements detail
add_text(s, 0.6, 4.8, 12, 0.4, "Disagreements & Known Issues",
         size=20, color=TITLE_CLR, bold=True, font_name="Segoe UI")

issues = [
    ("CID 27746  (persistent)",
     "strncpy to 8-byte field passed to DeviceIoControl. "
     "Planner never asked about downstream buffer consumption by SDK."),
    ("CID 27724  (fixed in run_008)",
     "Missed !pFile.IsValid() guard at call site. "
     "Fixed via planner prompt update \u2014 now generates explicit guard lead."),
    ("CID 22293 / 23745  (NMD)",
     "Involve constant relationships (LOCAL_CLIENT_COUNT \u2264 STATIC_MAX_LOCAL_CLIENTS). "
     "Database couldn\u2019t resolve one constant."),
]
tf = add_text(s, 0.6, 5.2, 12, 0.3, "", size=14, font_name="Segoe UI")
for title, detail in issues:
    add_para(tf, f"  {title}", size=15, color=YELLOW, bold=True,
             font_name="Cascadia Code", space_before=Pt(8))
    add_para(tf, f"    {detail}", size=14, color=TEXT_CLR,
             font_name="Segoe UI", space_before=Pt(2))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 11 — Key Takeaways
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Key Takeaways")

takeaways = [
    ("\u2705  Structured decomposition",
     "The planner breaks complex alerts into 2\u20134 focused leads, "
     "preventing the LLM from drifting or getting stuck."),
    ("\u2705  Python-orchestrated control",
     "Tool calling, caching, and budgets are managed by Python \u2014 "
     "the LLM answers questions, it doesn\u2019t drive the process."),
    ("\u2705  Parallel investigation",
     "Independent leads execute concurrently via ThreadPoolExecutor, "
     "reducing wall-clock time for multi-lead cases."),
    ("\u2705  Surgical replay & debugging",
     "Each phase produces versioned artifacts. Re-run a single lead "
     "or re-synthesize without re-running the whole pipeline."),
    ("\u2705  Guard-aware planning",
     "Planner explicitly generates leads for call-site guards, "
     "addressing the most common source of missed FPs."),
    ("\u2705  Cost efficiency",
     "Tool caching + focused questions + early termination yield "
     "lower cost per CID while maintaining 88%+ accuracy."),
]

tf = add_text(s, 0.8, 1.3, 11.5, 0.5, "", size=18, font_name="Segoe UI")
for i, (title, body) in enumerate(takeaways):
    p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(20)
    p.font.color.rgb = ACCENT
    p.font.bold = True
    p.font.name = "Segoe UI"
    p.space_before = Pt(12)

    p2 = tf.add_paragraph()
    p2.text = "    " + body
    p2.font.size = Pt(16)
    p2.font.color.rgb = TEXT_CLR
    p2.font.name = "Segoe UI"
    p2.space_before = Pt(2)

# ══════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════
out_path = r"_rearch\Vulnhalla_Orchestrated_Overview.pptx"
prs.save(out_path)
print(f"Saved → {out_path}")
