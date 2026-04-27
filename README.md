# ServerLoadMonitor

ServerLoadMonitor je projekt pro monitorování Linux serverů z Android aplikace. Skládá se ze tří částí:

- `ServerLoadMonitoring/` - Android aplikace v Javě
- `ServerLoadBack/` - Django REST API backend
- `ServerAgent/` - Python agent běžící na monitorovaném serveru

## Funkce

- přihlášení a registrace uživatele,
- párování serveru přes pairing kód nebo QR kód,
- přehled serverů s online/offline stavem,
- metriky CPU, RAM, disk, síť a uptime,
- historie metrik pro grafy s volbou časového rozsahu,
- tabulka procesu,
- seznam systemd services,
- vzdálený start/stop/enable/disable services přes agent commands,
- nastavení intervalu sběru dat a retence metrik,
- Android push notifikace přes Firebase Cloud Messaging.

## Architektura

1. Agent se při prvním spuštění zaregistruje na backendu.
2. Backend agentovi vrátí `server_id`, `agent_token` a pairing kód.
3. Uživatel server spáruje v Android aplikaci.
4. Agent pravidelně posílá metriky, procesy a services.
5. Android aplikace čte data z backendu přes JWT autentizaci.
6. Akce nad services se uloží jako command v backendu a agent je postupně vykoná.

## Rychlé spuštění backendu

```bash
cd ServerLoadBack
python -m venv ../.venv
../.venv/Scripts/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Na Linux/macOS použij aktivaci:

```bash
source ../.venv/bin/activate
```

## Android aplikace

Projekt otevři v Android Studiu ze složky:

```text
ServerLoadMonitoring/
```

Adresa backendu je v:

```text
ServerLoadMonitoring/app/src/main/java/com/example/serverloadmonitoring/ApiConfig.java
```

Pro Android emulátor použij typicky:

```java
public static final String BASE_URL = "http://10.0.2.2:8000";
```

Pro reálné zařízení nastav IP adresu počítače/serveru v síti.

## Agent

Na monitorovaném Linux serveru:

```bash
cd ServerAgent
python3 setup.py
```

Setup:

- nainstaluje Python balíčky z `requirements.txt`,
- zaregistruje server na backendu,
- zobrazí pairing kód a QR kód,
- počká na spárování v Android aplikaci,
- vytvoří systemd service `server-monitoring-agent`,
- spustí agenta jako `root`, aby mohl ovládat systemd services.

Kontrola služby:

```bash
sudo systemctl status server-monitoring-agent
journalctl -u server-monitoring-agent -n 100 --no-pager
```

## Firebase / push notifikace

Pro push notifikace je potřeba Firebase Admin service account JSON na backendu a `google-services.json` v Android aplikaci.

Tyto soubory se nesmí commitovat:

- `firebase-service-account.json`
- `google-services.json`

Jsou ignorované v `.gitignore`.

## Další dokumentace

Detailnější informace jsou ve složkách:

- `ServerLoadBack/README.md`
- `ServerAgent/README.md`
- `ServerLoadMonitoring/README.md`
