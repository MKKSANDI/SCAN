# scan.py
# SCAN — System Checks & Analysis (stable UI, issue counter, PyInstaller-ready, 30 checks)
# Requires: pip install rich pystyle

import os, sys, re, time, shutil, ctypes, logging, tempfile, subprocess, textwrap
from logging.handlers import RotatingFileHandler
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

# ================= PyInstaller helpers =================
def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return str(Path(base) / rel)

def is_frozen() -> bool:
    return getattr(sys, "frozen", False)

# ================= Paths / Logs =================
OUTDIR = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "reset_diag"
TMPDIR = OUTDIR / "_tmp"
OUTDIR.mkdir(parents=True, exist_ok=True)
TMPDIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = OUTDIR / "full_log.txt"              # verbose command logs
SUMMARY_PATH = OUTDIR / "problems.txt"          # issues only
TRANSCRIPT_PATH = OUTDIR / "console_output.log" # everything shown
open(SUMMARY_PATH, "w", encoding="utf-8").close()

# ================= Console mirroring (Rich-friendly) =================
class ConsoleTee:
    """
    Mirror console output to transcript while behaving TTY-ish so Rich can live-render.
    """
    def __init__(self, stream, log_path):
        self.stream = stream
        self.log_file = open(log_path, "a", encoding="utf-8", errors="replace")
        self.encoding = "utf-8"
        self.errors = "replace"
        self.closed = False
    def isatty(self):
        try: return self.stream.isatty()
        except Exception: return True
    def fileno(self):
        try: return self.stream.fileno()
        except Exception: return 1
    def writable(self): return True
    def readable(self): return False
    def seekable(self): return False
    def write(self, s):
        if not isinstance(s, str):
            s = str(s)
        self.stream.write(s); self.stream.flush()
        self.log_file.write(s); self.log_file.flush()
        return len(s)
    def flush(self):
        try: self.stream.flush()
        except Exception: pass
        try: self.log_file.flush()
        except Exception: pass
    def close(self):
        if self.closed: return
        try: self.log_file.close()
        except Exception: pass
        self.closed = True

try:
    sys.stdout = ConsoleTee(sys.__stdout__, TRANSCRIPT_PATH)
    sys.stderr = ConsoleTee(sys.__stderr__, TRANSCRIPT_PATH)
except Exception:
    pass

# ================= Third-party deps (after tee) =================
try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.progress import (
        Progress, BarColumn, TextColumn, TimeElapsedColumn, SpinnerColumn
    )
    from rich.text import Text
    from rich.rule import Rule
    from pystyle import Colors, Colorate, Center
except ImportError as e:
    print("Missing dependency:", e)
    print("\nInstall with:\n  pip install rich pystyle\n")
    sys.exit(1)

console = Console(force_terminal=True)

# ================= Logging =================
logger = logging.getLogger("scan")
logger.setLevel(logging.DEBUG)
fh_full = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
fh_full.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(fh_full)

def stamp(msg: str):
    logger.info(f"=== {msg} ===")

# ================= Subprocess helpers =================
DEFAULT_TIMEOUT = 15  # short default; heavy checks override

def run_cmd(cmd, timeout=DEFAULT_TIMEOUT):
    logger.debug(f"--- Running: {cmd}")
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        out = (p.stdout or b"").decode("utf-8", errors="replace")
        err = (p.stderr or b"").decode("utf-8", errors="replace")
        txt = out + (("\n"+err) if err else "")
        logger.debug(txt.rstrip("\n"))
        return p.returncode, txt
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {cmd}")
        return 124, ""

def ps(ps_code, timeout=DEFAULT_TIMEOUT):
    return run_cmd(f'powershell -NoProfile -ExecutionPolicy Bypass -Command {ps_code}', timeout=timeout)

def warmup_ps():
    ps("$PSVersionTable.PSVersion | Out-String", timeout=5)
    ps("(Get-Process -Id $PID).Name | Out-String", timeout=5)

# ================= Issue API (severity + hint) =================
class Issue:
    __slots__ = ("code", "detail", "severity", "hint")
    def __init__(self, code, detail="", severity="warn", hint=""):
        self.code, self.detail, self.severity, self.hint = code, detail, severity, hint
    def line(self):
        sev = {"crit":"[CRIT]", "warn":"[WARN]", "info":"[INFO]"}.get(self.severity, "[WARN]")
        txt = f"{sev} {self.code}"
        if self.detail: txt += f" — {self.detail}"
        if self.hint:   txt += f"\n    > {self.hint}"
        return txt

def add_issue(issues, code, detail="", severity="warn", hint=""):
    i = Issue(code, detail, severity, hint)
    issues.append(i)
    with open(SUMMARY_PATH, "a", encoding="utf-8") as f:
        f.write(f"- {i.line()}\n")

# ================= Admin elevation =================
def is_admin() -> bool:
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def relaunch_as_admin():
    """
    Relaunch elevated.
    - Frozen (exe): run the exe with ORIGINAL args (NO argv[0]).
    - Script: run python.exe with script path + args.
    """
    if is_frozen():
        lpFile = sys.executable
        lpParams = " ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:])
    else:
        lpFile = sys.executable
        target = str(Path(__file__).resolve())
        lpParams = f'"{target}" ' + " ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", lpFile, lpParams, None, 1)

# ================= Banner (pystyle) =================
def banner():
    art = r"""
   ███████╗ ██████╗ █████╗ ███╗   ██╗
   ██╔════╝██╔════╝██╔══██╗████╗  ██║
   ███████╗██║     ███████║██╔██╗ ██║
   ╚════██║██║     ██╔══██║██║╚██╗██║
   ███████║╚██████╗██║  ██║██║ ╚████║
   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
              SCAN — System Checks
"""
    colored = Colorate.Horizontal(Colors.green_to_cyan, Center.XCenter(art), 1)
    print(colored)

# ================= Utility =================
def gb(nbytes: int) -> int:
    return int(nbytes / 1024 / 1024 / 1024)

def should_pause(no_pause: bool) -> bool:
    return not no_pause  # pause by default unless --no-pause passed

# ================= Activity log (stable rows) =================
ACTIVITY_CAPACITY = 12  # keep this constant to lock panel height

class Activity:
    def __init__(self, capacity=ACTIVITY_CAPACITY):
        self.capacity = capacity
        self.lines = deque(maxlen=capacity)
    def add(self, msg: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.lines.append(f"[{now}] {msg}")
    def render(self):
        # Always render exactly capacity rows to keep height fixed
        tbl = Table.grid(padding=(0,1))
        lines = list(self.lines)
        pad = self.capacity - len(lines)
        for line in lines:
            tbl.add_row(Text(line, style="white"))
        for _ in range(pad):
            tbl.add_row(Text(" ", style="dim"))
        return tbl

activity = Activity()

# ================= Fixed-position UI (fixed height panel) =================
# Header rows = 5 (title, session, paths, spacer, current)
# + 1 rule + 1 progress + 1 rule + 1 "Live activity:" + ACTIVITY_CAPACITY lines
PANEL_HEIGHT = 5 + 1 + 1 + 1 + 1 + ACTIVITY_CAPACITY  # = 9 + capacity

def make_status_panel(progress_renderable, label, issues_count):
    header = Table.grid(padding=(0,1))
    header.add_row(Text("SCAN — Python Edition", style="bold cyan"))
    header.add_row(Text(f"Session dir: {OUTDIR}", style="dim"))
    header.add_row(Text(f"Full log: {LOG_PATH.name}   Transcript: {TRANSCRIPT_PATH.name}   Summary: {SUMMARY_PATH.name}", style="dim"))
    header.add_row("")  # spacer
    issues_style = "yellow" if issues_count else "green"
    header.add_row(Text(f"Current: {label}    |    Issues: {issues_count}", style=f"bold {issues_style}"))

    body = Group(
        header,
        Rule(style="cyan"),
        progress_renderable,
        Rule(style="cyan"),
        Text("Live activity:", style="bold cyan"),
        activity.render()
    )
    # Fix panel height & padding so borders never flicker
    return Panel(body, border_style="cyan", title="Live Status", title_align="left",
                 padding=(0,1), height=PANEL_HEIGHT)

# ================= Enhanced Checks (30 total) =================
def check_low_disk_space(issues, cache):
    sysdrive = os.environ.get("SystemDrive", "C:") + "\\"
    total, used, free = shutil.disk_usage(sysdrive)
    free_gb = gb(free)
    logger.info(f"DiskFree({sysdrive}): {free_gb} GB free")
    if free_gb < 15:
        add_issue(issues, "LOW_DISK_SPACE", f"~{free_gb} GB free on {sysdrive}",
                  "warn", "Free ≥15 GB on C: — delete temp files, downloads, or uninstall big apps.")

def check_smart_failing(issues, cache):
    activity.add("Checking SMART via CIM/WMIC…")
    rc, text = ps("(Get-CimInstance -ClassName Win32_DiskDrive | "
                  "Select-Object Model,Status) | Format-Table -AutoSize", timeout=20)
    if rc != 0 or "Status" not in text:
        rc, text = run_cmd("wmic diskdrive get Status,Model", timeout=20)
    for line in text.splitlines():
        if re.search(r"\b(Caution|Bad)\b", line, re.I):
            m = re.split(r"\s{2,}", line.strip())
            model = m[-1] if m else line.strip()
            state = "Caution" if "Caution" in line else "Bad"
            add_issue(issues, "SMART_FAILING", f"{state} — {model}", "crit",
                      "Backup now. Replace failing drive before attempting resets.")

def check_ntfs_errors(issues, cache):
    activity.add("Running CHKDSK online scan…")
    drive = os.environ.get("SystemDrive","C:")
    rc, text = run_cmd(f"chkdsk {drive} /scan", timeout=180)
    if re.search(r"errors found|bad sectors", text, re.I):
        add_issue(issues, "NTFS_ERRORS", "CHKDSK reports problems", "crit",
                  "Run: chkdsk /f and schedule repair on reboot; then re-run SCAN.")

def check_sfc_violations(issues, cache):
    activity.add("SFC verify only…")
    rc, text = run_cmd("sfc /verifyonly", timeout=900)
    if re.search(r"found integrity violations|repair pending|could not", text, re.I):
        add_issue(issues, "SFC_VIOLATIONS", "System file integrity problems", "warn",
                  "Run: SFC /SCANNOW, then DISM /Online /Cleanup-Image /RestoreHealth.")

def check_dism_repairable(issues, cache):
    activity.add("DISM /checkhealth…")
    rc, text = run_cmd("dism /online /cleanup-image /checkhealth", timeout=240)
    if re.search(r"repairable|component store is repairable", text, re.I):
        add_issue(issues, "DISM_REPAIRABLE", "Component store repairable", "warn",
                  "Run: DISM /Online /Cleanup-Image /RestoreHealth then SFC /SCANNOW.")

def check_winre_disabled(issues, cache):
    activity.add("Querying WinRE status…")
    rc, text = run_cmd("reagentc /info", timeout=15)
    cache["reagentc_info"] = text
    if re.search(r"Windows RE status:\s*Disabled", text, re.I):
        add_issue(issues, "WINRE_DISABLED", "", "warn",
                  "Enable with: reagentc /enable")

def check_winre_missing_image(issues, cache):
    info = cache.get("reagentc_info","")
    m = re.search(r"WinRE location:\s*(.+)", info, re.I)
    if m:
        path = m.group(1).strip()
        exists = True
        try:
            if not path.startswith("\\\\?\\"):
                exists = Path(path).exists()
        except:
            exists = False
        if not exists:
            add_issue(issues, "WINRE_MISSING_IMAGE", f"at {path}", "warn",
                      "Recreate WinRE or re-point location (reagentc /setreimage).")

def check_reset_policies(issues, cache):
    activity.add("Checking OS reset policies…")
    rc, text = run_cmd(r'reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v DisableOSReset')
    if "DisableOSReset" in text and re.search(r"\b0x1\b", text, re.I):
        add_issue(issues, "RESET_POLICY_BLOCK", "DisableOSReset=1", "warn",
                  "Set value to 0 or delete the policy to allow Reset This PC.")

def check_pending_reboots(issues, cache):
    activity.add("Looking for pending reboot flags…")
    rc1, _ = run_cmd(r'reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"')
    rc2, _ = run_cmd(r'reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"')
    if rc1 == 0:
        add_issue(issues, "REBOOT_PENDING_CBS", "", "info", "Reboot to complete servicing operations.")
    if rc2 == 0:
        add_issue(issues, "REBOOT_PENDING_WU", "", "info", "Reboot to finish Windows Update.")

def check_trustedinstaller(issues, cache):
    activity.add("Checking TrustedInstaller service…")
    rc, text = run_cmd("sc query trustedinstaller")
    if rc != 0:
        add_issue(issues, "TRUSTEDINSTALLER_DOWN", "service missing?", "warn",
                  "Run: sc config trustedinstaller start= demand & start trustedinstaller")
    elif not re.search(r"STATE\s*:\s*\d+\s+RUNNING", text, re.I):
        add_issue(issues, "TRUSTEDINSTALLER_DOWN", "not running", "info",
                  "Start: net start trustedinstaller")

def check_bcd(issues, cache):
    activity.add("Reading BCD store…")
    rc, text = run_cmd("bcdedit /enum")
    if rc != 0 or re.search(r"could not be opened|The boot configuration data store could not be opened", text, re.I):
        add_issue(issues, "BCD_ERROR", "bcdedit failed/inaccessible", "crit",
                  "Repair BCD: bootrec /RebuildBcd from WinRE or use bcdboot.")

def check_bitlocker(issues, cache):
    activity.add("Checking BitLocker on system drive…")
    sysdrive = os.environ.get("SystemDrive","C:")
    rc, text = run_cmd(f"manage-bde -status {sysdrive}")
    if re.search(r"Lock Status:\s*Locked", text, re.I):
        add_issue(issues, "BITLOCKER_BLOCK", "drive locked", "crit",
                  "Unlock with recovery key before attempting resets.")
    if re.search(r"Conversion Status:\s*Encryption in Progress", text, re.I):
        add_issue(issues, "BITLOCKER_BLOCK", "encryption in progress", "info",
                  "Wait for BitLocker to complete or pause protection.")

def check_restore_disabled(issues, cache):
    activity.add("Checking System Restore policy…")
    rc, text = run_cmd(r'reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore" /v DisableSR')
    if "DisableSR" in text and re.search(r"\b0x1\b", text, re.I):
        add_issue(issues, "RESTORE_DISABLED", "", "info",
                  "Enable System Restore if you want restore points as fallback.")

def check_suspicious_autoruns(issues, cache):
    activity.add("Scanning autoruns (Run/Policies)…")
    bad = r"wscript\.exe|cscript\.exe|powershell\.exe|mshta\.exe|\.vbs|\.js|\.hta|\.ps1"
    keys = [
        r'HKLM\Software\Microsoft\Windows\CurrentVersion\Run',
        r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run',
        r'HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run',
        r'HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run',
        r'HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce',
        r'HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce',
    ]
    agg = []
    for key in keys:
        rc, text = run_cmd(f'reg query "{key}"')
        if rc == 0 and text: agg.append(text)
    combo = "\n".join(agg)
    if re.search(bad, combo, re.I):
        add_issue(issues, "SUSPICIOUS_AUTORUN", "script host detected in autoruns", "warn",
                  "Inspect the Run*/Policies keys and remove malicious entries.")

def check_suspicious_services(issues, cache):
    activity.add("Enumerating services for script hosts…")
    rc, text = run_cmd("sc query state= all")
    bad = r"wscript\.exe|cscript\.exe|powershell\.exe|mshta\.exe|\.vbs|\.js|\.hta|\.ps1"
    if re.search(bad, text, re.I):
        add_issue(issues, "SUSPICIOUS_SERVICE", "service invoking script host", "warn",
                  "Open services.msc and inspect ImagePath for suspicious hosts.")

def check_dism_log(issues, cache):
    activity.add("Tailing DISM log for errors…")
    dism = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Logs" / "DISM" / "dism.log"
    if dism.exists():
        try:
            text = dism.read_text(encoding="utf-8", errors="replace")[-200_000:]
            if re.search(r"\berror\b|\bfailed\b", text, re.I):
                add_issue(issues, "SSU_ISSUE", "DISM log shows recent errors", "warn",
                          "Review C:\\Windows\\Logs\\DISM\\dism.log for specifics.")
        except Exception as e:
            logger.warning(f"Read DISM log failed: {e}")

def check_windows_update_client(issues, cache):
    activity.add("Poking Windows Update client…")
    rc, text = run_cmd("usoclient StartScan")
    if re.search(r"0x80|0x8024|0x80240fff|0x8024a", text, re.I):
        add_issue(issues, "WU_BROKEN", "USOClient error encountered", "warn",
                  "Reset WU components: stop wuauserv/bits; clear SoftwareDistribution; re-register DLLs.")

def check_recovery_partition(issues, cache):
    activity.add("Checking for Recovery partition…")
    script = TMPDIR / "dp.txt"
    script.write_text("list disk\nlist volume\n", encoding="ascii")
    rc, text = run_cmd(f'diskpart /s "{script}"')
    if not re.search(r"\bRecovery\b", text, re.I):
        add_issue(issues, "RECOVERY_PARTITION_MISSING", "", "info",
                  "OEM/WinRE partition not detected; WinRE may be disabled.")

def check_secureboot_tpm(issues, cache):
    activity.add("Checking Secure Boot / TPM…")
    rc, text = ps("try{[bool](Confirm-SecureBootUEFI)}catch{'Unknown'}")
    if "False" in text:
        add_issue(issues, "SECUREBOOT_TPM_POLICY", "Secure Boot disabled", "info",
                  "Enable Secure Boot in firmware for best protection & reset reliability.")
    rc, tpm = ps("(Get-CimInstance -ClassName Win32_Tpm | Select-Object -First 1 SpecVersion,IsActivated_Initialzed) | Out-String")
    if rc == 0 and tpm.strip():
        cache["tpm_info"] = tpm.strip()

def check_elevation(issues, cache):
    if not is_admin():
        add_issue(issues, "NOT_ELEVATED", "script not elevated", "crit",
                  "Right-click → Run as administrator (this tool auto-prompts).")

def check_profile_corruption(issues, cache):
    activity.add("Verifying user profile mapping…")
    userprofile = os.environ.get("USERPROFILE", "")
    if not userprofile or not Path(userprofile).exists():
        add_issue(issues, "PROFILE_CORRUPTION", "USERPROFILE path missing", "warn",
                  "Create a new profile and migrate data if corruption persists.")
    username = os.environ.get("USERNAME","")
    rc, text = run_cmd(r'reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList" /s')
    if username and username.lower() not in text.lower():
        logger.info("ProfileList did not clearly map current user; note only.")

def check_thirdparty_av(issues, cache):
    activity.add("Detecting 3rd-party AV/EDR…")
    rc, text = run_cmd("sc query state= all")
    vendors = r"Avast|Kaspersky|Bitdefender|CrowdStrike|CarbonBlack|Sophos|Sentinel|Cylance|ESET|Malwarebytes"
    if re.search(vendors, text, re.I):
        add_issue(issues, "THIRDPARTY_AV_BLOCK", "non-Defender AV/EDR active", "info",
                  "Temporarily disable or add exclusions if resets are blocked.")

def check_network_readiness(issues, cache):
    activity.add("Pinging Microsoft hosts…")
    hosts = ["download.microsoft.com", "aka.ms", "windowsupdate.microsoft.com"]
    reachable = 0
    for h in hosts:
        rc, text = run_cmd(f"ping -n 1 {h}")
        if re.search(r"TTL=", text, re.I):
            reachable += 1
    if reachable == 0:
        add_issue(issues, "NO_NETWORK_FOR_CLOUD_RECOVERY", "key hosts unreachable", "warn",
                  "Check DNS and connectivity; required for cloud reinstall/reset.")

def check_shadow_copies(issues, cache):
    activity.add("Listing VSS snapshots…")
    rc, text = run_cmd("vssadmin list shadows")
    if re.search(r"No items found", text, re.I):
        add_issue(issues, "NO_SHADOW_COPIES", "", "info",
                  "Consider enabling System Restore to create restore points.")

def check_winsxs_pending(issues, cache):
    activity.add("Looking for winsxs\\pending.xml…")
    pending = Path(os.environ.get("WINDIR", r"C:\Windows")) / "winsxs" / "pending.xml"
    if pending.exists():
        add_issue(issues, "WINSXS_PENDING", "pending.xml present", "info",
                  "Complete pending operations (reboot) before proceeding.")

def check_winre_policy(issues, cache):
    activity.add("Checking WinRE policy keys…")
    rc, text = run_cmd(r'reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows\WinRE" /s')
    if text.strip():
        add_issue(issues, "WINRE_POLICY_BLOCK", "WinRE policy present", "warn",
                  "Remove or relax policy to allow Windows Recovery usage.")

def check_tasks(issues, cache):
    activity.add("Scanning Scheduled Tasks…")
    rc, text = run_cmd("schtasks /query /fo LIST /v")
    bad = r"wscript\.exe|cscript\.exe|powershell\.exe|mshta\.exe|\.vbs|\.js|\.hta|\.ps1|\\AppData\\Local\\Temp|%APPDATA%"
    if re.search(bad, text, re.I):
        add_issue(issues, "SUSPICIOUS_TASK", "script host/temp path in task", "warn",
                  "Open Task Scheduler and disable/delete suspicious tasks.")

def check_startup_folders(issues, cache):
    activity.add("Checking Startup folders…")
    paths = [
        Path(os.environ.get("ProgramData", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs\StartUp",
        Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup",
    ]
    found = []
    for p in paths:
        try:
            if p.exists():
                for name in os.listdir(p):
                    if name.lower().endswith((".vbs",".js",".ps1",".hta",".cmd",".bat",".lnk")):
                        found.append(str(p / name))
        except Exception as e:
            logger.debug(f"Startup scan error: {e}")
    if found:
        add_issue(issues, "SUSPICIOUS_STARTUP", f"{len(found)} script-like startup items", "warn",
                  "Inspect Startup folders and remove unknown scripts/shortcuts.")

def check_reset_files(issues, cache):
    activity.add("Verifying Reset/WinRE files…")
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    missing = []
    for rel in (r"System32\Recovery\ReAgent.dll", r"System32\Recovery\ReAgent.xml"):
        if not (windir / rel).exists():
            missing.append(rel)
    if missing:
        add_issue(issues, "RESET_FILES_MISSING", ", ".join(missing), "warn",
                  "Repair WinRE (reagentc /enable or re-add recovery image).")

def check_disk_event_errors(issues, cache):
    activity.add("Reading recent critical disk errors…")
    rc, text = ps(
        "Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; ProviderName='disk'} "
        "-MaxEvents 20 | Select-Object TimeCreated,Id,Message | Out-String", timeout=12)
    if rc == 0 and re.search(r"Id\s*:\s*\d+", text):
        add_issue(issues, "DISK_ERROR_EVENTS", "Recent critical disk errors found", "warn",
                  "Open Event Viewer → System → source 'disk' and resolve hardware/cable issues.")

# ================= Main =================
def main():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--fast", action="store_true",
                        help="Skip heavy checks (SFC/DISM/CHKDSK) for a quick first pass.")
    parser.add_argument("--no-pause", action="store_true",
                        help="Do not wait for Enter at the end.")
    args, _ = parser.parse_known_args()

    if not is_admin():
        banner()
        print(Colorate.Horizontal(Colors.yellow, "Administrator privileges required — prompting..."))
        time.sleep(0.2)
        relaunch_as_admin()
        sys.exit(0)

    banner()
    warmup_ps()
    start = datetime.now()
    stamp(f"Start {start} (Python build{' [frozen]' if is_frozen() else ''})")

    # FAST first, HEAVY later — total = 30 checks
    fast_checks = [
        ("LOW_DISK_SPACE",                check_low_disk_space),
        ("NOT_ELEVATED",                  check_elevation),
        ("NO_NETWORK_FOR_CLOUD_RECOVERY", check_network_readiness),
        ("THIRDPARTY_AV_BLOCK",           check_thirdparty_av),
        ("SUSPICIOUS_AUTORUN",            check_suspicious_autoruns),
        ("SUSPICIOUS_SERVICE",            check_suspicious_services),
        ("SUSPICIOUS_TASK",               check_tasks),
        ("SUSPICIOUS_STARTUP",            check_startup_folders),
        ("RESET_POLICY_BLOCK",            check_reset_policies),
        ("REBOOT_PENDINGS",               check_pending_reboots),
        ("WINRE_DISABLED",                check_winre_disabled),
        ("WINRE_MISSING_IMAGE",           check_winre_missing_image),
        ("WINRE_POLICY_BLOCK",            check_winre_policy),
        ("RECOVERY_PARTITION_MISSING",    check_recovery_partition),
        ("RESET_FILES_MISSING",           check_reset_files),
        ("TRUSTEDINSTALLER_DOWN",         check_trustedinstaller),
        ("BCD_ERROR",                     check_bcd),
        ("SECUREBOOT_TPM_POLICY",         check_secureboot_tpm),
        ("PROFILE_CORRUPTION",            check_profile_corruption),
        ("DISK_ERROR_EVENTS",             check_disk_event_errors),
        ("WU_BROKEN",                     check_windows_update_client),
    ]  # 21

    heavy_checks = [
        ("NTFS_ERRORS",                   check_ntfs_errors),
        ("DISM_REPAIRABLE",               check_dism_repairable),
        ("SFC_VIOLATIONS",                check_sfc_violations),
        ("SSU_ISSUE",                     check_dism_log),
        ("SMART_FAILING",                 check_smart_failing),
        ("BITLOCKER_BLOCK",               check_bitlocker),
        ("NO_SHADOW_COPIES",              check_shadow_copies),
        ("WINSXS_PENDING",                check_winsxs_pending),
        ("RESTORE_DISABLED",              check_restore_disabled),
    ]  # 9

    checks = fast_checks if args.fast else (fast_checks + heavy_checks)
    issues, cache = [], {}

    # Progress used as a renderable inside Live.
    # Keep bar narrow and remove ETA to avoid width jitter (which caused border flicker).
    progress = Progress(
        SpinnerColumn(style="bold magenta"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=40, complete_style="bold green", finished_style="bold green",
                  pulse_style="bold yellow", style="grey19"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        expand=False,    # don't stretch; keeps height to 1 line
        transient=False,
    )
    task = progress.add_task("", total=len(checks), start=False)
    progress.start()

    first_label = f"Running {checks[0][0]}"

    try:
        with Live(console=console, refresh_per_second=12, transient=False, auto_refresh=True) as live:
            progress.start_task(task)
            progress.update(task, description=first_label)
            live.update(make_status_panel(progress, first_label, 0))

            for i, (name, fn) in enumerate(checks, 1):
                progress.update(task, description=f"Running {name}")
                activity.add(f"{name}…")
                live.update(make_status_panel(progress, name, len(issues)))

                try:
                    fn(issues, cache)
                except Exception as e:
                    logger.exception(f"{name} failed: {e}")
                    add_issue(issues, f"{name}_EXCEPTION", str(e), "warn", "See full_log.txt for traceback.")
                finally:
                    progress.advance(task)
                    live.update(make_status_panel(progress, name, len(issues)))

            # Summary card (after box)
            finish = datetime.now()
            stamp(f"Finished {finish}")
            elapsed = int((finish - start).total_seconds())

            result = Table.grid()
            result.add_row(Text("SCAN — RESULT CARD", style="bold cyan"))
            if SUMMARY_PATH.stat().st_size > 0:
                result.add_row(Text("Findings:", style="bold yellow"))
                result.add_row("")
                result.add_row(Text(Path(SUMMARY_PATH).read_text(encoding="utf-8"), style="white"))
            else:
                result.add_row(Text("No reset blockers detected in this pass.", style="bold green"))
            result.add_row("")
            result.add_row(Text(f"Full log:       {LOG_PATH}", style="dim"))
            result.add_row(Text(f"Transcript:     {TRANSCRIPT_PATH}", style="dim"))
            result.add_row(Text(f"Issue summary:  {SUMMARY_PATH}", style="dim"))
            result.add_row(Text(f"Elapsed:        {elapsed}s", style="dim"))
            result.add_row("")
            result.add_row(Text("Suggested remediation (safe order):", style="italic"))
            result.add_row(Text(
                textwrap.dedent("""\
                    • DISM /Online /Cleanup-Image /RestoreHealth
                    • SFC /SCANNOW
                    • reagentc /enable (if WINRE_DISABLED / WINRE_POLICY_BLOCK)
                    • Free ≥ 15 GB on C: (if LOW_DISK_SPACE)
                    • Complete pending reboots (REBOOT_PENDING_*) then re-run
                """).rstrip(),
                style="white"
            ))
            live.console.print(Panel(result, border_style="green", title="Summary"))
    finally:
        try: progress.stop()
        except Exception: pass

    # Exit code: non-zero if issues found
    exit_code = 1 if issues else 0

    if should_pause(args.no_pause):
        try: input("\nPress Enter to close… ")
        except Exception:
            try: os.system("pause")
            except Exception: pass

    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        # Late import so functions exist in __main__
        from datetime import datetime  # noqa: F401 (used earlier)
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        try: input("\nPress Enter to close… ")
        except Exception: pass
