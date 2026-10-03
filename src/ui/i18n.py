"""Small runtime localization helper for the desktop UI."""

from __future__ import annotations

import json
import logging
import os
import sys
import tkinter.ttk as ttk
from pathlib import Path

logger = logging.getLogger(__name__)

_LANGUAGE = "en"
_EN_TO_DE = {
    "Advanced Settings": "Erweiterte Einstellungen",
    "⚙️ Advanced": "⚙️ Einstellungen",
    "🤖 Let me handle it (Auto)": "🤖 Automatik übernehmen",
    "Resolution:": "Auflösung:",
    "File": "Datei",
    "Trash Red (<=30%)": "Rote Dateien (<=30%) in Papierkorb",
    "Trash <=50%": "Dateien <=50% in Papierkorb",
    "Trash <=": "In Papierkorb verschieben bei <=",
    "Trash Custom": "Benutzerdefiniert in Papierkorb",
    "Source": "Quelle",
    "Duration": "Dauer",
    "✅  Converted Files": "✅  Konvertierte Dateien",
    "empty": "leer",
    "Clear": "Leeren",
    "Search...": "Suchen …",
    "🧹 Cleanup Assistant": "🧹 Aufräumhilfe",
    "🚚 Move Converted & Clear List": "🚚 Konvertierte verschieben und Liste leeren",
    "Move good files to final destination": "Gute Dateien ins Zielverzeichnis verschieben",
    "This is a separate folder from the workshop folder above — e.g. your Batocera share or USB stick. Files are only moved here when you click the button below.": "Das ist ein eigener Ordner, getrennt vom Werkstatt-Ordner oben — z. B. dein Batocera-Share oder ein USB-Stick. Dateien werden erst hierhin verschoben, wenn du den Button unten anklickst.",
    "Please select a final destination folder first.": "Bitte zuerst einen endgültigen Zielordner auswählen.",
    "Final destination folder does not exist:\n{path}": "Endgültiger Zielordner existiert nicht:\n{path}",
    "Move": "Verschieben",
    "The converted list is empty.": "Die Liste der konvertierten Dateien ist leer.",
    "Move incomplete": "Verschieben unvollständig",
    "{count} file(s) could not be moved and remain in the list. See the log.": "{count} Datei(en) konnten nicht verschoben werden und bleiben in der Liste. Details stehen im Protokoll.",
    "🎞️  DMD GIF Converter": "🎞️  DMD-GIF-Konverter",
    "➕ Dateien": "➕ Dateien",
    "📂 Ordner": "📂 Ordner",
    "✕ Entfernen": "✕ Entfernen",
    "🔄 Ordner neu einlesen": "🔄 Ordner neu einlesen",
    "🎮  LaunchBox-Logos (PNG) laden": "🎮  LaunchBox-Logos (PNG) laden",
    "🌐  ScreenScraper-Medien suchen": "🌐  ScreenScraper-Medien suchen",
    "🕹  Batocera-Medien importieren": "🕹  Batocera-Medien importieren",
    "Quelle": "Quelle",
    "Dauer": "Dauer",
    "Status": "Status",
    "🖥️  Preview  —  SOURCE → AUTO → DMD": "🖥️  Vorschau  —  QUELLE → AUTO → DMD",
    "🔄 All": "🔄 Alle",
    "▶ Source": "▶ Quelle",
    "🎯 Auto": "🎯 Auto",
    "🔬 DMD": "🔬 DMD",
    "💡 LED Sim ✓": "💡 LED-Simulation ✓",
    "✂️  Trim  (single-file only)": "✂️  Zuschneiden (nur einzelne Datei)",
    "Start": "Start",
    "End": "Ende",
    "↺ Reset": "↺ Zurücksetzen",
    "🚀  Convert": "🚀  Konvertieren",
    "▶  Convert selected file": "▶  Ausgewählte Datei konvertieren",
    "▶  Convert {count} selected files": "▶  {count} ausgewählte Dateien konvertieren",
    "Auto-Trash ≤": "Automatisch in Papierkorb ≤",
    "⏹ Force Stop": "⏹ Abbrechen",
    "🎨  Content mode": "🎨  Inhaltsmodus",
    "Mode": "Modus",
    "⚡  Parallelism": "⚡  Parallelität",
    "Workers (CPU)": "Prozesse (CPU)",
    "📐  Dimensions": "📐  Abmessungen",
    "Bypass framing for equivalent ratio": "Ausschnitt bei gleichem Seitenverhältnis überspringen",
    "📜  Scroll": "📜  Bildlauf",
    "Scroll speed": "Bildlaufgeschwindigkeit",
    "Top crop (%)": "Oben abschneiden (%)",
    "Bottom crop (%)": "Unten abschneiden (%)",
    "Scroll cycles": "Bildlaufzyklen",
    "🎬  Render FPS": "🎬  Ausgabe-FPS",
    "FPS minimum": "FPS (Minimum)",
    "FPS maximum": "FPS (Maximum)",
    "━━  🎯  Auto Action Framing (pre-ffmpeg)": "━━  🎯  Automatischer Bildausschnitt (vor FFmpeg)",
    "Enable cinematic auto-framing before ffmpeg (default OFF)": "Automatischen Bildausschnitt aktivieren (standardmäßig aus)",
    "Detection mode": "Erkennungsmodus",
    "Subject framing": "Motivausschnitt",
    "Enable dynamic zoom for all DMD sizes": "Dynamischen Zoom für alle DMD-Größen aktivieren",
    "Auto Detector Fallback (Person → Hybrid)": "Automatischer Erkennungswechsel (Person → Hybrid)",
    "DMD Visibility": "DMD-Sichtbarkeit",
    "DMD Readability": "DMD-Lesbarkeit",
    "Action strength": "Stärke der Bildführung",
    "🎛️  Colorimetry": "🎛️  Farbanpassung",
    "━━  💬  Text Overlay": "━━  💬  Textüberlagerung",
    "Enable Text Overlay": "Textüberlagerung aktivieren",
    "⚙️ Settings": "⚙️ Einstellungen",
    "━━  🖼️  Multi-Dalle / Tiling": "━━  🖼️  Mehrfach-DMD / Kachelung",
    "Dimensions Preset": "Größenvorgabe",
    "Custom Width": "Benutzerdefinierte Breite",
    "Custom Height": "Benutzerdefinierte Höhe",
    "━━  📍  Positioning": "━━  📍  Bildposition",
    "━━  ✨  Visual Effects": "━━  ✨  Bildeffekte",
    "🔧  Advanced Settings  ▼": "🔧  Erweiterte Einstellungen  ▼",
    "🔧  Advanced Settings  ▲": "🔧  Erweiterte Einstellungen  ▲",
    "All settings here are hidden by default.\n    Default values reproduce the standard v2.0 output unchanged.": "Diese Einstellungen sind standardmäßig ausgeblendet.\n    Standardwerte erhalten die Ausgabe der Version 2.0.",
    "Auto vertical scroll  (default — matches standard behaviour)": "Automatischer vertikaler Bildlauf (Standardverhalten)",
    "📤 Output / Destination folder": "📤 Ausgabeordner / Zielordner",
    "Workshop folder (conversion output)": "Werkstatt-Ordner (Konvertierungsziel)",
    "New conversions are written here so you can review their score before moving the good ones to a final folder.": "Neue Konvertierungen landen hier, damit du die Bewertung prüfen kannst, bevor du die guten Dateien in einen endgültigen Ordner verschiebst.",
    "Final destination folder": "Endgültiger Zielordner",
    "Choose a final destination folder to enable moving files there.": "Wähle einen endgültigen Zielordner, um Dateien dorthin verschieben zu können.",
    "Target Resolution:": "Zielauflösung:",
    "Choose output folder before converting": "Vor dem Konvertieren einen Ausgabeordner wählen",
    "Choose output folder": "Ausgabeordner auswählen",
    "Select output folder": "Ausgabeordner auswählen",
    "Output folder: choose a folder before converting": "Ausgabeordner: Vor dem Konvertieren einen Ordner wählen",
    "Output folder: {path}": "Ausgabeordner: {path}",
    "Convert selected file": "Ausgewählte Datei konvertieren",
    "Convert all": "Alle konvertieren",
    "Batch folder": "Ordner stapelweise konvertieren",
    "Output / Destination folder": "Ausgabeordner / Zielordner",
    "Category": "Kategorie",
    "Interface language": "Sprache der Oberfläche",
    "Language": "Sprache",
    "Settings": "Einstellungen",
    "Colorimetry": "Farbanpassung",
    "Contrast": "Kontrast",
    "Saturation": "Farbsättigung",
    "Brightness": "Helligkeit",
    "Gamma": "Gamma",
    "Sharpen Lum": "Schärfe Helligkeit",
    "Sharpen Chr": "Schärfe Farbe",
    "Images": "Bilder",
    "Videos and GIFs": "Videos und GIFs",
    "Direkte Verbindung zur Batocera-Netzwerkfreigabe": "Direkte Verbindung zur Batocera-Netzwerkfreigabe",
    "Welche Batocera-Systeme importieren?": "Welche Batocera-Systeme importieren?",
    "Alle auswählen": "Alle auswählen",
    "Auswahl importieren": "Auswahl importieren",
    "Systemliste konnte nicht geladen werden": "Systemliste konnte nicht geladen werden",
    "Videos und GIFs": "Videos und GIFs",
    "Artwork (Cover, Marquee, Fanart, Thumbnail)": "Artwork (Cover, Logo, Hintergrund, Vorschaubild)",
    "Sprache": "Sprache",
    "Logo": "Logo",
    "Search": "Suchen",
    "Load": "Laden",
    "Download": "Herunterladen",
    "Cancel": "Abbrechen",
    "Close": "Schließen",
    "Browse": "Durchsuchen",
    "Folder": "Ordner",
    "Files": "Dateien",
    "Remove": "Entfernen",
    "Source files": "Quelldateien",
    "Preview": "Vorschau",
    "Converted Files": "Konvertierte Dateien",
    "Automatically determines the optimal number of CPU workers based on your system.": "Ermittelt automatisch die passende Anzahl an CPU-Arbeitern für dein System.",
    "Number of concurrent CPU threads to use during conversion.\nHigher is faster but uses more system resources.": "Anzahl gleichzeitig verwendeter CPU-Threads.\nMehr Threads können schneller sein, benötigen aber mehr Ressourcen.",
    "Master switch for Cinematic Auto-Framing.\nUses YOLO AI to track the subject and dynamically frame the 128x32 view.": "Hauptschalter für den automatischen Bildausschnitt.\nVerfolgt Motive mit YOLO und passt den 128×32-Ausschnitt dynamisch an.",
    "Group: frames multiple detected people or moving regions together, useful for arcade games with several characters.\nPrimary: follows the main detected subject or motion region.": "Gruppe: fasst mehrere erkannte Personen oder Bewegungsbereiche zusammen – passend für Spiele mit mehreren Figuren.\nHauptmotiv: folgt dem wichtigsten erkannten Motiv oder Bewegungsbereich.",
    "Dynamic zoom is automatic for 32×64 portrait output. Enable this option to also use it for other output sizes.": "Bei Hochformat-Ausgabe 32×64 ist dynamischer Zoom automatisch aktiv. Mit dieser Option wird er auch für andere Größen verwendet.",
    "Limits automatic zooms based on the resulting image's visibility and readability on a DMD display.\nPrevents zooming into blurry messes.": "Begrenzt den automatischen Zoom anhand der Sichtbarkeit und Lesbarkeit auf dem DMD.\nVerhindert unbrauchbar unscharfe Ausschnitte.",
    "English": "Englisch",
    "German": "Deutsch",
    "Error": "Fehler",
    "Could not save the language preference: {error}": "Spracheinstellung konnte nicht gespeichert werden: {error}",
    "Please select a file from the list first.": "Bitte zuerst eine Datei aus der Liste auswählen.",
    "The file list is empty.": "Die Dateiliste ist leer.",
    "A conversion is already running.": "Eine Konvertierung läuft bereits.",
    "No supported files found in this folder.": "In diesem Ordner wurden keine unterstützten Dateien gefunden.",
    "Finished — {success} succeeded, {failed} failed": "Fertig — {success} erfolgreich, {failed} fehlgeschlagen",
    "Batch finished — {success} succeeded, {failed} failed": "Stapelverarbeitung fertig — {success} erfolgreich, {failed} fehlgeschlagen",
    "Choose an existing output folder before converting.": "Vor dem Konvertieren einen vorhandenen Ausgabeordner auswählen.",
    "Output: choose a folder before converting": "Ausgabe: Vor dem Konvertieren einen Ordner wählen",
    "Converting…": "Wird konvertiert …",
    "The language will change after restarting the app.": "Die Sprache wird nach einem Neustart der App geändert.",
    "Restart required": "Neustart erforderlich",
    "Invalid threshold": "Ungültiger Grenzwert",
    "Output filename conflicts": "Konflikte bei Ausgabedateinamen",
    "This batch would overwrite existing output or two sources share a name. Choose another output folder or rename the source files.": "Dieser Stapellauf würde vorhandene Ausgaben überschreiben oder zwei Quellen haben denselben Namen. Wähle einen anderen Ausgabeordner oder benenne die Quelldateien um.",
    "Invalid output folder": "Ungültiger Ausgabeordner",
    "The selected output folder does not exist.": "Der ausgewählte Ausgabeordner ist nicht vorhanden.",
    "Enter a whole-number score from 0 to 100.": "Bitte eine ganze Bewertungszahl von 0 bis 100 eingeben.",
    "The score threshold must be between 0 and 100.": "Der Bewertungsgrenzwert muss zwischen 0 und 100 liegen.",
    "Confirm automatic cleanup": "Automatisches Aufräumen bestätigen",
    "After this batch, move only newly created GIFs scoring {threshold}% or less to the system trash? Existing files will not be touched.": "Nach diesem Stapellauf nur neu erstellte GIFs mit einer Bewertung von höchstens {threshold}% in den Papierkorb verschieben? Vorhandene Dateien bleiben unberührt.",
    "Cannot move to trash": "Verschieben in den Papierkorb nicht möglich",
    "The system-trash integration is unavailable. No files were deleted.": "Der Papierkorb ist nicht verfügbar. Es wurden keine Dateien gelöscht.",
    "Some files could not be moved": "Einige Dateien konnten nicht verschoben werden",
    "{count} file(s) remain in the converted list. See the log for details.": "{count} Datei(en) verbleiben in der konvertierten Liste. Details stehen im Protokoll.",
    "Preview is limited to 10 seconds; conversion exports the selected or full duration.": "Die Vorschau ist auf 10 Sekunden begrenzt; beim Export wird der ausgewählte oder gesamte Zeitraum verwendet.",
    "Busy": "Beschäftigt",
    "Info": "Hinweis",
    "Starting": "Wird gestartet",
    "Conversion": "Konvertierung",
    "Moments": "Momente",
    "{done}/{total} processed — {succeeded} succeeded, {failed} failed": "{done}/{total} bearbeitet — {succeeded} erfolgreich, {failed} fehlgeschlagen",
    "Batch failed: {error}": "Stapelverarbeitung fehlgeschlagen: {error}",
    "Cancelled — {success} succeeded, {failed} failed, {pending} not started": "Abgebrochen — {success} erfolgreich, {failed} fehlgeschlagen, {pending} nicht gestartet",
    "Output: {path}": "Ausgabe: {path}",
    "Stopping…": "Wird angehalten …",
    "💡 LED Sim": "💡 LED-Simulation",
    "⏳  Converting…": "⏳  Wird konvertiert …",
    "Videos/GIFs": "Videos/GIFs",
    "System / IP": "System / IP",
    "Connecting to Batocera share…": "Verbindung zur Batocera-Freigabe wird hergestellt …",
    "Which Batocera systems should be imported?": "Welche Batocera-Systeme sollen importiert werden?",
    "First, only the system folders under “roms” are listed. Only selected systems and their scraped media will be imported. Type a first letter to jump to that system.": "Zuerst werden nur die Systemordner unter „roms“ aufgelistet. Nur ausgewählte Systeme und deren Medien werden importiert. Tippe den Anfangsbuchstaben, um zu einem System zu springen.",
    "Direct connection to the Batocera network share": "Direkte Verbindung zur Batocera-Netzwerkfreigabe",
    "Existing game lists and their <video> files under “roms” will be read.": "Vorhandene Spielelisten und deren <video>-Dateien unter „roms“ werden gelesen.",
    "The default login is root / linux. The server, share, and username are stored locally. The password is saved only if you choose to use the keychain.": "Standardanmeldung: root / linux. Server, Freigabe und Benutzername werden lokal gespeichert. Das Passwort wird nur mit Auswahl des Schlüsselbunds dauerhaft gespeichert.",
    "System folders are being read … {count} found": "Systemordner werden gelesen … {count} gefunden",
    "{completed} media processed; {loaded} loaded — {filename}": "{completed} Medien bearbeitet; {loaded} geladen — {filename}",
    "Import failed: {error}": "Import fehlgeschlagen: {error}",
    "Import complete: {count} media found.": "Import abgeschlossen: {count} Medien gefunden.",
    "No media imported.": "Keine Medien importiert.",
    "Selected systems ({count}) will be read; found media is copied to the local cache.": "Ausgewählte Systeme ({count}) werden gelesen; gefundene Medien kommen in den lokalen Cache.",
    "System {current}/{total}: {path} — reading game list …": "System {current}/{total}: {path} — Spieleliste wird gelesen …",
    "Cancelled. {count} file(s) were added.": "Abgebrochen. {count} Datei(en) wurden übernommen.",
    "Import complete: {count} media found. ": "Fertig: {count} Medium/Medien gefunden. ",
    "No media imported. ": "Keine Medien übernommen. ",
    "No game list for: {systems}. ": "Keine Spieleliste für: {systems}. ",
    "{count} games read, but no <video>/<image>/<marquee>/<fanart> entries were found. ": "{count} Spiele gelesen, aber keine <video>/<image>/<marquee>/<fanart>-Einträge gefunden. ",
    "{count} media path(s) could not be found on the share. ": "{count} Medienpfad(e) konnten auf der Freigabe nicht gefunden werden. ",
    "The game list contains no game entries. ": "Die Spieleliste enthält keine Spieleinträge. ",
    "Read: {games} games, {videos} video and {images} image references.": "Gelesen: {games} Spiele, {videos} Video- und {images} Bildverweise.",
    "Import finished without results.": "Import ohne Ergebnis beendet.",
    "Ready": "Bereit",
}
_DE_TO_EN = {
    "Erweiterte Einstellungen": "Advanced Settings",
    "Abbrechen": "Cancel",
    "Schließen": "Close",
    "Auswahl importieren": "Import selection",
    "Wartend": "Waiting",
    "Wird konvertiert": "Converting",
    "Fertig": "Done",
    "Fehler": "Error",
    "Quelldateien": "Source files",
    "Alle Medien": "All media",
    "Videos/GIFs": "Videos/GIFs",
    "Bilder": "Images",
    "Medien importieren": "Import media",
    "Ausgabeordner auswählen": "Choose output folder",
    "PNG-Darstellung:": "PNG display:",
    "W:": "W:",
    "H:": "H:",
    "Datei": "File",
    "GIF-Suche": "GIF search",
    "Suchbegriff …": "Search term …",
    "Anz.": "Qty",
    "Suchen": "Search",
    "⚠ Suchpakete fehlen; siehe Hinweise beim Suchen": "⚠ Search packages missing; see search hints",
    "⬇  GIFs werden geladen …": "⬇  Downloading GIFs …",
    "⏳…": "⏳…",
    "Lade die Plattformliste, wähle eine oder mehrere Plattformen aus und füge deren Clear Logos als PNG zu den Quelldateien hinzu.": "Load the platform list, select one or more platforms, and add their Clear Logos as PNG files to the source files.",
    "Beim ersten Mal werden die LaunchBox-Metadaten geladen. Danach nutzt die App den lokalen Cache. Bereits geladene Logos werden übersprungen.": "The LaunchBox metadata is downloaded the first time. Later, the local cache is used. Already downloaded logos are skipped.",
    "Plattformen laden": "Load platforms",
    "Lade die Plattformliste": "Loading platform list",
    "LaunchBox-Plattformliste wird aus dem lokalen Metadatenarchiv gelesen …": "Reading the LaunchBox platform list from the local metadata archive …",
    "Plattformen aktualisieren": "Refresh platforms",
    "Auswahl herunterladen": "Download selection",
    "Lade herunter …": "Downloading …",
    "LaunchBox-Logos herunterladen": "Download LaunchBox logos",
    "▼ Filter und Suchquelle": "▼ Filters and search source",
    "▲ Filter ausblenden": "▲ Hide filters",
    "Suchquelle": "Search source",
    "Min.:": "Min.:",
    "✕ Abbrechen": "✕ Cancel",
    "🗑  Quelldateien leeren": "🗑  Clear source files",
    "Bereit": "Ready",
    "Datei(en)": "file(s)",
    "Trash Red (<=30%)": "Discard red (<=30%)",
    "Trash <=50%": "Discard <=50%",
    "Trash <=": "Discard <=",
    "Trash Custom": "Discard custom",
    "Selected systems": "Ausgewählte Systeme",
    "Systeme auswählen": "Select systems",
    "Verbinde und lese Systemordner …": "Connecting and reading system folders …",
    "Systeme gefunden. Wähle ein oder mehrere aus.": "systems found. Select one or more.",
    "Import wird vorbereitet …": "Preparing import …",
    "Abbruch angefordert; laufende Datei wird noch beendet …": "Cancellation requested; the current file will finish first …",
    "Abbruch läuft …": "Cancelling …",
    "Import ohne Ergebnis beendet.": "Import finished without results.",
    "Bitte mindestens ein System auswählen.": "Select at least one system.",
    "Bitte Videos/GIFs und/oder Artwork auswählen.": "Select videos/GIFs and/or artwork.",
    "Sprache der Oberfläche": "Interface language",
    "Englisch": "English",
    "Deutsch": "German",
    "1️⃣ 📁  Quelldateien": "1️⃣ 📁  Source files",
    "➕ Dateien": "➕ Files",
    "📂 Ordner": "📂 Folder",
    "✕ Entfernen": "✕ Remove",
    "🔄 Ordner neu einlesen": "🔄 Rescan folder",
    "🎮  LaunchBox-Logos (PNG) laden": "🎮  Load LaunchBox logos (PNG)",
    "🌐  ScreenScraper-Medien suchen": "🌐  Search ScreenScraper media",
    "🕹  Batocera-Medien importieren": "🕹  Import Batocera media",
    "Klick: Vorschau · Strg/Umschalt: Mehrfachauswahl\nMehrere markiert? → Alle werden mit „Ausgewählte Datei(en) konvertieren“ umgewandelt · Entf: Auswahl entfernen": "Click: preview · Ctrl/Shift: select multiple\nMultiple selected? → All are converted with \"Convert selected file(s)\" · Delete: remove selection",
    "Direkte Verbindung zur Batocera-Netzwerkfreigabe": "Direct connection to Batocera network share",
    "Batocera-Verbindung": "Batocera connection",
    "Batocera-Systeme auswählen": "Select Batocera systems",
    "Verbinden und importieren": "Connect and import",
    "Es werden vorhandene Spielelisten und deren <video>-Dateien unter „roms“ gelesen.": "Existing game lists and their <video> files under “roms” will be read.",
    "Freigabe": "Share",
    "Benutzername": "Username",
    "Passwort": "Password",
    "Passwort im System-Schlüsselbund speichern": "Save password in system keychain",
    "Bitte Server und Freigabe angeben.": "Enter a server and share.",
    "Welche Batocera-Systeme importieren?": "Which Batocera systems should be imported?",
    "Keine Systemordner im Batocera-Share „roms“ gefunden.": "No system folders found in the Batocera “roms” share.",
    "Alle auswählen": "Select all",
    "Videos und GIFs": "Videos and GIFs",
    "Artwork (Cover, Marquee, Fanart, Thumbnail)": "Artwork (cover, marquee, fan art, thumbnail)",
    "Nur ausgewählte Systeme und darin gescrapte Medien werden importiert.": "Only selected systems and their scraped media will be imported.",
    "Systemordner werden gelesen … {count} gefunden": "Reading system folders … {count} found",
    "Sprache": "Language",
    "Logo": "Logo",
    "⚙️ Einstellungen": "⚙️ Settings",
    "Auflösung:": "Resolution:",
    "Quelle": "Source",
    "Dauer": "Duration",
    "Kategorie": "Category",
    "Konvertierte Dateien": "Converted Files",
    "Leeren": "Clear",
    "Suchen …": "Search...",
    "🧹 Aufräumhilfe": "🧹 Cleanup Assistant",
    "Ausgabeordner / Zielordner": "Output / Destination folder",
    "🖥️  Vorschau  —  QUELLE → AUTO → DMD": "🖥️  Preview  —  SOURCE → AUTO → DMD",
    "Ausgewählte Datei konvertieren": "Convert selected file",
    "Alle konvertieren": "Convert all",
    "Ordner stapelweise konvertieren": "Batch folder",
    "Vor dem Konvertieren einen Ausgabeordner wählen": "Choose output folder before converting",
    "⚡  Parallelität": "⚡  Parallelism",
    "Prozesse (CPU)": "Workers (CPU)",
    "Bildlaufgeschwindigkeit": "Scroll speed",
    "Oben abschneiden (%)": "Top crop (%)",
    "Unten abschneiden (%)": "Bottom crop (%)",
    "━━  💬  Textüberlagerung": "━━  💬  Text Overlay",
    "Textüberlagerung aktivieren": "Enable Text Overlay",
    "Konvertierung": "Conversion",
    "Momente": "Moments",
    "Systeme laden": "Load systems",
    "Spieltitel, z. B. Sonic the Hedgehog": "Game title, e.g. Sonic the Hedgehog",
    "Spiele suchen": "Search games",
    "Treffer": "Matches",
    "Unterstützte Medien": "Supported media",
    "Medien für ausgewähltes Spiel laden": "Load media for selected game",
    "Auswahl laden und übernehmen": "Download and add selection",
    "ScreenScraper-Medien suchen": "Search ScreenScraper media",
    "Bereit.": "Ready.",
}
from src.ui.i18n_extra import DE_TO_EN as _EXTRA_DE_TO_EN, EN_TO_DE as _EXTRA_EN_TO_DE

_EN_TO_DE.update(_EXTRA_EN_TO_DE)
_DE_TO_EN.update(_EXTRA_DE_TO_EN)
_DE_TO_EN_REVERSE = {value: key for key, value in _EN_TO_DE.items()}


def language_path() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "DMD_GIF_Converter" / "preferences.json"


def load_language() -> str:
    path = language_path()
    if not path.exists():
        return "en"
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read UI preferences from %s: %s", path, exc)
        return "en"
    language = values.get("language") if isinstance(values, dict) else None
    return language if language in {"en", "de"} else "en"


def save_language(language: str) -> None:
    if language not in {"en", "de"}:
        raise ValueError(f"Unsupported UI language: {language}")
    path = language_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    try:
        values = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                values = existing
        values["language"] = language
        temporary_path.write_text(
            json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(path)
    except (OSError, json.JSONDecodeError):
        temporary_path.unlink(missing_ok=True)
        raise


def set_language(language: str) -> None:
    global _LANGUAGE
    if language not in {"en", "de"}:
        raise ValueError(f"Unsupported UI language: {language}")
    _LANGUAGE = language


def get_language() -> str:
    return _LANGUAGE


def tr(text: str) -> str:
    if _LANGUAGE == "de":
        return _EN_TO_DE.get(text, text)
    return _DE_TO_EN.get(text, _DE_TO_EN_REVERSE.get(text, text))


def localize_widget_tree(root) -> None:
    """Translate known widget labels without changing option values or callbacks."""
    stack = [root]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if isinstance(widget, ttk.Treeview):
            for column in ("#0", *widget["columns"]):
                try:
                    current = widget.heading(column, "text")
                    translated = tr(current)
                    if translated != current:
                        widget.heading(column, text=translated)
                except (KeyError, TypeError, ValueError):
                    continue
            continue
        if widget.__class__.__name__ in {"CTkOptionMenu", "CTkComboBox"}:
            continue
        try:
            options = widget.keys()
        except (AttributeError, TypeError):
            continue
        if "text" in options:
            try:
                current = widget.cget("text")
                translated = tr(current)
                if translated != current:
                    widget.configure(text=translated)
            except (TypeError, ValueError):
                continue
        if "placeholder_text" in options:
            try:
                current = widget.cget("placeholder_text")
                translated = tr(current)
                if translated != current:
                    widget.configure(placeholder_text=translated)
            except (TypeError, ValueError):
                continue
