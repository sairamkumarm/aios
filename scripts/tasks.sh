#!/bin/bash

TASKS_DIR="$HOME/.tasks"
METADATA_FILE="$TASKS_DIR/metadata.txt"

mkdir -p "$TASKS_DIR"
touch "$METADATA_FILE"

sanitize_title() {
  echo "$1" | tr ' ' '_' | tr -cd '[:alnum:]_'
}

get_default_deadline() {
  date -u -d 'tomorrow 00:00:00' +"%Y-%m-%dT%H:%M:%SZ"
}

is_valid_iso_utc() {
  [[ "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$ ]]
}

case $1 in
  add)
    TITLE="$2"
    DEADLINE="${3:-$(get_default_deadline)}"

    if [ -z "$TITLE" ]; then
      echo "Error: Title is required."
      exit 1
    fi

    if ! is_valid_iso_utc "$DEADLINE"; then
      echo "Invalid deadline format. Use ISO format: YYYY-MM-DDTHH:MM:SSZ"
      exit 1
    fi

    if grep -q "^$TITLE," "$METADATA_FILE"; then
      echo "A task with the title '$TITLE' already exists."
    else
      CREATED_DATE=$(date -u +"%Y-%m-%d %H:%M:%S")
      FILENAME=$(sanitize_title "$TITLE").txt
      echo -e "${TITLE^^}\nCreated: $CREATED_DATE UTC\nDeadline: $DEADLINE" > "$TASKS_DIR/$FILENAME"
      echo "$TITLE,$CREATED_DATE,$DEADLINE,$FILENAME" >> "$METADATA_FILE"
      echo "Task '$TITLE' added with deadline $DEADLINE!"
    fi
    ;;
  delete)
    FILENAME=$(grep "^$2," "$METADATA_FILE" | cut -d ',' -f4)
    if [ -z "$FILENAME" ]; then
      echo "Task '$2' not found."
    else
      rm -f "$TASKS_DIR/$FILENAME"
      sed -i "/^$2,/d" "$METADATA_FILE"
      echo "Task '$2' deleted."
    fi
    ;;
  list)
    printf "\e[1m%-30s %-20s %-25s\e[0m\n" "TITLE" "CREATED" "DEADLINE"
    while IFS=',' read -r TITLE CREATED DEADLINE FILENAME; do
      printf "%-30s %-20s %-25s\n" "$TITLE" "$CREATED" "$DEADLINE"
    done < "$METADATA_FILE"
    ;;
  read)
    FILENAME=$(grep "^$2," "$METADATA_FILE" | cut -d ',' -f4)
    if [ -z "$FILENAME" ]; then
      echo "Task '$2' not found."
    else
      cat "$TASKS_DIR/$FILENAME"
    fi
    ;;
  *)
    echo "Usage: tasks {add <title> [deadline] | delete <title> | list | read <title>}"
    echo "  - Deadline must be in format: YYYY-MM-DDTHH:MM:SSZ"
    echo "  - If no deadline is given, defaults to next midnight UTC"
    ;;
esac
