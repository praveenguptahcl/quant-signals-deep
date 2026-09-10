#!/usr/bin/env python3
"""Final Part II validator for MASTER.md. Produces findings JSON."""
import re, json, sys

PATH = "/home/hatch/workspace/quant-signals-deep/MASTER.md"
lines = open(PATH).read().split("\n")

def gh_anchor(heading_text):
    # heading_text without the leading ## marks
    t = heading_text.strip().lower()
    t = re.sub(r"[^\w\s-]", "", t)  # drop punctuation except _ and -
    t = t.replace(" ", "-")  # GitHub: each space -> one hyphen (no collapsing)
    return t

findings = []
def add(sev, check, chapter, line, evidence):
    findings.append({"severity": sev, "check": check, "chapter": chapter,
                     "line": line, "evidence": evidence[:400]})

# ---- current chapter context per line ----
# map stage number -> chapter id
stage_of_line = [None] * (len(lines)+1)
chapter_of_line = [None] * (len(lines)+1)
stage_nums = []
stage_headings = []
for i, ln in enumerate(lines, 1):
    m = re.match(r"^## Stage (\d+)/200 — ([ST]\d{3}):", ln)
    if m:
        n = int(m.group(1)); ch = m.group(2)
        stage_nums.append(n)
        stage_headings.append((n, ch, i, ln))
        cur_stage, cur_ch = n, ch
    else:
        try: cur_stage
        except NameError: cur_stage, cur_ch = 0, "FRONTMATTER"
    stage_of_line[i] = cur_stage
    chapter_of_line[i] = cur_ch

# ============ CHECK 8: stage order 1-200 ============
seen = set(); dupes = []; prev = 0; gaps = []
for n, ch, i, ln in stage_headings:
    if n in seen: dupes.append((n, ch, i))
    seen.add(n)
    if n != prev + 1 and prev != 0:
        gaps.append((prev, n, i))
    prev = n
missing = [n for n in range(1, 201) if n not in seen]
extra = sorted(seen - set(range(1, 201)))
if missing: add("BLOCKER", "stage-order", "MASTER", 0, f"Missing stage numbers: {missing}")
if extra: add("BLOCKER", "stage-order", "MASTER", 0, f"Stage numbers out of 1-200: {extra}")
if dupes: add("BLOCKER", "stage-order", "MASTER", 0, f"Duplicate stage headings: {dupes}")
if gaps: add("BLOCKER", "stage-order", "MASTER", 0, f"Order gaps/out-of-sequence: {gaps}")
check8 = {"total_stage_headings": len(stage_headings), "missing": missing,
          "extra": extra, "dupes": [(n, ch, ln) for n, ch, ln in dupes], "gaps": gaps}

# ============ CHECK 1: TOC anchors ============
anchors_defined = set()
for n, ch, i, ln in stage_headings:
    heading_text = ln.lstrip("#").strip()
    anchors_defined.add("#" + gh_anchor(heading_text))
# TOC anchors: markdown links with # anchors
toc_anchors = []
broken = []
ok = 0
for i, ln in enumerate(lines, 1):
    for m in re.finditer(r"\]\(#([A-Za-z0-9\-_]+)\)", ln):
        a = "#" + m.group(1)
        toc_anchors.append((a, i))
        if a in anchors_defined: ok += 1
        else: broken.append((a, i, chapter_of_line[i], ln.strip()[:120]))
if broken:
    for a, i, ch, ln in broken:
        add("BLOCKER", "toc-anchor", ch, i, f"TOC anchor {a} has no matching heading. Context: {ln}")
check1 = {"toc_anchor_links": len(toc_anchors), "resolved": ok, "broken": len(broken)}

# ============ CHECK 2: cross-references ============
valid_ids = {f"S{n:03d}" for n in range(1, 101)} | {f"T{n:03d}" for n in range(1, 101)}
dangling = []
total_refs = 0
for i, ln in enumerate(lines, 1):
    # skip "Stage 0" prose? The task says exclude S0XX in "Stage 0" prose.
    for m in re.finditer(r"\b([ST])(\d{3})\b", ln):
        rid = m.group(0)
        if rid.startswith("S0"):  # S0XX — could be Stage 0 prose; check context
            if re.search(r"Stage 0", ln): continue
        total_refs += 1
        if rid not in valid_ids:
            dangling.append((rid, i, chapter_of_line[i], ln.strip()[:150]))
# dedupe by (rid, line)
dangling = sorted(set(dangling))
if dangling:
    for rid, i, ch, ln in dangling:
        add("MAJOR", "cross-ref", ch, i, f"Dangling chapter ref {rid}. Context: {ln}")
check2 = {"total_chapter_refs": total_refs, "dangling": len(dangling)}

# ============ CHECK 3: chatbot-only evidence tables ============
# find S9/T9 sections: heading "### S9." or "### T9." through next "### S10."/"### T10."
pub_markers = re.compile(r"arXiv|doi\.org|DOI|10\.\d{4,}|\(19\d{2}\)|\(20\d{2}\)|NBER|JFQA|Journal|SSRN|github\.com/|GitHub|blog|paper|study", re.I)
chat_markers = re.compile(r"grok|chatbot|duck\.ai|research note|unverified lead|unverified claim", re.I)
chatbot_only_chapters = []
in_ev = None; ev_rows = []; ev_chapter = None; ev_line = None
for i, ln in enumerate(lines, 1):
    if re.match(r"^### [ST]9\. ", ln):
        in_ev = True; ev_rows = []; ev_chapter = chapter_of_line[i]; ev_line = i
    elif re.match(r"^### [ST]10\. ", ln) and in_ev:
        # evaluate collected rows
        rows = [r for r in ev_rows if r.strip().startswith("|") and "Study" not in r and "---" not in r]
        if rows:
            pub_hits = [r for r in rows if pub_markers.search(r)]
            chat_hits = [r for r in rows if chat_markers.search(r)]
            if not pub_hits and chat_hits:
                chatbot_only_chapters.append((ev_chapter, ev_line, rows))
        in_ev = False
    elif in_ev and ln.strip().startswith("|"):
        ev_rows.append(ln)
for ch, i, rows in chatbot_only_chapters:
    add("MAJOR", "chatbot-only-evidence", ch, i,
        f"Evidence table rows cite only chatbot/Grok/research-note material, no published source. Rows: {rows[:3]}")
check3 = {"evidence_tables_scanned": "S9+T9 sections", "chatbot_only": len(chatbot_only_chapters)}

# also: chatbot claims inside evidence tables mixed with published sources (informational)
mixed_chat = []
for i, ln in enumerate(lines, 1):
    pass

# ============ CHECK 4: same-bar execution (strategy chapters only) ============
viol_pat = re.compile(
    r"fills?\s+on\s+the\s+same\s+bar|enters?\s+at\s+the\s+close\s+of\s+the\s+signal\s+bar|"
    r"executes?\s+immediately\s+on\s+bar\s+t\b|fills?\s+at\s+the\s+signal-bar\s+close|"
    r"trade\s+inside\s+the\s+same\s+bar|enter\s+on\s+the\s+signal\s+bar\s+close",
    re.I)
samebar = []
for i, ln in enumerate(lines, 1):
    ch = chapter_of_line[i]
    if ch and ch.startswith("T") and stage_of_line[i] and stage_of_line[i] >= 101:
        if viol_pat.search(ln):
            samebar.append((ch, i, ln.strip()[:200]))
# Also search for suspicious phrasing "same bar" in T chapters broadly
samebar_loose = []
for i, ln in enumerate(lines, 1):
    ch = chapter_of_line[i]
    if ch and ch.startswith("T") and stage_of_line[i] and stage_of_line[i] >= 101:
        if re.search(r"same.?bar", ln, re.I):
            samebar_loose.append((ch, i, ln.strip()[:200]))
check4 = {"strict_violations": len(samebar), "loose_samebar_hits": len(samebar_loose)}

# ============ CHECK 5: vendor disclaimers ============
suffix = "indicative — verify before budgeting"
dollar_lines = []
for i, ln in enumerate(lines, 1):
    if re.search(r"\$[0-9]", ln) and suffix not in ln:
        dollar_lines.append((chapter_of_line[i], i, ln.strip()[:220]))
# filter to vendor-ish mentions
vendor_pat = re.compile(r"polygon|optionmetrics|bloomberg|alpaca|refinitiv|factset|iex|dxfeed|rithmic|"
    r"quantconnect|databento|tickdata|algoseek|first rate|tradestation|interactive brokers|"
    r"sierra chart|ninjatrader|multicharts|bookmap|quantchaos|unusual whales|flowalgo|"
    r"vendor|subscription|per month|/mo|/yr|annual|license", re.I)
vendor_no_suffix = [(ch, i, ln) for ch, i, ln in dollar_lines if vendor_pat.search(ln)]
check5 = {"dollar_lines_without_suffix_total": len(dollar_lines),
          "vendor_like_without_suffix_total": len(vendor_no_suffix)}

# ============ CHECK 7: formula sanity ============
formula_issues = []
in_display = False  # inside a multi-line $$ ... $$ block
for i, ln in enumerate(lines, 1):
    ch = chapter_of_line[i]
    n_ds = ln.count("$$")
    if in_display:
        if n_ds % 2 == 1:  # closes the block
            in_display = False
        continue
    else:
        if n_ds % 2 == 1:
            # opens a block unless a closing $$ exists later on same line... odd count = unbalanced on this line -> opens block
            in_display = True
    if "$$$" in ln and ln.strip().startswith("|"):
        formula_issues.append((ch, i, "triple-$ inside table cell (renders oddly): " + ln.strip()[:150]))
    if re.search(r"(?<!\\)\bNaN\b", ln):
        formula_issues.append((ch, i, "contains NaN: " + ln.strip()[:150]))
    if re.search(r"\b(XXX|TODO|FIXME)\b", ln):
        formula_issues.append((ch, i, "placeholder: " + ln.strip()[:150]))
# check \( \) balance per line
for i, ln in enumerate(lines, 1):
    if r"\(" in ln or r"\)" in ln:
        o = len(re.findall(r"\\\(", ln)); c = len(re.findall(r"\\\)", ln))
        if o != c:
            formula_issues.append((chapter_of_line[i], i,
                f"unbalanced \\( ({o}) vs \\) ({c}): " + ln.strip()[:150]))
# check \[ \] display-math balance per line
for i, ln in enumerate(lines, 1):
    if r"\[" in ln or r"\]" in ln:
        o = len(re.findall(r"\\\[", ln)); c = len(re.findall(r"\\\]", ln))
        if o != c:
            formula_issues.append((chapter_of_line[i], i,
                f"unbalanced \\[ ({o}) vs \\] ({c}): " + ln.strip()[:150]))
check7 = {"formula_issues": len(formula_issues)}

# ============ CHECK 9: placeholders ============
ph_pat = re.compile(r"\b(TODO|FIXME|TBD|CHAPTER-DEFERRED)\b|XXX(?![A-Za-z])")
placeholders = []
for i, ln in enumerate(lines, 1):
    m = ph_pat.search(ln)
    if m:
        placeholders.append((chapter_of_line[i], i, m.group(0), ln.strip()[:150]))
for ch, i, ph, ln in placeholders:
    add("MINOR", "placeholder", ch, i, f"{ph}: {ln}")
check9 = {"placeholders": len(placeholders)}

out = {
    "check1_toc": check1,
    "check2_xref": check2,
    "check3_chatbot_evidence": check3,
    "check4_samebar": {"strict": samebar, "loose": samebar_loose},
    "check5_vendor": {"dollar_lines_without_suffix": dollar_lines,
                      "vendor_like": vendor_no_suffix},
    "check7_formulas": formula_issues[:60],
    "check8_stage_order": check8,
    "check9_placeholders": placeholders[:60],
    "findings": findings,
}
json.dump(out, open("/home/hatch/workspace/quant-signals-deep/batches/validation_results.json", "w"), indent=1)
print(json.dumps({k: (v if not isinstance(v, dict) else {kk: (len(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()}) for k, v in out.items() if k != "findings"}, indent=1))
print("FINDINGS:", len(findings))
for f in findings:
    print(f["severity"], "|", f["check"], "|", f["chapter"], "| L" + str(f["line"]), "|", f["evidence"][:120])
