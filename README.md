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
3. Die App erstellt ein **Vorschau-Video**, das **Transkript** und (im YouTube-Modus) die **Schnittvorschläge**.
   Den Fortschritt siehst du in der Projektliste.
4. Auf das Projekt klicken: links das Video, rechts das Transkript.

### Schneiden (YouTube-Modus)

Im Transkript ist alles **durchgestrichen**, was geschnitten wird. Die Farbe zeigt den Grund:

| Farbe | Grund |
|---|---|
| rot | **Retake**: Du hast neu angesetzt. Die letzte Version bleibt. Auch bei „again“ / „nochmal“. |
| orange | **doppeltes oder abgebrochenes Wort** („then then“, „Resi- Resilienz“) |
| gelb | **Füllwort** (äh, ähm, uh, um …) |
| grau | **von dir gelöscht** |
| ⏸ 2,4 s | **Pause**, wird auf eine natürliche Länge gekürzt |
| gestrichelt | **Vorschlag**: wird nicht geschnitten, außer du klickst „Vorschlag übernehmen“ |

- **Klick auf ein Wort** wählt es aus (bei einem Schnitt der ganze Schnitt). Oben erscheint, warum es geschnitten wird,
  und ein Knopf **„Schnitt zurücknehmen“**.
- **Selbst löschen:** Wort anklicken (mit **Umschalt + Klick** mehrere), dann **Löschen** oder die Taste **Entf**.
- **Pause behalten:** auf das ⏸-Kästchen klicken.
- **Rückgängig:** Knopf oben oder **Strg + Z**.
- **Tempo:** *locker* / *normal* / *straff* bestimmt, wie viel Pause zwischen den Sätzen bleibt.
- **Vorschau:** Mit dem Haken „Vorschau mit Schnitten abspielen“ überspringt der Player alles Geschnittene,
  so hörst du sofort, wie es klingt. Der Balken unter dem Video zeigt lila, was bleibt.
- **Einstellungen** (unter dem Transkript): Füllwörter einzeln an/aus, Signalwörter, Retake-Abstand.

**Retake-Regel:** Wenn du dieselben Wörter innerhalb von **5 Sekunden Sprechen** nochmal sagst
(Denkpausen zählen nicht), wird der erste Versuch geschnitten. Bei mehreren Anläufen bleibt nur der letzte.

### Blick, Zoom, Ton, Untertitel, Buzzwords

- **Blick weg (lila, gestrichelt):** Die App erkennt, wenn du länger als 1,5 s nicht in die Kamera schaust
  (z. B. ins Script). Das ist nur ein **Vorschlag**, ein Klick auf „Vorschlag übernehmen“ schneidet die Stelle.
- **★ Buzzwords:** Wort(e) anklicken → **„★ Als Buzzword“**. Im Video poppt das Wort dann in einer Flieder-Box auf,
  nie über deinem Gesicht. Unter „Final rendern“ kannst du dir Buzzwords auch von der lokalen KI (Ollama)
  **vorschlagen lassen** und danach einzeln entfernen oder ergänzen.
- **Vorschau:** Buzzwords und (wenn eingeschaltet) Untertitel siehst du schon im Vorschau-Player.
- **Beim Rendern wählbar:** Zoom-Wechsel bei Schnitten (100/108/115 %, Gesicht bleibt im Bild),
  Lautstärke angleichen (−14 LUFS, Standard bei YouTube), Rauschen mindern, Untertitel
  (keine / nur SRT-Datei / ins Video einbrennen, optional Karaoke).

### YouTube-Paket (unter der Schnittansicht)

- **Titel, Beschreibung, Kapitel, Tags, 5 Hashtags:** mit der lokalen KI (Ollama) oder über „Auftrag für claude.ai
  kopieren“ → in claude.ai einfügen → Antwort zurück einfügen. Die App prüft auf Heilversprechen und YouTube-Regeln.
- **Thumbnail-Vorschläge** (beste Standbilder) und **Thumbnail gestalten** im Stil deiner bisherigen
  (Aussage mit *Schlüsselwort* in Rosa, oder Meditation), 3 Varianten zum Herunterladen.

### Reels aus einem YouTube-Video

Im YouTube-Projekt unter **„Reels aus diesem Video“**: **„Mit Claude vorschlagen“** (oder kostenlos mit Ollama).
Die App findet die stärksten 15–20-Sekunden-Momente, Hook in Sekunde 0, Stücke auch aus verschiedenen Stellen.
- **▶ Vorschau** spielt den Vorschlag ab, **Hook-Text** ist änderbar, **Wünsche zur Verfeinerung** → „Neu vorschlagen“.
- **„Passt – Reel rendern“**: 1080×1920, Querformat ohne Zoom mittig mit schwarzen Balken (Hook oben im Balken),
  Untertitel mit lila Karaoke-Wort, Lautstärke −14 LUFS, unter 30 MB. Caption, 5 Hashtags und Shorts-Titel zum Kopieren.

### Reel veredeln (Modus „Reel veredeln“)

- **Nichts wird gekürzt**: Länge, Tempo, Format und Ton bleiben genau wie im Original, kein Filter.
- **Texte im Video:** Hook-Karte (Creme, Cormorant, *Wort in Sternchen* lila-kursiv) in der Safe Zone, nie über
  dem Gesicht, mindestens 4,4 s sichtbar. Weitere Texte mit „+ Text bei …“. Buzzwords wie bei YouTube.
- **Reel-Paket:** Caption in deiner Stimme, **genau 5 Hashtags**, Cover-Text, YouTube-Shorts-Titel
  (Ollama oder claude.ai), dazu das **Reel-Cover** im Farbwechsel lila → hell → oliv.
- **Reel ohne Sprechen** (Musik, Natur, stumme Clips, auch ganz ohne Tonspur): Schreib im Reel-Paket deine **Idee**
  (z. B. „Sonntags-Scaries, polarisierender Hook, am Ende mein Notizbuch“). Die App schlägt Texte fürs Video,
  Caption, 5 Hashtags und Cover-Text vor. Erst wenn du **„Passt – ins Video übernehmen“** klickst, kommen die Texte
  ins Video (gleichmäßig verteilt, jeder mind. 4,4 s).
- **Reel rendern:** fertiges MP4 unter 30 MB.
- Hashtags: Die App nimmt deine Sammlung und **lernt neue passende Hashtags selbst dazu**.

### Final rendern

Erst wenn du links auf **„Final rendern“** klickst, entsteht das fertige Video (MP4, H.264, sehr gute Qualität).
Es liegt dann zum Herunterladen in der Liste darunter und im Export-Ordner des Projekts,
zusammen mit der Untertitel-Datei (`.srt`, z. B. zum Hochladen bei YouTube oder für CapCut).
**Dein Original wird nie verändert.** Die App arbeitet mit einer Kopie im Ordner `projekte`.

## Video Studio (Drone Cutter)

Oben im Menü **„Video Studio“**. Aus deinen Drohnen-Clips wird automatisch ein Reise-Video im Stil von
„Explore the World 4K“.

1. **Clips hochladen** (mp4/mov, bis 4K). Ein Clip reicht, mehrere gehen auch. Mit der Maus kannst du die Reihenfolge ändern.
2. **Format:** Reel/Short 9:16 (15, 30, 45 oder 60 Sekunden) oder YouTube 16:9 (HD oder 4K, Länge in Minuten).
3. **Stil:** Farb-Look (z. B. „Natural+“, „Tropical Pop“, „Golden Hour“) mit Stärke und Hautton-Schutz, Musik
   (automatisch nach Stimmung, ein Stück aus deiner Bibliothek, ein eigener Song oder keine Musik), Lautstärke,
   Originalton auf Wunsch leise darunter.
4. **Intro-Titel:** Ortsname in Großbuchstaben, dünne Schrift, sehr weite Buchstaben-Abstände, langsam einblenden.
   Schrift, Größe, Abstand, Höhe und Farbe kannst du einstellen. Rechts siehst du die Vorschau.
5. **„Generate preview“** macht eine kleine Vorschau. Mit **„Other version“** bekommst du eine andere Reihenfolge und andere Musik.
   **„Render final“** macht die fertige Datei (1080×1920 bzw. HD/4K). Sie liegt zum Herunterladen bereit und auf dem Desktop.

Was die App automatisch macht:
- Sie findet die besten Momente: scharf, ruhig, gut belichtet, farbig. Wackelige, dunkle und unscharfe Stellen nimmt sie nicht.
- Die beste Aufnahme kommt zuerst (Hook).
- Die Schnitte liegen genau auf dem Takt der Musik, und die Länge stimmt aufs Bild genau.

**Neu (Schritte 3–8):**
- **„Both“**: Hochformat-Reel *und* Querformat-Video mit einem Klick.
- **Tempo:** Zeitlupen-Rampen auf den schönsten ruhigen Aufnahmen und doppeltes Tempo bei langen Fahrten.
  Im Final werden Zeitlupen weich gerechnet (Zwischenbilder).
- **Zeitleiste:** Unter jedem Video siehst du die Aufnahmen. Pro Aufnahme kannst du sie tauschen (⇄),
  verschieben (← →), das Tempo oder eine Rampe ändern und den Übergang nach ihr wählen.
- **Klick auf ein Aufnahme-Bild** öffnet das Bearbeiten:
  - **Filters:** alle Looks mit *deinem* Bild, Vorher/Nachher-Schieber, Stärke, eigene .cube-LUT importieren.
  - **Adjust:** Belichtung, Kontrast, Lichter, Tiefen, Weiß, Schwarz, Temperatur, Tönung, Sättigung, Dynamik, Verblassen.
  - **HSL:** Sättigung und Farbton pro Farbe.
  - **Effects:** Schärfe, Klarheit, Vignette, Körnung, Entrauschen, Flackern entfernen, Stabilisieren.
  - **Crop & zoom:** Bildausschnitt (bei Hochkant sucht die App ihn automatisch) und langsames Heranfahren.
  - **Curves:** Kurven für Helligkeit und für Rot, Grün, Blau.
  - **Colour wheels:** Farbe und Helligkeit für Tiefen, Mitteltöne und Lichter.
  - **Mask:** Farbe nur in einem Bereich ändern (Himmel, Verlauf, Streifen, Kreis, Rechteck, Herz, Stern;
    weiche Kante, umkehren).
  - **AI tools** (laufen auf deinem PC, kostenlos): Hintergrund hinter Personen weichzeichnen oder einfärben,
    kleines Objekt entfernen (Kasten), Bild verbessern.
  - **Text:** Vorlagen (Ort mit Pin, Kino-Titel, Untertitel, Abonnieren-Knopf, Danke fürs Zuschauen).
  - „Auf alle Aufnahmen übertragen“.
- **Übergänge:** 25 Stück plus Automatik (meist harte Schnitte auf dem Takt, Wisch in Bewegungsrichtung,
  Zoom vor schönen Momenten, ruhige Überblendungen bei YouTube).
- **Titel:** 5 Einblend- und 3 Ausblend-Animationen, optionaler Abspann (z. B. dein Account).
- **Untertitel:** automatisch aus dem gesprochenen Ton (Whisper), 4 Stile, Füllwörter weglassen,
  `.srt`-Datei neben dem fertigen Video. Dafür muss „Keep original sound“ an sein.
- **Stil:** Schärfe, Klarheit, Vignette, Körnung, „Drone crisp“, alle Aufnahmen stabilisieren, Entrauschen,
  Helligkeit der Aufnahmen angleichen, Lautstärke auf −14 LUFS.
- Nach Änderungen auf **„Update preview (keep shots)“** klicken. Bei anderem Format oder anderer Länge auf **„Make new preview“**.

**Musik:** Lege lizenzfreie Stücke (YouTube Audio Library, Pixabay Music) in den Ordner `assets/music/`.
Die App erkennt Tempo (BPM) und Stimmung von selbst. Die Angaben stehen in `assets/music/library.json`
und dürfen geändert werden. Bekannte Songs aus den Charts können auf YouTube/Instagram Content-ID-Ansprüche
auslösen (stummgeschalteter Ton oder gesperrtes Video).

## Wie lange dauert das?

| | mit Nvidia-Grafikkarte | nur Prozessor |
|---|---|---|
| Transkript für 20 Minuten Video | ca. 1–3 Minuten | ca. 5–15 Minuten |
| Vorschau-Video für 20 Minuten | ca. 2–4 Minuten | ca. 10–25 Minuten |
| Final rendern (10 Min Ergebnis, 1080p) | ca. 3–6 Minuten | ca. 20–40 Minuten |

Vorschau-Video und Transkript laufen gleichzeitig. Oben rechts in der App steht, ob die Grafikkarte benutzt wird.
Bricht etwas ab (z. B. PC aus), macht die App beim nächsten Start dort weiter, wo sie war.

## Updates

Gibt es eine neue Version, erscheint oben ein gelber Balken **„Jetzt aktualisieren“**. Ein Klick genügt:
Die App holt die neue Version, startet sich neu und lädt die Seite von selbst neu.
(Das klappt, wenn du die App über VS Code mit „Git: Clone“ geholt hast, nicht beim ZIP-Download.)

## Texte mit Claude

- **Einmal einrichten:** oben **„Einstellungen“** → Schritt für Schritt: auf console.anthropic.com Guthaben aufladen
  (z. B. 10 $, kein Abo), Schlüssel erstellen, in der App einfügen. Die App prüft ihn sofort.
- **Danach ein Klick:** im Reel- oder YouTube-Paket **„Mit Claude erstellen“** → nach ca. 20–60 Sekunden sind alle
  Texte da (Texte fürs Video, Caption, 5 Hashtags, Cover-Text, Shorts-Titel bzw. YouTube-Titel, Kapitel …).
- **„Social Media Content“** (oben): Chat mit Claude direkt in der App, deine Regeln und dein Stil sind immer dabei.
- Kosten: ca. 0,05–0,10 $ pro Reel-Text, ca. 3–8 $ im Monat. Kostenlos geht es weiterhin mit **„Kostenlos mit Ollama“**.

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
- **Video Studio** (`backend/editor_app/video_studio/`, Oberfläche `frontend/src/video-studio/`):
  - `analysis.py`: Szenen (Histogramm + Phasenkorrelation), Qualität pro Moment, Helden- und Fahrt-Momente.
  - `beats.py`: Takt/BPM nur mit numpy, ohne librosa (dessen numba passt nicht zur numpy-Version unter Windows).
  - `planner.py`: Auswahl, Reihenfolge, Schnitte auf dem Takt.
  - `color.py`: Farb-Looks werden zu einer .cube-LUT gebacken. ffmpeg nutzt `lut3d`, ohne `lut3d` `haldclut`.
  - `text.py`: Intro-Titel. `music.py`: Bibliothek, Ducking. `render.py`: ffmpeg. `store.py`: Projekte unter `daten/studio/`.
  - **Neuer Farb-Look:** einen Eintrag in `color.PRESETS` (Regler wie temp, contrast, highlights, vibrance, sat_by,
    hue_shift, split, fade) und einen Namen in `LOOK_NAMES` (`StudioPage.tsx`).
  - **Neue Schrift:** die .ttf nach `assets/fonts/` und `frontend/src/fonts/` legen, einen Eintrag in `text.FONTS`
    und ein `@font-face` in `styles.css` anlegen.
  - **Musik:** die Dateien nach `assets/music/` legen (nicht im Git).
  - **Testclips:** in `test-media/` (nicht im Git).
  - **Lizenzen:** Montserrat und Raleway (SIL OFL 1.1, Lizenzdateien in `assets/fonts/`). Keine fremden LUTs,
    Effekte oder Musik im Repo, alle Looks sind eigene Parameter.
- Grafikkarte: `uv sync --extra gpu` installiert die CUDA-Bibliotheken (cuBLAS, cuDNN 9). Klappt die Karte nicht,
  rechnet die App automatisch mit dem Prozessor weiter.
