import os
import subprocess
from pathlib import Path

class notes:
    """
    Python class to interact with the notes shell script.
    This class provides methods to list, add, append, delete, and read notes.
    """
    
    def __init__(self, detailed_intent: str):
        """
        Initialize the notes class.
        """
        self.script_path = "/usr/local/bin/notes"
        self.detailed_intent = detailed_intent
    
    def run(self, params: dict):
        match self.detailed_intent:
            case "list_notes":
                return self.list_notes()
            case "add_note":
                return self.add_note(params["title"], params["content"])
            case "append_to_note":
                return self.append_to_note(params["title"], params["content"])
            case "delete_note":
                return self.delete_note(params["title"])
            case "read_note":
                return self.read_note(params["title"])
            case _:
                return f"Invalid detailed intent: {self.detailed_intent}"

    def _run_command(self, args):
        """
        Run the notes script with given arguments.
        
        Args:
            args (list): List of command-line arguments to pass to the script.
            
        Returns:
            str: Output from the script execution.
        """
        try:
            env = os.environ.copy()
            env["HOME"] = "/Users/tenzintsering"
            result = subprocess.run(
                [self.script_path] + args,
                capture_output=True,
                text=True,
                check=False,
                env=env
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing notes command: {str(e)}"
    
    def list_notes(self):
        """
        List all existing notes.
        
        Returns:
            str: A formatted string containing the list of notes.
        """
        return self._run_command(["list"])
    
    def add_note(self, title, content):
        """
        Add a new note with the given title and content.
        
        Args:
            title (str): The title for the new note.
            content (str): The content of the note.
            
        Returns:
            str: Result message from the script.
        """
        return self._run_command(["add", title, content])
    
    def append_to_note(self, title, content):
        """
        Append content to an existing note.
        
        Args:
            title (str): The title of the note to append to.
            content (str): The content to append.
            
        Returns:
            str: Result message from the script.
        """
        return self._run_command(["append", title, content])
    
    def delete_note(self, title):
        """
        Delete a note with the given title.
        
        Args:
            title (str): The title of the note to delete.
            
        Returns:
            str: Result message from the script.
        """
        return self._run_command(["delete", title])
    
    def read_note(self, title):
        """
        Read the content of a note.
        
        Args:
            title (str): The title of the note to read.
            
        Returns:
            str: The content of the note or an error message.
        """
        return self._run_command(["read", title])