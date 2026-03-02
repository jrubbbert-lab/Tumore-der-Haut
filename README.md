# Medizin Lernhelfer

Digitale Tafel-Sicherung für Medizin- und Pflegeschüler.
Die Lehrkraft erarbeitet mit der Klasse strukturierte Krankheitsbilder –
Claude analysiert die Schülerantworten und unterstützt beim fachlichen Ergänzen.

---

## Voraussetzungen

- **Python 3.11 oder neuer** – Download: https://www.python.org/downloads/
  _(Bei der Installation „Add Python to PATH" aktivieren)_
- **Claude API-Schlüssel** – kostenlos registrieren unter https://console.anthropic.com

---

## Installation

### Windows

```cmd
# 1. Ins Projektverzeichnis wechseln
cd "Pfad\zu\medizin_lernhelfer"

# 2. Abhängigkeiten installieren
pip install -r requirements.txt

# 3. App starten
python main.py
```

### macOS

```bash
# 1. Ins Projektverzeichnis wechseln
cd /Pfad/zu/medizin_lernhelfer

# 2. Abhängigkeiten installieren
pip3 install -r requirements.txt

# 3. App starten
python3 main.py
```

---

## Wissensbasis einrichten

Öffne die Datei `knowledge_base.txt` und füge den relevanten Text aus
**„i care Pathophysiologie"** ein (Kapitel zu Malignem Melanom,
Plattenepithelkarzinom und Basalzellkarzinom).

Die Datei ist mit Kommentaren vorgegeben – einfach den Buchtext darunter einfügen.
Das Tool weist Claude explizit an, **ausschließlich diesen Text** als Quelle zu
verwenden und kein eigenes Wissen hinzuzufügen.

---

## API-Schlüssel eingeben

1. App starten
2. Oben rechts auf **⚙ API-Schlüssel** klicken
3. Schlüssel eingeben und speichern
   _(Der Schlüssel wird lokal in `~/.medizin_lernhelfer/config.ini` gespeichert)_

---

## Bedienung

| Schritt | Aktion |
|---------|--------|
| 1 | Erkrankung auswählen (Startbildschirm) |
| 2 | Schülerantwort in das Textfeld eingeben |
| 3 | **Analysieren** klicken → Claude gibt Feedback |
| 4 | Fehlende Aspekte und überarbeitete Version erscheinen |
| 5 | **Weiter** zur nächsten Kategorie |
| 6 | Am Ende: **Als PDF exportieren** |

**Tastenkürzel:** `Enter` in Dialogen bestätigt die Eingabe.

---

## PDF-Export

Das exportierte PDF enthält für jede Kategorie:

- **Schülerantwort** (blau hinterlegt)
- **Fehlende Aspekte** (orange hinterlegt)
- **Überarbeitete Version** (grün hinterlegt)

Das PDF ist für den Druck auf A4 optimiert.

---

## Projektstruktur

```
medizin_lernhelfer/
├── main.py             ← Hauptprogramm
├── knowledge_base.txt  ← Hier i-care-Text einfügen
├── requirements.txt    ← Python-Abhängigkeiten
└── README.md           ← Diese Anleitung
```

---

## Als ausführbare Datei bauen (optional)

Falls du eine `.exe` (Windows) oder `.app` (macOS) ohne Python-Installation
erstellen möchtest:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
# Ergebnis liegt in dist/main.exe (Windows) bzw. dist/main (macOS)
```

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` ausführen |
| App startet nicht (macOS) | `python3` statt `python` verwenden |
| API-Fehler 401 | API-Schlüssel prüfen (⚙ oben rechts) |
| Keine Wissensbasis | `knowledge_base.txt` mit i-care-Text befüllen |
| PDF lässt sich nicht speichern | Schreibrechte im Zielordner prüfen |
