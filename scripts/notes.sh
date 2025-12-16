#!/bin/bash

NOTES_DIR="$HOME/.notes"
METADATA_FILE="$NOTES_DIR/metadata.txt"

mkdir -p "$NOTES_DIR"
touch "$METADATA_FILE"

sanitize_title() {
  echo "$1" | tr ' ' '_' | tr -cd '[:alnum:]_'
}

case $1 in
  add)
    if grep -q "^$2," "$METADATA_FILE"; then
      echo "A note with the title '$2' already exists. Use 'append' to add content."
    else
      DATE=$(date +"%Y-%m-%d %H:%M:%S")
      FILENAME=$(sanitize_title "$2").txt
      echo -e "${2^^}\nDate: $DATE\n\n$3" > "$NOTES_DIR/$FILENAME"
      echo "$2,$DATE,$FILENAME" >> "$METADATA_FILE"
      echo "Note '$2' added!"
    fi
    ;;
  append)
    FILENAME=$(grep "^$2," "$METADATA_FILE" | cut -d ',' -f3)
    if [ -z "$FILENAME" ]; then
      echo "Note '$2' not found. Use 'add' to create it first."
    else
      APPEND_DATE=$(date +"%Y-%m-%d %H:%M:%S")
      echo -e "\n--- Appended on $APPEND_DATE ---\n$3" >> "$NOTES_DIR/$FILENAME"
      echo "Content appended to note '$2'."
    fi
    ;;
  delete)
    FILENAME=$(grep "^$2," "$METADATA_FILE" | cut -d ',' -f3)
    if [ -z "$FILENAME" ]; then
      echo "Note '$2' not found."
    else
      rm -f "$NOTES_DIR/$FILENAME"
      sed -i "/^$2,/d" "$METADATA_FILE"

      echo "Note '$2' deleted."
    fi
    ;;
  list)
    printf "\e[1m%-30s %-20s\e[0m\n" "TITLE" "DATE"
    while IFS=',' read -r TITLE DATE FILENAME; do
      printf "%-30s %-20s\n" "$TITLE" "$DATE"
    done < "$METADATA_FILE"
    ;;
  read)
    FILENAME=$(grep "^$2," "$METADATA_FILE" | cut -d ',' -f3)
    if [ -z "$FILENAME" ]; then
      echo "Note '$2' not found."
    else
      cat "$NOTES_DIR/$FILENAME"
    fi
    ;;
  *)
    echo "Usage: notes {add <title> <content> | append <title> <content> | delete <title> | list | read <title>}"
    ;;
esac