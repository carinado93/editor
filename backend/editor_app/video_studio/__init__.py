"""Video Studio: Drone Cutter (automatischer Schnitt von Drohnen-Clips) und später der allgemeine Clip-Editor.

Module:
  analysis  Szenen, Qualität pro Moment (Schärfe, ruhige Bewegung, Helligkeit, Farbe), Helden-Momente
  beats     Takt/BPM der Musik (eigene numpy-Umsetzung, keine schwere Abhängigkeit)
  planner   welche Momente in welcher Reihenfolge und Länge (Reel 9:16 / YouTube 16:9), Schnitte auf dem Takt
  color     Farbe: alle Einstellungen einer Aufnahme werden zu EINER .cube-LUT gebacken (Vorschau = Export)
  text      Ort-Titel im Reel-Intro (dünn, Großbuchstaben, sehr weite Laufweite, Animation)
  music     Musik-Bibliothek (assets/music), Auswahl nach Stimmung/Länge, Kürzen, Blenden, Ducking
  render    ffmpeg: Aufnahmen schneiden, Farbe, Format, Titel, Musik → MP4
  store     Projekte unter daten/studio/<sid>/state.json
"""
