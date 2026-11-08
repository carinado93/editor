# Bauplan: "Cary Cut" – automatischer Video-Editor

(Arbeitstitel, Name können wir ändern.)

## Wie die App aufgebaut ist (einfach erklärt)

```
Browser (dein Chrome/Edge)            Dein PC im Hintergrund
┌─────────────────────────┐          ┌──────────────────────────────┐
│ Oberfläche (React)      │  ⇄  ⇄    │ "Motor" (Python, FastAPI)    │
│ - Upload, Projektliste  │          │ - ffmpeg: schneiden, Ton     │
│ - Transkript + Player   │          │ - Whisper: Transkript        │
│ - Vorlagen, Freigaben   │          │ - MediaPipe: Blick, Hände    │
└─────────────────────────┘          │ - Remotion: Reel-Animationen │
                                     │ - KI-Texte: Ollama (lokal)   │
                                     │   + claude.ai per Kopieren   │
                                     └──────────────────────────────┘
```

- **Start:** Doppelklick auf `start.bat`. Beim ersten Mal installiert es alles selbst (Python über `uv`, Node.js, ffmpeg), danach öffnet sich der Browser auf `http://localhost:8000`.
- **Originale bleiben unangetastet.** Jedes Projekt hat einen eigenen Ordner: `projekte/<Name>/` mit Kopie-Verweis, Vorschau-Video (klein), Transkript, `schnitte.json` (die Schnittliste) und den fertigen Exporten.
- **Nichts wird gerendert ohne deinen Klick** auf "Final rendern" bzw. ohne Freigabe des Reel-Skripts.
- **Unsichere Schnitte heißen "Vorschlag"** und sind standardmäßig *nicht* aktiv (nur markiert). Sichere Schnitte sind aktiv, aber per Klick rücknehmbar.

**Warum diese Technik?**
- Python, weil Whisper, MediaPipe und DeepFilterNet nur dort richtig gut laufen.
- React im Browser, weil du dann nichts installieren musst außer dem Start-Skript, und es später leicht online geht.
- Remotion für Reels, weil deine Animations-Bausteine Web-Optik sind (Schriften, Schatten, Karten) und es für dich kostenlos ist.
- Schnittliste als JSON, damit alles nicht-destruktiv ist.

## Meilensteine

Nach jedem Meilenstein bekommst du: **Screenshots der App + Vorschau-Bilder/Video aus dem echten Ergebnis**, eine kurze Erklärung und Fragen. Erst nach deinem OK geht es weiter.

### M1 – Grundgerüst, Upload, Transkript (ca. 1 Sitzung)
- Ordnerstruktur, `start.bat`, README in einfachem Deutsch
- Upload per Drag&Drop (auch mehrere GB, in Stücken hochgeladen), Projektliste, Modus-Wahl A / B1 / B2
- Erstellen des Vorschau-Videos (540p, schnell)
- Transkription mit faster-whisper, Wort-Zeitstempel, Sprache automatisch, GPU wenn vorhanden, sonst CPU mit Modellwahl (`small`/`medium`), Fortschrittsbalken, lange Videos in Stücken, Zwischenspeicher
- Einfache Review-Ansicht: Transkript, Klick auf Wort springt im Player dorthin
- **Demo:** Screenshot mit deinem Testvideo und Transkript

### M2 – YouTube-Rohschnitt (Kern) (ca. 1–2 Sitzungen)
- Pausen kürzen (locker 0,7 s / normal 0,45 s / straff 0,25 s Rest-Pause)
- Füllwörter (Schalter pro Wort), Stotterer/Fragmente, Retakes (Signalwörter + Ähnlichkeit, letzte Version bleibt)
- Review: durchgestrichen + Farbe pro Grund (Pause grau, Retake rot, Wiederholung orange, Füllwort gelb, Blick lila), Grund beim Drüberfahren, Klick = zurücknehmen, Wörter markieren = zusätzlich löschen, Rückgängig
- Vorschau-Player spielt die Schnitte live (überspringt Geschnittenes)
- "Final rendern": MP4 1080p/4K, H.264 CRF 18, AAC, kurze Audio-Überblendungen (20 ms) gegen Knackser
- **Demo:** Vorher/Nachher-Länge, Screenshot Review, Frames aus dem fertigen MP4

### M3 – Blick, Zoom, Ton, Untertitel (ca. 1–2 Sitzungen)
- Blick-Erkennung (MediaPipe, Kalibrierung, Schwellwerte einstellbar), Stellen als "Vorschlag": schneiden oder Zoom-Schnitt
- Zoom-Stufen 100/108/115 % abwechselnd bei Jump Cuts (Gesicht bleibt mittig)
- Ton: −14 LUFS (loudnorm, 2 Durchgänge), sanfte Kompression, optional Rauschentfernung
- Untertitel wortgenau, SRT, optional eingebrannt im Reel-Stil, Karaoke-Highlight optional
- **Neu (Wunsch 8.11.): Buzzwords und Animationen auch für YouTube.** Schlüsselwörter/Kernsätze aus dem Transkript
  (Vorschlag per Ollama, von dir bestätigt) werden als animierte Text-Einblendungen in deinem Stil gezeigt
  (Flieder-Highlight, Wort-Pop, Kernsatz-Karte), nie über dem Gesicht. Im Transkript markierst du Wörter als
  „Buzzword“, die Vorschau zeigt sie, gerendert wird erst nach deinem Klick.
- **Demo:** Blick-Markierungen im Transkript, Frames mit Zoom und Untertiteln

### M4 – Exporte & YouTube-Extras (ca. 1 Sitzung)
- Export MP4 + SRT (für CapCut). Keine Schnittlisten für DaVinci & Co. (Carina nutzt nur Programme, die sie hat.)
- Kapitel mit Zeitstempeln, 3 Titel, Beschreibung, Tags (Claude, mit deinen Leitplanken)
- Thumbnail-Vorschläge: Frames mit offenen Augen, Blick in Kamera, Lächeln, scharf
- **Demo:** Export-Ordner, Beispiel-Texte, 6 Thumbnail-Kandidaten

### M4b – Thumbnail- & Cover-Generator (neu, Wunsch 8.11.)
- Bestes Standbild aus dem Video (aus M4: Augen offen, Blick in Kamera, Lächeln, scharf), Carina auf Wunsch
  freigestellt (lokal, kostenlos), dazu Text und Gestaltung im Stil ihrer bisherigen Thumbnails bzw. Reel-Cover
- YouTube-Thumbnail 1280×720 und Reel-Cover 1080×1920 (Cover-Rotation lila → hell → oliv, nächstes: hell)
- Mehrere Varianten zur Auswahl, Text aus dem Titel/Hook, alles editierbar, keine KI-generierten Gesichter
- Stil-Beschreibung aus ihren Beispielen: `docs/THUMBNAIL_STIL.md` (YouTube: „Talking Head“ und „Meditation“,
  Reel-Cover mit Farbschleier lila/hell/oliv)
- **Demo:** 3 Thumbnail- und 3 Cover-Varianten aus ihrem Testvideo

### Querschnitt: Captions & Hashtags für alle Formate (Wunsch 8.11.)
Ein gemeinsamer Text-Baustein für **YouTube, Reels und Karussells** (EN für @carina.dorca, DE für @carinadorca.coach):
- **YouTube** (fertig in M4): Beschreibung + Kapitel + Tags + 3 Hashtags; dazu Shorts-Titel
- **Reel/Short**: Caption in Carinas Stimme (Hook-Zeile, kurze Absätze, Mini-Aufgabe, 📌 Save / 💌 Share,
  „Follow me for …“, Hinweis „not a diagnosis or therapy“), Hashtags, Cover-Text, YouTube-Shorts-Titel
- **Karussell**: gleiche Caption-Struktur wie ihre Beispiele, Hashtags
- Hashtags kommen aus ihrer eigenen Sammlung `vorlagen/hashtags.json` (editierbar) + passend zum Thema
- Leitplanken-Prüfung (keine Heilversprechen) und Zählen der Hashtags automatisch
- Wege: Ollama (automatisch) oder claude.ai-Kopierweg, alles editierbar, Kopier-Knöpfe

### M5 – Reel-Modus B1 "Veredeln" (ca. 2 Sitzungen)
- `style.json` mit deinen Farben, Schriften, Safe Zone, Lesezeit (4,4 s), Cover-Rotation (nächstes: **hell**)
- Video bleibt exakt wie es ist (Länge, Tempo, Format, kein Filter, Ton unangetastet)
- Texte/Highlights/Buzzwords aus dem Transkript, Platzierung nur in der Safe Zone und nie über Gesicht/Händen (Gesichts- und Handerkennung pro Szene)
- Lieferung: Reel (< 30 MB) + Caption + genau 5 Hashtags + Cover + Shorts-Titel
- **Demo:** Vorschau-Standbilder mit Safe-Zone-Rahmen, dann (nach OK) das Reel

### M6 – Vorlagen-Bibliothek + B2 "Reel aus Idee" (ca. 3–4 Sitzungen)
- Die 12 Bausteine als Remotion-Vorlagen mit Namen, Vorschau-GIF, Parametern; Auswahl per Dropdown oder Prompt
- Reihenfolge: zuerst die einfachsten und meistgenutzten (1 Durchstreich-Reveal, 2 Statements, 3 Wort-Jump-In, 8 The secret, 5 Slam), dann die mit Tracking (7 Hand, 6 annotiert, 4 Freisteller)
- Prompt → Claude → Szenen-JSON (mit Leitplanken) → **deine Freigabe** → Vorschau-Standbilder → Render, EN + DE aus einer Vorlage
- Inspirations-Reel → eigene Version in deinen Worten (nie 1:1)
- **Demo:** pro Vorlage ein Beispiel-GIF, ein komplettes Reel EN+DE

### M6c – Inspiration → eigene Version (für nächste Woche vorgemerkt, Wunsch 8.11.)
- Carina gibt ein Beispiel: **Screenshots**, eine **Bildschirmaufnahme** des Reels oder den heruntergeladenen Clip
  (falls sie ihn hat) – Screensharing live ist nicht nötig.
- Die App zerlegt das Beispiel: Szenen und Schnitt-Takt (Szenenerkennung), Text-Positionen und -Längen, Art der
  Animation, Farben, Aufbau (Hook → Aussagen → Abschluss). Bilder liest **Gemma 3 über Ollama** (kann Bilder,
  kostenlos) oder Claude über den claude.ai-Weg.
- Daraus wird eine **Vorlage** (Szenen-JSON) aus der Vorlagen-Bibliothek, die mit **Carinas eigenen Videos,
  Worten und Farben** gefüllt wird – nie 1:1 kopiert (Texte, Musik und Bilder anderer bleiben außen vor).
- Vorschau-Standbilder, Freigabe, dann Render – wie bei B2.

### M6b – Karussell-Generator (neu, Wunsch 8.11.)
- Aus einem Prompt (z. B. „Karussell über Coping-Tools vs. Ursachen, EN“) → Folientexte + Caption + 5 Hashtags
  (Vorschlag per Ollama oder claude.ai-Kopierweg, **erst nach Carinas Freigabe** wird gestaltet)
- Folien 1080×1350 exakt im bisherigen Stil (`docs/KARUSSELL_STIL.md`): Creme mit Goldrahmen, Profil-Kopf,
  Cormorant mit Lila-Kursiv-Akzent, „BUT…“-Wendepunkt, Foto-Variante, Fuß mit Website + SWIPE
- Vorschau aller Folien, Texte direkt editierbar, Export als PNGs (+ ZIP) und Caption zum Kopieren, EN + DE
- **Braucht von Carina:** weitere Beispiele (kommen), Profilfoto in hoher Auflösung

### M7 – Politur (ca. 1–2 Sitzungen)
- Verständliche deutsche Fehlermeldungen überall, Fortschritt für jeden Schritt
- Batch: mehrere Videos hintereinander abarbeiten
- Metricool: prüfen, ob Upload per Schnittstelle sinnvoll geht; sonst "Export-Ordner für Metricool"
- **Demo:** Batch mit 3 Videos

## Was ich von dir brauche (bevor ich M1 starte)

1. **Dein PC:** Welche Grafikkarte? (Windows-Taste → "Geräte-Manager" → "Grafikkarten" → Name abschreiben.) Und wie viel Arbeitsspeicher (RAM)?
2. **Testvideos:** ein kurzes Roh-YouTube-Stück (2–5 Min, mit mindestens einem "nochmal" und einem Blick ins Script) und ein fertiges Reel. Am einfachsten per Google-Drive-Link.
3. **Ort für den Code:** erledigt, eigenes Repo `carinado93/editor`.
4. **Schriften:** Ist es ok, die Google-Fonts-Versionen zu nutzen? Oder hast du eigene Schriftdateien?
5. **Später (ab M5):** 2–3 Beispiel-Cover im "Coperti reels"-Stil (lila/hell/oliv), dein Logo, Profilbild, die PDFs (Notizbuch "Not All At Once", Produkte).
6. **KI-Texte ohne Zusatzkosten:** Ollama (schon installiert) erledigt einfache Texte automatisch und gratis. Für Hooks und Reel-Skripte gibt es zusätzlich "Kopieren & Einfügen" in claude.ai (dein Abo, 0 € extra). Claude API nur als optionaler Schalter.
