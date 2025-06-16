#!/bin/bash

# Output file
OUTPUT_FILE="startup_commands.txt"
# Clear file at start
> "$OUTPUT_FILE"

# Get all running container IDs
CONTAINERS=$(docker ps -q)

if [ -z "$CONTAINERS" ]; then
  echo "No running containers found."
  exit 0
fi

for CONTAINER in $CONTAINERS; do
  echo "------------------------------------------"
  echo "Container: $CONTAINER"
  
  IMAGE=$(docker inspect --format='{{.Config.Image}}' "$CONTAINER")
  NAME=$(docker inspect --format='{{.Name}}' "$CONTAINER" | sed 's/^\/\?//')

  ENV_VARS=$(docker inspect --format='{{range .Config.Env}}-e "{{.}}" {{end}}' "$CONTAINER")
  PORTS=$(docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{if $conf}}{{range $conf}}-p {{.HostIp}}:{{.HostPort}}:{{$p}} {{end}}{{end}}{{end}}' "$CONTAINER")
  VOLUMES=$(docker inspect --format='{{range .Mounts}}-v {{.Source}}:{{.Destination}}{{if .RW}},rw{{else}},ro{{end}} {{end}}' "$CONTAINER")
  RESTART=$(docker inspect --format='{{with .HostConfig.RestartPolicy}}{{if .Name}}--restart {{.Name}}{{end}}{{end}}' "$CONTAINER")
  NETWORK=$(docker inspect --format='{{if .HostConfig.NetworkMode}}--network {{.HostConfig.NetworkMode}}{{end}}' "$CONTAINER")
  ENTRYPOINT=$(docker inspect --format='{{if .Config.Entrypoint}}--entrypoint "{{join .Config.Entrypoint " "}}"{{end}}' "$CONTAINER")
  CMD=$(docker inspect --format='{{if .Config.Cmd}}{{range .Config.Cmd}}"{{.}}" {{end}}{{end}}' "$CONTAINER")

  # Compose full command
  FULL_COMMAND="docker run -d --name $NAME $ENV_VARS $PORTS $VOLUMES $RESTART $NETWORK $ENTRYPOINT $IMAGE $CMD"

  # Output to console
  echo ""
  echo "$FULL_COMMAND"
  echo ""

  # Save to file
  echo "$FULL_COMMAND" >> "$OUTPUT_FILE"
done

echo "All startup commands saved to $OUTPUT_FILE"
