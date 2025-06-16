#!/bin/bash

# Sprawdzanie czy podano parametr
if [ $# -ne 1 ]; then
  echo "Użycie: $0 numer_snapshotu"
  exit 1
fi

SNAPSHOT_NUM=$1

# Pobranie listy ID wszystkich działających kontenerów
CONTAINERS=$(docker ps -q)

if [ -z "$CONTAINERS" ]; then
  echo "Brak działających kontenerów."
  exit 0
fi

for CONTAINER_ID in $CONTAINERS; do
  # Pobranie nazwy oryginalnego obrazu kontenera
  IMAGE_NAME=$(docker inspect --format='{{.Config.Image}}' $CONTAINER_ID)

  # Jeżeli obraz nie ma tagu, nadamy 'latest'
  if [[ "$IMAGE_NAME" != *:* ]]; then
    IMAGE_NAME="${IMAGE_NAME}:latest"
  fi

  # Wyciągamy tylko nazwę obrazu bez tagu
  BASE_IMAGE_NAME=$(echo "$IMAGE_NAME" | cut -d':' -f1)

  # Nowa nazwa obrazu
  NEW_IMAGE_NAME="${BASE_IMAGE_NAME}_snapshot_${SNAPSHOT_NUM}"

  echo "Tworzę snapshot kontenera $CONTAINER_ID -> $NEW_IMAGE_NAME"

  docker commit $CONTAINER_ID $NEW_IMAGE_NAME
done
