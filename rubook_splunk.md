# Runbook: Instalacja i Konfiguracja Splunk Universal Forwarder

## Cel
Ten skrypt automatyzuje proces instalacji Splunk Universal Forwarder, konfiguracji monitorowania logów oraz instalacji aplikacji integrującej z chmurą Splunk.

---

## Kroki wykonywane przez skrypt

### 1. Instalacja `curl`
```bash
apt-get update
apt-get install curl -y
```
**Cel:** Upewnienie się, że `curl` jest dostępny (niezbędny w wielu środowiskach automatyzacji).

---

### 2. Instalacja Splunk Universal Forwarder
```bash
dpkg -i splunkforwarder-9.4.3-237ebbd22314-linux-amd64.deb
```
**Cel:** Zainstalowanie paczki `.deb` z lokalnego katalogu.

---

### 3. Utworzenie katalogu na logi
```bash
mkdir /opt/logs
chmod 777 /opt/logs
```
**Cel:** Umożliwienie aplikacjom zapisu logów oraz zapewnienie, że Splunk ma do nich pełny dostęp.

---

### 4. Przeniesienie aplikacji SPL do katalogu tymczasowego
```bash
cp ./splunkclouduf.spl /tmp/
```
**Cel:** Przygotowanie aplikacji SPLunk (.spl) do instalacji.

---

### 5. Uruchomienie Splunk Forwardera
```bash
/opt/splunkforwarder/bin/splunk start
```
**Cel:** Pierwsze uruchomienie usługi.

 - Login: sc_admin
 - Pass: CyberFight
---

### 6. Konfiguracja pliku `input.conf`
```bash
cat << EOF >/opt/splunkforwarder/etc/system/local/inputs.conf
[monitor:/opt/logs/*]
disabled=false
followTail=0
initCrcLenght=65535
index=mods
source=mods
EOF
```
**Cel:** Konfiguracja monitorowania katalogu `/opt/logs` i przypisanie danych do indeksu `mods`.

---

### 7. Instalacja aplikacji `.spl`
```bash
/opt/splunkforwarder/bin/splunk install app /tmp/splunkclouduf.spl
```
**Cel:** Instalacja aplikacji integrującej Splunk z chmurą (Universal Forwarder Cloud App).

---

### 8. Restart Splunk
```bash
/opt/splunkforwarder/bin/splunk restart
```
**Cel:** Restart jest wymagany po instalacji aplikacji.

---

### 9. Walidacja
```bash
/opt/splunkforwarder/bin/splunk list forward-server
```
**Cel:** Sprawdzenie, czy forwardery danych są aktywne.

---

### 10. Weryfikacja w konsoli splunk
```bash

https://prd-p-tws40.splunkcloud.com/ 
Login: sc_admin 
Pass: CyberFight 

```
**Cel:** Sprawdzenie, czy  dane trafiają do konsoli.

---

## Możliwe problemy i rozwiązania

| Problem | Możliwe przyczyny | Rozwiązanie |
|--------|--------------------|-------------|
| `dpkg: error processing package` | Brak zależności | Uruchom `apt-get install -f` |
| Splunk nie startuje | Brak uprawnień, błędna konfiguracja | Sprawdź logi: `/opt/splunkforwarder/var/log/splunk` |
| Logi nie pojawiają się w Splunku | Błędna ścieżka w `input.conf`, brak zapisu do `/opt/logs` | Zweryfikuj ścieżki, sprawdź uprawnienia |
| Aplikacja `.spl` się nie instaluje | Uszkodzony plik, brak miejsca | Zweryfikuj plik `splunkclouduf.spl`, sprawdź `df -h` |

---

## Uwagi końcowe

- Upewnij się, że porty i reguły firewall umożliwiają komunikację Splunka z platformą chmurową.
- Jeżeli skrypt wykonuje się jako część CI/CD, dodaj walidację istnienia plików `.deb` i `.spl`.

