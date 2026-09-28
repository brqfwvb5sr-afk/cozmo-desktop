# Echter Cozmo unter Ubuntu / experimental direct Wi-Fi

Version 0.3.0 implements a physical adapter using PyCozmo 0.8.0. It sends real robot
commands. Transport codecs, the worker watchdog and Qt integration have automated
hardware-free tests. **Physical hardware validation is still pending.** No phone
bridge, firmware updater or original mobile-app behavior engine is included.

## Installation / Update (Internet noch verbunden lassen)

```bash
cd ~/cozmo-desktop
git pull --ff-only
sudo apt update
sudo apt install python3-venv espeak-ng libegl1 libopengl0 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0 libxcb-xinerama0 fonts-dejavu-core
bash scripts/setup-ubuntu.sh
```

Das Skript erstellt eine eigene Python-3.12-Umgebung `.venv312`, auch bei System-
Python 3.14. System-Python bleibt unverändert. Vorhandenes `.venv/bin/uv` wird
wiederverwendet; sonst installiert es uv in `.venv-tools`. Python und Pakete werden
heruntergeladen. Ubuntu 22.04/24.04 werden in CI geprüft; Ubuntu 26.04 ist noch kein
geprüftes Target. Die alte .venv wird nicht gelöscht.

## VMware und USB-WLAN-Adapter

1. In VMware den USB-WLAN-Adapter an Ubuntu übergeben: **VM → Removable Devices →
   dein WLAN-Adapter → Connect (Disconnect from host)**. Menünamen können variieren.
2. In Ubuntu `lsusb` und `nmcli device status` prüfen. Ein `wifi`-Gerät (`wlx…` oder
   `wlan0`) muss erscheinen. Nur `ens33`/Ethernet reicht nicht: VMware-NAT ersetzt
   keinen WLAN-Adapter, mit dem Ubuntu Cozmos Netzwerk auswählen kann.
3. Cozmo auf die versorgte Ladestation stellen. Lift heben/senken, bis WLAN-Name
   und Passwort erscheinen. Die mobile Cozmo-App schließen.
4. In **Ubuntus** WLAN-Einstellungen `Cozmo_…` auswählen und das angezeigte Passwort
   eingeben. „Kein Internet“ auf diesem WLAN ist normal.
5. `ip route get 172.31.1.1` muss das WLAN-Gerät und eine Quelladresse `172.31.1.x`
   zeigen. Eine VPN- oder VMware-NAT-Route ist falsch.
6. Prüfen und starten:

```bash
bash scripts/start-ubuntu.sh --check-direct
bash scripts/start-ubuntu.sh
```

Der Prüfbefehl kontrolliert Abhängigkeit und Route ohne Roboterbefehle zu senden.
Eine passende Route allein beweist keine Roboterverbindung.

## Erstes Verbinden und Bedienen

- **Connect Cozmo**: „Connected“ setzt echte Statusmeldungen voraus. Fehler führen
  niemals zu einem automatischen Wechsel zum Simulator.
- Zunächst Kamera, Batteriespannung und Augen testen. Eigene Fahr-/Kopf-/Liftbefehle
  bleiben gesperrt. **Cozmo kann beim Protokollstart selbst kalibrieren.**
- Cozmo auf einen freien Boden setzen, **Connection → Clear floor** und danach
  **Enable motors** wählen. Der Zustand **Elevated/table** sperrt Fahrbefehle.
  Nicht auf einer Tischkante fahren oder Freeplay dort bewegen lassen.
- **Tischsensor-Messung ohne Motoren:** Motoren gesperrt lassen. Auf **Connection**
  **Start sensor trace** wählen und `center` markieren. Cozmo mit einer Hand sichern,
  ihn auf der Oberfläche langsam zur Tischkante schieben und die passende Richtung
  (`front edge` usw.) markieren. Danach **Stop sensor trace** und **Export trace** wählen. Niemals
  für diese Messung Fahrmotoren freigeben oder Cozmo an einer Kante loslassen.
  Die JSON-Datei enthält nur relative Zeit, vier Rohwerte, Positionsmarkierung,
  Raddrehzahlen und Sicherheitsflags; keine Kamera, Sprache, WLAN-Daten oder Konten. Ohne Auswertung
  echter Messungen bleibt Tischfahren gesperrt.
- **Control**: WASD zum Fahren gedrückt halten, loslassen zum Stoppen; Pfeiltasten
  hoch/runter bewegen den Kopf, R/F den Lift. Anfangs 20 mm/s, maximal 40 mm/s.
- **Speak**: lokales deutsches eSpeak NG über Cozmos Lautsprecher. Kein Mikrofon.
  Kurze Texte, maximal ungefähr 30 Sekunden.
- **Expressions / Animations**: eigene Augenbilder und Augenanimationen. Expressions
  können bei freigegebenen Motoren zusätzlich Kopf-/Lift-Posen setzen.
- **Camera**: echte Graustufenbilder, Vorschau bis 5 Bilder/s, PNG-Schnappschüsse.
  Keine simulierten Gesichts-/Würfelmarkierungen.
- **Cubes**: erster Klick verbindet einen erkannten Würfel, zweiter Klick setzt
  seine LEDs auf Grün. Tap-/Bewegungsereignisse bleiben kurz sichtbar. Würfelbatterie
  und Ausrichtung sind nicht verfügbar.
- **Home → Start Freeplay**: Augen, Blick, Stimmung und synthetisierte Laute laufen
  selbstständig. Die separate Bewegungsoption erfordert Clear floor und Enable motors.
- **Games**: Quick Tap und Memory Match mit Würfel 1–3, Keepaway mit Würfel 1.
  Eigenständig programmierte Spielregeln nutzen LEDs und Tap-/Bewegungsereignisse.
  Bei Quick Tap zeigt Würfel 3 den Countdown: Würfel 1 nur bei gleichen Farben
  antippen, niemals bei Rot. Cozmo reagiert über Augen und Laute, tippt aber
  ohne verifizierte Würfelposition noch keinen Würfel körperlich an.
  Die proprietäre Original-App und ihre Spiel-Engine sind nicht enthalten. Keepaway
  verfolgt den Würfel nicht räumlich; die direkte Verbindung liefert dafür derzeit
  keine verlässlich geprüfte Würfelposition. Während Spielen bleiben die Räder still.
- **Conversation**: optionales lokales Ollama-Modell. In Ubuntu Ollama und ein Modell
  separat installieren, mit `ollama list` dessen Namen prüfen, diesen in der App
  eingeben und Text senden. Die Antwort erscheint und wird gesprochen. Kein Mikrofon.
- **STOP** bricht Desktop-Aktionen ab und sperrt die Bedienung bis **Resume controls**.
  Nach Verbindungsfehlern erneut **Connect Cozmo** wählen. Nach Watchdog-, Pickup-,
  Lade- oder Klippenereignissen zusätzlich **Enable motors** betätigen.

## Grenzen der Stop-Funktion

Ein separater Prozess besitzt die UDP-Verbindung. Er prüft Fahrbefehle mit 350 ms
Gültigkeit sowie Desktop-Heartbeat und echte Telemetrie mit jeweils 800 ms Timeout.
Fehlender Heartbeat, Pipe-Abbruch oder fehlende Telemetrie beendet die Sitzung.
Klippen-Stopp wird im Protokoll aktiviert; erkannte Pickup-/Cliff-/Ladezustände
sperren eigene Motorbefehle. Keine automatische Wiederverbindung oder Freigabe.

Dies ist **kein hardwareverifizierter Not-Aus**: STOP wird an PyCozmo übergeben;
Empfang und tatsächlicher Motorstillstand sind dadurch nicht bestätigt. Bei
WLAN-Ausfall, Prozess-/OS-Absturz oder blockiertem Transport kann STOP ausbleiben.
Die Firmware-Reaktion ist noch zu prüfen. Nur beaufsichtigt auf dem Boden testen;
keine zugesicherte Stoppdistanz oder Stoppzeit.

## Fehlerhilfe

- Kein WLAN-Gerät: USB-Durchreichung und Linux-Treiber des Adapters prüfen.
- WLAN vorhanden, aber Route falsch: `nmcli device status` und
  `ip route get 172.31.1.1` prüfen; der WLAN-Adapter muss `connected` sein und die
  Quelladresse muss aus `172.31.1.x` kommen. Cozmos WLAN ohne Internet ist normal.
- Falsche Quelladresse: Ubuntu mit Cozmos WLAN verbinden; Route/VPN prüfen.
- Keine Telemetrie: mobile App beenden, Cozmo aufwecken, WLAN erneut verbinden.
- Python-Fehler: Startskript verwenden; es nutzt `.venv312`, nicht Python 3.14.
- Motoren gesperrt: Kamera/Status prüfen, Cozmo vom Ladegerät auf den Boden setzen,
  Resume controls nach STOP und anschließend Enable motors wählen.
- Keine Sprache: `espeak-ng --version` prüfen. Proprietäre Sounds sind nicht nötig.
- Kein Chat: Ollama in derselben Ubuntu-VM starten, `ollama list` prüfen und exakt
  einen installierten Modellnamen in Conversation eingeben.

## Physical validation record

Pending: robot/firmware version, Ubuntu version, Wi-Fi adapter, connect/disconnect,
camera/OLED, TTS, head/lift, supervised low-speed wheels, key/focus/STOP response,
lost GUI/UDP/telemetry, pickup/cliff and raw cliff traces on several surfaces,
individual cube connect/tap/lights, Freeplay movement and game timing. Record
observed results before describing this adapter as stable. No original app assets,
OBB archives or firmware images are downloaded by the application.
