"""Begleitheft (PDF) pro Fach aus allen Kapitel-Skripten: das Wichtigste, Rechenwege, Merke-Kästen,
Übungen mit Platz zum Rechnen, Notizspalte rechts, Lösungen im Anhang.

Aufruf: python3 handout.py "<Fach>"  ->  out/<Fach>/<Fach>_Begleitheft.pdf
"""
import json, os, re, sys, glob
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                Preformatted, PageBreak, KeepTogether)
from xml.sax.saxutils import escape

FACH = sys.argv[1]
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("D", FD + "DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("DB", FD + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DM", FD + "DejaVuSansMono.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("D", normal="D", bold="DB", italic="D", boldItalic="DB")

files = sorted(glob.glob(os.path.join("skripte", FACH, "kapitel_*.json")))
if not files: sys.exit(0)
KAP = [json.load(open(f)) for f in files]
gl_p = os.path.join("skripte", FACH, "gliederung.json")
GL = {k["nr"]: k for k in json.load(open(gl_p))["kapitel"]} if os.path.exists(gl_p) else {}

PW, PH = A4; ML, MR, NOTE = 16 * mm, 10 * mm, 48 * mm          # rechte Spalte = Notizen
CW = PW - ML - MR - NOTE - 6 * mm
ACC = colors.HexColor("#2563EB"); ORA = colors.HexColor("#EA7814"); GRN = colors.HexColor("#10A078"); RED = colors.HexColor("#C83250")
st = lambda n, **k: ParagraphStyle(n, fontName=k.pop("f", "D"), **k)
S = dict(
    h1=st("h1", f="DB", fontSize=17, leading=21, textColor=colors.HexColor("#21252F"), spaceAfter=4),
    h2=st("h2", f="DB", fontSize=11.5, leading=15, textColor=ACC, spaceBefore=8, spaceAfter=3),
    p=st("p", fontSize=9.6, leading=13.2), b=st("b", fontSize=9.6, leading=13.2, leftIndent=10, bulletIndent=1),
    sm=st("sm", fontSize=8.6, leading=11.5, textColor=colors.HexColor("#555A66")),
    box=st("box", fontSize=9.4, leading=12.8), code=st("code", f="DM", fontSize=8.2, leading=10.4),
)
P = lambda t, s="p": Paragraph(escape(str(t)).replace("\n", "<br/>"), S[s])

def page(c, d):
    c.saveState()
    x = PW - MR - NOTE
    c.setFont("DB", 7.5); c.setFillColor(colors.HexColor("#9AA0AC")); c.drawString(x + 2 * mm, PH - 14 * mm, "NOTIZEN")
    c.setStrokeColor(colors.HexColor("#E3E5EA")); c.setLineWidth(0.4)
    c.line(x, 14 * mm, x, PH - 12 * mm)
    y = PH - 20 * mm
    while y > 16 * mm: c.line(x + 2 * mm, y, PW - MR, y); y -= 7 * mm
    c.setFont("D", 7.5); c.setFillColor(colors.HexColor("#9AA0AC"))
    c.drawString(ML, 8 * mm, f"{FACH.replace('_', ' ')} – Begleitheft zu den Lernvideos mit Professor Kai")
    c.drawRightString(PW - MR, 8 * mm, str(d.page)); c.restoreState()

def box(flows, col, title):
    t = Table([[Paragraph(f'<font name="DB" color="{col.hexval()}">{title}</font>', S["box"])]] + [[f] for f in flows], colWidths=[CW])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, col), ("LINEBEFORE", (0, 0), (0, -1), 3, col),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.Color(col.red, col.green, col.blue, 0.06)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t

def lines(n):  # Platz zum Rechnen
    t = Table([[""]] * n, colWidths=[CW], rowHeights=[7 * mm] * n)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D8DE"))])); return t

story, loes = [], []
story += [Spacer(1, 30 * mm), P(FACH.replace("_", " "), "h1"), P("Begleitheft zu den Lernvideos", "h2"),
          P("So nutzt du das Heft: Video starten, hier mitlesen, rechts Notizen machen. Bei jeder Übung das Video pausieren "
            "und im Kasten rechnen. Die Lösungen stehen gesammelt im Anhang – erst nachschauen, wenn du es selbst versucht hast."),
          Spacer(1, 6 * mm), P("Inhalt", "h2")]
story += [P(f"Kapitel {k['nr']}: {k['titel']}", "b") for k in KAP] + [PageBreak()]

for k in KAP:
    nr = k["nr"]; g = GL.get(nr, {})
    story += [P(f"Kapitel {nr}: {k['titel']}", "h1")]
    if g.get("quellen"): story.append(P("Vorlesung: " + ", ".join(g["quellen"]), "sm"))
    if g.get("leitfragen"):
        story += [Spacer(1, 3), box([P("• " + q, "box") for q in g["leitfragen"]], RED, "LEITFRAGEN – das musst du beantworten können")]
    ue = 0
    for sz in k["szenen"]:
        typ = sz.get("typ", "erklaerung"); pts = sz.get("folie_punkte") or []
        if typ == "einstieg": continue
        if typ == "aufgabe":
            ue += 1
            fl = [P(p, "box") for p in pts]
            if sz.get("code"): fl.append(Preformatted(sz["code"], S["code"]))
            story += [Spacer(1, 5), KeepTogether([box(fl, ORA, f"ÜBUNG {nr}.{ue}: {sz.get('folie_titel', '')}"), lines(6)])]
            continue
        if typ == "loesung":
            loes.append((f"Lösung {nr}.{max(ue, 1)}: {sz.get('folie_titel', '')}", sz)); continue
        blk = [P(sz.get("folie_titel", ""), "h2")]
        for p in pts: blk.append(Paragraph(escape(p), S["b"], bulletText="•"))
        if sz.get("code"): blk += [Spacer(1, 3), box([Preformatted(sz["code"], S["code"])], colors.HexColor("#21252F"), "CODE")]
        if sz.get("rechnung"):
            blk += [Spacer(1, 3), box([P(r, "box") for r in sz["rechnung"]], ACC, "RECHENWEG")]
        if typ == "leitfrage":
            blk += [Spacer(1, 2), box([P(" ".join(sz.get("sprechtext", [])), "box")], RED, "ANTWORT AUF DIE LEITFRAGE")]
        elif typ in ("beispiel", "zusammenfassung") and not sz.get("rechnung"):
            blk += [Spacer(1, 2), box([P(" ".join(sz.get("sprechtext", [])), "box")], GRN, "BEISPIEL" if typ == "beispiel" else "ZUSAMMENFASSUNG")]
        if sz.get("merke"):
            blk += [Spacer(1, 3), box([P(m, "box") for m in (sz["merke"] if isinstance(sz["merke"], list) else [sz["merke"]])], RED, "MERKE / BEMERKUNG")]
        story.append(KeepTogether(blk))
    story.append(PageBreak())

if loes:
    story.append(P("Anhang: Lösungen", "h1"))
    for title, sz in loes:
        fl = [P(p, "box") for p in (sz.get("folie_punkte") or [])]
        if sz.get("rechnung"): fl += [P(r, "box") for r in sz["rechnung"]]
        if sz.get("code"): fl.append(Preformatted(sz["code"], S["code"]))
        fl.append(P(" ".join(sz.get("sprechtext", [])), "sm"))
        story += [Spacer(1, 5), box(fl, GRN, title)]

out = os.path.join("out", FACH); os.makedirs(out, exist_ok=True)
doc = BaseDocTemplate(os.path.join(out, f"{FACH}_Begleitheft.pdf"), pagesize=A4, title=f"{FACH} – Begleitheft")
doc.addPageTemplates([PageTemplate(frames=[Frame(ML, 14 * mm, CW, PH - 28 * mm, 0, 0, 0, 0)], onPage=page)])
doc.build(story)
print("Begleitheft:", FACH, len(KAP), "Kapitel")
