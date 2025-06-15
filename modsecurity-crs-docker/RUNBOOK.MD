# Podłączenie ModSecurity (MS) do aplikacji

## Krok 1: Weryfikacja kontenerów i portów

Sprawdź, jakie kontenery są uruchomione i na jakich portach działają:

```bash
docker ps
```

## Krok 2: Sprawdzenie sieci Dockera

Zidentyfikuj, do jakiej sieci jest podpięty kontener:

```bash
docker network ls
docker network inspect <nazwa_sieci_z_poprzedniej_komendy>
```

## Krok 3: Konfiguracja backendu w ModSecurity

W pliku konfiguracyjnym ModSecurity ustaw, dokąd ma kierować ruch:

```yaml
BACKEND: http://hostname:port
BACKEND: https://docker-nginx-flask-demo-nginx-1:443/
```

## Krok 4: Dodanie sieci do `docker-compose.yaml`

Dodaj sieć do konfiguracji:

```yaml
networks:
  backend:
    name: docker-nginx-flask-demo_default
    driver: bridge
    external: true
```

## Krok 5: Certyfikaty

Z chronionego kontenera pobierz certyfikat i klucz, a następnie podłącz je do proxy:

```yaml
- ./cert.pem:/etc/nginx/conf/server.crt
- ./key.pem:/etc/nginx/conf/server.key
```

## Krok 6: Logowanie

Ustaw odpowiednią nazwę pliku logów w ModSecurity:

```yaml
MODSEC_AUDIT_LOG: "/opt/logs/flask.log"
```

## Krok 7: Mapowanie portów

W sekcji `services` ustaw porty (ważne: pierwszy port przed `:` powinien odpowiadać temu z właściwej usługi):

```yaml
ports:
  - "80:8080"
  - "443:8443"
```

⚠️ W **oryginalnej** usłudze należy usunąć sekcję `ports`, aby uniknąć konfliktu.

## Krok 8: Uruchomienie ModSecurity

Przejdź do katalogu z konfiguracją ModSecurity i uruchom:

```bash
docker compose up
```

## Krok 9: Konfiguracja logów dla SPLUNKa

Jeśli SPLUNK jest zainstalowany, logi powinny znaleźć się w `/opt/logs`.

Jeśli katalog nie istnieje, należy go utworzyć i nadać odpowiednie uprawnienia:

```bash
mkdir /opt/logs
chmod 777 /opt/logs
```

W razie problemów:

```bash
docker compose down
/opt/splunkforwarder/bin/splunk restart
```

---

> Dokument ten opisuje podstawowe kroki do integracji ModSecurity z aplikacją działającą w Dockerze oraz konfiguracji logowania dla SPLUNKa.

Wyjątki dodajemy do plików:
RESPONSE-999-EXCLUSION-RULES-AFTER-CRS.conf
REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf

```bash
#
# Wyłączenie konkretnej reguły CRS, bo generuje fałszywe alarmy
#
SecRuleRemoveById 981176
```

