"""Build CID 25863 walkthrough PowerPoint."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# ── Colours ──
BG       = RGBColor(0x1E, 0x1E, 0x2E)  # dark navy
TITLE_CLR = RGBColor(0x89, 0xB4, 0xFA)  # soft blue
TEXT_CLR  = RGBColor(0xCD, 0xD6, 0xF4)  # light grey
ACCENT    = RGBColor(0xA6, 0xE3, 0xA1)  # green
WARN      = RGBColor(0xFA, 0xB3, 0x87)  # peach/orange
CODE_BG   = RGBColor(0x31, 0x32, 0x44)  # slightly lighter
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
DIM       = RGBColor(0x6C, 0x70, 0x86)  # muted
TBL_HDR   = RGBColor(0x45, 0x47, 0x5A)
TBL_ROW1  = RGBColor(0x2A, 0x2B, 0x3D)
TBL_ROW2  = RGBColor(0x24, 0x25, 0x35)


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


def set_cell(tbl, r, c, text, color=TEXT_CLR, bold=False, size=14):
    cell = tbl.cell(r, c)
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = "Cascadia Code"


# ══════════════════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
set_bg(s)
add_text(s, 1, 1.8, 11, 1.2,
         "Vulnhalla: Orchestrated Static-Analysis Triage",
         size=36, color=TITLE_CLR, bold=True, font_name="Segoe UI")
add_text(s, 1, 3.2, 11, 0.6,
         "CID 25863  ·  Memory — Illegal Accesses (Uninitialized Use)",
         size=22, color=TEXT_CLR, font_name="Segoe UI")
add_text(s, 1, 3.9, 11, 0.5,
         "fx_draw.cpp, line 104  →  FX_DrawModularParticles(&drawState, ...)",
         size=18, color=DIM, font_name="Cascadia Code")
add_text(s, 1, 5.5, 11, 0.5,
         "Plan  →  Investigate  →  Synthesize",
         size=20, color=ACCENT, bold=True, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 2 — The Alert (actual input to planner)
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Planner Input — What the LLM Actually Sees")

# Left: the Coverity alert block (raw text)
add_text(s, 0.5, 1.1, 5.8, 0.4,
         "Issue Overview (from Coverity export):",
         size=15, color=DIM, font_name="Segoe UI")

alert_text = (
    "Name: 25863\n"
    "Description: Memory - illegal accesses\n"
    "Message:\n"
    "  Event uninit_use_in_call : Using uninitialized\n"
    "  element of array \"drawState.atlasDataOffsets\"\n"
    "  when calling \"FX_DrawModularParticles\".\n"
    "  Event uninit_use_in_call : Using uninitialized\n"
    "  value \"drawState.flareSurfGlob\" when calling\n"
    "  \"FX_DrawModularParticles\".\n"
    "  Event uninit_use_in_call : Using uninitialized\n"
    "  element of array \"drawState.padding\" when\n"
    "  calling \"FX_DrawModularParticles\".\n"
    "Location: fx_draw.cpp:104"
)
alert_box = s.shapes.add_textbox(Inches(0.5), Inches(1.5),
                                 Inches(5.8), Inches(3.8))
alert_box.fill.solid()
alert_box.fill.fore_color.rgb = CODE_BG
atf = alert_box.text_frame
atf.word_wrap = True
p = atf.paragraphs[0]
p.text = alert_text
p.font.size = Pt(13)
p.font.color.rgb = WARN
p.font.name = "Cascadia Code"
p.line_spacing = Pt(19)

# Right: the flagged source code
add_text(s, 6.8, 1.1, 6, 0.4,
         "Flagged source code (auto-extracted around line 104):",
         size=15, color=DIM, font_name="Segoe UI")

code = (
    "62: static void FXIR_DrawSpriteElems(...)\n"
    "65:   FxDrawState drawState;\n"
    "67:   DebugWipe(&drawState, sizeof(drawState));\n"
    "      ...\n"
    "76:     drawState.drawFlares = false;\n"
    "81:     R_BeginFlareSurfs(&drawState.flareSurfGlob);\n"
    "87:   FX_SpriteReset(&drawState.sprite);\n"
    "88:   drawState.system = system;\n"
    "91:   drawState.codeSurfThreadLocal = nullptr;\n"
    "94:   drawState.codeSurfListType = codeSurfListType;\n"
    "      ...\n"
    "104:  FX_DrawModularParticles(&drawState, system,\n"
    "          codeSurfGlob, backEndData);"
)
code_box = s.shapes.add_textbox(Inches(6.8), Inches(1.5),
                                Inches(6), Inches(3.8))
code_box.fill.solid()
code_box.fill.fore_color.rgb = CODE_BG
ctf = code_box.text_frame
ctf.word_wrap = True
p = ctf.paragraphs[0]
p.text = code
p.font.size = Pt(13)
p.font.color.rgb = ACCENT
p.font.name = "Cascadia Code"
p.line_spacing = Pt(19)

# Bottom note
add_text(s, 0.5, 5.6, 12, 0.8,
         "This is all the planner gets — a terse alert + the surrounding "
         "source. No field types, no struct layout, no call graph.",
         size=18, color=TITLE_CLR, bold=False, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 3 — Phase 1: Planner
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Phase 1 — Planner")

add_text(s, 0.5, 1.2, 12, 0.5,
         "LLM decomposes the alert into 6 targeted investigation leads:",
         size=18, color=TEXT_CLR, font_name="Segoe UI")

tbl = styled_table(s, 7, 3, 0.5, 1.9, 12.3, 4.5,
                   col_widths=[0.5, 8.5, 3.3])
# Header
set_cell(tbl, 0, 0, "#", WHITE, True)
set_cell(tbl, 0, 1, "Question", WHITE, True)
set_cell(tbl, 0, 2, "Strategy", WHITE, True)

leads = [
    ("1", "Is atlasDataOffsets assigned before line 104?",
     "Check caller init"),
    ("2", "Is padding assigned before line 104?",
     "Check caller init"),
    ("3", "Is flareSurfGlob initialized on the non-effect path?",
     "Conditional init"),
    ("4", "How does the callee use flareSurfGlob — including\nfunctions it delegates to?",
     "Trace downstream"),
    ("5", "How does the callee use atlasDataOffsets — including\nany functions it passes those offsets to?",
     "Deep data-flow trace"),
    ("6", "How does the callee use padding — including\nfunctions it passes the padding to?",
     "Trace downstream"),
]
for i, (num, q, strat) in enumerate(leads):
    set_cell(tbl, i+1, 0, num, ACCENT, True)
    set_cell(tbl, i+1, 1, q, TEXT_CLR, False, size=13)
    set_cell(tbl, i+1, 2, strat, DIM, False, size=13)

add_text(s, 0.5, 6.5, 12, 0.5,
         "Leads 1–3: What's initialized before the call?    "
         "Leads 4–6: What's actually read after the call?",
         size=16, color=ACCENT, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 4 — Phase 2: Investigation Results
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Phase 2 — Investigation Results")

tbl = styled_table(s, 7, 4, 0.5, 1.2, 12.3, 5.2,
                   col_widths=[0.5, 1.2, 1.2, 9.4])
set_cell(tbl, 0, 0, "#", WHITE, True)
set_cell(tbl, 0, 1, "Conf.", WHITE, True)
set_cell(tbl, 0, 2, "Tools", WHITE, True)
set_cell(tbl, 0, 3, "Key Finding", WHITE, True)

findings = [
    ("1", "High", "1",
     "atlasDataOffsets NOT assigned — only DebugWipe zeros it"),
    ("2", "High", "1",
     "padding NOT assigned — only DebugWipe zeros it"),
    ("3", "High", "1",
     "On != EFFECT path, flareSurfGlob gets no init beyond DebugWipe"),
    ("4", "High", "7",
     "flareSurfGlob only consumed via Draw_LensFlare — which only runs on the == EFFECT path where R_BeginFlareSurfs already initialized it"),
    ("5", "High", "13",
     "atlasDataOffsets read only on cache HIT — but cache starts zeroed, "
     "so first access is always a MISS (write-first). "
     "Traced 12 levels deep to FX_AddAtlasDataReserveCodeSurfBuffers"),
    ("6", "High", "1",
     "padding NEVER read anywhere in the entire call chain"),
]
for i, (num, conf, tools, finding) in enumerate(findings):
    set_cell(tbl, i+1, 0, num, ACCENT, True)
    set_cell(tbl, i+1, 1, conf, ACCENT)
    set_cell(tbl, i+1, 2, tools, TEXT_CLR)
    set_cell(tbl, i+1, 3, finding, TEXT_CLR, size=13)

add_text(s, 0.5, 6.6, 12, 0.5,
         "Lead 5 was the hardest — required tracing through 12 nested "
         "function calls to reach the actual read/write site.",
         size=15, color=WARN, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 5 — Phase 3: Synthesizer Verdict
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Phase 3 — Synthesizer Verdict")

# Big verdict
add_text(s, 0.5, 1.3, 12, 0.7,
         "Verdict:  FALSE POSITIVE  (No Issue — Code 1007)",
         size=28, color=ACCENT, bold=True, font_name="Segoe UI")

# Per-field table
tbl = styled_table(s, 4, 2, 0.5, 2.3, 12.3, 3.2,
                   col_widths=[2.8, 9.5])
set_cell(tbl, 0, 0, "Field", WHITE, True)
set_cell(tbl, 0, 1, "Why It's Safe", WHITE, True)

set_cell(tbl, 1, 0, "atlasDataOffsets", WARN, True)
set_cell(tbl, 1, 1,
         "DebugWipe zeros it → cache-owner check guarantees "
         "write-before-read (zero ≠ valid material pointer)",
         TEXT_CLR, size=14)

set_cell(tbl, 2, 0, "flareSurfGlob", WARN, True)
set_cell(tbl, 2, 1,
         "Uninitialized only on non-effect path → but flare drawing "
         "only executes on the effect path where R_BeginFlareSurfs "
         "initializes it",
         TEXT_CLR, size=14)

set_cell(tbl, 3, 0, "padding", WARN, True)
set_cell(tbl, 3, 1,
         "Zero from DebugWipe, never read anywhere — no sink exists",
         TEXT_CLR, size=14)

# Stats bar
add_text(s, 0.5, 5.8, 12, 0.8,
         "Run Stats:  40 tool calls  ·  6 leads (all high confidence)  "
         "·  $1.68  ·  ~8 minutes",
         size=16, color=DIM, font_name="Cascadia Code")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 6 — Why This Case Is Interesting
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Why This Case Is Interesting")

add_text(s, 0.5, 1.2, 12, 0.6,
         "Deep delegation chains challenge agentic analysis",
         size=22, color=WARN, bold=True, font_name="Segoe UI")

tf = add_text(s, 0.5, 2.0, 12, 4.5, "", size=17, font_name="Segoe UI")
items = [
    ("Lead 5 required tracing atlasDataOffsets through 12 nested\n"
     "function calls before reaching FX_AddAtlasDataReserveCodeSurfBuffers\n"
     "— the only place the field is actually read/written.",
     TEXT_CLR),
    ("Without the full trace, the engine sees \"field never assigned\" +\n"
     "\"field passed to callee\" → wrong True Positive verdict.",
     TEXT_CLR),
    ("Three prompt-level fixes made the model reliably follow the chain:",
     TITLE_CLR),
    ("  1. Planner: scope questions to include transitive callees",
     ACCENT),
    ("  2. Investigator: \"cannot answer until you follow the chain\"",
     ACCENT),
    ("  3. Investigator: \"stopping at a pass-through is incomplete\"",
     ACCENT),
    ("Budget extension mechanism (12 → 16 rounds) prevents the agent\n"
     "from being cut off mid-trace when it's still productive.",
     TEXT_CLR),
]
for txt, clr in items:
    add_para(tf, txt, size=17, color=clr, font_name="Segoe UI",
             space_before=Pt(12))

# ══════════════════════════════════════════════════════════════════════
# SLIDE 7 — Problem: Non-Deterministic Agent
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "Problem: Non-Deterministic Agent")

# Quote-style lead question
add_text(s, 0.5, 1.2, 12, 0.7,
         "\u201cHow does FX_DrawModularParticles use "
         "drawState.atlasDataOffsets after the call at line 104?\u201d",
         size=20, color=WARN, bold=False, font_name="Cascadia Code")

# Image (extracted from user's slide)
import os
img_path = os.path.join(os.path.dirname(__file__) or ".",
                        "_rearch", "slide7_image.png")
if not os.path.exists(img_path):
    img_path = r"_rearch\slide7_image.png"
if os.path.exists(img_path):
    s.shapes.add_picture(img_path,
                         Emu(1351822), Emu(2562656),
                         Emu(5740693), Emu(2390944))

# Bottom callout
add_text(s, 0.5, 5.5, 12, 0.6,
         "Same lead, same prompt, same model \u2014 wildly different behavior",
         size=22, color=TITLE_CLR, bold=True, font_name="Segoe UI")

# ══════════════════════════════════════════════════════════════════════
# SLIDE 8 — The Cause and Solution
# ══════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s)
add_title(s, "The Cause and Solution")

tf = add_text(s, 0.5, 1.2, 12, 5.5, "", size=17, font_name="Segoe UI")

cause_items = [
    ("THE CAUSE",
     TITLE_CLR, True),
    ("The prompt says: \u201cCAN I ANSWER NOW? If remaining unknowns "
     "would not change the answer, stop.\u201d",
     TEXT_CLR, False),
    ("Agents 3,4: \u201cFunction A doesn\u2019t access field X \u2192 "
     "I can answer\u201d \u2014 ignores that Function A passes the "
     "entire struct to Function B",
     WARN, False),
    ("Agents 2,5 reasoned more deeply and followed Function B and so on",
     DIM, False),
    ("",
     TEXT_CLR, False),
    ("THE FIX  (3 prompt changes)",
     TITLE_CLR, True),
    ("1. Investigator: \u201c\u2026But if the data is passed to a callee, "
     "you CANNOT answer until you follow the chain\u201d",
     ACCENT, False),
    ("2. Investigator FOLLOW DELEGATION CHAINS: \u201cStopping at a "
     "pass-through is an incomplete answer. You must look up the callee.\u201d",
     ACCENT, False),
    ("3. Planner: \u201cWhen a question asks how a function uses data, "
     "scope it to include any functions the data is passed to, "
     "not just the immediate function.\u201d",
     ACCENT, False),
]
for txt, clr, bld in cause_items:
    add_para(tf, txt, size=17, color=clr, bold=bld,
             font_name="Segoe UI", space_before=Pt(10))

# ── Save ──
out = r"C:\Users\tliggett\source\repos\Vulnhalla\_rearch\CID-25863-walkthrough.pptx"
prs.save(out)
print(f"Saved \u2192 {out}")
