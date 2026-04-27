# ServerLoadMonitor

ServerLoadMonitor je projekt pro monitorovani Linux serveru z Android aplikace. Sklada se ze tri casti:

- `ServerLoadMonitoring/` - Android aplikace v Jave
- `ServerLoadBack/` - Django REST API backend
- `ServerAgent/` - Python agent bezici na monitorovanem serveru

## Funkce

- prihlaseni a registrace uzivatele,
- parovani serveru pres pairing kod nebo QR kod,
- prehled serveru s online/offline stavem,
- metriky CPU, RAM, disk, sit a uptime,
- historie metrik pro grafy s volbou casoveho rozsahu,
- tabulka procesu,
- seznam systemd services,
- vzdaleny start/stop/enable/disable services pres agent commands,
- nastaveni intervalu sberu dat a retence metrik,
- Android push notifikace pres Firebase Cloud Messaging.

## Architektura

1. Agent se pri prvnim spusteni zaregistruje na backendu.
2. Backend agentovi vrati `server_id`, `agent_token` a pairing kod.
3. Uzivatel server sparuje v Android aplikaci.
4. Agent pravidelne posila metriky, procesy a services.
5. Android aplikace cte data z backendu pres JWT autentizaci.
6. Akce nad services se ulozi jako command v backendu a agent je postupne vykona.

## Rychle spusteni backendu

```bash
cd ServerLoadBack
python -m venv ../.venv
../.venv/Scripts/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Na Linux/macOS pouzij aktivaci:

```bash
source ../.venv/bin/activate
```

## Android aplikace

Projekt otevri v Android Studiu ze slozky:

```text
ServerLoadMonitoring/
```

Adresa backendu je v:

```text
ServerLoadMonitoring/app/src/main/java/com/example/serverloadmonitoring/ApiConfig.java
```

Pro Android emulator pouzij typicky:

```java
public static final String BASE_URL = "http://10.0.2.2:8000";
```

Pro realne zarizeni nastav IP adresu pocitace/serveru v siti.

## Agent

Na monitorovanem Linux serveru:

```bash
cd ServerAgent
python3 setup.py
```

Setup:

- nainstaluje Python balicky z `requirements.txt`,
- zaregistruje server na backendu,
- zobrazi pairing kod a QR kod,
- pocka na sparovani v Android aplikaci,
- vytvori systemd service `server-monitoring-agent`,
- spusti agenta jako `root`, aby mohl ovladat systemd services.

Kontrola sluzby:

```bash
sudo systemctl status server-monitoring-agent
journalctl -u server-monitoring-agent -n 100 --no-pager
```

## Firebase / push notifikace

Pro push notifikace je potreba Firebase Admin service account JSON na backendu a `google-services.json` v Android aplikaci.

Tyto soubory se nesmi commitovat:

- `firebase-service-account.json`
- `google-services.json`

Jsou ignorovane v `.gitignore`.

## Git

Pred commitem over, ze citlive JSON soubory nejsou staged:

```bash
git check-ignore -v firebase-service-account.json ServerLoadMonitoring/app/google-services.json
git status --short
```

Zakladni push:

```bash
git add .
git commit -m "Update project"
git push
```

## Dalsi dokumentace

Detailnejsi informace jsou ve slozkach:

- `ServerLoadBack/README.md`
- `ServerAgent/README.md`
- `ServerLoadMonitoring/README.md`
