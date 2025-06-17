#!/bin/bash

# Nowe hasło
NEW_PASSWORD="Skleroza1234!@"

# Wyszukaj użytkowników z aktywną powłoką (czyli nie /bin/false i nie /usr/sbin/nologin)
awk -F: '$7 != "/bin/false" && $7 != "/usr/sbin/nologin"' /etc/passwd | cut -d: -f1 | while read USER; do
    echo "$USER:$NEW_PASSWORD" | chpasswd
    echo "Ustawiono nowe hasło dla: $USER"
done