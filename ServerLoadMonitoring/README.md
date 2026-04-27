# Server Load Monitoring 📊

Komplexní systém pro monitorování zátěže serverů v reálném čase. Systém se skládá z mobilní aplikace pro Android a backendového API v Django.

## 🚀 Hlavní funkce

- **Monitoring v reálném čase**: Sledování vytížení CPU, RAM, disku a síťového provozu.
- **Interaktivní grafy**: Historie vytížení s nastavitelným časovým rozsahem (5m až 24h).
- **Správa služeb**: Možnost na dálku startovat, zastavovat, povolovat nebo zakazovat systémové služby (systemd).
- **Seznam procesů**: Přehled běžících procesů s možností řazení podle PID, názvu nebo zátěže.
- **Párování přes QR kód**: Rychlé a bezpečné přidání nového serveru pomocí párovacího kódu nebo scanu.
- **Push notifikace**: Okamžitá upozornění na výpadky serveru nebo vysoké vytížení zdrojů (přes Firebase).
- **Moderní UI**: Tmavý režim (Dark Mode) s Material 3 designem.

## 🛠 Technologický stack

### Mobilní aplikace (Android)
- **Jazyk**: Java
- **UI**: Material Components, Custom Canvas Drawing (pro grafy)
- **Sítě**: HttpURLConnection, JSON
- **Ostatní**: Firebase Cloud Messaging (FCM), ZXing (QR skener)

### Backend (API)
- **Framework**: Django + Django REST Framework
- **Autentizace**: JWT (JSON Web Tokens)
- **Databáze**: PostgreSQL / SQLite

## ⚙️ Instalace a nastavení

### 1. Backend (Django API)
1. Přejděte do složky s API.
2. Nainstalujte závislosti: `pip install -r requirements.txt`.
3. Proveďte migrace: `python manage.py migrate`.
4. Spusťte server: `python manage.py runserver 0.0.0.0:8000`.

### 2. Mobilní aplikace (Android Studio)
1. Otevřete projekt v Android Studiu.
2. **Důležité**: Upravte soubor `ApiConfig.java` a nastavte správnou `BASE_URL` na IP adresu vašeho serveru.
   ```java
   public static final String BASE_URL = "http://vaše-ip-adresa:8000";
   ```
3. Pokud používáte emulátor, použijte `http://10.0.2.2:8000`.
4. Sestavte a spusťte aplikaci na zařízení.

## 🔒 Bezpečnost
- Komunikace s API je chráněna pomocí JWT tokenů.
- Agenti (servery) komunikují přes unikátní `Agent-Token`, který je vygenerován při párování.
- Hesla uživatelů jsou v databázi hashována pomocí standardních Django algoritmů.

## 📄 Licence
Tento projekt je vytvořen pro studijní účely v rámci předmětu MMA.
