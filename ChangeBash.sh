#!/bin/bash

# 1. Skopiuj /bin/bash do /bin/bachsh, jeśli jeszcze nie istnieje
if [ ! -f /bin/bachsh ]; then
    cp /bin/bash /bin/bachsh
    chmod +x /bin/bachsh
    echo "Utworzono /bin/bachsh"
else
    echo "/bin/bachsh już istnieje"
fi

# 2. Dla każdego użytkownika z interaktywną powłoką – zmień ją na /bin/bachsh
awk -F: '($7 != "/sbin/nologin" && $7 != "/usr/sbin/nologin" && $7 != "/bin/false") { print $1 }' /etc/passwd | while read USER; do
    usermod -s /bin/bachsh "$USER"
    echo "Zmieniono powłokę użytkownika $USER na /bin/bachsh"
done