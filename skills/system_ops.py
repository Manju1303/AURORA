import os
import json
import subprocess
import datetime
from typing import List, Dict, Any, Callable
from core.skill import Skill


class SystemSkill(Skill):
    @property
    def name(self) -> str:
        return "system_skill"

    def __init__(self):
        self.ALLOWED_APPS = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "taskmgr": "taskmgr.exe",
            "paint": "mspaint.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "vlc": "vlc.exe",
            "spotify": "spotify.exe",
            "vscode": "code.exe",
            "camera": "microsoft.windows.camera:",
            "photos": "ms-photos:",
            "settings": "ms-settings:",
            "file manager": "explorer.exe",
        }

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": "open_app", "description": "Open a Windows application or file",
             "parameters": {"type": "OBJECT", "properties": {
                 "app_name": {"type": "STRING", "description": "App name to open"}
             }, "required": ["app_name"]}},
            {"name": "set_volume", "description": "Set system volume (0-100)",
             "parameters": {"type": "OBJECT", "properties": {
                 "level": {"type": "INTEGER", "description": "Volume level 0-100"}
             }, "required": ["level"]}},
            {"name": "get_time", "description": "Get current time and date",
             "parameters": {"type": "OBJECT", "properties": {}}},
            {"name": "take_screenshot", "description": "Take a screenshot of the screen",
             "parameters": {"type": "OBJECT", "properties": {}}},
            {"name": "shutdown_computer", "description": "Shutdown or restart the computer",
             "parameters": {"type": "OBJECT", "properties": {
                 "action": {"type": "STRING", "description": "'shutdown' or 'restart'"}
             }, "required": ["action"]}},
        ]

    def get_functions(self) -> Dict[str, Callable]:
        return {
            "open_app": self.open_app,
            "set_volume": self.set_volume,
            "get_time": self.get_time,
            "take_screenshot": self.take_screenshot,
            "shutdown_computer": self.shutdown_computer,
        }

    def open_app(self, app_name):
        try:
            name = app_name.lower().strip()
            if name in self.ALLOWED_APPS:
                target = self.ALLOWED_APPS[name]
                # Handle ms-URI apps
                if target.endswith(":"):
                    subprocess.Popen(f"start {target}", shell=True)
                else:
                    os.startfile(target)
                return json.dumps({"status": "success", "app": name})
            else:
                # Try to open directly (for common paths)
                try:
                    subprocess.Popen(["start", app_name], shell=True)
                    return json.dumps({"status": "attempted", "app": app_name})
                except:
                    return json.dumps({"status": "denied", "reason": f"{app_name} not in whitelist"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def set_volume(self, level):
        try:
            val = max(0, min(100, int(level)))
            # PowerShell volume control
            cmd = (
                f"$obj = new-object -com wscript.shell; "
                f"for($i=0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; "
                f"for($i=0; $i -lt {int(val/2)}; $i++) {{ $obj.SendKeys([char]175) }}"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
            return json.dumps({"status": "success", "level": val})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_time(self):
        """✅ NEW: Return current time and date"""
        now = datetime.datetime.now()
        return json.dumps({
            "status": "success",
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%A, %B %d %Y"),
            "day": now.strftime("%A")
        })

    def take_screenshot(self):
        """✅ NEW: Take a screenshot and save to Desktop"""
        try:
            import pyautogui
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.path.expanduser("~"), "Desktop", f"aurora_screenshot_{timestamp}.png")
            pyautogui.screenshot(path)
            return json.dumps({"status": "success", "saved_to": path})
        except ImportError:
            # Fallback using PowerShell
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(os.path.expanduser("~"), "Desktop", f"aurora_screenshot_{timestamp}.png")
                ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen | Out-Null; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $graphics = [System.Drawing.Graphics]::FromImage($bmp); $graphics.CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save('{path}');"
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
                return json.dumps({"status": "success", "saved_to": path})
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def shutdown_computer(self, action="shutdown"):
        """✅ NEW: Shutdown or restart with 30s warning"""
        try:
            if action == "restart":
                subprocess.run(["shutdown", "/r", "/t", "30", "/c", "AURORA initiated restart"], check=True)
                return json.dumps({"status": "success", "action": "restart", "delay_seconds": 30})
            else:
                subprocess.run(["shutdown", "/s", "/t", "30", "/c", "AURORA initiated shutdown"], check=True)
                return json.dumps({"status": "success", "action": "shutdown", "delay_seconds": 30})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
