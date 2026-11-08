# Carinas Video-Editor

Eine App, die deine Videos automatisch vorbereitet und schneidet. Sie läuft **auf deinem PC im Browser**.
Deine Videos werden nirgendwo hochgeladen: Sie bleiben auf deinem PC.

## Starten (Windows)

1. Lade den Ordner herunter: auf GitHub oben rechts **Code → Download ZIP**, dann entpacken
   (z. B. nach `Dokumente\Video-Editor`).
2. **Doppelklick auf `start.bat`.**
   - Beim **ersten Mal** lädt die App alles, was sie braucht (Python, ffmpeg, Spracherkennung).
     Das dauert je nach Internet **5–15 Minuten**. Danach geht der Start in wenigen Sekunden.
   - Falls Windows fragt „Der Computer wurde durch Windows geschützt“: auf **Weitere Informationen → Trotzdem ausführen** klicken.
3. Der Browser öffnet sich mit der App (Adresse: `http://127.0.0.1:8000`).
4. Das **schwarze Fenster offen lassen**, solange du arbeitest. Zum Beenden das Fenster schließen.

## So benutzt du die App

1. Oben den **Modus** wählen: *YouTube* (langes Rohvideo) oder *Reel veredeln*.
2. Video in das Feld **ziehen** (oder klicken und auswählen). Mehrere Videos auf einmal gehen auch,
   sie werden nacheinander verarbeitet.
3. Die App erstellt ein **Vorschau-Video** und das **Transkript** (jedes Wort mit genauer Zeit).
   Den Fortschritt siehst du in der Projektliste.
4. Auf das Projekt klicken: links das Video, rechts das Transkript.
   **Klick auf ein Wort** springt im Video genau dorthin.

**Dein Original wird nie verändert.** Die App arbeitet mit einer Kopie im Ordner `projekte`.

## Wie lange dauert das?

| | mit Nvidia-Grafikkarte | nur Prozessor |
|---|---|---|
| Transkript für 20 Minuten Video | ca. 1–3 Minuten | ca. 5–15 Minuten |
| Vorschau-Video für 20 Minuten | ca. 2–4 Minuten | ca. 10–25 Minuten |

Vorschau-Video und Transkript laufen gleichzeitig. Oben rechts in der App steht, ob die Grafikkarte benutzt wird.
Bricht etwas ab (z. B. PC aus), macht die App beim nächsten Start dort weiter, wo sie war.

## Wenn etwas nicht klappt

- **Die App zeigt eine Fehlermeldung:** Sie sagt auf Deutsch, was los ist. Oft hilft „nochmal versuchen“.
- **Der Browser zeigt „Seite nicht erreichbar“:** Ist das schwarze Fenster noch offen? Sonst `start.bat` nochmal starten.
- **Festplatte voll:** Alte Projekte in der App löschen (dein Original bleibt erhalten).
- Sonst: Foto vom schwarzen Fenster und von der Meldung an Claude schicken.

## Wo liegt was?

| Ordner/Datei | Inhalt |
|---|---|
| `start.bat` | Startet die App |
| `projekte/` | Deine Projekte (Kopie des Videos, Vorschau, Transkript). Nur auf deinem PC. |
| `modelle/` | Die Spracherkennung (wird beim ersten Mal geladen, ca. 0,5–1,6 GB) |
| `tools/ffmpeg/` | Das Schnitt-Programm ffmpeg |
| `RESEARCH.md`, `BAUPLAN.md`, `PROGRESS.md` | Recherche, Plan und aktueller Stand |

---

## Für Entwickler

- Motor: Python 3.12, FastAPI, faster-whisper, ffmpeg (`backend/editor_app/`). Start: `uv run backend/app.py`
- Oberfläche: React + Vite + TypeScript (`frontend/`). Die gebaute Version liegt in `frontend/dist/`,
  damit Carina kein Node.js braucht. Nach Änderungen: `cd frontend && npm install && npm run build`.
  Entwickeln mit Live-Neuladen: `npm run dev` (leitet `/api` an Port 8000 weiter).
- Tests: `uv run --group dev pytest`
- Grafikkarte: `uv sync --extra gpu` installiert die CUDA-Bibliotheken (cuBLAS, cuDNN 9). Klappt die Karte nicht,
  rechnet die App automatisch mit dem Prozessor weiter.
