# Fortschritt

## Stand: 8. November 2026

**Phase:** Meilenstein 3 fertig (Blick, Zoom, Ton, Untertitel, Buzzwords). Wartet auf Carinas Test und OK für Meilenstein 4.

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

- [x] Carina hat getestet (8.11.): Grafikkarte wird genutzt, Schnitte passen bei eigenem Video.
- [x] **Meilenstein 3**
  - `gaze.py`: MediaPipe Face Landmarker (Blendshapes + Kopfhaltung), 5 Bilder/s auf dem Vorschau-Video,
    Kalibrierung per Median, Ereignisse ≥ 1,5 s → Erkennung „blick“ (immer nur Vorschlag). Speichert auch
    Gesichtsposition (Zoom-Ausschnitt, Text-Platzierung) und Lächeln/Augen zu (für Thumbnails in M4).
    Test: 2:44-Video in 16 s analysiert, 4 Stellen gefunden (3 klar richtig, 1 grenzwertig).
    Ältere Projekte bekommen die Analyse beim App-Start nachträglich.
  - Render: Zoom-Wechsel per `zoompan` (pro Abschnitt 100/108/115 %, Gesicht als Mittelpunkt), Ton: Kompressor +
    `loudnorm` 2-Pass auf −14 LUFS (gemessen: −14,0 LUFS, −1,3 dBTP), optional `afftdn`
  - `subtitles.py`: SRT (immer bei „srt“/„einbrennen“), eingebrannt per ASS/libass mit Poppins SemiBold auf Creme-Box,
    Karaoke optional; Buzzwords als Pop-Animation (Cormorant Garamond Bold, tiefes Lila auf Flieder),
    Hochformat: Untertitel 70 % Höhe, Buzzwords unter dem Gesicht; Querformat: Buzzwords neben dem Gesicht
  - `llm.py`: Ollama (gemma3:12b) schlägt Buzzwords vor (ca. eins pro 15 s), verständliche Meldung, wenn Ollama nicht läuft
  - Schriften in `assets/fonts` (OFL-Lizenzen liegen bei)
  - UI: Buzzword-Knopf, lila Blick-Vorschläge, Render-Optionen, Text-Vorschau direkt über dem Video
  - 20 automatische Tests

### Wartet auf Carina
- [ ] Neue Version holen (Git: Pull), ein Video mit Buzzwords + eingebrannten Untertiteln rendern und sagen, ob Stil,
  Größe und Position passen
- [ ] OK für Meilenstein 4
- [ ] Ein deutsches Testvideo (für Füllwörter wie „äh/ähm“) und eines mit Blick ins Script

- [x] 8.11.: Carina sah keine Buzzwords (sie mussten von Hand gesetzt werden). Jetzt automatisch: nach dem Transkript
  bzw. beim App-Start für bestehende Projekte einmalig Ollama-Vorschlag, sonst eingebaute Regeln (`buzz.py`:
  Themenwörter, Zahlen, starke Wörter, ca. alle 15 s, keine Wiederholung). Von Hand gesetzte werden nie überschrieben.

- [x] 8.11.: Render-Fehler bei Carina „Unrecognized option 'filter_complex_script'“: ihr ffmpeg (Gyan, 7/8) kennt die
  alte Option nicht mehr → App erkennt die Version und nutzt `-/filter_complex datei`. (Konnte ffmpeg 8 hier nicht
  selbst ausführen, Test mit nachgestellten Versionsangaben.)
- [x] 8.11.: Laute ohne Wort („meah“, „mh“, Schmatzer): `noises.py` findet sie am Ton (fast so laut wie Sprache,
  mit Stille davor und danach, damit Wortenden nie abgeschnitten werden) und schneidet sie heraus. Anzeige „🔊 Laut“,
  per Klick behaltbar. Neue Füllwörter: meh, mäh, mh, mmh, ehm, äm, uhm (eh/ah standardmäßig aus).
- [x] 8.11.: „meah“ bei 2:14 kam direkt nach „someone.“ ohne Stille → Regel jetzt: Lautstärke sinkt nach dem Wort
  ≥ 10 dB ab und steigt wieder an = eigener Laut (ein Wortende klingt nur aus). MediaPipe-`tongueOut` ist immer 0
  und Mund-Werte schlagen auch beim Sprechen an → für Grimassen unbrauchbar (Zunge wird nur genutzt, falls je > 0).

### Offen / Ideen
- Blick-Stellen mit Zoom „überdecken“ statt schneiden (aktuell nur Schneiden als Vorschlag)
- Buzzword-Varianten (Durchstreichen, Wort-Slam, Karte) kommen mit der Vorlagen-Bibliothek (M6) auch für YouTube

### Neu geplant
- **Captions & Hashtags für YouTube, Reels und Karussells** (Wunsch 8.11.): gemeinsamer Baustein, Hashtag-Sammlung
  aus ihren Beispielen in `vorlagen/hashtags.json`. Offen: Anzahl Hashtags (Vorgabe „genau 5“ vs. ~20 im
  Karussell-Beispiel als erster Kommentar).
- **M6b Karussell-Generator** (Wunsch 8.11.): Prompt → Folien im bisherigen Stil + Caption. Erste Beispiele erhalten,
  Stil in `docs/KARUSSELL_STIL.md`. Carina schickt weitere Beispiele.
- **M4b Thumbnail- & Cover-Generator** (Wunsch 8.11.): Standbild aus dem Video → Thumbnail/Reel-Cover im Stil ihrer
  bisherigen. Beispiele erhalten (8.11.), Stil festgehalten in `docs/THUMBNAIL_STIL.md`.

- [x] **Meilenstein 4** (YouTube-Paket)
  - `meta.py`: Auftrag mit Leitplanken (Prävention, keine Heilversprechen, Hinweis „keine Diagnose oder Therapie“),
    Zeiten im geschnittenen Video; Ollama oder claude.ai-Kopierweg; Prüfung: 3 Titel, Kapitel ab 0:00 mit ≥ 10 s
    Abstand, Warnung bei Heilversprechen-Wörtern; Beschreibung + Kapitel + Hashtags zum Kopieren
  - `thumbs.py`: 6 Bild-Vorschläge (Augen offen, Blick in Kamera, Lächeln, Gesichtsgröße, Schärfe, ≥ 5 s Abstand,
    nur aus behaltenen Stellen), volle Auflösung aus dem Original
  - UI „YouTube-Paket“ unter der Schnittansicht; 29 automatische Tests
  - Ollama-Weg hier nicht testbar (läuft nur auf Carinas PC); claude.ai-Weg mit einer Test-Antwort geprüft

- [x] 8.11.: **Immer genau 5 Hashtags** (auch YouTube). App lernt neue Hashtags selbst (daten/hashtags_gelernt.json,
  nicht im Git), Grundsammlung `vorlagen/hashtags.json`.
- [x] 8.11.: DaVinci-Export entfernt (keine Programme, die Carina nicht hat).
- [x] **M4b Thumbnail- & Cover-Generator** (`covers.py`, Pillow):
  - YouTube „Aussage“ 1280×720: Creme-Rosa links, fette Versalien (Poppins ExtraBold als Ersatz, bis Carina ihre
    Canva-Schrift nennt), *Schlüsselwort* rosa und größer, weinrote Pille, Carina rechts mit weicher Blende, Aquarell
  - YouTube „Meditation“: Foto mit Creme-Blende links, Serif-Titel, kursiver Untertitel, Pille + Label, Name-Fuß
  - Reel-Cover 1080×1920: Farbschleier lila/hell/oliv, Cormorant zentriert über/unter dem Gesicht, Rotation wird
    gemerkt (daten/einstellungen.json, Start: hell)
  - 3 Varianten aus den 3 besten Standbildern, JPEG < 2 MB; UI „Thumbnail gestalten“ im YouTube-Paket

### Nächster Schritt
M5 Reel-Modus (läuft).

### Entscheidungen
- 8.11.: **Keine Programme, die Carina nicht schon hat** (kein DaVinci). DaVinci-Export (FCPXML/EDL) wieder entfernt.
  Nachbearbeitung nur in CapCut (MP4 + SRT). Vorhanden: CapCut, Canva, Ollama, claude.ai-Abo, Metricool.
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
