import subprocess

class alarms:
    """
    A class to manage alarms using the `at` command and notify-send on Linux.
    Supports listing, scheduling (by time/date or duration), and removing alarms.
    """

    def __init__(self, detailed_intent: str):
        self.detailed_intent = detailed_intent

    def run(self, params: dict):
        match self.detailed_intent:
            case "list_scheduled_alarms":
                return self.list_scheduled_alarms()
            case "schedule_alarm_at_time_and_date":
                return self.schedule_alarm_at_time_and_date(params["time"], params["date"])
            case "schedule_alarm_at_duration_from_now":
                return self.schedule_alarm_at_duration(params["duration"])
            case "remove_scheduled_alarm":
                return self.remove_scheduled_alarm(params["job_id"])
            case _:
                return f"Invalid detailed intent: {self.detailed_intent}"

    def _run_command(self, command, input_text=None):
        try:
            result = subprocess.run(
                command,
                input=input_text,
                capture_output=True,
                text=True,
                shell=True
            )
            return result.stdout.strip() if result.stdout else result.stderr.strip()
        except Exception as e:
            return f"Error: {e}"

    def list_scheduled_alarms(self):
        return self._run_command("atq")

    def schedule_alarm_at_time_and_date(self, time: str, date: str):
        # time: "14:30", date: "040625" -> becomes "14:30 04/06/25"
        if date in ["tom", "day_after_tom"]:
            date_str = date  # directly use for now, to be interpreted by another system
        else:
            date_str = f"{date[:2]}/{date[2:4]}/{date[4:]}"
        at_time = f"{time} {date_str}"
        command = f'echo "notify-send \'Alarm\' \'⏰ Alarm triggered!\'" | at {at_time}'
        return self._run_command(command)

    def schedule_alarm_at_duration(self, duration: str):
        # Example: '10 minutes' → at now + 10 minutes
        command = f'echo "notify-send \'Alarm\' \'⏰ Alarm triggered!\'" | at now + {duration}'
        return self._run_command(command)

    def remove_scheduled_alarm(self, job_id: str):
        return self._run_command(f"atrm {job_id}")
