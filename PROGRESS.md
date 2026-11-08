# Fortschritt

## Stand: 7. November 2026

**Phase:** Recherche fertig, Bauplan wartet auf Carinas OK.

### Erledigt
- [x] Recherche → `RESEARCH.md` (Tools, Blick-Erkennung, Retakes, Remotion-Lizenz, Best Practices, Kosten)
- [x] Bauplan mit 7 Meilensteinen → `BAUPLAN.md`

### Wartet auf Carina
- [ ] OK zum Bauplan (oder Änderungswünsche)
- [ ] Grafikkarte + RAM des Windows-PCs
- [ ] Testvideos (kurzes YouTube-Rohvideo mit Retake, ein Reel)
- [x] Eigenes Repo `carinado93/editor` angelegt, Dateien umgezogen
- [ ] Schriften: Google Fonts ok?
- [ ] Ausgabe von `ollama list` (welche Modelle sind installiert?)

### Nächster Schritt
Meilenstein 1: Grundgerüst, `start.bat`, Upload, Transkription mit Wort-Zeitstempeln, einfache Review-Ansicht.

### Entscheidungen
- 8.11.: **So wenig bezahlen wie möglich.** KI-Texte standardmäßig per "Kopieren & Einfügen" in claude.ai (bestehendes Abo, 0 € extra). Ollama (lokal) und Claude API nur als optionale Einstellung. Keine kostenpflichtigen Dienste einbauen.
- 8.11.: **Ollama ist schon installiert.** Plan: Ollama automatisch für einfache Texte (Kapitel, Tags, Beschreibung, Caption-Entwurf, Retake-Zweitmeinung); für Hooks und Reel-Skripte zusätzlich Knopf "in claude.ai verbessern" (Kopieren & Einfügen). Offen: welche Modelle (`ollama list`), GPU/RAM.
- 8.11.: Carina hat **Canva und CapCut** schon. Die App braucht beide nicht, liefert aber passende Dateien: für CapCut MP4 + SRT (+ Text-Ebenen als transparente PNG/MOV, falls sinnvoll), für Canva das Cover zusätzlich als PNG ohne Text zum Weiterbearbeiten.

### Notizen für die nächste Sitzung
- Retake-Logik aus `carinado93/app: tools/audio/clean_recordings.py` (Signalwörter + Satzanfang-Vergleich) wiederverwenden.
- Cover-Rotation: zuletzt lila → nächstes Cover **hell**, dann oliv.
- Remotion-Lizenzseite war aus der Arbeitsumgebung nicht erreichbar; Carina soll sie einmal selbst prüfen.
- Die Retake-Logik liegt im Repo `carinado93/app` unter `tools/audio/clean_recordings.py`.
