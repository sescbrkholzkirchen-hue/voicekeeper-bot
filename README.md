# VoiceKeeper 2.0

Der Bot bleibt in einem festgelegten Discord-Sprachkanal und spielt deinen eigenen Sound ab, sobald ein echter Benutzer den Kanal betritt.

## Enthaltene Funktionen

- automatische Verbindung mit dem Sprachkanal
- automatische Wiederverbindung
- eigener Begrüßungssound
- Warteschlange bei mehreren Beitritten
- Cooldown gegen schnelles Rein- und Rausgehen
- Railway-Logs
- keine Nickname-Funktion

## 1. Eigene Sounddatei hinzufügen

Benenne deine Datei am einfachsten:

```text
welcome.mp3
```

Lege sie direkt neben `bot.py` in das Repository.

Der Dateiname muss exakt mit `WELCOME_AUDIO` in Railway übereinstimmen. Groß- und Kleinschreibung zählen.

## 2. Dateien nach GitHub hochladen

Du kannst alle Dateien dieses Ordners in dein vorhandenes Repository hochladen. Bereits vorhandene Dateien mit gleichem Namen werden ersetzt.

Wichtig: Deinen Discord-Token niemals in eine Datei schreiben oder auf GitHub hochladen.

## 3. Railway-Variablen

Öffne in Railway den Bot-Service und danach `Variables`.

Pflichtvariablen:

| Name | Wert |
|---|---|
| `DISCORD_TOKEN` | dein geheimer Discord-Bot-Token |
| `VOICE_CHANNEL_ID` | die Zahlen-ID deines Sprachkanals |

Empfohlene Zusatzvariablen:

| Name | Wert | Bedeutung |
|---|---:|---|
| `WELCOME_AUDIO` | `welcome.mp3` | Dateiname des Sounds |
| `WELCOME_VOLUME` | `0.5` | Lautstärke von 0.0 bis 2.0 |
| `JOIN_COOLDOWN_SECONDS` | `10` | Sperrzeit je Benutzer |
| `CONNECTION_CHECK_SECONDS` | `30` | Abstand der Verbindungsprüfung |

## 4. Discord-Rechte

Der Bot braucht im Zielkanal:

- Kanal ansehen
- Verbinden
- Sprechen

Der Bot sollte nicht serverseitig stummgeschaltet sein.

## 5. Deployment

Railway erkennt das `Dockerfile`, installiert Python, FFmpeg und die benötigten Pakete und startet anschließend `bot.py`.

Im Build-Log sollte Railway anzeigen, dass ein Dockerfile erkannt wurde.

## 6. Test

1. Warte, bis der Bot im Sprachkanal sitzt.
2. Verlasse den Kanal vollständig.
3. Warte ein paar Sekunden.
4. Betritt den Kanal erneut.

Erwartete Logs:

```text
Eingeloggt als VoiceKeeper
Voice-Überwachung gestartet.
Sound-Warteschlange gestartet.
Erfolgreich mit Allgemein verbunden.
Max ist dem Sprachkanal Allgemein beigetreten.
Begrüßungssound für Max wird abgespielt.
Begrüßungssound für Max wurde vollständig abgespielt.
```

## Fehlerhilfe

### `Audiodatei nicht gefunden`

Prüfe:

- Liegt `welcome.mp3` direkt im Repository?
- Heißt die Railway-Variable exakt `WELCOME_AUDIO`?
- Steht als Wert exakt `welcome.mp3` darin?

### `ffmpeg was not found`

Prüfe, ob die Datei exakt `Dockerfile` heißt, mit großem D und ohne Dateiendung.

### Bot spricht nicht

Prüfe:

- Berechtigung `Sprechen`
- Bot nicht serverseitig stumm
- persönliche Bot-Lautstärke in Discord
- Sounddatei enthält hörbaren Ton
- `WELCOME_VOLUME` ist nicht `0`

### Sound startet nicht beim Betreten

Nur ein echter Wechsel in den Zielkanal löst den Sound aus. Stumm- oder Lautstellen reicht nicht.
