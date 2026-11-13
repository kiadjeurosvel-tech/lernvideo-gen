"""Rendert aus skripte/<Fach>/kapitel_XX.json ein Erklärvideo mit Tutor-Figur „Professor Kai“.

Aufruf:  python3 build.py "<Fach>" [kapitel]      -> out/<Fach>/Kapitel_XX_<Titel>.mp4 (+ _Aufgaben.md)
Stimme:  Piper (Umgebungsvariable VOICE = Pfad zur .onnx), LENGTH = Sprechtempo (1.0 normal, höher = langsamer)
"""
import json, os, re, sys, glob, math, subprocess, unicodedata
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 15
FACH = sys.argv[1]
WANT = sys.argv[2] if len(sys.argv) > 2 else ""
VOICE = os.environ.get("VOICE", "voices/de_DE-thorsten-high.onnx")
LENGTH = float(os.environ.get("LENGTH", "1.08"))
OUT = os.path.join("out", FACH); os.makedirs(OUT, exist_ok=True)

FD = "/usr/share/fonts/truetype/dejavu/"
def F(sz, w="Sans"): return ImageFont.truetype(FD + {"Sans": "DejaVuSans.ttf", "Bold": "DejaVuSans-Bold.ttf", "Mono": "DejaVuSansMono.ttf"}[w], sz)

BG, INK, MUTED = (248, 247, 244), (33, 37, 48), (110, 114, 126)
TYP = {  # Farbe, Etikett
    "einstieg": ((52, 120, 246), "EINSTIEG"), "erklaerung": ((52, 120, 246), "ERKLÄRUNG"),
    "beispiel": ((16, 160, 120), "BEISPIEL"), "leitfrage": ((140, 70, 220), "LEITFRAGE"),
    "aufgabe": ((236, 120, 20), "ÜBUNG"), "loesung": ((16, 160, 120), "LÖSUNG"),
    "zusammenfassung": ((200, 50, 80), "ZUSAMMENFASSUNG"),
}

# ---------------------------------------------------------------- Stimme
if os.environ.get("FAKE_TTS"):
    SR = 22050
    def tts(t):
        n = int(len(t) * 0.065 * SR); x = np.arange(n) / SR
        return (0.3 * np.sin(2 * np.pi * 140 * x) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * x)) ** 2).astype(np.float32)
else:
    from piper import PiperVoice, SynthesisConfig
    V = PiperVoice.load(VOICE); SR = V.config.sample_rate
    CFG = SynthesisConfig(length_scale=LENGTH, noise_scale=0.6, noise_w_scale=0.75)
    def tts(t):
        a = np.concatenate([c.audio_int16_array.astype(np.float32) / 32768 for c in V.synthesize(t, syn_config=CFG)])
        i = np.where(np.abs(a) > 0.008)[0]
        return a[max(i[0] - 200, 0): i[-1] + 400] if len(i) else a

def sprech(t):  # Aussprache-Hilfen für die Stimme
    t = re.sub(r"\bz\.\s?B\.", "zum Beispiel", t); t = re.sub(r"\bd\.\s?h\.", "das heißt", t)
    t = re.sub(r"\bbzw\.", "beziehungsweise", t); t = re.sub(r"\bu\.\s?a\.", "unter anderem", t)
    t = re.sub(r"\bggf\.", "gegebenenfalls", t); t = re.sub(r"\bvgl\.", "vergleiche", t)
    t = t.replace("§", "Paragraf ").replace("€", " Euro").replace("%", " Prozent").replace("&", " und ")
    return t

# ---------------------------------------------------------------- Professor Kai (eigene Figur)
SS = 3
def kai(mouth=0, blink=False, point=False):
    w, h = 300, 470
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    S = lambda *v: [x * SS for x in v]
    SKIN, SKIN2, HAIR = (141, 94, 66), (120, 78, 54), (28, 24, 26)
    SWEAT, SWEAT2, SHIRT = (34, 150, 160), (26, 120, 130), (245, 245, 240)
    d.rounded_rectangle(S(55, 300, 245, 470), 60 * SS, fill=SWEAT)                    # Körper
    d.polygon(S(120, 300, 150, 345, 180, 300), fill=SHIRT)                             # Kragen
    d.rectangle(S(135, 268, 165, 305), fill=SKIN2)                                     # Hals
    if point:   # Arm zeigt nach links auf die Folie
        d.line(S(80, 340, 40, 290, 26, 240), fill=SWEAT2, width=30 * SS, joint="curve")
        d.ellipse(S(8, 206, 44, 242), fill=SKIN)
        d.line(S(220, 340, 240, 420), fill=SWEAT2, width=34 * SS); d.ellipse(S(226, 410, 256, 440), fill=SKIN)
    else:
        d.line(S(80, 340, 60, 420), fill=SWEAT2, width=34 * SS); d.line(S(220, 340, 240, 420), fill=SWEAT2, width=34 * SS)
        d.ellipse(S(44, 410, 74, 440), fill=SKIN); d.ellipse(S(226, 410, 256, 440), fill=SKIN)
    d.ellipse(S(52, 160, 82, 205), fill=SKIN); d.ellipse(S(218, 160, 248, 205), fill=SKIN)  # Ohren
    d.ellipse(S(70, 70, 230, 285), fill=SKIN)                                           # Kopf
    d.chord(S(66, 58, 234, 200), 180, 360, fill=HAIR); d.ellipse(S(80, 52, 220, 110), fill=HAIR)
    for ex in (118, 182):                                                               # Augen + Brille
        if blink: d.line(S(ex - 11, 175, ex + 11, 175), fill=HAIR, width=4 * SS)
        else:
            d.ellipse(S(ex - 11, 164, ex + 11, 186), fill=(255, 255, 255)); d.ellipse(S(ex - 6, 168, ex + 6, 182), fill=HAIR)
            d.ellipse(S(ex - 2, 170, ex + 2, 174), fill=(255, 255, 255))
        d.ellipse(S(ex - 25, 152, ex + 25, 198), outline=(40, 40, 46), width=5 * SS)
        d.line(S(ex - 13, 140, ex + 13, 136), fill=HAIR, width=5 * SS)                  # Augenbrauen
    d.line(S(143, 172, 157, 172), fill=(40, 40, 46), width=5 * SS)
    d.line(S(150, 192, 145, 218, 154, 220), fill=SKIN2, width=4 * SS)                   # Nase
    if mouth == 0: d.arc(S(128, 222, 172, 252), 15, 165, fill=(90, 30, 30), width=5 * SS)
    elif mouth == 1: d.ellipse(S(134, 232, 166, 252), fill=(90, 30, 30))
    else:
        d.ellipse(S(130, 228, 170, 262), fill=(90, 30, 30)); d.ellipse(S(140, 246, 160, 260), fill=(210, 110, 110))
    im = im.resize((w, h), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255
    return a[..., :3] * 255, a[..., 3:4]
SPR = {(m, b, p): kai(m, b, p) for m in range(3) for b in (0, 1) for p in (0, 1)}
KX, KY = 950, H - 470 - 52

# ---------------------------------------------------------------- Folien
def wrap(text, font, maxw, draw):
    out = []
    for para in str(text).split("\n"):
        line = ""
        for w in para.split():
            t = (line + " " + w).strip()
            if draw.textlength(t, font=font) <= maxw: line = t
            else:
                if line: out.append(line)
                line = w
        out.append(line)
    return out

def folie(k, sz, satz, n_sz, i_sz):
    col, lab = TYP.get(sz.get("typ"), TYP["erklaerung"])
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 44], fill=(33, 37, 48))
    d.text((24, 22), f"{FACH.replace('_', ' ')}  ·  Kapitel {k['nr']}: {k['titel']}"[:95], font=F(17), fill=(220, 222, 230), anchor="lm")
    d.text((W - 24, 22), f"{i_sz + 1}/{n_sz}", font=F(17), fill=(160, 164, 176), anchor="rm")
    d.rectangle([0, 44, int(W * (i_sz + 1) / n_sz), 50], fill=col)
    bw = d.textlength(lab, font=F(16, "Bold")) + 28
    d.rounded_rectangle([40, 72, 40 + bw, 102], 15, fill=col); d.text((54, 87), lab, font=F(16, "Bold"), fill="white", anchor="lm")
    y = 118
    for ln in wrap(sz.get("folie_titel", ""), F(34, "Bold"), 860, d)[:2]:
        d.text((40, y), ln, font=F(34, "Bold"), fill=INK); y += 44
    y += 14
    code = (sz.get("code") or "").strip("\n")
    if code:
        lines = code.split("\n")[:16]; fs = 19 if len(lines) <= 12 else 16
        hgt = len(lines) * (fs + 7) + 28
        d.rounded_rectangle([40, y, 900, y + hgt], 12, fill=(30, 33, 44))
        for j, ln in enumerate(lines): d.text((60, y + 14 + j * (fs + 7)), ln[:70], font=F(fs, "Mono"), fill=(220, 230, 200))
        y += hgt + 16
    pts = sz.get("folie_punkte") or []
    fs = 25 if len(pts) <= 4 and not code else 21
    for p in pts[:7]:
        lines = wrap(p, F(fs), 820, d)
        if y + len(lines) * (fs + 9) > H - 120: break
        d.ellipse([46, y + fs // 2 - 5, 58, y + fs // 2 + 7], fill=col)
        for ln in lines: d.text((72, y), ln, font=F(fs), fill=INK); y += fs + 9
        y += 10
    if satz:  # Untertitel des gerade gesprochenen Satzes
        lines = wrap(satz, F(21), 860, d)[:3]; bh = len(lines) * 28 + 18
        d.rounded_rectangle([30, H - 22 - bh, 910, H - 22], 12, fill=(255, 255, 255), outline=(220, 220, 214))
        for j, ln in enumerate(lines): d.text((470, H - 22 - bh + 9 + j * 28), ln, font=F(21), fill=(55, 58, 70), anchor="ma")
    return np.asarray(im).astype(np.float32)

def pause_overlay(base, rest, total):
    im = Image.fromarray(base.astype(np.uint8)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([210, 250, 750, 470], 22, fill=(236, 120, 20))
    d.text((480, 300), "Jetzt du: Video pausieren & lösen!", font=F(26, "Bold"), fill="white", anchor="mm")
    d.text((480, 385), f"{int(math.ceil(rest))} s", font=F(60, "Bold"), fill="white", anchor="mm")
    d.rounded_rectangle([250, 440, 710, 452], 6, fill=(255, 200, 160))
    d.rounded_rectangle([250, 440, 250 + int(460 * (1 - rest / total)), 452], 6, fill="white")
    return np.asarray(im).astype(np.float32)

# ---------------------------------------------------------------- ein Kapitel bauen
def slug(s):
    s = unicodedata.normalize("NFKD", s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue"))
    return re.sub(r"[^A-Za-z0-9]+", "_", s.encode("ascii", "ignore").decode()).strip("_")[:60]

def build(path):
    k = json.load(open(path)); n = len(k["szenen"])
    name = f"Kapitel_{k['nr']:02d}_{slug(k['titel'])}"
    print("Baue", name, flush=True)
    audio, segs, t = [np.zeros(int(0.6 * SR), np.float32)], [], 0.6
    for i, sz in enumerate(k["szenen"]):
        saetze = [s for s in (sz.get("sprechtext") or []) if s.strip()]
        for j, s in enumerate(saetze):
            a = tts(sprech(s)); d = len(a) / SR
            segs.append(dict(a=t, b=t + d, sz=i, satz=s, talk=True, point=(j % 3 == 1)))
            gap = 0.45 if s.rstrip()[-1:] in ".!?:" else 0.25
            audio += [a, np.zeros(int(gap * SR), np.float32)]; t += d + gap
        if sz.get("typ") == "aufgabe" and sz.get("bedenkzeit_sek"):
            p = float(min(max(sz["bedenkzeit_sek"], 15), 120))
            segs.append(dict(a=t, b=t + p, sz=i, satz="", talk=False, pause=p))
            audio.append(np.zeros(int(p * SR), np.float32)); t += p
        audio.append(np.zeros(int(0.9 * SR), np.float32)); t += 0.9   # Atempause zwischen Szenen
    audio.append(np.zeros(int(1.5 * SR), np.float32)); t += 1.5
    wav = np.concatenate(audio)
    import soundfile as sf; sf.write("_voice.wav", wav, SR)
    hop = SR // FPS; nfr = int(t * FPS)
    rms = np.array([np.sqrt(np.mean(wav[f * hop:(f + 1) * hop] ** 2) + 1e-9) for f in range(nfr)])
    ref = np.percentile(rms[rms > 0.005], 80) if (rms > 0.005).any() else 1
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", "_voice.wav", "-af", "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:makeup=2,loudnorm=I=-16:TP=-1.5",
                           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "24", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", os.path.join(OUT, name + ".mp4")], stdin=subprocess.PIPE)
    cache, si = {}, 0
    for f in range(nfr):
        ts = f / FPS
        while si < len(segs) - 1 and ts >= segs[si]["b"]: si += 1
        sg = segs[si] if segs else dict(sz=0, satz="", talk=False)
        key = (sg["sz"], sg["satz"])
        if key not in cache:
            cache.clear(); cache[key] = folie(k, k["szenen"][sg["sz"]], sg["satz"], n, sg["sz"])
        fr = cache[key]
        if sg.get("pause") and ts >= sg["a"]: fr = pause_overlay(fr, min(max(sg["b"] - ts, 0), sg["pause"]), sg["pause"])
        else: fr = fr.copy()
        lv = rms[f] / ref if sg.get("talk") else 0; m = 0 if lv < 0.25 else (1 if lv < 0.7 else 2)
        blink = (f % (FPS * 4)) in (0, 1)
        rgb, al = SPR[(m, int(blink), int(bool(sg.get("point")) and sg.get("talk", False)))]
        y0 = KY + int(3 * math.sin(ts * 1.7)); h, w = al.shape[:2]
        fr[y0:y0 + h, KX:KX + w] = fr[y0:y0 + h, KX:KX + w] * (1 - al) + rgb * al
        ff.stdin.write(fr.astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    # Übungsblatt zum Mitschreiben
    md = [f"# {FACH.replace('_', ' ')} – Kapitel {k['nr']}: {k['titel']}\n"]
    for sz in k["szenen"]:
        if sz.get("typ") in ("aufgabe", "loesung", "leitfrage"):
            md.append(f"## {TYP[sz['typ']][1].title()}: {sz.get('folie_titel', '')}\n")
            md += [f"- {p}" for p in sz.get("folie_punkte", [])]
            if sz.get("code"): md.append("```\n" + sz["code"] + "\n```")
            md.append("\n" + " ".join(sz.get("sprechtext", [])) + "\n")
    open(os.path.join(OUT, name + "_Aufgaben.md"), "w").write("\n".join(md))
    print(f"  fertig: {t / 60:.1f} min", flush=True)

wanted = {int(x) for x in re.findall(r"\d+", WANT)} if WANT.strip() else None
done_f = os.path.join("skripte", FACH, "fertig.txt")
done = set(open(done_f).read().split()) if os.path.exists(done_f) else set()
for p in sorted(glob.glob(os.path.join("skripte", FACH, "kapitel_*.json"))):
    nr = int(re.findall(r"\d+", os.path.basename(p))[0])
    if wanted is not None and nr not in wanted: continue
    if wanted is None and os.path.basename(p) in done: continue   # schon als Video vorhanden
    build(p); done.add(os.path.basename(p))
    open(done_f, "w").write("\n".join(sorted(done)) + "\n")
