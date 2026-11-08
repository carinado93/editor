# Recherche: Auto-Video-Editor für Carina

Stand: 7. November 2026. Kurz, ehrlich, mit Quellen. Fachwörter sind in Klammern erklärt.

> Hinweis zu den Quellen: Viele Seiten im Netz zu Reels/YouTube sind Blogs von Tool-Anbietern, die etwas verkaufen wollen.
> Zahlen von dort sind **Faustregeln**, keine offiziellen Regeln. Ich habe das jeweils dazugeschrieben.

---

## 1. Fertige Open-Source-Werkzeuge für Pausen, Retakes und Füllwörter

| Werkzeug | Was es kann | Lizenz | Nutzen wir es? |
|---|---|---|---|
| **auto-editor** (WyattBlue) | Schneidet Stille (und wenig Bewegung) automatisch raus, exportiert Schnittlisten für Premiere, DaVinci Resolve, Final Cut | frei (Open Source) | **Als Vorbild und für den Export-Teil**, nicht als Kern. Es schneidet nur nach Lautstärke, kennt keine Wörter. Wir brauchen Schnitte nach Wörtern (sonst kann man in der Review-Ansicht nichts durchstreichen). |
| **jumpcutter / unsilence / av_slice** | Nur Stille entfernen oder beschleunigen | MIT | Nein. Kann auto-editor besser, und wir machen es selbst über die Wort-Zeitstempel. |
| **faster-whisper** | Whisper-Spracherkennung, 4x schneller, mit **Wort-Zeitstempeln** (genaue Zeit für jedes Wort) und eingebauter Stille-Erkennung (VAD) | MIT | **Ja, als Kern.** Läuft auf CPU und Nvidia-GPU, erkennt DE/EN automatisch. |
| **WhisperX** | faster-whisper + "Forced Alignment" (ein zweites Modell legt jedes Wort sehr genau auf die Tonspur) | BSD | **Ja, optional als 2. Schritt**, wenn Wortgrenzen ungenau sind. Kostet etwas mehr Rechenzeit. |
| **CrisperWhisper** | Schreibt *wortwörtlich* mit, auch "äh", "ähm", Stotterer | **nicht kommerziell** (CC-BY-NC) | **Nein**, du nutzt die App beruflich. |
| **Smart Cut** (GitHub, MIT) | faster-whisper + erkennt wiederholte Sätze per Text-Vergleich, gibt MP4 + EDL aus | MIT | **Als Vorbild** für die Retake-Erkennung. |
| **Cadence Lab** (MIT, frühe Phase) | Lässt eine KI das ganze Transkript beurteilen | MIT | Nein, zu früh und teurer. Idee "KI als zweite Meinung" übernehmen wir optional. |
| **Dein eigenes Skript** `tools/audio/clean_recordings.py` (im Repo `carinado93/app`) | Erkennt "again"/"nochmal"-Retakes und Satz-Wiederholungen in deinen Sprachaufnahmen | eigenes | **Ja!** Die Retake-Logik (Signalwörter + Satzanfang-Vergleich) übernehmen und erweitern. |

**Wichtiges Problem bei Füllwörtern:** Normales Whisper lässt "äh/ähm/um/uh" oft einfach weg (es "räumt auf"). Dann können wir sie nicht durchstreichen.
Unsere Lösung (drei Ebenen, damit nichts verloren geht):
1. Whisper bekommt einen Start-Text mit Füllwörtern ("Ähm, also, äh, ich meine…"). Das bringt Whisper bei, sie mitzuschreiben (bekannter Trick).
2. **Lücken-Prüfung:** Wenn zwischen zwei Wörtern Ton zu hören ist, aber kein Wort erkannt wurde, ist das sehr wahrscheinlich ein Füllwort oder Atmer. Wird als **"Vorschlag"** markiert, nicht automatisch geschnitten.
3. Pro Füllwort ein Schalter (z. B. "also" bleibt an, weil es oft echt gemeint ist).

**Empfehlung:** faster-whisper (+ optional WhisperX) als Basis, Schnitt-Logik selbst bauen (auf Wort-Ebene, damit die Review-Ansicht funktioniert), Export-Formate (FCPXML/EDL) nach dem Vorbild von auto-editor.

Quellen: [auto-editor Überblick](https://knightli.com/en/2026/04/23/auto-editor-auto-cut-silence-premiere-resolve-workflow/), [auto-editor auf PyPI](https://pypi.org/project/auto-editor/21.39.1), [jumpcutter](https://alternativeto.net/software/carykh-jumpcutter/about), [av_slice](https://pypi.org/project/av-slice), [CrisperWhisper (Lizenz, Füllwörter)](https://huggingface.co/nyrahealth/faster_CrisperWhisper), [Studie: Whisper entfernt Füllwörter](https://aphasia.talkbank.org/publications/2024/Wagner24.pdf), [WhisperX](https://www.sourcepulse.org/projects/1473319), [Smart Cut](https://github.com/qkirara/Smart-Cut), [Cadence Lab](https://cadence-lab-marketing-site.pages.dev/)

---

## 2. Blick-Erkennung ("schaut sie in die Kamera?")

**Wichtig vorab:** MediaPipe Iris findet die Pupille, sagt aber selbst nicht, *wohin* jemand schaut. Das müssen wir aus zwei Signalen zusammenbauen.

**Empfohlene Methode:** MediaPipe **Face Landmarker** (aktuelle Version von Face Mesh, Apache-2.0-Lizenz, läuft auf CPU schnell):
1. **Kopfhaltung** aus der "Transformationsmatrix" (Face Landmarker liefert sie auf Wunsch): Neigung nach unten (Pitch) und Drehung zur Seite (Yaw) in Grad.
2. **Augen-Position:** Wo sitzt die Iris zwischen den Augenwinkeln und zwischen Ober- und Unterlid? (Punkte 468–477 bei eingeschalteter Iris-Verfeinerung.) Beim Ablesen vom Script/Handy gehen oft nur die Augen runter, der Kopf kaum.
3. **Automatische Kalibrierung pro Video:** Die häufigste Kopf-/Augenhaltung im Video ist "Blick in die Kamera" (du schaust ja meistens rein). Alles wird relativ dazu gemessen. So spielt es keine Rolle, ob das Handy etwas höher oder tiefer steht.
4. **Zeitfilter:** Erst wenn der Blick **länger als 1,5 s** weg ist, wird markiert. Kurzes Wegschauen beim Nachdenken bleibt.

**Start-Schwellwerte** (alle einstellbar, werden mit deinem ersten Video nachjustiert; es gibt keine offiziellen Werte):

| Signal | "weg" ab | Begründung |
|---|---|---|
| Kopf nach unten (gegenüber Kalibrierung) | > 12° | Script/Handy unter der Kamera |
| Kopf zur Seite | > 20° | Seitlicher Blick, Notizen daneben |
| Iris nach unten (relativ zur Lidöffnung) | > 0,15 der Augenhöhe | Nur-Augen-Blick nach unten |
| Mindestdauer | 1,5 s | dein Wunsch |
| Analyse-Takt | 5 Bilder pro Sekunde | reicht für 1,5-s-Regel, 6x schneller als jedes Bild |

**Alternative:** spezialisierte Blick-Netze (z. B. L2CS-Net) sind genauer, brauchen aber GPU und die Lizenz muss geprüft werden. Erst nehmen, wenn MediaPipe bei deinen Videos nicht reicht.

Quellen: [TensorFlow-Blog: Iris-Tracking ist keine Blickschätzung](https://blog.tensorflow.org/2020/11/iris-landmark-tracking-in-browser-with-MediaPipe-and-TensorFlowJS.html), [Face-Mesh-Punkte (478)](https://dev.to/metsander/mediapipe-face-mesh-all-478-landmark-points-5ec8), [Landmark-Indizes](https://hackernoon.com/mediapipe-face-mesh-landmark-indices-cheat-sheet), [Studie: FaceMesh + Kopfbewegung](https://dspace.vut.cz/items/b6f69c90-9773-40f4-aef7-8f94d407824c/full), [Beispielprojekt Eye-Tracking](https://www.github.com/Manoj-2702/EyeTracking)

---

## 3. Retake-Erkennung per Text-Ähnlichkeit

So machen es ähnliche Tools: Smart Cut vergleicht aufeinanderfolgende Sätze per Text-Ähnlichkeit (SequenceMatcher). FireCut und Cutback ("Remove Retakes") suchen wiederholte Sätze und lassen dich wählen, welche Version bleibt. Tella **schlägt** Schnitte vor und du bestätigst. Genau das bauen wir auch.

**Unsere Stufen (von sicher zu unsicher):**

| Stufe | Erkennt | Wie | Ergebnis |
|---|---|---|---|
| 1. Signalwort | "again", "nochmal", "noch mal", "stopp", "cut", "von vorne" (Liste editierbar) | Wort im Transkript, danach Satz/Abschnitt davor finden | **sicherer Schnitt** |
| 2. Wiederholter Satzanfang | "Stress ist… Stress ist eigentlich…" | Fuzzy-Vergleich (unscharfer Textvergleich, Bibliothek `rapidfuzz`) der ersten 3–6 Wörter, Ähnlichkeit ≥ 85 % | sicherer Schnitt, letzte Version bleibt |
| 3. Ganzer Satz nochmal, leicht anders formuliert | "Das ist wichtig für dich." → "Das ist so wichtig für dich." | Ähnlichkeit ≥ 75 % **oder** Satz-Embeddings (Bedeutungs-Vergleich, Modell `paraphrase-multilingual-MiniLM`, DE+EN, Apache 2.0, läuft lokal) | **"Vorschlag"** |
| 4. Stotterer / abgebrochenes Wort | "Resi- Resilienz", "die die" | Wort ist Anfang des nächsten Worts oder doppelt; sehr kurze Wortdauer | sicherer Schnitt (nur das Fragment) |
| 5. (optional) KI-Zweitmeinung | Grenzfälle | Claude liest den Abschnitt und sagt "Retake ja/nein" | nur als Vorschlag, kostet Cent-Beträge |

Nur Sätze, die **direkt hintereinander** (innerhalb ~20 s) vorkommen, gelten als Retake. Sonst würde ein absichtlich wiederholter Kernsatz am Ende fälschlich gelöscht.

Quellen: [Smart Cut](https://github.com/qkirara/Smart-Cut), [FireCut "Remove repetition"](https://firecut.ai/features/remove-repetition), [Cutback "Remove Retakes"](https://cutback.video/blog/how-to-instantly-remove-retakes-in-premiere-pro-using-ai-(fastest-2025-method)), [Tella "Remove mistakes"](https://www.tella.com/agent/remove-mistakes)

---

## 4. Animations-Werkzeug für Reels: Remotion und Alternativen

| Werkzeug | Wie es funktioniert | Lizenz / Kosten für dich | Eignung |
|---|---|---|---|
| **Remotion** | Videos als React-Seiten, jedes Bild wird im Browser gezeichnet. Texte, Verläufe, Schatten, Schriften, Sticker: alles wie auf einer Webseite. Sehr gut für "Szenen als JSON". | **Kostenlos** für Einzelpersonen und Firmen bis 3 Personen, auch kommerziell. Erst ab 4 Personen Firmenlizenz (ca. 100 $/Monat). | ★★★★★ |
| Revideo | Abspaltung von Motion Canvas mit Render-Schnittstelle | MIT, kostenlos | ★★★★ (Plan B) |
| Motion Canvas | Animationen auf einer Zeichenfläche, eher für Erklärvideos von Hand | MIT, kostenlos | ★★★ |
| MoviePy | Python, Videos zusammensetzen | MIT, kostenlos | ★★ langsam, Animationen mühsam |
| ffmpeg + PIL | Jedes Bild selbst malen | frei | ★★ volle Kontrolle, sehr viel Handarbeit |
| Manim | Mathe-Animationen | MIT | ★ falscher Stil |

**Empfehlung: Remotion.** Du bist Einzelunternehmerin, also fällst du unter die kostenlose Lizenz. Deine Bausteine (Durchstreich-Linie, Flieder-Box, drehender Stern, Slam-Wörter, Notizbuch-Collage) sind mit Web-Technik am einfachsten in deiner Optik umzusetzen, und Google Fonts (Cormorant, Poppins, Caveat, Noto Serif Display) sind sofort nutzbar.
Wenn du irgendwann mehr als 3 Leute im Team hast, wechseln wir auf Revideo oder kaufen die Lizenz.

**Ehrlicher Hinweis:** Die Remotion-Lizenzseite selbst konnte ich aus meiner Arbeitsumgebung nicht öffnen (Netzwerk gesperrt). Die Angaben stammen aus mehreren Suchergebnissen, die das übereinstimmend sagen. Bitte vor dem ersten kommerziellen Reel einmal selbst auf [remotion.dev/license](https://remotion.dev/license) nachlesen.

Quellen: [Remotion Preise](https://www.remotion.dev/docs/pricing), [Remotion Lizenz](https://remotion.dev/license), [Remotion Firmenlizenz](https://www.remotion.dev/blog/company-licenses), [Remotion vs. Motion Canvas](https://www.remotion.dev/docs/compare/motion-canvas), [Vergleich Remotion/Motion Canvas/Revideo 2026](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026), [Ist Remotion kostenlos?](https://autoae.online/blog/is-remotion-free)

---

## 5. Aktuelle Best Practices

### YouTube (lange Videos)
- **Hook in den ersten 3–5 Sekunden**, und in den ersten ~30 s ein echter Nutzen, nicht nur ein Teaser.
- **Leerlauf raus** (Pausen, Wiederholungen, Abschweifungen). Aber: Ein guter Jump Cut entfernt *etwas*, er versteckt nicht nur eine Pause. Nicht über-schneiden, dein ruhiger Coaching-Stil passt zu deiner Zielgruppe.
- **Zoom-Wechsel** (100/108/115 %) bei Jump Cuts machen Sprünge angenehmer, alle paar Sekunden ein visueller Wechsel.
- **Untertitel:** groß, kontrastreich, Wort für Wort oder Phrase für Phrase. (Die oft genannten "+15–25 % Zuschauerbindung" sind unbelegt.)
- **Kapitel** mit Zeitstempeln helfen beim Finden und in der Google-Suche.
- Am Ende zählt deine eigene Zuschauerbindungs-Kurve in YouTube Studio mehr als jede Faustregel.

### Instagram Reels / YouTube Shorts
- **Die ersten 3 Sekunden entscheiden.** Test: erste 3 s **ohne Ton** anschauen. Versteht man den Hook? (Darum ist Text auf dem Video so wichtig.)
- **Länge:** Faustregel 7–30 s für Reichweite, bis 90 s ok. Über 90 s wird angeblich schlechter an neue Leute ausgespielt (Mosseri-Aussagen, nur indirekt belegt).
- **Safe Zone:** Es gibt keine offiziellen Zahlen für normale Posts, nur für Werbung. Quellen nennen oben 210–290 px, rechts ~190 px, unten 400–670 px frei lassen. **Deine Vorgabe (y 280–1250, x 90–900) ist strenger als fast alle Quellen, also sicher für Instagram UND Shorts.** Behalten wir so.
- **Konkrete, polarisierende Hooks** schlagen allgemeine (deine Erfahrung mit "in case no one told you…" passt dazu).

Quellen: [Hook & Pacing](https://air.io/en/youtube-hacks/advanced-retention-editing-cutting-patterns-that-keep-viewers-past-minute-8), [Retention-Editing (Mario Joos)](https://vidpros.com/retention-editing-what-you-can-learn-from-mario-joos/), [YouTube-Schnitt 2026](https://c-istudios.com/youtube-video-editing-in-2026-what-you-can-and-cant-do/), [Retention-Kurve lesen](https://dreamina.capcut.com/ai-video/youtube-audience-retention), [Shorts-Länge](https://opus.pro/blog/ideal-youtube-shorts-length-format-retention), [Reels-Länge 2026](https://klap.app/blog/how-long-should-reels-be), [Reels Best Practices](https://quso.ai/blog/instagram-reels-best-practices.html), [Safe-Zone-Leitfaden (DE)](https://adaptlypost.com/de/blog/social-media-safe-zones-2026-complete-guide), [Safe-Zone-Checker Reels](https://admanage.ai/instagram-reels-safe-zone), [Safe-Zone-Checker Shorts](https://www.upload-post.com/tools/safe-zone-checker/)

---

## 6. Kosten: Was ist gratis, was kostet Geld?

### Kostenlos (läuft auf deinem PC)
| Teil | Lizenz |
|---|---|
| ffmpeg (Schneiden, Encodieren, Lautheit) | frei |
| faster-whisper / WhisperX (Transkript) | MIT / BSD |
| MediaPipe (Gesicht, Blick, Hände) | Apache 2.0 |
| DeepFilterNet (Rauschentfernung) | MIT oder Apache 2.0, kommerziell erlaubt. Alternative ohne Installation: ffmpeg-Filter `arnndn` (RNNoise) |
| rapidfuzz, Satz-Embeddings | MIT / Apache 2.0 |
| FastAPI, React, Vite | MIT |
| Remotion | kostenlos für dich (siehe oben) |
| Schriften (Cormorant Garamond, Poppins, Caveat, Noto Serif Display) | Google Fonts, OFL, kostenlos auch kommerziell |

### Kostet Geld: nur die KI-Texte (Claude API)
Gebraucht für: Reel-Skripte aus Prompt (B2), Caption + 5 Hashtags + Cover-Text, YouTube-Titel/Beschreibung/Kapitel/Tags. **Alles andere (Schneiden, Transkript, Blick) läuft ohne KI-Kosten.**

Preise pro 1 Million Tokens (1 Token ≈ ¾ Wort), Stand Okt. 2026:

| Modell | Eingabe | Ausgabe | Einsatz |
|---|---|---|---|
| Claude Opus 5.5 (bestes) | 4 $ | 20 $ | Reel-Skripte, Hooks (Qualität zählt) |
| Claude Sonnet 5.5 | 2 $ | 10 $ | Alternative, halb so teuer |
| Claude Haiku 5.5 | 0,10 $ | 0,50 $ | Kleinkram (z. B. Tags) |

**Schätzung pro Monat** (z. B. 20 Reels + 4 YouTube-Videos, mit ein paar Überarbeitungen ≈ 60–80 KI-Aufrufe):
- Reel-Aufruf: ca. 6.000 Tokens rein (Stil-Regeln + Leitplanken + Transkript) und 2.500 raus → mit Opus ≈ **0,07 $**
- YouTube-Extras für 20 Min Video: ca. 10.000 rein, 3.000 raus → ≈ **0,10 $**
- **Gesamt: ca. 3–8 $ im Monat** mit dem besten Modell, ca. 2–4 $ mit Sonnet. Die Stil-Regeln werden zwischengespeichert ("Prompt-Caching"), das macht es nochmal billiger.
- Ein Anthropic-API-Konto braucht ein Guthaben (Prepaid, z. B. 5–10 $ aufladen). Kein Abo.

### Entscheidung (8.11.): so wenig bezahlen wie möglich → 0 € extra
Carina möchte möglichst keine weiteren Apps/Dienste bezahlen. Darum hat die App **drei KI-Wege**, Standard ist der kostenlose:

| Weg | Kosten | Qualität | Wie |
|---|---|---|---|
| **1. Kopieren & Einfügen mit claude.ai** (Standard) | 0 € extra (nutzt dein bestehendes Claude-Abo) | beste | App erstellt den fertigen Auftrag (mit Stil-Regeln und Leitplanken) → Knopf "Kopieren" → in claude.ai einfügen → Antwort zurück in die App einfügen. Die App prüft die Antwort (richtiges Format, genau 5 Hashtags, keine Heilversprechen). |
| 2. Lokale KI (Ollama, offene Modelle wie Qwen/Gemma) | 0 € | spürbar schwächer, v. a. bei deutschen Hooks; braucht guten PC (16 GB RAM+) | läuft komplett auf deinem PC, automatisch |
| 3. Claude API | ca. 3–8 $/Monat | beste, vollautomatisch | nur falls dir das Kopieren irgendwann zu umständlich wird |

Hinweis: Ein claude.ai-Abo kann technisch nicht direkt von einer eigenen App benutzt werden, deshalb der Kopier-Weg.

Auch sonst gilt: **kein Abo nötig** für ffmpeg, Whisper, MediaPipe, Remotion (für dich gratis), Schriften. CapCut Pro brauchst du für diese Abläufe nicht mehr; die Cover macht die App selbst (Canva bleibt optional).

### Andere mögliche Kosten (ehrlich)
- **Strom/Zeit:** Ohne Nvidia-Grafikkarte dauert die Transkription auf der CPU etwa 0,5–1x Videolänge mit dem Modell `small` (30 Min Video ≈ 15–30 Min). Mit GPU wenige Minuten.
- **Später online stellen:** Ein Server mit GPU kostet ca. 30–150 €/Monat. Ohne GPU (nur Vorschau, Rendern weiter lokal) ca. 5–20 €/Monat. Erst entscheiden, wenn es lokal gut läuft.
- **Metricool:** hast du schon. Direkte Übergabe nur, wenn deren Schnittstelle Video-Uploads erlaubt (prüfen wir in Meilenstein 7).
- **Remotion:** erst Kosten, wenn dein Team > 3 Personen wird.

Quellen: Claude-Preise aus der offiziellen Anthropic-Modellübersicht (Stand 06.10.2026, [Preisseite](https://platform.claude.com/docs/en/about-claude/pricing)), [DeepFilterNet Lizenz](https://github.com/lucribas/deepfilternet), [deepfilter-multimedia](https://pypi.org/project/deepfilter-multimedia/)
