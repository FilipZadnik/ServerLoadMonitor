# Server Monitoring Agent

Jednoduchý Python agent pro Linux server, který:
- sbírá systémové metriky,
- posílá je na Django backend,
- přijímá příkazy a spouští `systemctl` akce,
- při prvním spuštění se zaregistruje a zobrazí párovací QR kód v terminálu.

## Požadavky

- Python 3
- Linux se `systemd` (`systemctl`)

## Instalace

```bash
pip install -r requirements.txt
```

## Prvni spusteni (setup.py)

Jako prvni krok spust:

```bash
python3 setup.py
```

`setup.py` udela:
- nainstaluje zavislosti z `requirements.txt` pomoci `pip ... --break-system-packages`,
- registraci serveru na backendu (`POST /api/agent/register/`),
- vypis pairing kodu + QR do terminalu,
- pocka na uspesne sparovani v mobilni aplikaci,
- az potom vytvori `systemd` sluzbu a zapne autostart pri bootu.

Volitelne parametry:
- `--service-name server-monitoring-agent` (jmeno systemd sluzby),
- `--service-user <linux_user>` (pod jakym uzivatelem pobezi, default je `root`),
- `--no-start` (sluzbu nezapinat hned, jen enable),
- `--skip-service` (jen registrace + QR bez systemd),
- `--force-register` (vynutena nova registrace).
- `--pairing-timeout 300` (cekani na sparovani v sekundach, `0` = neomezene),
- `--pairing-poll-interval 3` (jak casto overovat stav sparovani).
- `--skip-install` (preskoci instalaci requirements v setupu).

## Konfigurace

Agent používá proměnné prostředí:

- `INTERVAL_SECONDS` (interval cyklu v sekundách, např. `5`)
- `PROCESS_SNAPSHOT_INTERVAL_SECONDS` (interval odeslání procesů, default `30`)
- `SERVICE_SNAPSHOT_INTERVAL_SECONDS` (interval odeslání služeb, default `60`)
- `AGENT_CONFIG_PATH` (cesta ke konfiguračnímu JSON souboru, default `agent_config.json`)

Volitelné:
- `HTTP_TIMEOUT_SECONDS` (default `10`)
- `HTTP_RETRIES` (default `3`)
- `RETRY_DELAY_SECONDS` (default `2`)

Volitelně lze předat i:
- `SERVER_ID`
- `AGENT_TOKEN`

Pokud `SERVER_ID` a `AGENT_TOKEN` nejsou dostupné ani v env ani v `agent_config.json`,
agent provede registraci na `POST /api/agent/register/`, uloží data do `agent_config.json`
a vypíše `pairing_code` + QR kód (`qrcode_terminal`).

Příklad:

```bash
export INTERVAL_SECONDS="5"
```

## Spusteni agenta rucne

```bash
python3 agent.py
```

Při prvním spuštění:
- agent zavolá `POST /api/agent/register/`,
- uloží `SERVER_ID` + `AGENT_TOKEN`,
- vypíše párovací kód a QR kód (QR payload je JSON: `{"pairing_code":"XXX-XXX"}`).

Do registrace posílá i systémové informace serveru:
- `os_name`, `kernel_version`
- `cpu_model`, `cpu_cores`
- `total_ram_bytes`, `total_disk_bytes`

Po spárování agent v každém cyklu načítá `GET /api/agent/{server_id}/settings/`.
Pokud se intervaly změní v aplikaci, agent je za běhu aplikuje a uloží do `agent_config.json`.

## Co agent posílá

- `POST /metrics/`
  - `cpu_usage`, `ram_usage`, `disk_usage`
  - `uptime_seconds`
  - `network_upload_bytes`, `network_download_bytes` (delta od posledního měření)
- `POST /processes/`
  - top 10 procesů podle CPU (`pid`, `name`, `cpu_usage`, `ram_usage`)
- `POST /services/`
  - služby ze `systemctl` (`name`, `status`, `enabled`)

## Příkazy z backendu

Agent pravidelně volá:

- `GET /api/agent/{server_id}/commands/`

Podporované akce:

- `systemctl start <service>`
- `systemctl stop <service>`
- `systemctl enable <service>`
- `systemctl disable <service>`

Výsledek provedení posílá na:

- `POST /api/agent/{server_id}/commands/{id}/result/`

Všechny agent endpointy používají:
- `Authorization: Agent <AGENT_TOKEN>`

## Struktura projektu

- `agent.py` - hlavní smyčka
- `config.py` - konfigurace
- `metrics.py` - sběr metrik
- `processes.py` - sběr procesů
- `services.py` - sběr služeb
- `commands.py` - načtení/spuštění příkazů a odeslání výsledku
