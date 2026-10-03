"""Additional UI translations (English <-> German), merged into src.ui.i18n."""

EN_TO_DE = {
    "Text Overlay Settings": "Text-Overlay-Einstellungen",
    "Auto-Action & Video Cutter Settings": "Auto-Action- und Video-Cutter-Einstellungen",
    "All": "Alle",
    "Generate AI Moments": "KI-Momente erzeugen",
    "📊 Show AI Report": "📊 KI-Bericht anzeigen",
    "Section 1 - Video Selection": "Abschnitt 1 – Videoauswahl",
    "No video selected": "Kein Video ausgewählt",
    "Duration: -- | Resolution: --": "Dauer: -- | Auflösung: --",
    "Select Video": "Video auswählen",
    "Use Current Video": "Aktuelles Video verwenden",
    "Section 2 - Detection Settings": "Abschnitt 2 – Erkennungseinstellungen",
    "Moments to Generate": "Zu erzeugende Momente",
    "Detection Criteria": "Erkennungskriterien",
    "Epic": "Episch",
    "Character": "Charakter",
    "Loopable": "Loopfähig",
    "Section 4 - Generation Settings": "Abschnitt 4 – Erzeugungseinstellungen",
    "Duration Range (s):": "Dauerbereich (s):",
    "Min": "Min.",
    "Max": "Max.",
    "Analyze FPS:": "Analyse-FPS:",
    "Analyze video at N frames per second.\n\nLower FPS = Faster processing time (skips more frames).\nHigher FPS = Better precision (analyzes more frames).\n\nDefault is 5.0 (analyzes 1 frame out of 5 on a 25fps video).":
        "Analysiert das Video mit N Bildern pro Sekunde.\n\nNiedrigere FPS = schnellere Verarbeitung (mehr Bilder werden übersprungen).\nHöhere FPS = höhere Genauigkeit (mehr Bilder werden analysiert).\n\nStandard ist 5,0 (analysiert 1 von 5 Bildern bei einem 25-fps-Video).",
    "Auto Action Framing": "Auto-Action-Bildausschnitt",
    "Optimize for DMD": "Für DMD optimieren",
    "No Video Loaded": "Kein Video geladen",
    "[ Set IN Point": "[ IN-Punkt setzen",
    "Set OUT Point ]": "OUT-Punkt setzen ]",
    "Selected: 00.0s — 05.0s": "Ausgewählt: 00,0 s — 05,0 s",
    "▶ Play Selection": "▶ Auswahl abspielen",
    "✂️ Add Manual Moment": "✂️ Manuellen Moment hinzufügen",
    "⏸ Pause": "⏸ Pause",
    "Analyzing...": "Analysiere …",
    "Select a video and generate AI moments.": "Video auswählen und KI-Momente erzeugen.",
    "Select Video for AI Analysis": "Video für KI-Analyse auswählen",
    "No moments found.": "Keine Momente gefunden.",
    "Copy Report to Clipboard": "Bericht in die Zwischenablage kopieren",
    "Extracting...": "Extrahiere …",
    "Extracting moments to temporary files...": "Momente werden in temporäre Dateien extrahiert …",
    "▼  Log": "▼  Protokoll",
    "▶  Log": "▶  Protokoll",
    "Filter:": "Filter:",
    "Show All": "Alle anzeigen",
    "Text Content": "Textinhalt",
    "Text Color": "Textfarbe",
    "Text Position": "Textposition",
    "Font": "Schriftart",
    "Text Style": "Textstil",
    "Animation (Magic!)": "Animation (Zauberei!)",
    "Background box (dark box behind text)": "Hintergrundbox (dunkle Box hinter dem Text)",
    "Box opacity": "Box-Deckkraft",
    "🎬 Auto-Cutter (Extract Highlights)": "🎬 Auto-Cutter (Highlights extrahieren)",
    "Enable Auto-Cutter for long videos": "Auto-Cutter für lange Videos aktivieren",
    "    Automatically scans the video and extracts the best moments.\n    Creates multiple GIFs if Top N > 1.":
        "    Durchsucht das Video automatisch und extrahiert die besten Momente.\n    Erzeugt mehrere GIFs, wenn Top N > 1.",
    "🎯 Auto-Action Framing": "🎯 Auto-Action-Bildausschnitt",
    "Enable cinematic auto-framing": "Filmischen Auto-Bildausschnitt aktivieren",
    "🧠 Smart Features": "🧠 Intelligente Funktionen",
    "Smart Crop (Dynamically adjust vertical framing)": "Smart Crop (vertikalen Ausschnitt dynamisch anpassen)",
    "Background Subtraction (Isolate subjects)": "Hintergrundentfernung (Motive freistellen)",
    "Calculate Visibility Score (DMD Quality)": "Sichtbarkeits-Score berechnen (DMD-Qualität)",
    "Calculate Text Readability Score": "Textlesbarkeits-Score berechnen",
    "%  (batch)": "%  (Stapel)",
    "Source folder — Batch": "Quellordner — Stapel",
    "SOURCE": "QUELLE",
    "AUTO ACTION": "AUTO-ACTION",
    "← Select a file to preview": "← Datei für die Vorschau auswählen",
    "Auto action preview\n(disabled by default)": "Auto-Action-Vorschau\n(standardmäßig deaktiviert)",
    "← Select a file then\n  click 🔬 Refresh DMD": "← Datei auswählen, dann\n  🔬 DMD aktualisieren klicken",
    "⏳  Loading preview…": "⏳  Vorschau wird geladen …",
    "⚠️  Preview unavailable\n(ffmpeg missing?)": "⚠️  Vorschau nicht verfügbar\n(ffmpeg fehlt?)",
    "Auto action disabled": "Auto-Action deaktiviert",
    "⏳  Generating auto-action preview…": "⏳  Auto-Action-Vorschau wird erzeugt …",
    "⏳ Auto…": "⏳ Auto …",
    "❌  Auto-action failed": "❌  Auto-Action fehlgeschlagen",
    "⏭️  Bypassed\n(Original or perfect ratio)": "⏭️  Übersprungen\n(Original oder passendes Seitenverhältnis)",
    "Auto Action is skipped. Color Boost & FPS only.": "Auto-Action wird übersprungen. Nur Farbverstärkung und FPS.",
    "⏳ DMD…": "⏳ DMD …",
    "❌  DMD render failed": "❌  DMD-Rendering fehlgeschlagen",
    "ℹ️  All settings here are hidden by default.\n    Default values reproduce the standard v2.0 output unchanged.":
        "ℹ️  Alle Einstellungen hier sind standardmäßig ausgeblendet.\n    Die Standardwerte erzeugen unverändert die Standardausgabe von v2.0.",
    "✋  Manual frame — auto-scroll is OFF\n    Zoom first, then adjust X / Y to choose the visible 128×32 window.\n    DMD preview auto-refreshes ~2 s after you stop moving sliders.":
        "✋  Manueller Ausschnitt — Auto-Scroll ist AUS\n    Zuerst zoomen, dann X / Y einstellen, um das sichtbare 128×32-Fenster zu wählen.\n    Die DMD-Vorschau aktualisiert sich ca. 2 s nach dem letzten Schieberegler-Zug.",
    "Zoom factor for manual positioning.\nValues > 1.0 zoom in, < 1.0 zoom out.":
        "Zoomfaktor für die manuelle Positionierung.\nWerte > 1,0 zoomen hinein, < 1,0 zoomen heraus.",
    "Horizontal pan offset in pixels.\nAvailable range depends on the current Zoom level.":
        "Horizontaler Versatz in Pixeln.\nDer verfügbare Bereich hängt von der aktuellen Zoomstufe ab.",
    "Vertical pan offset in pixels.\nAvailable range depends on the current Zoom level.":
        "Vertikaler Versatz in Pixeln.\nDer verfügbare Bereich hängt von der aktuellen Zoomstufe ab.",
    "All effects are OFF by default (values = 0 / unchecked).\nNon-zero values add extra ffmpeg filter passes.":
        "Alle Effekte sind standardmäßig AUS (Werte = 0 / nicht angehakt).\nWerte ungleich 0 fügen zusätzliche ffmpeg-Filterdurchläufe hinzu.",
    "Shift the color hue by degrees (e.g. 180° inverts colors).":
        "Verschiebt den Farbton um Grad (z. B. 180° invertiert die Farben).",
    "Smooths out blocky compression artifacts.\nHigh values may blur fine details.":
        "Glättet blockige Kompressionsartefakte.\nHohe Werte können feine Details verwischen.",
    "Adds artificial film grain texture.\nHelps reduce banding on the LED matrix.":
        "Fügt künstliches Filmkorn hinzu.\nHilft, Streifenbildung auf der LED-Matrix zu verringern.",
    "Vignette  (darkens edges — default OFF)": "Vignette  (dunkelt die Ränder ab — standardmäßig AUS)",
    "Applies automatic cinematic camera panning and zooming to focus on the action.\n(Forced ON when Let me handle it is active)":
        "Wendet automatische filmische Kameraschwenks und Zooms an, um die Action zu fokussieren.\n(Immer AN, wenn „Ich mache das selbst“ aktiv ist)",
    "Dynamically switch to 'hybrid' mode if 'person' detects nothing.\nEvaluates dynamically per-scene if Dynamic Scene Detection is enabled.":
        "Wechselt dynamisch in den Modus „hybrid“, wenn „person“ nichts erkennt.\nWird pro Szene ausgewertet, wenn die dynamische Szenenerkennung aktiv ist.",
    "Limits automatic zooms based on the resulting image's visibility and readability on a DMD display.\n(Forced ON when Let me handle it is active)":
        "Begrenzt automatische Zooms anhand der Sichtbarkeit und Lesbarkeit des Ergebnisbilds auf einem DMD.\n(Immer AN, wenn „Ich mache das selbst“ aktiv ist)",
    "How aggressively the camera tracks the subject.\n0.0 = Very loose tracking (camera barely moves).\n1.0 = Very tight tracking (camera locks onto subject).":
        "Wie stark die Kamera dem Motiv folgt.\n0,0 = sehr lose (Kamera bewegt sich kaum).\n1,0 = sehr eng (Kamera haftet am Motiv).",
    "Auto strength  (overrides slider · detects game/anime type)":
        "Auto-Stärke  (überschreibt Regler · erkennt Spiel-/Anime-Typ)",
    "Adds inertia to camera movements to prevent motion sickness.\n0.0 = No smoothing (instant jump cuts).\n0.98 = Maximum cinematic smoothing (very slow camera pans).":
        "Fügt den Kamerabewegungen Trägheit hinzu, um Bewegungsübelkeit zu vermeiden.\n0,0 = keine Glättung (harte Sprünge).\n0,98 = maximale filmische Glättung (sehr langsame Schwenks).",
    "Auto smooth  (overrides slider · detects game/anime type)":
        "Auto-Glättung  (überschreibt Regler · erkennt Spiel-/Anime-Typ)",
    "Maximum dynamic zoom factor for portrait DMD layouts such as 32×64.\nThe camera zooms in only as far as needed to frame detected subjects, then smoothly zooms back out when they are not detected.":
        "Maximaler dynamischer Zoomfaktor für Hochformat-DMDs wie 32×64.\nDie Kamera zoomt nur so weit wie nötig auf erkannte Motive und zoomt sanft wieder heraus, wenn keine erkannt werden.",
    "Adds extra space (margin) around the tracked subject.\n0.0 = No margin (subject touches the screen edges).\n0.20 = Adds 20% breathing room around the subject.":
        "Fügt zusätzlichen Platz (Rand) um das verfolgte Motiv hinzu.\n0,0 = kein Rand (Motiv berührt den Bildrand).\n0,20 = 20 % Luft um das Motiv.",
    "Wait a few seconds before zooming in on the subject.\nUseful for establishing context (showing the full wide scene) before the action starts.":
        "Wartet einige Sekunden, bevor auf das Motiv gezoomt wird.\nNützlich, um zuerst die ganze Szene zu zeigen, bevor die Action beginnt.",
    "Performance optimization. Skips AI detection on X frames out of X.\nExample: 3 means AI runs 3x faster with almost no visual penalty since frames are interpolated.":
        "Leistungsoptimierung. Überspringt die KI-Erkennung bei X von X Bildern.\nBeispiel: 3 bedeutet, die KI läuft 3× schneller, praktisch ohne sichtbaren Nachteil, da Bilder interpoliert werden.",
    "⚡ Auto Fast Tracking (Scale tracking speed to video FPS)":
        "⚡ Auto-Schnell-Tracking (Tracking-Tempo an Video-FPS anpassen)",
    "Optimization: Skips YOLO analysis on X frames out of X.\nFor example, 3 divides tracking time by 3 without visual loss.\nThis setting remains editable even when 'Let me handle it' is checked.":
        "Optimierung: Überspringt die YOLO-Analyse bei X von X Bildern.\nBeispiel: 3 teilt die Tracking-Zeit durch 3, ohne sichtbaren Verlust.\nDiese Einstellung bleibt auch bei „Ich mache das selbst“ editierbar.",
    "━━  📐  Crop & Vertical Bias": "━━  📐  Zuschnitt & vertikale Verschiebung",
    "🧠 Smart Auto Crop  —  engine analyses context & activates the optimal combination":
        "🧠 Smart Auto Crop  —  die Engine analysiert den Kontext und aktiviert die optimale Kombination",
    "Automatically analyzes the scene to optimize bottom crop, top crop, and floor tracking.\n(Forced ON when Let me handle it is active)":
        "Analysiert die Szene automatisch, um unteren Zuschnitt, oberen Zuschnitt und Boden-Tracking zu optimieren.\n(Immer AN, wenn „Ich mache das selbst“ aktiv ist)",
    "Scene Type:": "Szenentyp:",
    "Auto Scene Type  (overrides dropdown · detects scene from content)":
        "Auto-Szenentyp  (überschreibt Auswahl · erkennt die Szene am Inhalt)",
    "Dynamic Scene Detection (per-shot, requires Auto Scene Type)":
        "Dynamische Szenenerkennung (pro Einstellung, benötigt Auto-Szenentyp)",
    "🎞  Auto Pillarbox Crop (Black bars)": "🎞  Auto-Pillarbox-Zuschnitt (schwarze Balken)",
    "Ignores the bottom X% of the video when detecting subjects.\nUseful for hiding UI elements, subtitles, or static HUDs in games.":
        "Ignoriert die unteren X % des Videos bei der Motiverkennung.\nNützlich, um UI-Elemente, Untertitel oder statische HUDs in Spielen auszublenden.",
    "Auto bottom crop  (overrides slider · detects floor / feet / face priority)":
        "Auto-Zuschnitt unten  (überschreibt Regler · erkennt Boden / Füße / Gesicht)",
    "Ignores the top X% of the video when detecting subjects.\nUseful for hiding upper HUD elements or sky/ceiling areas.":
        "Ignoriert die oberen X % des Videos bei der Motiverkennung.\nNützlich, um obere HUD-Elemente oder Himmel/Decke auszublenden.",
    "Auto top crop  (overrides slider · detects head / sky / ceiling)":
        "Auto-Zuschnitt oben  (überschreibt Regler · erkennt Kopf / Himmel / Decke)",
    "Shifts the camera center vertically without altering the zoom level.\n-1.0 = Pan camera up (focus on sky/ceiling).\n+1.0 = Pan camera down (focus on floor/feet).":
        "Verschiebt die Kameramitte vertikal, ohne die Zoomstufe zu ändern.\n-1,0 = Kamera nach oben (Fokus auf Himmel/Decke).\n+1,0 = Kamera nach unten (Fokus auf Boden/Füße).",
    "Auto floor detect (asymmetric EMA · overrides Vertical bias)":
        "Auto-Bodenerkennung (asymmetrisches EMA · überschreibt vertikale Verschiebung)",
    "Enable Background Subtraction (replaces background with black)":
        "Hintergrundentfernung aktivieren (ersetzt den Hintergrund durch Schwarz)",
    "Replaces the detected background with black to maximize contrast and reduce LED power consumption.":
        "Ersetzt den erkannten Hintergrund durch Schwarz, um den Kontrast zu maximieren und den LED-Stromverbrauch zu senken.",
    "Bypass framing/cropping and apply only Render FPS and Color Boost when the source video ratio matches the target ratio. By definition, selecting 'Original' resolution will always trigger this bypass.":
        "Überspringt Ausschnitt/Zuschnitt und wendet nur Render-FPS und Farbverstärkung an, wenn das Seitenverhältnis der Quelle dem Zielverhältnis entspricht. Die Auswahl der Auflösung „Original“ löst diese Umgehung immer aus.",
    "Speed of the automatic vertical panning (pixels per second).":
        "Geschwindigkeit des automatischen vertikalen Schwenks (Pixel pro Sekunde).",
    "Percentage of the top of the video to ignore (e.g. 10% = ignore top 10%).":
        "Anteil des oberen Videorands, der ignoriert wird (z. B. 10 % = oberste 10 % ignorieren).",
    "Percentage of the bottom to ignore (useful for hiding HUDs or subtitles).":
        "Anteil des unteren Videorands, der ignoriert wird (nützlich für HUDs oder Untertitel).",
    "Number of times to bounce the vertical pan up and down during the video's duration.\nA value of 1.0 means it pans down once.":
        "Anzahl der vertikalen Auf-und-ab-Schwenks während der Videodauer.\nEin Wert von 1,0 bedeutet, dass einmal nach unten geschwenkt wird.",
    "The lowest frame rate allowed for the output video/GIF.\nThe tool will drop frames down to this limit if possible to save file size.":
        "Die niedrigste erlaubte Bildrate für das Ausgabevideo/GIF.\nDas Tool verwirft Bilder bis zu diesem Limit, um Dateigröße zu sparen.",
    "The highest frame rate allowed.\nHigh FPS creates smoother animations but results in larger files.":
        "Die höchste erlaubte Bildrate.\nHohe FPS ergeben flüssigere Animationen, aber größere Dateien.",
    "Adjusts the difference between light and dark areas. Higher = more punchy.":
        "Passt den Unterschied zwischen hellen und dunklen Bereichen an. Höher = kräftiger.",
    "Adjusts the intensity of colors. Higher = more vivid.":
        "Passt die Farbintensität an. Höher = lebendiger.",
    "Overall lightness of the image.": "Gesamthelligkeit des Bildes.",
    "Adjusts mid-tones. Lower = brighter shadows, Higher = darker shadows.":
        "Passt die Mitteltöne an. Niedriger = hellere Schatten, höher = dunklere Schatten.",
    "Sharpens the brightness details (edges).": "Schärft die Helligkeitsdetails (Kanten).",
    "Sharpens color details. Use sparingly to avoid color artifacts.":
        "Schärft Farbdetails. Sparsam einsetzen, um Farbartefakte zu vermeiden.",
}

DE_TO_EN = {
    "Alle": "All",
    "leer": "empty",
    "🔍  GIF-Suche": "🔍  GIF search",
    "Lade …": "Loading …",
    "⏹ Abbruch läuft …": "⏹ Cancelling …",
    "Video-, GIF- oder PNG-Dateien auswählen": "Select video, GIF or PNG files",
    "Quellordner auswählen": "Select source folder",
    "Standbild · Auto-Action nicht erforderlich": "Still image · Auto-Action not required",
    "Standbild-Vorschau nicht verfügbar": "Still image preview not available",
    "ScreenScraper-Zugang": "ScreenScraper access",
    "Zugangsdaten sicher speichern": "Store credentials securely",
    "Zugangsdaten im System-Schlüsselbund gespeichert.": "Credentials stored in the system keychain.",
    "Systemsuche abgebrochen.": "System search cancelled.",
    "Abbruch der Systemsuche angefordert …": "Cancelling system search …",
    "ScreenScraper: System, Spiel und Medien auswählen": "ScreenScraper: choose system, game and media",
    "ScreenScraper-Systemliste wird geladen …": "Loading ScreenScraper system list …",
    "Bitte zuerst die Systemliste laden und ein System wählen.": "Please load the system list first and choose a system.",
    "Bitte einen Spieltitel eingeben.": "Please enter a game title.",
    "Bitte zuerst einen Spieltreffer auswählen.": "Please select a game result first.",
    "Bitte mindestens ein Medium auswählen.": "Please select at least one medium.",
    "Abbruch angefordert …": "Cancelling …",
}
