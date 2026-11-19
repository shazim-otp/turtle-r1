import json
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import psutil
import pyautogui

# Set pyautogui failsafe to False so automated mouse movements near edges don't throw exception
pyautogui.FAILSAFE = False

# Common application launch paths / aliases on Windows
COMMON_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "command prompt": ["cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "task manager": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
    "vscode": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"), "code"],
    "code": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"), "code"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        "chrome.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "msedge.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        "brave.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        "firefox.exe",
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        "spotify.exe",
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe --processStart Discord.exe"),
        "discord.exe",
    ],
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
        "steam.exe",
    ],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
}

def run_powershell(command: str, timeout_seconds: int = 30) -> str:
    """Execute arbitrary PowerShell command on Windows with complete freedom."""
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            return f"Command exited with code {proc.returncode}.\nOutput: {out}\nError: {err}"
        return out if out else (err if err else "Command executed successfully with no output.")
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout_seconds} seconds."
    except Exception as exc:
        return f"Failed to execute command: {type(exc).__name__}: {exc}"

def run_command(command: str, timeout_seconds: int = 30) -> str:
    """Execute arbitrary command or PowerShell script on Windows."""
    return run_powershell(command, timeout_seconds)

def open_app(app_name: str) -> str:
    """Open any application, program, or registered file type on the Windows system."""
    key = app_name.strip().lower()

    # 1. Check known aliases
    if key in COMMON_APPS:
        candidates = COMMON_APPS[key]
        for candidate in candidates:
            try:
                if " " in candidate and not Path(candidate.split()[0]).exists() and not candidate.endswith(".exe"):
                    subprocess.Popen(candidate, shell=True)
                    return f"Started {app_name}."
                exe_part = candidate.split()[0] if " --" in candidate else candidate
                if Path(exe_part).exists() or shutil.which(exe_part):
                    subprocess.Popen(candidate, shell=True)
                    return f"Started {app_name}."
            except Exception:
                continue

    # 2. Try direct os.startfile (Windows shell launch for exe, protocol, or registered name)
    try:
        os.startfile(app_name)
        return f"Started {app_name} via Windows Shell."
    except Exception:
        pass

    # 3. Try with .exe appended
    if not app_name.endswith(".exe"):
        try:
            os.startfile(f"{app_name}.exe")
            return f"Started {app_name}.exe via Windows Shell."
        except Exception:
            pass

    # 4. Try via PowerShell Start-Process
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Start-Process -FilePath '{app_name}'"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return f"Started {app_name} via Start-Process."
    except Exception:
        pass

    # 5. Search in Start Menu or Common Folders
    search_dirs = [
        Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")),
        Path(os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")),
    ]
    for sdir in search_dirs:
        if sdir.exists():
            for link in sdir.rglob("*.lnk"):
                if key in link.stem.lower():
                    try:
                        os.startfile(str(link))
                        return f"Found and launched shortcut: {link.name}"
                    except Exception:
                        pass

    return f"Could not find or launch application '{app_name}'. You can launch it using run_powershell."

def open_windows_settings(page: str = "") -> str:
    """Open Windows Settings. Optionally pass specific sub-page e.g. 'network', 'bluetooth', 'apps'."""
    if os.name != "nt":
        return "Windows Settings is only available on Windows."
    uri = f"ms-settings:{page}".strip()
    try:
        os.startfile(uri)
        return f"Opened Windows Settings ({uri})."
    except Exception as exc:
        return f"Could not open Windows Settings: {exc}"

def search_files(root: str, filename_contains: str, max_results: int = 25) -> str:
    """Search file names recursively in a specified directory."""
    base = Path(root).expanduser()
    if not base.exists() or not base.is_dir():
        return f"Directory does not exist: {root}"
    term = filename_contains.lower()
    found = []
    try:
        for path in base.rglob("*"):
            if term in path.name.lower():
                found.append(f"{'[DIR] ' if path.is_dir() else '[FILE] '}{str(path)}")
                if len(found) >= min(max_results, 50):
                    break
    except (PermissionError, OSError):
        pass
    return "\n".join(found) if found else f"No files matching '{filename_contains}' found in {root}."

def read_file(path: str, max_lines: int = 200) -> str:
    """Read contents of a file on the computer."""
    target = Path(path).expanduser()
    if not target.exists():
        return f"File does not exist: {path}"
    if not target.is_file():
        return f"Path is not a regular file: {path}"
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return "".join(lines)
    except Exception as exc:
        return f"Failed to read file: {type(exc).__name__}: {exc}"

def write_file(path: str, content: str, mode: str = "w") -> str:
    """Write or append text content to a file."""
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_mode = "a" if mode.lower() in ("a", "append") else "w"
        with open(target, write_mode, encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {target} (mode: {write_mode})."
    except Exception as exc:
        return f"Failed to write to file: {type(exc).__name__}: {exc}"

def create_folder(path: str) -> str:
    """Create a folder at the specified path."""
    target = Path(path).expanduser()
    try:
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder ready at: {target}"
    except Exception as exc:
        return f"Failed to create folder: {exc}"

def system_status() -> str:
    """Retrieve detailed hardware and OS status: CPU, RAM, Disk, Battery, Uptime."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.home().anchor or "C:\\"))
    battery = psutil.sensors_battery()
    bat_str = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'Discharging'})" if battery else "No battery/Desktop"
    
    return (
        f"CPU Utilization: {psutil.cpu_percent(interval=0.3)}%\n"
        f"RAM Usage: {mem.percent}% ({round(mem.used / (1024**3), 1)} GB / {round(mem.total / (1024**3), 1)} GB)\n"
        f"System Disk: {disk.percent}% used ({round(disk.free / (1024**3), 1)} GB free)\n"
        f"Battery: {bat_str}\n"
        f"Running Processes: {len(psutil.pids())}"
    )

def take_screenshot() -> str:
    """Capture the current screen and save to Pictures/TURTLE."""
    folder = Path.home() / "Pictures" / "TURTLE"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "latest_screen.png"
    try:
        pyautogui.screenshot().save(target)
        return f"Screenshot captured and saved to: {target}"
    except Exception as exc:
        return f"Could not capture screenshot: {type(exc).__name__}: {exc}"

def analyze_screen(prompt: str = "Analyze the screen and describe the active windows and contents.") -> str:
    """Directly capture and visually inspect the user's screen using vision AI."""
    from .vision import analyze_desktop
    try:
        return analyze_desktop(prompt)
    except Exception as exc:
        return f"Screen vision analysis failed: {type(exc).__name__}: {exc}"

def browser_search(query: str) -> str:
    """Search Google in the default browser."""
    url = "https://www.google.com/search?q=" + quote_plus(query)
    webbrowser.open(url)
    return f"Opened Google search for: {query}"

def open_url(url: str) -> str:
    """Open any URL or web address in the default browser."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Navigated to: {url}"

def type_text(text: str) -> str:
    """Type text into the currently active/focused window."""
    pyautogui.write(text, interval=0.01)
    return f"Typed {len(text)} characters into the focused application."

def press_hotkey(keys: list[str]) -> str:
    """Press a key combination, e.g. ['ctrl', 'c'], ['alt', 'tab'], ['win', 'd'], ['enter']."""
    try:
        pyautogui.hotkey(*keys)
        return f"Pressed key combination: {' + '.join(keys)}"
    except Exception as exc:
        return f"Failed to press hotkey: {exc}"

def click_mouse(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
    """Click mouse at specified screen coordinates or current cursor position."""
    try:
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, clicks=clicks, button=button)
            return f"Clicked {button} button {clicks} time(s) at ({x}, {y})."
        else:
            pyautogui.click(clicks=clicks, button=button)
            return f"Clicked {button} button {clicks} time(s) at current cursor position."
    except Exception as exc:
        return f"Failed to click mouse: {exc}"

def control_volume(action: str) -> str:
    """Control audio: 'volume_up', 'volume_down', 'mute', 'play_pause', 'next', 'prev'."""
    action = action.lower().strip()
    key_map = {
        "volume_up": "volumeup",
        "up": "volumeup",
        "volume_down": "volumedown",
        "down": "volumedown",
        "mute": "volumemute",
        "play_pause": "playpause",
        "next": "nexttrack",
        "prev": "prevtrack",
    }
    if action in key_map:
        pyautogui.press(key_map[action])
        return f"Media control triggered: {action}"
    return f"Unknown volume/media action: {action}. Available: {list(key_map.keys())}"

def close_app(process_name: str) -> str:
    """Terminate or close a process/application by name (e.g. 'notepad.exe', 'chrome.exe')."""
    pname = process_name.lower().strip()
    if not pname.endswith(".exe"):
        pname_with_exe = f"{pname}.exe"
    else:
        pname_with_exe = pname
    killed = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in (pname, pname_with_exe):
                proc.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if killed > 0:
        return f"Terminated {killed} process instance(s) matching '{process_name}'."
    return f"No running processes matching '{process_name}' were found."

def activate_gesture_control() -> str:
    """Activate hand gesture control: hand as cursor, index+thumb pinch to left click, pinky+thumb to right click, fist/hold to scroll."""
    from .gesture import start_gesture_control
    return start_gesture_control()

def deactivate_gesture_control() -> str:
    """Deactivate hand gesture mouse control and close the tracking HUD."""
    from .gesture import stop_gesture_control
    return stop_gesture_control()

def stop_voice() -> str:
    """Immediately stop text-to-speech output and audio playback."""
    from .voice import stop_speech
    stop_speech()
    return "Voice playback stopped."

def execute_computer_task(task_instruction: str) -> str:
    """Execute a complex, multi-step autonomous desktop or browser operation using the Computer Use Engine (MCUE)."""
    from .computer_use import get_computer_engine
    engine = get_computer_engine()
    res = engine.execute_task(task_instruction)
    if res.get("success"):
        return f"Autonomous Task Succeeded: {res.get('summary', 'Completed.')}"
    return f"Autonomous Task Notice: {res.get('error', res.get('message', 'Completed with notes.'))}"

TOOL_FUNCTIONS = {
    "run_command": run_command,
    "run_powershell": run_powershell,
    "open_app": open_app,
    "close_app": close_app,
    "open_windows_settings": open_windows_settings,
    "search_files": search_files,
    "read_file": read_file,
    "write_file": write_file,
    "create_folder": create_folder,
    "system_status": system_status,
    "take_screenshot": take_screenshot,
    "analyze_screen": analyze_screen,
    "browser_search": browser_search,
    "open_url": open_url,
    "type_text": type_text,
    "press_hotkey": press_hotkey,
    "click_mouse": click_mouse,
    "control_volume": control_volume,
    "activate_gesture_control": activate_gesture_control,
    "deactivate_gesture_control": deactivate_gesture_control,
    "stop_voice": stop_voice,
    "execute_computer_task": execute_computer_task,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": "Execute PowerShell command or script on Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "PowerShell command to run."}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Launch program by name (e.g. 'chrome', 'notepad', 'calc').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application name or path."}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Close process by name (e.g. 'notepad.exe').",
            "parameters": {
                "type": "object",
                "properties": {
                    "process_name": {"type": "string", "description": "Process name to terminate."}
                },
                "required": ["process_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_windows_settings",
            "description": "Open Windows Settings, optional page (e.g. 'bluetooth', 'network').",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "Optional Settings URI subpage."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Find files recursively by name substring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string", "description": "Root folder path to search."},
                    "filename_contains": {"type": "string", "description": "Filename keyword."},
                    "max_results": {"type": "integer", "description": "Max results (default 25)."}
                },
                "required": ["root", "filename_contains"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read text file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text to file ('w' or 'a').",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path."},
                    "content": {"type": "string", "description": "Text content."},
                    "mode": {"type": "string", "description": "'w' or 'a'."}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create folder directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder path to create."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": "Get CPU, RAM, Disk, Battery status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Save full screen image to Pictures/TURTLE.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": "Capture screen and analyze with vision AI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Question or focus area."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_search",
            "description": "Google search in browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open URL in browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into focused element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type."}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_hotkey",
            "description": "Press keyboard shortcut keys e.g. ['ctrl', 'c'].",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"}, "description": "Key names."}
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_mouse",
            "description": "Click mouse at coordinates or current spot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string"},
                    "clicks": {"type": "integer"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": "Adjust audio: 'volume_up', 'volume_down', 'mute', 'play_pause'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "'volume_up', 'volume_down', 'mute', 'play_pause'"}
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "activate_gesture_control",
            "description": "Start webcam hand gesture mouse tracking.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deactivate_gesture_control",
            "description": "Stop hand gesture mouse tracking.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_voice",
            "description": "Stop text-to-speech audio.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_computer_task",
            "description": "Autonomous multi-step computer task across desktop/browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_instruction": {"type": "string", "description": "Task instruction."}
                },
                "required": ["task_instruction"],
            },
        },
    },
]

# Freedom / Jarvis Mode: Empty set means NO permission prompts ever.
APPROVAL_REQUIRED = set()
