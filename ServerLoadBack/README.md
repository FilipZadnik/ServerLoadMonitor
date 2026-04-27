# ServerLoadMonitoring Backend

Django + DRF backend pro monitoring serveru s JWT autentizaci mobilni appky a pairing flow pro agenta.

## Co to umi

- registrace noveho agenta (`unpaired` server),
- registrace/prihlaseni uzivatele pres JWT,
- parovani serveru k prihlasenemu uzivateli pres jednorazovy kod,
- vypis pouze vlastnich sparovanych serveru,
- prijem metrik/procesu/sluzeb od agenta,
- fronta prikazu pro agenta a ukladani vysledku.
- Android push notifikace (FCM) pro `offline`, `cpu_high`, `ram_high`.

## Pozadavky

- Python 3
- `django`
- `djangorestframework`
- `djangorestframework-simplejwt`
- `firebase-admin`

## Rychly start

```bash
python -m venv .venv
source .venv/bin/activate
pip install django djangorestframework djangorestframework-simplejwt
python manage.py migrate
python manage.py runserver
```

## Autentizace

### Mobilni appka (user endpointy)

Pouziva JWT access token:

```http
Authorization: Bearer <access_token>
```

Relevantni endpointy:

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/servers/`
- `POST /api/servers/pair/`
- `POST /api/users/push-token/`

### Agent endpointy

Pouzivaji header:

```http
Authorization: Agent <agent_token>
```

## Pairing flow

1. Agent zavola `POST /api/agent/register/` s:
```json
{
  "hostname": "raspberrypi",
  "ip_address": "192.168.1.10"
}
```
2. Backend vrati:
```json
{
  "server_id": 1,
  "pairing_code": "482-913",
  "agent_token": "long-random-token"
}
```
3. Agent zobrazi pairing code + QR.
4. Uzivatel v Android appce je prihlaseny (ma JWT access token) a posle:
```json
{
  "pairing_code": "482-913",
  "name": "Web Server",
  "interval_seconds": 5,
  "process_snapshot_interval_seconds": 30,
  "service_snapshot_interval_seconds": 60
}
```
na `POST /api/servers/pair/`.

5. Backend server priradi prihlasenemu uzivateli, nastavi nazev a `is_paired=true`.
6. Uzivatel vidi pouze sve servery pres `GET /api/servers/`.

`pairing_code` ma format `XXX-XXX`, plati 15 minut a po sparovani se invaliduje.

## Endpointy

### User auth + servery

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/servers/`
- `POST /api/servers/pair/`
- `GET /api/servers/<server_id>/settings/`
- `PATCH /api/servers/<server_id>/settings/`
- `DELETE /api/servers/<server_id>/settings/`
- `POST /api/servers/<server_id>/commands/` (enqueue `start/stop/enable/disable` for agent)

### Agent

- `POST /api/agent/register/`
- `GET /api/agent/<server_id>/settings/`
- `POST /metrics/`
- `POST /processes/`
- `POST /services/`
- `GET /api/agent/<server_id>/commands/`
- `POST /api/agent/<server_id>/commands/<id>/result/`

## Android push alerty (FCM)

1. Nainstaluj requirements:
```bash
pip install -r requirements.txt
```

2. Nastav env promenne:
```bash
export FCM_ENABLED=1
export FCM_SERVICE_ACCOUNT_FILE=/absolute/path/to/firebase-service-account.json
```

3. Mobilni app po loginu posle FCM token na:
- `POST /api/users/push-token/` body: `{"token":"...", "device_name":"Pixel 9"}`

4. Worker je defaultne zapnuty pri startu backendu.

Pokud ho chces vypnout:
```bash
export ALERT_WORKER_AUTOSTART=0
```

Volitelne ho muzes spustit rucne:
```bash
python manage.py run_alert_worker
```

Volitelne:
- vlastni interval (sekundy): `python manage.py run_alert_worker --interval 10`
- bez odesilani push: `python manage.py run_alert_worker --dry-run`

Alternativa (jednorazovy beh evaluatoru):
```bash
python manage.py evaluate_alerts
```

Volitelne bez push odesilani (jen update state):
```bash
python manage.py evaluate_alerts --dry-run
```
