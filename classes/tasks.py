import os
import subprocess
import datetime
from pathlib import Path

class tasks:
    """
    Python class to interact with the tasks shell script.
    This class provides methods to add, delete, list, and read tasks.
    """
    
    def __init__(self, detailed_intent: str):
        """
        Initialize the tasks class.
        """
        self.script_path = os.environ.get('TASKS_PATH')
        self.detailed_intent = detailed_intent 
    
    def run(self, params: dict):
        match self.detailed_intent:
            case "add_task":
                title = params["title"]
                deadline = params.get("deadline", None)
                return self.add_task(title, deadline)
            case "delete_task":
                return self.delete_task(params["title"])
            case "list_tasks":
                return self.list_tasks()
            case "read_task":
                return self.read_task(params["title"])
            case _:
                return f"Invalid detailed intent: {self.detailed_intent}"

    def _run_command(self, args):
        """
        Run the tasks script with given arguments.
        
        Args:
            args (list): List of command-line arguments to pass to the script.
            
        Returns:
            str: Output from the script execution.
        """
        try:
            result = subprocess.run(
                [self.script_path] + args,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing tasks command: {str(e)}"
    
    def list_tasks(self):
        """
        List all existing tasks.
        
        Returns:
            str: A formatted string containing the list of tasks.
        """
        return self._run_command(["list"])
    
    def add_task(self, title, deadline=None):
        """
        Add a new task with the given title and optional deadline.
        
        Args:
            title (str): The title for the new task.
            deadline (str, optional): The deadline in ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ).
                                      If omitted, defaults to next-day midnight UTC.
            
        Returns:
            str: Result message from the script.
        """
        args = ["add", title]
        if deadline:
            args.append(deadline)
        return self._run_command(args)
    
    def delete_task(self, title):
        """
        Delete a task with the given title.
        
        Args:
            title (str): The title of the task to delete.
            
        Returns:
            str: Result message from the script.
        """
        return self._run_command(["delete", title])
    
    def read_task(self, title):
        """
        Read the content of a task.
        
        Args:
            title (str): The title of the task to read.
            
        Returns:
            str: The content of the task or an error message.
        """
        return self._run_command(["read", title])
