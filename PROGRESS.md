# Fortschritt

## Stand: 8. November 2026

**Phase:** Meilenstein 1 fertig, wartet auf Carinas Test auf dem eigenen PC und ihr OK für Meilenstein 2.

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

### Wartet auf Carina
- [ ] `start.bat` auf dem eigenen PC ausprobieren und sagen, ob oben rechts „Spracherkennung: Grafikkarte“ steht
- [ ] OK für Meilenstein 2
- [ ] Später: ein deutsches Testvideo (für Füllwörter wie „äh/ähm“) und eines mit langen Pausen/Blick ins Script

### Nächster Schritt: Meilenstein 2 (YouTube-Rohschnitt)
Pausen, Füllwörter, Wortwiederholungen, „again/nochmal“-Retakes, durchgestrichene Wörter in der Review-Ansicht,
Vorschau spielt die Schnitte live, „Final rendern“.

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
