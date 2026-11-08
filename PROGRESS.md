# Fortschritt

## Stand: 8. November 2026

**Phase:** Meilenstein 2 fertig (Rohschnitt). Wartet auf Carinas Test und ihr OK für Meilenstein 3.

### Erledigt
- [x] Recherche → `RESEARCH.md`
- [x] Bauplan mit 7 Meilensteinen → `BAUPLAN.md` (Carina hat ihn am 8.11. freigegeben)
- [x] Eigenes Repo `carinado93/editor`
- [x] **Meilenstein 1**
  - `start.bat` (installiert beim ersten Start uv, Python 3.12, ffmpeg und, bei Nvidia-Karte, die CUDA-Bibliotheken)
  - Upload per Drag&Drop in 8-MB-Stücken (mehrere GB, mehrere Dateien nacheinander), Projektliste, Modus-Wahl
  - Vorschau-Video 540p (NVENC, wenn verfügbar) und Transkript laufen **gleichzeitig**
  - Transkript: faster-whisper mit Wort-Zeitstempeln, Sprache automatisch, GPU → `large-v3-turbo`, sonst `small`,
    automatischer Wechsel auf den Prozessor, falls die Grafikkarte nicht klappt
  - Lange Videos (z. B. 20 Min) in ~10-Min-Stücken, geschnitten an leisen Stellen; jedes Stück wird gespeichert,
    nach Abbruch geht es dort weiter
  - Review-Ansicht: Player + Transkript, Klick auf Wort springt hin, aktuelles Wort wird hervorgehoben,
    unsichere Wörter gepunktet
  - Deutsche Fehlermeldungen, README in einfachem Deutsch, 3 automatische Tests (`uv run --group dev pytest`)
  - Test mit Carinas Video (DJI, 2:44, 1512×2688, HEVC 60 fps, 1,1 GB): Upload → fertig in ca. 3 Min auf einem
    4-Kern-Prozessor ohne Grafikkarte. Transkript Englisch, 294 Wörter, alle Retakes sind im Text erhalten.

- [x] **Meilenstein 2** (YouTube-Rohschnitt)
  - `cuts.py`: Retakes (Neuanfang mit denselben Wörtern, letzte Version bleibt, mehrere Anläufe → nur der letzte),
    Signalwörter (nur wenn allein gesprochen), doppelte/abgebrochene Wörter, Füllwörter (Schalter pro Wort),
    Pausen kürzen (locker 0,75→0,5 s / normal 0,45→0,3 s / straff 0,3→0,18 s)
  - Carinas Regeln (8.11.): max. **5 s Sprechen** zwischen erstem Versuch und Neuanfang (Denkpausen zählen nicht),
    wiederholte ganze Sätze werden immer geschnitten (sie wiederholt Sätze nie absichtlich).
    Zwei gleiche Wörter zählen nur am Satz-/Teilsatzanfang (sonst Fehltreffer wie „in the … in the“).
  - `cutstore.py`: schnitte.json pro Projekt, nicht-destruktiv, Rückgängig (50 Schritte), Einstellungen neu berechnen
    behält manuelle Änderungen
  - Review-UI: farbig durchgestrichen nach Grund, Vorschläge gestrichelt, Pausen-Kästchen, Auswahl + Löschen/Zurücknehmen,
    Entf / Strg+Z / Leertaste, Tempo-Knöpfe, Vorschau überspringt Schnitte live, Zeitleiste
  - `render.py`: Schnittkanten auf ganze Bilder gerundet (Bild/Ton bleiben synchron), Ton per numpy mit 10-ms-Blenden
    (keine Knackser), Video per ffmpeg `select`, H.264 CRF 18 (NVENC cq 19), AAC 192k, 1080p/4K/Original
  - Test mit Carinas Video: 2:44 → 1:09, alle Retakes raus, Bild und Ton exakt gleich lang (69,903 s),
    keine Knackser an 17 Schnittkanten, erneute Transkription des Ergebnisses: kein angeschnittenes Wort
  - 17 automatische Tests

### Wartet auf Carina
- [ ] `start.bat` auf dem eigenen PC ausprobieren (erster Versuch scheiterte an cuBLAS ohne Windows-Version → behoben)
  und sagen, ob oben rechts „Spracherkennung: Grafikkarte“ steht
- [ ] Schnitte an einem eigenen Video prüfen, OK für Meilenstein 3
- [ ] Ein deutsches Testvideo (für Füllwörter wie „äh/ähm“) und eines mit Blick ins Script

### Nächster Schritt: Meilenstein 3
Blick-Erkennung (MediaPipe), Zoom-Wechsel bei Jump Cuts, Lautheit −14 LUFS + Kompression, Untertitel (SRT, eingebrannt),
**Buzzword-Highlights und Text-Animationen auch im YouTube-Modus** (Carinas Wunsch vom 8.11.).

### Entscheidungen
- 8.11.: **So wenig bezahlen wie möglich.** Keine kostenpflichtigen Dienste einbauen.
- 8.11.: **Ollama ist installiert (Modell `gemma3:12b`).** Ollama automatisch für einfache Texte (Kapitel, Tags,
  Beschreibung, Caption-Entwurf, Retake-Zweitmeinung); für Hooks und Reel-Skripte zusätzlich „in claude.ai
  verbessern“ (Kopieren & Einfügen, eigenes Abo). Claude API nur optional.
- 8.11.: Canva und CapCut sind vorhanden. Die App braucht sie nicht, liefert aber MP4 + SRT für CapCut und ein
  Cover ohne Text für Canva.
- 8.11.: Google Fonts sind ok.
- 8.11.: PC: Nvidia GeForce RTX 5070 Laptop (dazu AMD Radeon 610M). Manche Videos sind ~20 Min lang.
- Whisper-Einstellung: `condition_on_previous_text=True` (richtige Satzzeichen) + `hallucination_silence_threshold=2`.
  Getestet: Wiederholungen bleiben trotzdem im Transkript.

### Notizen für die nächste Sitzung
- Testvideo „DJI_20261106152128_0126_D.MP4“ liegt in Carinas Google-Drive-Ordner. Es eignet sich sehr gut für M2:
  „I decided to make a, I decided to make a …“, viermal „so make sure to“, „So here it is. So here it is.“,
  „then then“, „uh“.
- Retake-Logik aus `carinado93/app: tools/audio/clean_recordings.py` (Signalwörter + Satzanfang-Vergleich) wiederverwenden.
- RTX 5070 ist eine Blackwell-Karte: Falls CTranslate2 sie nicht unterstützt, fällt die App auf den Prozessor zurück.
  Dann prüfen, ob eine neuere CTranslate2-Version hilft.
- Cover-Rotation: zuletzt lila → nächstes Cover **hell**, dann oliv.
- Arbeitsumgebung „Carina Video-Editor“ erlaubt Google Drive und Hugging Face (für Testvideos und Modelle).
