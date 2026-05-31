# SCAN

`SCAN` is a Windows diagnostics tool for reset-readiness and repair blockers.  
It runs targeted system checks and gives actionable findings with remediation hints.

## Core Checks

- disk space, disk/event health, and NTFS-related risk signals
- SFC / DISM / CHKDSK / WinSxS pending state
- WinRE and reset-policy readiness
- reboot-required and servicing-state flags
- suspicious autoruns, services, tasks, and startup entries
- BCD, TrustedInstaller, BitLocker, Secure Boot, TPM, and update health

## Requirements

- Windows 10 or Windows 11
- Python 3.10+
- Administrator privileges

## Run From Source

Recommended launcher (auto-elevates + installs Python dependencies):

```bat
RUN.bat
```

Direct usage:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Flags:

```powershell
python main.py --fast
python main.py --no-pause
python main.py --fast --no-pause
```

## Output Files

SCAN writes logs to `%TEMP%\reset_diag`:

- `full_log.txt` - verbose command output
- `problems.txt` - findings only
- `console_output.log` - terminal transcript

Exit code behavior:

- `0` = no blockers detected
- `1` = one or more findings detected

## Build EXE (PyInstaller)

Use an isolated environment for reproducible builds:

```powershell
python -m venv .buildvenv
.\.buildvenv\Scripts\python -m pip install --upgrade pip
.\.buildvenv\Scripts\python -m pip install -r requirements.txt pyinstaller
.\.buildvenv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --name SCAN --icon icon.ico main.py
```

Build output:

- `dist\SCAN.exe`
 
