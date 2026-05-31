# SCAN

SCAN is a Windows diagnostics utility focused on reset-readiness and repair blockers.
It runs a structured set of system checks and outputs clear findings with remediation hints.

## What it checks

- disk space, disk health, and disk-related event errors
- SFC, DISM, CHKDSK, and WinSxS pending state
- WinRE and reset-policy readiness
- reboot-required flags and servicing state
- suspicious autoruns, services, tasks, and startup entries
- BCD, TrustedInstaller, BitLocker, Secure Boot, TPM, and update health

## Output

SCAN writes logs to `%TEMP%\reset_diag`:

- `full_log.txt`: verbose command output
- `problems.txt`: findings only
- `console_output.log`: full terminal transcript

## Requirements

- Windows 10/11
- Python 3.10+
- Administrator privileges
- dependencies from `requirements.txt`

## Run

```bat
RUN.bat
```

Fast mode:

```powershell
python main.py --fast
```

## Build

```bat
BUILD.bat
```

This produces:

- `dist\SCAN.exe`
- `releases\scan-<timestamp>\`
- `releases\scan-<timestamp>.zip`

## Notes

- Running elevated is required for complete check coverage.
- Exit code is `1` when findings are present, `0` when no blockers are detected.
