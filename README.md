# Poste de pesée RFID — Les Alchimistes (GarageWeek ISEN 2026)

Identification d'un bac par tag RFID, affichée sur une page web temps réel (SSE),
avec saisie d'une note qualité (1-3 étoiles) et photo de justification.

L'architecture sépare **acquisition** (matériel, thread de fond) et **exposition**
(Flask + page web). Une couche matérielle abstraite permet de tout développer et
démontrer **sans câbles** (mode `sim`), puis de basculer sur le Raspberry Pi câblé
(mode `real`) en ne changeant qu'une variable d'environnement.

## Structure

```
rfid_station/
├── app.py            # Serveur Flask : page, flux SSE, endpoints de simulation
├── station.py        # Logique métier : état du poste, broker SSE, traitements
├── db.py             # SQLite : bacs (UID → établissement) + pesées
├── config.py         # Constantes et mode matériel
├── hardware/
│   ├── base.py       # Interfaces abstraites (lecteur, balance, caméra, boutons)
│   ├── simulator.py  # Implémentations simulées (PC, sans câbles)
│   ├── real.py       # Implémentations Raspberry Pi (RC522, GPIO, caméra, banc)
│   └── __init__.py   # Fabrique sim/real
├── templates/index.html
├── static/{app.js,style.css,photos/}
└── requirements.txt
```

## Modèle de données

L'UID du tag sert de **clé**. Aucune donnée métier n'est écrite sur le tag : tout
est en base locale (`station.db`), indexé par UID. Un tag illisible en écriture
reste exploitable en lecture d'UID, et on modifie les infos d'un bac sans toucher
au tag. Table `bins` (uid → établissement), table `weighings` (historique noté).

## Installation sur le Raspberry Pi (Bookworm / Legacy Lite)

```bash
# 1. Activer SPI (pour le RC522, en mode réel)
sudo raspi-config        # Interface Options → SPI → Enable → reboot

# 2. Paquets système (propres, pas de souci externally-managed)
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-flask python3-spidev python3-gpiozero python3-lgpio python3-pip

# 3. Dépendance pip (lecteur RC522 ; tire RPi.GPIO en dépendance)
pip3 install -r requirements.txt --break-system-packages

# 4. Si le GPIO plante au runtime en mode réel (RPi.GPIO cassé sur Bookworm) :
sudo apt install -y python3-rpi-lgpio
```

## Lancement

```bash
# Mode simulation (défaut) — fonctionne sur le PC comme sur le Pi, sans câbles
python3 app.py

# Mode réel (sur le Pi câblé uniquement)
STATION_HW=real python3 app.py
```

Puis, depuis un navigateur sur le même réseau : `http://<ip-ou-hostname-du-pi>:8000`
(p. ex. `http://raspberrypi.local:8000`).

En mode `sim`, un **panneau de simulation** apparaît en bas de page : il remplace
le matériel (présenter un bac, noter, déclencher la photo) et permet de tout tester
et démontrer sans RC522 ni boutons.

## Câblage RC522 → Raspberry Pi (mode réel)

Le RC522 fonctionne en **3,3 V uniquement** (le 5 V détruit la puce). Les GPIO du
Pi sont en 3,3 V : connexion directe, sans level shifter.

| RC522 | Pi (BCM) | Broche physique |
|-------|----------|-----------------|
| SDA (SS) | GPIO8 (CE0) | 24 |
| SCK | GPIO11 | 23 |
| MOSI | GPIO10 | 19 |
| MISO | GPIO9 | 21 |
| RST | GPIO25 | 22 |
| 3.3V | 3V3 | 1 |
| GND | GND | 6 |
| IRQ | non connecté | — |

## Câblage des boutons (mode réel)

Chaque poussoir relie un GPIO au GND ; pull-up interne activé par logiciel
(repos = HIGH, appui = LOW). Aucune résistance externe.

| Bouton | GPIO (BCM) | Broche physique |
|--------|-----------|-----------------|
| 1 étoile | GPIO5 | 29 |
| 2 étoiles | GPIO6 | 31 |
| 3 étoiles | GPIO13 | 33 |
| Photo | GPIO19 | 35 |
| GND commun | — | 39 |

(La numérotation GPIO est modifiable dans `hardware/real.py`.)

## Points à compléter côté matériel réel

- `hardware/real.py::Rc522Reader.read_uid` : valider les noms d'API de la lib
  `mfrc522` au premier test de lecture.
- `hardware/real.py::PiCamera.capture` : implémenter la capture (picamera2 / fswebcam).
- `hardware/real.py::BenchScale.read_weight_kg` : interfacer le banc de pesée
  existant (liaison série / HX711 / API selon ce qu'expose la balance du site).

## Notes de sécurité (contexte PoC)

- **Pas d'authentification** : le poste est prévu pour un **réseau local de
  confiance**. `HOST=0.0.0.0` expose le serveur sur le LAN. Hors démo, restreindre
  l'accès réseau (pare-feu / VLAN dédié).
- **Endpoints `/sim/*`** : refusés (HTTP 403) hors mode `sim` (échec fermé). Ils
  modifient l'état mais ne sont actifs qu'en simulation.
- **Pas de CSRF** sur les POST de simulation : acceptable en PoC sur LAN isolé sans
  cookies de session. En production avec actions à effet de bord, ajouter une
  protection (Flask-WTF) ou restreindre l'origine.
- SQL **paramétré** partout ; entrées HTTP **validées côté serveur** (UID, note).
- `debug=False` (jamais le débogueur Werkzeug en exploitation).
- En-têtes : `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options`,
  `X-Frame-Options`.
