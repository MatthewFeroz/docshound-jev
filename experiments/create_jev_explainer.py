"""Build an editable Excalidraw board and matching vector/raster preview panels.

Run: uv run --no-project --with pillow python experiments/create_jev_explainer.py
"""

import html
import json
import math
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo/jev/explainer"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
INK, MUTED, BG = "#193249", "#526779", "#faf9f6"
BLUE, GREEN, GOLD, GRAY = "#e5efff", "#d9f5e5", "#fff0cd", "#edf0f3"
FONT = Path("C:/Windows/Fonts/arial.ttf")
elements = []
panels = []
offset = 0
frame_id = ""
serial = 0


def font(size):
    return ImageFont.truetype(str(FONT), size)


def element(kind, x, y, w, h, **extra):
    global serial
    serial += 1
    item = {
        "id": f"jev-{serial:04d}",
        "type": kind,
        "x": x,
        "y": y + offset,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": INK,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": frame_id or None,
        "roundness": None,
        "seed": serial * 7919,
        "version": 1,
        "versionNonce": serial * 3571,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1789786000000,
        "created": 1789786000000,
        "link": None,
        "locked": False,
    }
    item.update(extra)
    elements.append(item)
    return item


def rect(x, y, w, h, fill=GRAY, stroke=INK, group=None):
    return element(
        "rectangle",
        x,
        y,
        w,
        h,
        backgroundColor=fill,
        strokeColor=stroke,
        roundness={"type": 3},
        groupIds=[group] if group else [],
    )


def text(x, y, value, size=24, color=INK, max_width=None, group=None):
    lines = []
    for paragraph in value.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            attempt = f"{line} {word}" if line else word
            if max_width and font(size).getlength(attempt) > max_width and line:
                lines.append(line)
                line = word
            else:
                line = attempt
        lines.append(line)
    value = "\n".join(lines)
    width = max(font(size).getlength(line) for line in lines) + 4
    return element(
        "text",
        x,
        y,
        width,
        len(lines) * size * 1.25,
        text=value,
        originalText=value,
        fontSize=size,
        fontFamily=2,
        textAlign="left",
        verticalAlign="top",
        containerId=None,
        autoResize=True,
        lineHeight=1.25,
        strokeColor=color,
        groupIds=[group] if group else [],
    )


def arrow(points, color=MUTED, dashed=False, head=True):
    x, y = points[0]
    rel = [[px - x, py - y] for px, py in points]
    return element(
        "arrow" if head else "line",
        x,
        y,
        max(p[0] for p in rel) - min(p[0] for p in rel),
        max(p[1] for p in rel) - min(p[1] for p in rel),
        points=rel,
        strokeColor=color,
        strokeStyle="dashed" if dashed else "solid",
        startBinding=None,
        endBinding=None,
        startArrowhead=None,
        endArrowhead="arrow" if head else None,
        elbowed=False,
    )


def card(x, y, w, h, title, body, fill=GRAY, title_size=27, body_size=23):
    group = f"card-{serial + 1}"
    rect(x, y, w, h, fill=fill, group=group)
    heading = text(
        x + 22, y + 20, title, size=title_size, max_width=w - 44, group=group
    )
    content = text(
        x + 22,
        y + 28 + heading["height"],
        body,
        size=body_size,
        color=MUTED,
        max_width=w - 44,
        group=group,
    )
    assert content["y"] + content["height"] <= offset + y + h - 10, title


def panel(name, title, subtitle):
    global offset, frame_id
    offset = len(panels) * 1200
    frame_id = ""
    frame = element("frame", 0, 0, W, H, name=name, strokeColor="#c8ced3")
    frame_id = frame["id"]
    panels.append((name, offset, frame_id))
    rect(0, 0, W, H, fill=BG, stroke=BG)
    text(70, 48, title, size=44)
    text(70, 113, subtitle, size=25, color=MUTED)


panel(
    "01 - Harness architecture",
    "Where Jev sits in DocsHound",
    "Two classifier nodes + one optional drafting gate. This is the implemented LangGraph flow.",
)
card(
    70,
    200,
    1740,
    105,
    "llm_decide (Luna) + guarded route()",
    "Select the next stage. Dashed arrows are conditional routes; the bottom path returns control.",
    BLUE,
    29,
    24,
)
xs = [70, 430, 790, 1150, 1510]
for i, x in enumerate(xs):
    arrow([(x + 150, 313), (x + 150, 332)], dashed=True, head=False)
    arrow([(x + 150, 381), (x + 150, 399)], dashed=True)
    text(
        x + 22,
        349,
        ["1  RESEARCH", "2  ANALYZE", "3  SEARCH DOCS", "4  DRAFT", "5  STORE"][i],
        20,
        MUTED,
    )
card(70, 410, 300, 145, "GitHub research", "Read issues and\nmerged PRs.", GRAY)
card(
    430,
    410,
    300,
    145,
    "Luna analysis",
    "Turn source activity\ninto candidate findings.",
    BLUE,
)
arrow([(580, 561), (580, 588)], color="#26734d")
card(
    430,
    595,
    300,
    175,
    "Jev: triage",
    "Finding type\nBehavior readiness\nIntended audience",
    GREEN,
)
card(
    790,
    410,
    300,
    145,
    "Docs search",
    "NVIDIA retrieval +\nLuna coverage verdict.",
    BLUE,
)
arrow([(940, 561), (940, 588)], color="#26734d")
card(
    790,
    595,
    300,
    175,
    "Jev: evidence",
    "Documentation need\nRelevance of each\nretrieved passage",
    GREEN,
)
rect(1150, 410, 300, 360, BLUE)
card(
    1165,
    427,
    270,
    153,
    "Python gate",
    "If enabled + verify\nimplementation:\nmark finding held.",
    GOLD,
    26,
    21,
)
text(1175, 606, "Luna writes", 27)
text(
    1175, 650, "Only remaining\neligible findings.\nKeep held items visible.", 22, MUTED
)
card(1510, 410, 300, 145, "Finalize run", "Harness persists\nstate and trace.", GRAY)
arrow([(1660, 563), (1660, 616)])
rect(1585, 628, 150, 62, GRAY)
text(1623, 644, "END", 25)
for cx, bottom in [(220, 555), (580, 770), (940, 770), (1300, 770)]:
    arrow([(cx, bottom + 8), (cx, 825)], dashed=True, head=False)
arrow([(220, 825), (1860, 825), (1860, 252), (1818, 252)], dashed=True)
card(
    70,
    878,
    1090,
    138,
    "Both Jev nodes call Merge Gateway /v1/decisions",
    "typesafe/jev-1.13 returns choices. Shared state carries them to Python recommend(), then the drafting gate.",
    GREEN,
    25,
    23,
)
card(
    1190,
    878,
    620,
    138,
    "Only verification holds are enforced",
    "retrieve_more does not search again. No confidence threshold. Unavailable results advise manual review.",
    GOLD,
    24,
    22,
)

panel(
    "02 - Measured outcomes",
    "What changed in the 10 real runs?",
    "OpenCode + Pi | 200 issues + 200 merged PRs | distinct source items, not independent labels",
)
for x, title, body in [
    (70, "71", "findings"),
    (515, "142", "Jev requests"),
    (960, "497", "classification answers"),
    (1405, "$0.01228", "reported Jev cost"),
]:
    card(x, 195, 420, 120, title, body, GREEN, 35, 23)
card(
    70,
    465,
    350,
    165,
    "71 findings",
    "Luna assesses\ndocumentation coverage.",
    BLUE,
    32,
    25,
)
arrow([(429, 540), (487, 540), (487, 418), (560, 418)])
arrow([(487, 540), (487, 705), (560, 705)])
card(
    570,
    335,
    500,
    170,
    "52 eligible under Luna",
    "Coverage + recommended action\nallow a documentation draft.",
    BLUE,
    30,
    24,
)
card(
    570,
    620,
    500,
    170,
    "19 already ineligible",
    "Luna already says documented\nor unable to verify.",
    GRAY,
    30,
    24,
)
arrow([(1078, 420), (1200, 420), (1200, 406), (1348, 406)], color="#a76910")
arrow([(1200, 420), (1200, 608), (1348, 608)], color="#26734d")
card(
    1360,
    333,
    450,
    153,
    "33 newly held",
    "Jev gate changes eligibility.\nWhether that helped is unjudged.",
    GOLD,
    33,
    23,
)
card(
    1360,
    535,
    450,
    153,
    "19 drafts generated",
    "These findings pass the gate\nand Luna writes review drafts.",
    GREEN,
    32,
    23,
)
arrow([(1078, 705), (1200, 705), (1200, 805), (1348, 805)])
card(
    1360,
    746,
    450,
    139,
    "11 also flagged; 8 unheld",
    "None of these 19 was eligible\nfor a draft under Luna anyway.",
    GRAY,
    26,
    23,
)
card(
    70,
    920,
    1740,
    104,
    "44 hold flags = 33 eligibility changes + 11 overlapping decisions",
    "Zero independent human labels. The runs demonstrate a functioning gate, not improved accuracy or 44 bad drafts prevented.",
    GOLD,
    29,
    23,
)

panel(
    "03 - Evaluate the decisions",
    "Was Jev right? Review the disagreements.",
    "The video should show an observable intervention, then a fair test of whether that intervention helped.",
)
card(
    70,
    215,
    550,
    400,
    "1  Freeze the evidence",
    "Use the saved finding, original issue/PR text and exact retrieved excerpts.\n\nKeep the repo revision and date. Record the available evidence; do not silently add future fixes.\n\n71 cases are saved with blank review fields.",
    GRAY,
    31,
    26,
)
arrow([(630, 413), (673, 413)])
card(
    685,
    215,
    550,
    400,
    "2  Review before revealing",
    "Hide Luna and Jev verdicts.\n\nIs the claimed behavior established? Do the docs already answer the question? Is a draft justified?\n\nAllow unknown. For stronger ground truth, separately inspect pinned implementation code.",
    BLUE,
    30,
    25,
)
arrow([(1245, 413), (1288, 413)])
card(
    1300,
    215,
    550,
    400,
    "3  Compare the decisions",
    "Reveal model labels and actual action.\n\nReview all 33 newly held findings and the 19 drafts that passed. Check the 19 baseline-ineligible cases too.\n\nKeep rationale and evidence links, including disagreements.",
    GREEN,
    29,
    25,
)
card(
    70,
    670,
    550,
    190,
    "Useful intervention",
    "Among the 33 new holds:\nhow many findings lacked the evidence needed to justify drafting?",
    GREEN,
    29,
    25,
)
card(
    685,
    670,
    550,
    190,
    "Unnecessary friction",
    "Among the same 33 holds:\nhow many ready, useful documentation changes were delayed?",
    GOLD,
    29,
    25,
)
card(
    1300,
    670,
    550,
    190,
    "Missed problems",
    "Among the 19 generated drafts:\nhow many still contain unsupported claims or duplicate existing docs?",
    GOLD,
    29,
    25,
)
rect(70, 910, 1780, 113, INK, INK)
text(
    94,
    930,
    "SHOW: one hold, one pass, one redundant decision. SAY: quality benefit is still unproven.",
    28,
    "#ffffff",
)
text(
    94,
    974,
    "Report unknowns separately. The relevance labels, confidence scores and number of holds are not correctness measurements.",
    23,
    "#d7e3ed",
)


def render(name, top, fid):
    selected = [e for e in elements if e["frameId"] == fid]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    ]
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    for e in selected:
        x, y, w, h = e["x"], e["y"] - top, e["width"], e["height"]
        stroke, fill = e["strokeColor"], e["backgroundColor"]
        if e["type"] == "rectangle":
            draw.rounded_rectangle(
                (x, y, x + w, y + h), radius=14, fill=fill, outline=stroke, width=2
            )
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            )
        elif e["type"] == "text":
            assert 0 <= x and x + w < W + 1 and y + h < H + 1, e["text"]
            size = e["fontSize"]
            for i, line in enumerate(e["text"].split("\n")):
                ly = y + i * size * 1.25
                draw.text((x, ly), line, font=font(size), fill=stroke, anchor="lt")
                svg.append(
                    f'<text x="{x}" y="{ly + size * 0.92}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" fill="{stroke}">{html.escape(line)}</text>'
                )
        else:
            points = [(x + px, y + py) for px, py in e["points"]]
            dashed = e["strokeStyle"] == "dashed"
            for (ax, ay), (bx, by) in pairwise(points):
                length = math.hypot(bx - ax, by - ay)
                if dashed:
                    for step in range(0, math.ceil(length), 16):
                        t0, t1 = step / length, min(step + 8, length) / length
                        draw.line(
                            (
                                ax + (bx - ax) * t0,
                                ay + (by - ay) * t0,
                                ax + (bx - ax) * t1,
                                ay + (by - ay) * t1,
                            ),
                            fill=stroke,
                            width=3,
                        )
                else:
                    draw.line((ax, ay, bx, by), fill=stroke, width=3)
            dash = ' stroke-dasharray="8 8"' if dashed else ""
            coords = " ".join(f"{px},{py}" for px, py in points)
            svg.append(
                f'<polyline points="{coords}" fill="none" stroke="{stroke}" stroke-width="3"{dash}/>'
            )
            if e["type"] == "arrow":
                ax, ay = points[-2]
                bx, by = points[-1]
                angle = math.atan2(by - ay, bx - ax)
                head = [
                    (bx - 15 * math.cos(angle - 0.5), by - 15 * math.sin(angle - 0.5)),
                    (bx, by),
                    (bx - 15 * math.cos(angle + 0.5), by - 15 * math.sin(angle + 0.5)),
                ]
                draw.line(head, fill=stroke, width=3)
                coords = " ".join(f"{px},{py}" for px, py in head)
                svg.append(
                    f'<polyline points="{coords}" fill="none" stroke="{stroke}" stroke-width="3"/>'
                )
    svg.append("</svg>")
    slug = name.lower().replace(" - ", "-").replace(" ", "-")
    (OUT / f"{slug}.svg").write_text("\n".join(svg), encoding="utf-8")
    image.save(OUT / f"{slug}.png")


for args in panels:
    render(*args)
scene = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"viewBackgroundColor": BG, "gridSize": None},
    "files": {},
}
(OUT / "docshound-jev.excalidraw").write_text(
    json.dumps(scene, indent=2), encoding="utf-8"
)
assert len({e["id"] for e in elements}) == len(elements)
print(f"Created {len(elements)} editable elements in {len(panels)} panels: {OUT}")
