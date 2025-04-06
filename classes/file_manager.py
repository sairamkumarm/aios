import os
import shutil
import glob
from pathlib import Path

class file_manager:
    """
    Python class to handle file management operations.
    This class provides methods to move, copy, delete files and directories,
    as well as list directory contents.
    """
    
    def __init__(self, detailed_intent: str):
        """
        Initialize the file_manager class.
        
        Args:
            detailed_intent (str): The specific file operation to perform.
        """
        self.detailed_intent = detailed_intent
    
    def run(self, params: dict):
        """
        Execute the file operation based on the detailed intent.
        
        Args:
            params (dict): Parameters required for the operation.
            
        Returns:
            str: Result message of the operation.
        """
        match self.detailed_intent:
            case "move_file":
                return self.move_file(params["source_location"], params["destination_location"])
            case "move_entire_directory":
                return self.move_entire_directory(params["directory_source_location"], params["directory_destination_location"])
            case "remove_entire_directory":
                return self.remove_entire_directory(params["directory_source_location"])
            case "delete_file":
                return self.delete_file(params["file_location"])
            case "opening_file":
                return self.opening_file(params["file_location"])
            case "copy_file":
                return self.copy_file(params["source_location"], params["destination_location"])
            case "list_contents_of_directory_with_optional_file_type_filter":
                return self.list_contents(params["directory_location"], params.get("constraint", ".*"))
            case _:
                return f"Invalid detailed intent: {self.detailed_intent}"
    
    def move_file(self, source_location: str, destination_location: str) -> str:
        """
        Move a file from source to destination.
        
        Args:
            source_location (str): Path to the source file.
            destination_location (str): Path to the destination directory.
            
        Returns:
            str: Result message of the operation.
        """
        try:
            # Handle wildcard in source path
            if '*' in source_location:
                files = glob.glob(source_location)
                if not files:
                    return f"No files found matching {source_location}"
                
                results = []
                for file in files:
                    dest_path = os.path.join(destination_location, os.path.basename(file))
                    shutil.move(file, dest_path)
                    results.append(f"Moved {file} to {dest_path}")
                
                return "\n".join(results)
            else:
                # Ensure destination directory exists
                os.makedirs(os.path.dirname(destination_location), exist_ok=True)
                
                # If destination is a directory, append the source filename
                if os.path.isdir(destination_location):
                    dest_path = os.path.join(destination_location, os.path.basename(source_location))
                else:
                    dest_path = destination_location
                
                shutil.move(source_location, dest_path)
                return f"Successfully moved {source_location} to {dest_path}"
        except FileNotFoundError:
            return f"Error: File {source_location} not found"
        except PermissionError:
            return f"Error: Permission denied when moving {source_location}"
        except Exception as e:
            return f"Error moving file: {str(e)}"
    
    def move_entire_directory(self, directory_source_location: str, directory_destination_location: str) -> str:
        """
        Move an entire directory from source to destination.
        
        Args:
            directory_source_location (str): Path to the source directory.
            directory_destination_location (str): Path to the destination directory.
            
        Returns:
            str: Result message of the operation.
        """
        try:
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(directory_destination_location), exist_ok=True)
            
            # Move the directory
            shutil.move(directory_source_location, directory_destination_location)
            return f"Successfully moved directory {directory_source_location} to {directory_destination_location}"
        except FileNotFoundError:
            return f"Error: Directory {directory_source_location} not found"
        except PermissionError:
            return f"Error: Permission denied when moving directory {directory_source_location}"
        except Exception as e:
            return f"Error moving directory: {str(e)}"
    
    def remove_entire_directory(self, directory_source_location: str) -> str:
        """
        Remove an entire directory.
        
        Args:
            directory_source_location (str): Path to the directory to remove.
            
        Returns:
            str: Result message of the operation.
        """
        try:
            # Remove the directory and all its contents
            shutil.rmtree(directory_source_location)
            return f"Successfully removed directory {directory_source_location}"
        except FileNotFoundError:
            return f"Error: Directory {directory_source_location} not found"
        except PermissionError:
            return f"Error: Permission denied when removing directory {directory_source_location}"
        except Exception as e:
            return f"Error removing directory: {str(e)}"
    
    def delete_file(self, file_location: str) -> str:
        """
        Delete a file.
        
        Args:
            file_location (str): Path to the file to delete.
            
        Returns:
            str: Result message of the operation.
        """
        try:
            # Handle wildcard in file path
            if '*' in file_location:
                files = glob.glob(file_location)
                if not files:
                    return f"No files found matching {file_location}"
                
                results = []
                for file in files:
                    os.remove(file)
                    results.append(f"Deleted {file}")
                
                return "\n".join(results)
            else:
                os.remove(file_location)
                return f"Successfully deleted {file_location}"
        except FileNotFoundError:
            return f"Error: File {file_location} not found"
        except PermissionError:
            return f"Error: Permission denied when deleting {file_location}"
        except Exception as e:
            return f"Error deleting file: {str(e)}"
    
    def opening_file(self, file_location: str) -> str:
        """
        Open a file (returns the file path as this would typically be handled by the UI).
        
        Args:
            file_location (str): Path to the file to open.
            
        Returns:
            str: Result message with the file path.
        """
        try:
            if os.path.exists(file_location):
                return f"File ready to open: {file_location}"
            else:
                return f"Error: File {file_location} not found"
        except Exception as e:
            return f"Error opening file: {str(e)}"
    
    def copy_file(self, source_location: str, destination_location: str) -> str:
        """
        Copy a file from source to destination.
        
        Args:
            source_location (str): Path to the source file.
            destination_location (str): Path to the destination directory.
            
        Returns:
            str: Result message of the operation.
        """
        try:
            # Handle wildcard in source path
            if '*' in source_location:
                files = glob.glob(source_location)
                if not files:
                    return f"No files found matching {source_location}"
                
                results = []
                for file in files:
                    # Ensure destination directory exists
                    os.makedirs(destination_location, exist_ok=True)
                    
                    dest_path = os.path.join(destination_location, os.path.basename(file))
                    shutil.copy2(file, dest_path)
                    results.append(f"Copied {file} to {dest_path}")
                
                return "\n".join(results)
            else:
                # Ensure destination directory exists
                if os.path.isdir(destination_location):
                    os.makedirs(destination_location, exist_ok=True)
                    dest_path = os.path.join(destination_location, os.path.basename(source_location))
                else:
                    os.makedirs(os.path.dirname(destination_location), exist_ok=True)
                    dest_path = destination_location
                
                shutil.copy2(source_location, dest_path)
                return f"Successfully copied {source_location} to {dest_path}"
        except FileNotFoundError:
            return f"Error: File {source_location} not found"
        except PermissionError:
            return f"Error: Permission denied when copying {source_location}"
        except Exception as e:
            return f"Error copying file: {str(e)}"
    
    def list_contents(self, directory_location: str, constraint: str = ".*") -> str:
        """
        List contents of a directory with optional file type filtering.
        
        Args:
            directory_location (str): Path to the directory to list.
            constraint (str): File type filter in the format '.{ext1,ext2,...}' or '.*' for all files.
            
        Returns:
            str: Formatted string with directory contents.
        """
        try:
            # Default to current directory if not specified
            if not directory_location or directory_location == '/home/oreneus':
                directory_location = os.getcwd()
            
            # Ensure directory exists
            if not os.path.exists(directory_location):
                return f"Error: Directory {directory_location} not found"
            
            # Parse constraint to get file extensions
            if constraint == ".*" or constraint == ".{*}":
                pattern = "*"  # Match all files
            else:
                # Extract extensions from format like '.{jpg,png,gif}'
                extensions = constraint.strip('.{}').split(',')
                pattern = "*.{" + ",".join(extensions) + "}"
            
            # Get all matching files
            files = []
            for item in glob.glob(os.path.join(directory_location, pattern), recursive=False):
                if os.path.isfile(item):
                    size = os.path.getsize(item)
                    files.append(f"{os.path.basename(item)} ({self._format_size(size)})")
            
            # Get all directories
            directories = []
            for item in os.listdir(directory_location):
                item_path = os.path.join(directory_location, item)
                if os.path.isdir(item_path):
                    directories.append(f"{item}/ (directory)")
            
            # Combine results
            result = f"Contents of {directory_location}:\n"
            if directories:
                result += "\nDirectories:\n" + "\n".join(directories)
            if files:
                result += "\n\nFiles:\n" + "\n".join(files)
            if not directories and not files:
                result += "\nNo items found matching the criteria."
            
            return result
        except PermissionError:
            return f"Error: Permission denied when accessing {directory_location}"
        except Exception as e:
            return f"Error listing directory contents: {str(e)}"
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.
        
        Args:
            size_bytes (int): Size in bytes.
            
        Returns:
            str: Formatted size string.
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
