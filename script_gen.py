"""Erzeugt aus den Kurs-PDFs eines Fachs die Video-Skripte (JSON) mit der kostenlosen Gemini-API.

Aufruf:  python3 script_gen.py "<Fach-Ordner>" [kapitel]
Eingabe: kurse/<Fach>/*.pdf  (+ optional leitfragen.txt / leitfragen.pdf)
Ausgabe: skripte/<Fach>/gliederung.json und skripte/<Fach>/kapitel_XX.json
Bereits vorhandene Skripte werden nicht neu erzeugt (spart Kontingent).
Neue PDFs im Ordner -> Gliederung wird neu erstellt, bestehende Kapitel bleiben erhalten.
"""
import json, os, sys, time, glob, hashlib, re, unicodedata
from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_MODEL", "")
FACH = sys.argv[1]
WANT = sys.argv[2] if len(sys.argv) > 2 else ""
SRC = os.path.join("kurse", FACH)
OUT = os.path.join("skripte", FACH)
os.makedirs(OUT, exist_ok=True)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODELS = []

def pick_model():
    """Neuestes verfügbares Flash-Modell automatisch wählen (Google ändert die Namen regelmäßig)."""
    names = []
    for m in client.models.list():
        acts = getattr(m, "supported_actions", None) or []
        n = m.name.split("/")[-1]
        if "generateContent" in acts and "flash" in n and not any(x in n for x in ("lite", "image", "tts", "audio", "live", "exp", "thinking")):
            names.append(n)
    def ver(n):
        v = re.findall(r"(\d+(?:\.\d+)?)", n); return (float(v[0]) if v else 0, "preview" not in n, "latest" in n)
    names.sort(key=ver, reverse=True)
    print("Verfügbare Flash-Modelle:", names[:6], flush=True)
    MODELS[:] = names[:5] or ["gemini-flash-latest"]
    return MODELS[0]

if not MODEL:
    MODEL = pick_model()
print("Modell:", MODEL, flush=True)

files = sorted(f for f in glob.glob(os.path.join(SRC, "*")) if f.lower().endswith((".pdf", ".txt", ".md")))
if not files:
    sys.exit(f"Keine Kursdateien in {SRC}")
sig = hashlib.sha1("".join(f + str(os.path.getsize(f)) for f in files).encode()).hexdigest()[:12]

ROLLE = (
    "Du bist ein erfahrener, geduldiger Hochschuldozent für Wirtschaftsinformatik an der TH Augsburg. "
    "Du erstellst Skripte für Erklärvideos zur Klausurvorbereitung. Ein gezeichneter Tutor namens 'Professor Kai' spricht den Text. "
    "WICHTIG: Verwende AUSSCHLIESSLICH Inhalte aus den bereitgestellten Kursunterlagen. Erfinde keine Inhalte, die dort nicht vorkommen. "
    "Wenn du zur Veranschaulichung ein eigenes Beispiel oder eine Übungsaufgabe baust, muss sie genau den Stoff der Unterlagen anwenden. "
    "Leitfragen des Professors (ausdrücklich so genannt, oder Lernziele/Kontrollfragen/Wiederholungsfragen) haben höchste Priorität: "
    "Jede Leitfrage muss im Video explizit gestellt und vollständig beantwortet werden."
)

def call(contents, tries=12):
    global MODEL
    quota = set()  # Modelle, deren Tageskontingent aufgebraucht ist
    for i in range(tries):
        try:
            r = client.models.generate_content(
                model=MODEL, contents=contents,
                config=types.GenerateContentConfig(system_instruction=ROLLE, temperature=0.4,
                                                   response_mime_type="application/json"))
            return json.loads(r.text)
        except Exception as e:  # Kontingent (429) oder ungültiges JSON -> warten und erneut
            if "NOT_FOUND" in str(e) or "no longer available" in str(e):
                MODEL = "gemini-flash-latest" if MODEL != "gemini-flash-latest" else pick_model()
                print("  Modell nicht verfügbar -> wechsle zu", MODEL, flush=True); continue
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                quota.add(MODEL)
                if MODELS and quota >= set(MODELS):
                    open("/tmp/quota_exhausted", "w").write("1")
                    sys.exit("Tageskontingent von Gemini aufgebraucht – morgen geht es automatisch weiter.")
            if MODELS and ("503" in str(e) or "UNAVAILABLE" in str(e) or "overloaded" in str(e) or "429" in str(e) or "Disconnected" in str(e) or "disconnected" in str(e)):
                MODEL = MODELS[(MODELS.index(MODEL) + 1) % len(MODELS)] if MODEL in MODELS else MODELS[0]
                print("  -> anderes Modell:", MODEL, flush=True)
            wait = min(20 * (i + 1), 120)
            print(f"  Fehler ({e.__class__.__name__}: {str(e)[:160]}) -> neuer Versuch in {wait}s", flush=True)
            time.sleep(wait)
    sys.exit("Gemini antwortet nicht – später erneut starten.")

def upload():
    up = []  # abwechselnd Dateiname (Text) und Datei, damit Gemini Quellen benennen kann
    for f in files:
        print("Lade Kursdatei hoch …", flush=True)
        mime = "application/pdf" if f.lower().endswith(".pdf") else "text/plain"
        safe = unicodedata.normalize("NFKD", os.path.basename(f)).encode("ascii", "ignore").decode() or "kurs.pdf"
        with open(f, "rb") as fh:  # Dateiobjekt: Umlaute im Dateinamen würden den HTTP-Header sprengen
            u = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type=mime, display_name=safe))
        while u.state and u.state.name == "PROCESSING":
            time.sleep(3); u = client.files.get(name=u.name)
        up += [f"Datei: {os.path.basename(f)}", u]
    return up

def subset(up, names):
    if not names: return up
    out = []
    for i in range(0, len(up), 2):
        if up[i][len("Datei: "):] in names: out += up[i:i+2]
    return out or up

gl_path = os.path.join(OUT, "gliederung.json")
gl = json.load(open(gl_path)) if os.path.exists(gl_path) else None
uploaded = None

if not gl or gl.get("quellen_sig") != sig:
    uploaded = upload()
    alt = ""
    if gl:
        alt = ("Es gibt bereits diese Kapitel (Nummer und Titel unverändert übernehmen, nur neue Kapitel für neuen Stoff hinten anfügen):\n"
               + json.dumps([{"nr": k["nr"], "titel": k["titel"]} for k in gl["kapitel"]], ensure_ascii=False))
    print("Erstelle Gliederung …", flush=True)
    new = call(uploaded + [f"""Analysiere die Kursunterlagen des Fachs „{FACH}“ vollständig.
Teile den GESAMTEN klausurrelevanten Stoff in Video-Kapitel. Halte dich an den Aufbau der Vorlesung: gleiche Reihenfolge und, wenn vorhanden, die Kapitelnummern und -namen der Folien (z. B. „Kapitel 2 – Vorgehensmodelle“). Sehr lange Vorlesungskapitel darfst du in Teil 1/Teil 2 aufteilen.
Erfasse alle Leitfragen/Lernziele des Professors und ordne jede genau einem Kapitel zu.
{alt}
Antworte als JSON:
{{"fach": "...", "kapitel": [{{"nr": 1, "titel": "...", "themen": ["..."], "leitfragen": ["..."],
"quellen": ["exakte Dateinamen, in denen der Stoff steht"], "klausurrelevanz": "hoch|mittel|niedrig", "umfang": "kurz|mittel|lang"}}]}}"""])
    if gl:  # alte Kapitel behalten
        old = {k["nr"]: k for k in gl["kapitel"]}
        new["kapitel"] = [old.get(k["nr"], k) for k in new["kapitel"]]
    new["quellen_sig"] = sig
    gl = new
    json.dump(gl, open(gl_path, "w"), ensure_ascii=False, indent=2)

wanted = {int(x) for x in re.findall(r"\d+", WANT)} if WANT.strip() else None
DAUER = {"kurz": "6–9", "mittel": "10–15", "lang": "16–25"}

for k in gl["kapitel"]:
    if wanted and k["nr"] not in wanted:
        continue
    path = os.path.join(OUT, f"kapitel_{k['nr']:02d}.json")
    if os.path.exists(path):
        print("Vorhanden, übersprungen:", path); continue
    if uploaded is None:
        uploaded = upload()
    print(f"Skript Kapitel {k['nr']}: {k['titel']}", flush=True)
    s = call(subset(uploaded, k.get("quellen")) + [f"""Schreibe das vollständige Video-Skript für Kapitel {k['nr']} „{k['titel']}“ des Fachs „{FACH}“.
Themen: {json.dumps(k.get('themen', []), ensure_ascii=False)}
Leitfragen dieses Kapitels: {json.dumps(k.get('leitfragen', []), ensure_ascii=False)}

Anforderungen:
- Sprache: Deutsch, gesprochene Sprache, klar und ruhig, kurze Sätze (max. ~20 Wörter), duzen.
- Länge richtet sich nach dem Stoff: ungefähr {DAUER.get(k.get('umfang'), '10–15')} Minuten (≈ 130 gesprochene Wörter pro Minute). Lieber gründlich als oberflächlich.
- Aufbau: Einstieg (worum geht es, warum klausurrelevant) → Erklärungen Schritt für Schritt → zu jedem wichtigen Begriff ein konkretes Beispiel
  → jede Leitfrage explizit stellen und beantworten → nach jedem größeren Abschnitt eine Übungsaufgabe (typ "aufgabe") mit anschließender ausführlicher Lösung (typ "loesung")
  → am Ende Zusammenfassung + 3 typische Klausurfragen mit Kurzantwort.
- Rechenfächer (z. B. Kostenrechnung): Aufgaben mit Zahlen, Lösung Rechenschritt für Rechenschritt.
- Programmierfächer: kurze Code-Beispiele im Feld "code" (max. 14 Zeilen), Code im Sprechtext Zeile für Zeile erklären, aber NICHT Zeichen für Zeichen vorlesen.
- Recht: Prüfungsschema bzw. Gutachtenstil zeigen, Normen nennen, wenn sie in den Unterlagen stehen.
- Fachbegriffe exakt so verwenden wie in den Unterlagen.
- Die Felder merke und rechnung kommen zusätzlich ins schriftliche Begleitheft: Bemerkungen und Hinweise des Professors aus den Folien unbedingt als merke übernehmen; jede Rechnung (Beispiel und Lösung) vollständig als rechnung.
- Im Sprechtext keine Aufzählungszeichen, keine Abkürzungen wie „z. B.“ (ausschreiben: „zum Beispiel“), Zahlen so schreiben, wie man sie spricht, wenn sie mehrdeutig sind.
- Bei typ "aufgabe": letzter Satz fordert auf, das Video zu pausieren; setze "bedenkzeit_sek" (20 bis 90) passend zur Schwierigkeit.

Antworte als JSON:
{{"titel": "...", "szenen": [{{"typ": "einstieg|erklaerung|beispiel|leitfrage|aufgabe|loesung|zusammenfassung",
"folie_titel": "...", "folie_punkte": ["max. 6 kurze Stichpunkte"], "code": "", "bedenkzeit_sek": 0,
"merke": ["wichtige Bemerkung/Merksatz/typischer Klausurfehler, nur wenn es einen gibt"],
"rechnung": ["Rechenweg Schritt für Schritt mit Formel und Zahlen, nur bei Rechnungen"],
"sprechtext": ["Satz 1.", "Satz 2."]}}]}}"""])
    s["fach"], s["nr"] = FACH, k["nr"]
    json.dump(s, open(path, "w"), ensure_ascii=False, indent=2)
    time.sleep(8)  # freundlich zum kostenlosen Kontingent
print("Skripte fertig.")
