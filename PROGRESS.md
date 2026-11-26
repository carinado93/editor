# Fortschritt

## Stand: 8. November 2026

> **10 Nov 2026:** The whole app interface is now in English (all pages, buttons, hints, plus the progress, error and warning messages from the engine). The prompts sent to Claude/Ollama are unchanged, so texts are still written in German or English as chosen. From now on, notes are in English.

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

- [x] **Thumbnail maker (17 Nov 2026, merged to main after Carina's OK)**
  - New "Thumbnail" page (`#/thumbnail`) plus a "🎨 Thumbnail maker" button in every YouTube project (step-thumb card;
    the existing frame suggestions and CoverStudio stay unchanged).
  - Flow: photo (upload or one of 12 video frames) → cut-out (`fx.Segmenter` + GrabCut refine, finger/hair fix) →
    background description + "Suggest" (Claude: 3 backgrounds + 3 two-word titles, proposals only) → 3 versions
    ("3 backgrounds, same title" or "1 background, 3 titles") → grid with a 360 px phone preview → edit title, layout,
    text behind/in front, doodles, drag/arrow/size for her and for the title, "New background" for one version →
    download one PNG or a zip of all 3 (also saved in the project folder and in the Desktop outbox).
  - `image_gen.py`: `generate(prompt, w, h)`; providers: Pollinations (free, no key, default), Higgsfield
    (`api.higgsfield.ai`, model `bytedance/seedream/v4/text-to-image`, key `HF_KEY=id:secret` in `.env`,
    set in Settings → Thumbnail backgrounds), or "frame". Any failure/offline → blurred, darkened frame of her own
    photo (different crop per version). Prompt suffix always added (photorealistic, no people/text/logos, empty top).
    Cost shown before generating. Neither Pollinations nor Higgsfield could be reached from the dev container, so
    the real API calls are untested; the Higgsfield price (~$0.03/image) is an estimate.
  - `thumbmaker.py`: 1280×720 PNG < 2 MB; dark top ramp; her big, soft shadow, never graded; Poppins Black white word 1,
    lilac play tag #B79CE0, Cormorant Garamond Bold Italic word 2 with lilac brush underline; layouts top / two /
    side / auto; tries scale × lower × font size until text avoids face and (behind mode) ≥70 % of each word and
    the first letter stay visible, otherwise warns. Draw order bg → text (behind) → her → text (front) → tag → doodles.
  - `thumbstore.py` + `/api/thumbmaker/*` endpoints, `/api/einstellungen/image-gen`.
  - Tests `tests/test_thumbmaker.py`: fake generator (size, words not on face box, PNG < 2 MB, 3 versions) and the
    "text behind me" pixel check (opaque cut-out stays on top, ≥70 % visible). 79 tests pass.
  - "My colours" mode (Carina's wish, 17 Nov): 3 versions, each a soft gradient of 2 of her colours – lilac #C9B3EC +
    dusty rose #E8B9B7, pink + yellow #FAE8A5, yellow + lilac – with blurred light circles, fine grain and a plum top for
    the white title (`image_gen.colour_background`). Local, free, no AI; it is the default mode. Pink = dusty rose measured from her
    meditation thumbnails (pill #E8B9B7, light blush #F2D6D2), now also in the brand skill. Extra pairs white #FEF8F3 + pink and lilac + white;
    she picks a pair for each of the 3 versions (defaults lilac+pink, pink+yellow, yellow+lilac) and can switch per version.
  - "My own background, blurred" mode (Carina's wish, 17 Nov, reference: George Alexander-style thumbnails – real room,
    soft, person sharp): her photo's background with her removed first (cv2 inpaint of the cut-out mask, `cut_box` saved
    in state) and Gaussian blur 6 / 12 / 22 px for the 3 versions; no colour change. Pickable per version too.
  - Tested with Carina's own photo (17 Nov, desk + microphone, raised hand): fingers, nails, glasses, hair and mic are
    clean. Fixes from that test: (1) the segmenter takes her red armchair and plant leaves as "person" → new eraser /
    bring-back brush on the cut-out (`POST /photo/fix`, full mask kept as mask.png / mask_auto.png, versions re-render);
    (2) uncertain edge pixels no longer kept as a semi-transparent room veil (alpha remap 0.3–0.75 in `refine_mask`);
    (3) sizing by face height (≤38 % of H) and up to 1.15·W wide, so wide photos (arms out) stay big; (4) sides where
    she is cut off in the photo (`cut_box` touches the edge) are snapped to the frame edge; (5) no plum shadow behind her on her own blurred room (only the text uses lilac), edge snap tolerance 1.2 %;
    (6) if "text behind me"
    cannot keep ≥70 % of each word, the title goes in front of her with a note instead of hiding letters.

- [ ] **Video Studio – step 2 MVP (18 Nov 2026, branch `video-studio`, waiting for Carina's drone clips + OK)**
  - Plan approved (CapCut replacement: Drone Cutter + clip editor, 9 build steps). New menu entry "Video Studio"
    (`#/studio`), code in `backend/editor_app/video_studio/` and `frontend/src/video-studio/StudioPage.tsx`.
  - Drone Cutter MVP, working end to end:
    - chunked upload of 1..N clips (drag to reorder);
    - analysis (cv2 histogram + phase-correlation scene cuts, sharpness relative to the clip, shake, exposure,
      colourfulness, hero/transit/direction);
    - numpy beat tracker (±2 ms on a click track, BPM via regression);
    - planner (reel 1.5–3 s shots, hook = best/hero shot ≥ title length; YouTube 4–10 s; exact length to the frame;
      cuts on beats, ±25 % fallback; no frame used twice; slow-motion stretch + warning if footage is too short);
    - colour looks baked into one 33³ .cube (lut3d / haldclut fallback; 11 own looks, Natural+ default,
      skin protection);
    - location intro title (Montserrat ExtraLight, caps, 0.62→0.45 em tracking, fade in/out, shadow, optional subtitle,
      live CSS preview);
    - music library `assets/music/` (auto BPM/mood/best start, loop, fades, duck under title, own upload with
      Content-ID warning);
    - render: segments → concat → title + music, preview 540 px, final 1080×1920 / 1920×1080 / 4K, NVENC or x264;
      Desktop outbox.
  - Colour exception to the "never colour-grade" rule recorded in CLAUDE.md (her answer: "I need color grade on it").
  - Tested on a synthetic 45 s drone clip (`test-media/synthetic_drone.mp4`: push-in, fast pan, shaky, dark, blurred,
    reveal): all 7 sections detected; shaky/dark/blurred rejected; 15 s reel = 450 frames exactly; final
    1080×1920 H.264 + AAC 20 MB; 26 s for analysis + preview on the container CPU.
  - Tests: `tests/test_video_studio.py` (13). Suite total 94 passed.
  - Limitations / next: centre crop for 9:16 (smart reframing = step 9); hard cuts only (transitions = step 4);
    no speed ramps yet (step 3); not yet tested on her real DJI footage (D-Log, 4K HEVC); music library empty until
    she adds tracks.

- [x] **Video Studio – steps 3–8 (18/19 Nov 2026, branch `video-studio`)**
  - "Both" output: reel 9:16 + YouTube 16:9 (HD/4K) planned and rendered in one go; plans/renders stored per format
    (old single-plan projects migrate on load).
  - Step 3:
    - speed ramps (`speed.py`: hero/montage/bullet/flash curves, eased, rendered as 12 constant-speed pieces;
      minterpolate optical-flow slow motion in the final);
    - auto ramp on the best calm shots (not the hook);
    - transit shots 2×;
    - timeline per format (swap/move/speed/ramp/transition per shot, thumbnails);
    - "Update preview" re-renders the existing plan with the current colour/title/outro/transition settings.
  - Step 4:
    - transitions (`transitions.py`, xfade chain centred on the beat cut, all inputs normalised to one timebase);
    - auto mode: reel mostly cuts, match-cut swipe by direction, zoom into hero, dissolve; YouTube dissolves +
      dip to black;
    - title animations in (tracking/fade/rise/letters/blur) and out (fade/sink/none);
    - outro text (e.g. account).
  - Step 5/6:
    - per-shot panel with Filters (all looks rendered on her own frame, before/after slider, strength,
      .cube import), Adjust, HSL, Effects (sharpen/clarity/vignette/grain/denoise/deflicker/stabilize via vidstab),
      Crop & zoom (position + zoom keyframe start→end), apply to all;
    - per-shot LUT bake;
    - auto-reframe for vertical (saliency window);
    - brightness matching across shots;
    - "Drone crisp".
  - 19 Nov additions:
    - curves (5-point RGB/R/G/B) and colour wheels (shadows/midtones/highlights) baked into the LUT;
    - masks (`masks.py`: linear/mirror/circle/rectangle/heart/star/sky, feather/invert/rotate) rendered with
      maskedmerge (graded copy inside the mask);
    - auto captions (`captions.py`: Whisper → ASS clean/bold/karaoke/boxed, filler words dropped, .srt next to the
      final, needs keep_audio);
    - local AI tools in `ai_tools.py`: background blur/colour behind people (MediaPipe), object removal in a box
      (cv2 inpaint), enhance (CAS).
    - Still need an external provider or a large model: upscaling (Real-ESRGAN), SAM2/LaMa object removal,
      extend, remix, AI stylize, relight, lip-sync, eye contact.
  - Step 7 (partly): text templates (location pin, cinematic, caption, subscribe, thank you); loudness normalise
    −14 LUFS. Auto captions not added to Video Studio (drone clips have no speech; the project editor already has
    Whisper subtitles).
  - Step 8 (partly): 25 transitions; HSL per colour. Curves, colour wheels and masks are not built yet.
  - Step 9: ready: stabilize, denoise, deflicker, optical flow, auto-reframe. The generative tools are listed in
    `video_studio/ai_tools.py` with engines and licences, but not built yet: enhance, object removal, matting,
    extend, remix, stylize, relight, lip-sync, eye contact.
  - Tested on her DJI Mini 4 Pro clip (4K HEVC, 3:54): both formats, swap, look/text edits + update preview.
  - Tests: 23 in `test_video_studio.py`.
  - Fixed on main 18 Nov: Windows LUT path escaping (`C\:`) made Generate fail.

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
- **M6c Inspiration → eigene Version** (vorgemerkt für nächste Woche): Screenshots/Bildschirmaufnahme eines fremden
  Reels hochladen → App erkennt Aufbau, Takt, Text-Stil → baut daraus eine Vorlage mit Carinas eigenen Clips und
  Worten (nie 1:1). Bilderkennung über Gemma 3 (Ollama) oder claude.ai.
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

- [x] **M5 Reel-Modus B1 „Veredeln“**
  - Keine Schnitte (`no_cuts`), Ton wird 1:1 übernommen (`-c:a copy`), kein Zoom, keine Lautstärke-Änderung,
    Format bleibt (nur auf 1080 Breite verkleinert); Bitrate automatisch so, dass die Datei < 30 MB bleibt
  - Hook-Karte (ASS: Creme-Box, Cormorant SemiBold 92 px, *Akzent* lila-kursiv), Safe Zone y 280–1250 / x 90–900,
    über dem Gesicht wenn Platz, sonst darunter; Versprecher im Hook werden automatisch entfernt; ≥ 4,4 s
  - Buzzwords nie gleichzeitig mit der Hook-Karte; Blick-Analyse + automatische Buzzwords auch im Reel-Modus
  - `captions.py`: Caption nach Carinas Aufbau, genau 5 Hashtags (lernt neue dazu), Cover-Text, Shorts-Titel,
    Prüfung (Heilversprechen, „keine Diagnose/Therapie“), Ollama oder claude.ai-Kopierweg
  - UI: Reel-Paket (Texte im Video, Caption-Editor, Reel-Cover mit Rotation), Vorschau zeigt Hook-Karte live
  - Test mit dem 2:44-Video als Reel: Länge gleich, Ton unverändert (AAC 317 kbit/s übernommen), Hook + Buzzwords ok.
    Größe war 30,8 MB → Berechnung korrigiert (normale Reels ≤ 90 s liegen weit darunter).
  - 37 automatische Tests

- [x] 8.11.: **Reels ohne Sprechen mit eigener Idee/Prompt**: Feld „Deine Idee“ im Reel-Paket (+ Sprache EN/DE).
  Daraus: Szenen-Texte (max. Cliplänge/4,4 s, höchstens 6), Caption, 5 Hashtags, Cover-Text, Shorts-Titel
  (Ollama oder claude.ai). Szenen kommen erst nach „Passt – ins Video übernehmen“ ins Video (Freigabe).
  Clips ohne Tonspur: kein Transkript, Render ohne Ton. Auch bei Clips mit Sprechen kann eine Idee mitgegeben werden.

- [x] 8.11.: Carina: zu viel Handarbeit → **Weg B** gewählt (claude.ai-Abo, kein API-Geld):
  Knopf „Mit Claude erstellen“ öffnet claude.ai/new?q=<Auftrag> (Auftrag zusätzlich in der Zwischenablage),
  Carina drückt Enter + „Kopieren“, die App liest beim Zurückwechseln die Zwischenablage und übernimmt die Antwort
  automatisch (Einfügefeld nur noch als Notlösung). Ob claude.ai das ?q= wirklich ins Feld schreibt, konnte ich
  hier nicht prüfen (claude.ai nicht erreichbar) → Fallback Strg+V.
  Claude-API (ganz automatisch, ca. 3–8 $/Monat) als spätere Option angeboten, nicht gebaut.
- [x] 8.11.: **„Jetzt aktualisieren“-Knopf** (`updater.py`): git fetch alle 15 Min, Klick → git pull --ff-only →
  Motor endet mit Code 3 → start.bat macht uv sync und startet neu (ohne neuen Browser-Tab) → Seite lädt neu.
  Seite wird nie zwischengespeichert (kein Strg+F5 mehr). Nicht während Verarbeitung/Rendern.
- **Arbeitsregel (8.11.): Carina will gefragt werden, bevor ich etwas umbaue oder entferne.**
- [x] 8.11.: Weg B (claude.ai + Zwischenablage) scheiterte im Browser (leerer Tab, Kopieren blockiert, alter Motor).
  Carina wollte Claude direkt in der App → claude.ai lässt sich nicht einbetten → **Entscheidung: Claude-API**
  (ca. 3–8 $/Monat). `claude.py`: Schlüssel in `.env` (per Einstellungen-Seite, wird mit Mini-Anfrage geprüft),
  Claude Opus 5.5, JSON-Schema-Antworten, Ausweichen bei Ablehnung (`fallbacks: "default"`, sonst normaler Aufruf).
  „Mit Claude erstellen“ in Reel-/YouTube-Paket (ein Klick), Ollama als „Kostenlos mit Ollama“ daneben,
  neuer Bereich **„Social Media Content“** (Chat mit Carinas Regeln/Stil), Seite **„Einstellungen“**.
  claude.ai-Kopierweg entfernt (durch API ersetzt). Echter Aufruf mit gültigem Schlüssel noch nicht getestet
  (kein Schlüssel hier); falscher Schlüssel → echte 401 von Anthropic → verständliche Meldung (getestet).

- [x] 9.11.: **Reels aus YouTube-Videos** (`clips.py`, `render.render_clip`, UI „Reels aus diesem Video“):
  Claude (Opus 5.5, effort high) oder Ollama wählen aus dem bereinigten Transkript (Sätze mit genauen Längen)
  so viele starke 15–20-s-Reels wie es gibt, Hook zuerst, Stücke aus beliebigen Stellen in beliebiger Reihenfolge.
  Prüfung: Länge 10–26 s (Hinweis außerhalb 15–20), keine doppelt laufenden Momente, genau 5 Hashtags.
  Verfeinerung per Wunsch-Text (bisherige Vorschläge gehen mit). Render: Stücke per trim/concat in freier Reihenfolge,
  Ton per numpy mit Blenden + −14 LUFS, Querformat ohne Zoom mittig mit schwarzen Balken (Video endet bei y=1250,
  Hook im oberen Balken, Untertitel unten im Video), Hochformat voll; Karaoke-Untertitel; < 30 MB; SRT dazu.
  Getestet: Hochformat-Clip aus Carinas Video (Hook-Karte, Karaoke, −14 LUFS, A/V gleich lang), Querformat-Test
  mit Balken, Ablauf in der Oberfläche mit nachgestellter KI-Antwort. 53 Tests.

- [x] 9.11.: Carina: Reels ohne Text verstehen keinen Kontext → **Hook ab Sekunde 0 + weitere Texte mit
  Animationen** (Pop, Karte, Wort für Wort, Gleiten; wechseln sich ab, je 4,4–6 s). „Mit Claude erstellen“ (Klick,
  Carinas Wahl b) legt Hook + Texte direkt ins Video; Claude/Ollama bekommen 5 Standbilder aus dem Clip (versteht
  auch Clips ohne Sprechen, Idee optional). Warnung vor dem Rendern ohne Text. Reels aus YouTube-Videos bekommen
  zusätzlich 2–3 Einblendungen nach dem Hook. Getestet: Animationen im gerenderten Reel sichtbar.
- [x] 9.11.: Thumbnails: Hintergrund war „shitty“ (Flecken hinter dem Text, Text lief ins Foto/abgeschnitten) →
  saubere helle Fläche, Aquarell nur Ecke oben links + Pinselstrich unten, Foto genau rechte Hälfte, Text nur links
  und automatisch so groß, dass nichts abgeschnitten wird; „*WORT*?“ bleibt zusammen (Carinas Wahl: nachbauen).

- [x] 16.11.: **Studio effects from the "Day in my life" training** (`fx_studio.py`, new group "E" in the effects panel,
  Claude/Ollama may suggest them too, not ticked by default): battery (brain battery + Low Battery popup), codechips,
  nightfall (sun → moon, clock counts), logoff (glitch + "logging off…"), sportpill (stopwatch pill), ringtimer
  (meditation), savedcard ("WORKOUT SAVED" + cursor click), subscribe (lilac iris + subscribe/like buttons),
  heartcover (THANK YOU behind her + lilac heart covers the screen), sharestats (Strava-style "Share Activity" ending).
  New fonts Titan One, Fredoka, Inter (OFL). All know-how as Claude Code skills in `.claude/skills/` + `CLAUDE.md`.
  73 tests pass. Not yet in the app as effects (need multi-clip/plate support): rope + sticker flies into her,
  placed-down with clean plate, split screen, seamless mirror cut, language versions of a finished edit.
- [x] 16.11.: **Studio transitions + language versions.** "Join videos" has 4 new transitions
  (`transitions_studio.py`, rendered as their own seam clip between the trimmed clips, shown as "Transition" in the
  clip list): split (lilac split screen, then B grows to full screen), rope (A freezes, a rope with her sticker from
  B drops in, cursor click, sticker flies into the real video), placed (empty room, she is lowered in from above;
  room = last frame of A if A ends on the empty room, else built from B — warns in the log if it isn't clean),
  iris (lilac circle). Claude's transition planner knows them. Language version (`translate.py`, effects panel):
  Claude/Ollama proposes a translation table, Carina edits and approves, texts are swapped, originals stay saved
  and can be restored. The seamless mirror match cut stays a Claude Code workflow (skill
  `carina-seamless-match-cut`) because every pair of clips needs hand-picked frames. 76 tests pass.

### Nächster Schritt
M6 Vorlagen-Bibliothek + B2 (Reel aus Idee), M6b Karussell-Generator, M7 Politur. Carina wählt die Reihenfolge.

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

## 26 Nov 2026 – Thumbnail maker: own blurred photo, new shadows, clean cut-out
- Default background is now Carina's ORIGINAL photo, heavily blurred (`thumbmaker.own_blur_background`): width 1280×1.4,
  crop around cx 0.55/0.50/0.45 (she right/centre/left, left = mirrored), cy 0.45, Gaussian 70, brightness ×0.90,
  contrast ×0.75, text-side darkening #1E181A (22 %, centre layout 20 % on both edges, middle 40 % free), vignette ≤10 %,
  mean brightness forced into 45–85 %. Built per render from where she actually stands. AI backgrounds only on the
  separate "🤖 AI" buttons; "My colours" stays.
- "Own photo, blurred" + layout auto = 3 versions like her reference thumbnails: she right / centre / left.
- Shadow behind her: #281E1E 20 %, blur 30, offset +14/+10 (no purple). Text shadow: #230F2D 70 %, blur 10, +3/+5.
- New `thumb_cutout.py`: IS-Net isnet-general-use (rembg's model + pre-processing, run directly with onnxruntime –
  the rembg package itself would pull in opencv-python-headless, which clashes with opencv-contrib) + pymatting
  closed-form alpha matting, then ALWAYS: holes (small filled, big enclosed → transparent), leftover bright/grey
  background near the edge removed (inside protected; extra guard: must look like the nearby background so white
  clothes survive), soft light glow around the hair removed, alpha open/erode/largest piece/head close+open+blur/
  body open+close+blur, colour decontamination (pymatting foreground estimate + inside colour). Automatic fringe test,
  up to 3 rounds with stronger cleanup, otherwise a warning in the UI. `check_sheet()` makes the zoom sheet on #5A4646.
- 360 px phone check → warning if a word gets too small.
- New dependency: pymatting (numba, scipy). Model downloads to modelle/ on first use (~170 MB); falls back to the
  MediaPipe mask when offline.
- Tests: brightness range, text-side darkening, shadow colour, no white fringe, small/big holes, largest piece,
  3 own-blur looks with face free. 116 tests pass.
- Limit: tested on her 3 reference thumbnails (no original photo in the repo). These already contain an old light
  halo around the head, a little of it stays in the test; check with a real original photo.
- Follow-up 26 Nov: cut-out also removes an opaque light band / grey patches at the hair outline (colour closer to
  the wall than to her hair), face + glasses protected; test added.
- Effects: text fields are now multi-line (Enter = new line); `fx.wrap` honours "\n" for all text effects
  (typewriter etc.).
