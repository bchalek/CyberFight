#!/bin/bash

# Ustawienia daty dla nazw plików backupu
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Przetwarzaj wszystkich użytkowników z /etc/passwd
awk -F: '{ print $1 ":" $6 }' /etc/passwd | while IFS=":" read -r USER HOME_DIR; do
    AUTH_KEYS="$HOME_DIR/.ssh/authorized_keys"
    
    # Sprawdź czy plik authorized_keys istnieje
    if [ -f "$AUTH_KEYS" ]; then
        echo "[$USER] Znaleziono authorized_keys: $AUTH_KEYS"

        # Tworzenie backupu
        BACKUP_FILE="$HOME_DIR/.ssh/authorized_keys.backup.$TIMESTAMP"
        cp "$AUTH_KEYS" "$BACKUP_FILE"
        echo "[$USER] Backup zapisany jako: $BACKUP_FILE"

        # Usuwanie oryginalnego pliku
        rm "$AUTH_KEYS"
        echo "[$USER] Plik authorized_keys został usunięty"
    else
        echo "[$USER] Brak pliku authorized_keys"
    fi
done