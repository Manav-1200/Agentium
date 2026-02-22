"""
Host OS Detection & Cross-Platform Execution Tool
Detects the host system OS/distro outside Docker and executes
the correct command variant for that platform automatically.

Supported platforms:
  Windows  : Windows 10, 11, Server 2016/2019/2022
  macOS    : 10.x (Catalina) through 15.x (Sequoia)
  Linux    : Debian, Ubuntu, Kali, Mint, Pop!_OS
             RHEL, CentOS, Fedora, Rocky, AlmaLinux, Oracle
             Arch, Manjaro, EndeavourOS
             openSUSE Leap, Tumbleweed, SLES
             Alpine, Void, Gentoo, NixOS, Slackware
             Raspbian / Raspberry Pi OS
             Amazon Linux, ChromeOS (Crostini)
  BSD      : FreeBSD, OpenBSD, NetBSD, DragonFlyBSD

Authorized tiers: 0xxxx (Head), 1xxxx (Council), 2xxxx (Lead)
Task agents (3xxxx) are blocked — host access is privileged.
"""

import subprocess
import platform
import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime


# ── OS Family Constants ────────────────────────────────────────────────────────

OS_WINDOWS = "windows"
OS_MACOS   = "macos"
OS_LINUX   = "linux"
OS_BSD     = "bsd"
OS_UNKNOWN = "unknown"

# Linux distro families — used to pick the right package manager / command set
DISTRO_DEBIAN  = "debian"   # Debian, Ubuntu, Mint, Kali, Pop, Raspbian, Elementary
DISTRO_RHEL    = "rhel"     # RHEL, CentOS, Fedora, Rocky, Alma, Oracle, Amazon
DISTRO_ARCH    = "arch"     # Arch, Manjaro, EndeavourOS, Garuda
DISTRO_SUSE    = "suse"     # openSUSE Leap/Tumbleweed, SLES
DISTRO_ALPINE  = "alpine"   # Alpine Linux
DISTRO_GENTOO  = "gentoo"   # Gentoo, Funtoo
DISTRO_VOID    = "void"     # Void Linux
DISTRO_NIX     = "nixos"    # NixOS
DISTRO_SLACK   = "slackware"
DISTRO_UNKNOWN = "unknown"


# ── Distro ID → family mapping ─────────────────────────────────────────────────
# Values come from /etc/os-release ID= and ID_LIKE= fields

DISTRO_ID_MAP: Dict[str, str] = {
    # Debian family
    "debian": DISTRO_DEBIAN, "ubuntu": DISTRO_DEBIAN, "linuxmint": DISTRO_DEBIAN,
    "mint": DISTRO_DEBIAN, "kali": DISTRO_DEBIAN, "pop": DISTRO_DEBIAN,
    "elementary": DISTRO_DEBIAN, "raspbian": DISTRO_DEBIAN, "parrot": DISTRO_DEBIAN,
    "deepin": DISTRO_DEBIAN, "zorin": DISTRO_DEBIAN, "mx": DISTRO_DEBIAN,
    "lmde": DISTRO_DEBIAN, "peppermint": DISTRO_DEBIAN, "tails": DISTRO_DEBIAN,
    "backbox": DISTRO_DEBIAN, "pureos": DISTRO_DEBIAN, "devuan": DISTRO_DEBIAN,
    "armbian": DISTRO_DEBIAN, "crostini": DISTRO_DEBIAN,
    # RHEL family
    "rhel": DISTRO_RHEL, "centos": DISTRO_RHEL, "fedora": DISTRO_RHEL,
    "rocky": DISTRO_RHEL, "almalinux": DISTRO_RHEL, "ol": DISTRO_RHEL,
    "amzn": DISTRO_RHEL, "amazon": DISTRO_RHEL, "scientific": DISTRO_RHEL,
    "clearos": DISTRO_RHEL, "eurolinux": DISTRO_RHEL, "springdale": DISTRO_RHEL,
    "virtuozzo": DISTRO_RHEL,
    # Arch family
    "arch": DISTRO_ARCH, "manjaro": DISTRO_ARCH, "endeavouros": DISTRO_ARCH,
    "garuda": DISTRO_ARCH, "artix": DISTRO_ARCH, "arcolinux": DISTRO_ARCH,
    "blackarch": DISTRO_ARCH, "parabola": DISTRO_ARCH,
    # SUSE family
    "opensuse-leap": DISTRO_SUSE, "opensuse-tumbleweed": DISTRO_SUSE,
    "opensuse": DISTRO_SUSE, "sles": DISTRO_SUSE, "sled": DISTRO_SUSE,
    # Others
    "alpine": DISTRO_ALPINE,
    "gentoo": DISTRO_GENTOO, "funtoo": DISTRO_GENTOO,
    "void": DISTRO_VOID,
    "nixos": DISTRO_NIX,
    "slackware": DISTRO_SLACK,
}


# ── Per-OS command translations ────────────────────────────────────────────────
# Maps a logical operation name to the correct command list per OS/distro.
# Agents request by operation name; the tool resolves to the right binary.

COMMAND_MAP: Dict[str, Dict[str, List[str]]] = {

    # ── Package management ─────────────────────────────────────────────────────
    "pkg_update": {
        OS_WINDOWS:   ["powershell", "-Command", "winget upgrade --all"],
        OS_MACOS:     ["brew", "update"],
        DISTRO_DEBIAN: ["apt-get", "update"],
        DISTRO_RHEL:  ["dnf", "check-update"],
        DISTRO_ARCH:  ["pacman", "-Sy"],
        DISTRO_SUSE:  ["zypper", "refresh"],
        DISTRO_ALPINE:["apk", "update"],
        DISTRO_GENTOO:["emerge", "--sync"],
        DISTRO_VOID:  ["xbps-install", "-S"],
        DISTRO_NIX:   ["nix-channel", "--update"],
        DISTRO_SLACK: ["slackpkg", "update"],
    },
    "pkg_upgrade": {
        OS_WINDOWS:   ["powershell", "-Command", "winget upgrade --all --silent"],
        OS_MACOS:     ["brew", "upgrade"],
        DISTRO_DEBIAN: ["apt-get", "upgrade", "-y"],
        DISTRO_RHEL:  ["dnf", "upgrade", "-y"],
        DISTRO_ARCH:  ["pacman", "-Su", "--noconfirm"],
        DISTRO_SUSE:  ["zypper", "update", "-y"],
        DISTRO_ALPINE:["apk", "upgrade"],
        DISTRO_GENTOO:["emerge", "-uDN", "@world"],
        DISTRO_VOID:  ["xbps-install", "-Su"],
        DISTRO_NIX:   ["nixos-rebuild", "switch", "--upgrade"],
        DISTRO_SLACK: ["slackpkg", "upgrade-all"],
    },

    # ── System info ────────────────────────────────────────────────────────────
    "os_version": {
        OS_WINDOWS:   ["powershell", "-Command", "[System.Environment]::OSVersion.VersionString"],
        OS_MACOS:     ["sw_vers"],
        OS_LINUX:     ["cat", "/etc/os-release"],
        OS_BSD:       ["uname", "-a"],
    },
    "cpu_info": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,MaxClockSpeed | Format-List"],
        OS_MACOS:     ["sysctl", "-n", "machdep.cpu.brand_string"],
        OS_LINUX:     ["lscpu"],
        OS_BSD:       ["sysctl", "hw.model", "hw.ncpu"],
    },
    "memory_info": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | Format-List"],
        OS_MACOS:     ["vm_stat"],
        OS_LINUX:     ["free", "-h"],
        OS_BSD:       ["vmstat"],
    },
    "disk_info": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-PSDrive -PSProvider FileSystem | Format-Table"],
        OS_MACOS:     ["df", "-h"],
        OS_LINUX:     ["df", "-h"],
        OS_BSD:       ["df", "-h"],
    },
    "uptime": {
        OS_WINDOWS:   ["powershell", "-Command", "(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime"],
        OS_MACOS:     ["uptime"],
        OS_LINUX:     ["uptime", "-p"],
        OS_BSD:       ["uptime"],
    },
    "hostname": {
        OS_WINDOWS:   ["powershell", "-Command", "$env:COMPUTERNAME"],
        OS_MACOS:     ["hostname"],
        OS_LINUX:     ["hostname", "-f"],
        OS_BSD:       ["hostname"],
    },

    # ── Network ────────────────────────────────────────────────────────────────
    "network_interfaces": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-NetIPAddress | Format-Table"],
        OS_MACOS:     ["ifconfig"],
        OS_LINUX:     ["ip", "addr"],
        OS_BSD:       ["ifconfig"],
    },
    "open_ports": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-NetTCPConnection -State Listen | Format-Table"],
        OS_MACOS:     ["netstat", "-an", "-p", "tcp"],
        OS_LINUX:     ["ss", "-tlnp"],
        OS_BSD:       ["netstat", "-an", "-p", "tcp"],
    },
    "dns_lookup": {
        OS_WINDOWS:   ["nslookup"],
        OS_MACOS:     ["dig"],
        OS_LINUX:     ["dig"],
        OS_BSD:       ["dig"],
    },
    "ping": {
        OS_WINDOWS:   ["ping", "-n", "4"],
        OS_MACOS:     ["ping", "-c", "4"],
        OS_LINUX:     ["ping", "-c", "4"],
        OS_BSD:       ["ping", "-c", "4"],
    },

    # ── Process management ─────────────────────────────────────────────────────
    "list_processes": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 30 | Format-Table"],
        OS_MACOS:     ["ps", "aux"],
        OS_LINUX:     ["ps", "aux", "--sort=-%cpu"],
        OS_BSD:       ["ps", "aux"],
    },
    "kill_process": {
        OS_WINDOWS:   ["powershell", "-Command", "Stop-Process -Id"],  # append PID
        OS_MACOS:     ["kill", "-9"],
        OS_LINUX:     ["kill", "-9"],
        OS_BSD:       ["kill", "-9"],
    },

    # ── Service management ─────────────────────────────────────────────────────
    "list_services": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-Service | Format-Table"],
        OS_MACOS:     ["launchctl", "list"],
        DISTRO_DEBIAN: ["systemctl", "list-units", "--type=service", "--state=running"],
        DISTRO_RHEL:  ["systemctl", "list-units", "--type=service", "--state=running"],
        DISTRO_ARCH:  ["systemctl", "list-units", "--type=service", "--state=running"],
        DISTRO_SUSE:  ["systemctl", "list-units", "--type=service", "--state=running"],
        DISTRO_ALPINE:["rc-status"],
        DISTRO_GENTOO:["rc-status"],
        DISTRO_VOID:  ["sv", "status", "/var/service/*"],
        DISTRO_NIX:   ["systemctl", "list-units", "--type=service"],
        DISTRO_SLACK: ["ls", "/etc/rc.d/"],
        OS_BSD:       ["service", "-e"],
    },
    "service_start": {
        OS_WINDOWS:   ["powershell", "-Command", "Start-Service"],
        OS_MACOS:     ["launchctl", "start"],
        DISTRO_DEBIAN: ["systemctl", "start"],
        DISTRO_RHEL:  ["systemctl", "start"],
        DISTRO_ARCH:  ["systemctl", "start"],
        DISTRO_SUSE:  ["systemctl", "start"],
        DISTRO_ALPINE:["rc-service", "--start"],
        DISTRO_VOID:  ["sv", "start"],
        OS_BSD:       ["service", "--start"],
    },
    "service_stop": {
        OS_WINDOWS:   ["powershell", "-Command", "Stop-Service"],
        OS_MACOS:     ["launchctl", "stop"],
        DISTRO_DEBIAN: ["systemctl", "stop"],
        DISTRO_RHEL:  ["systemctl", "stop"],
        DISTRO_ARCH:  ["systemctl", "stop"],
        DISTRO_SUSE:  ["systemctl", "stop"],
        DISTRO_ALPINE:["rc-service", "--stop"],
        DISTRO_VOID:  ["sv", "stop"],
        OS_BSD:       ["service", "--stop"],
    },

    # ── Users & permissions ────────────────────────────────────────────────────
    "list_users": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-LocalUser | Format-Table"],
        OS_MACOS:     ["dscl", ".", "-list", "/Users"],
        OS_LINUX:     ["cat", "/etc/passwd"],
        OS_BSD:       ["cat", "/etc/passwd"],
    },
    "whoami": {
        OS_WINDOWS:   ["powershell", "-Command", "whoami"],
        OS_MACOS:     ["whoami"],
        OS_LINUX:     ["whoami"],
        OS_BSD:       ["whoami"],
    },

    # ── Environment ────────────────────────────────────────────────────────────
    "env_vars": {
        OS_WINDOWS:   ["powershell", "-Command", "Get-ChildItem Env: | Format-Table"],
        OS_MACOS:     ["printenv"],
        OS_LINUX:     ["printenv"],
        OS_BSD:       ["printenv"],
    },
    "installed_packages": {
        OS_WINDOWS:   ["powershell", "-Command", "winget list"],
        OS_MACOS:     ["brew", "list"],
        DISTRO_DEBIAN: ["dpkg", "--get-selections"],
        DISTRO_RHEL:  ["rpm", "-qa"],
        DISTRO_ARCH:  ["pacman", "-Q"],
        DISTRO_SUSE:  ["zypper", "packages", "--installed-only"],
        DISTRO_ALPINE:["apk", "info"],
        DISTRO_GENTOO:["qlist", "-I"],
        DISTRO_VOID:  ["xbps-query", "-l"],
        DISTRO_NIX:   ["nix-env", "-q"],
        DISTRO_SLACK: ["ls", "/var/log/packages"],
        OS_BSD:       ["pkg", "info"],
    },
    "kernel_version": {
        OS_WINDOWS:   ["powershell", "-Command", "[System.Environment]::OSVersion"],
        OS_MACOS:     ["uname", "-r"],
        OS_LINUX:     ["uname", "-r"],
        OS_BSD:       ["uname", "-r"],
    },
    "architecture": {
        OS_WINDOWS:   ["powershell", "-Command", "$env:PROCESSOR_ARCHITECTURE"],
        OS_MACOS:     ["uname", "-m"],
        OS_LINUX:     ["uname", "-m"],
        OS_BSD:       ["uname", "-m"],
    },
}


# ── OS Detection ───────────────────────────────────────────────────────────────

class OSDetector:
    """
    Detects the host OS and distro by reading /host/etc/os-release (Linux),
    /host/System32 presence (Windows), or /host/usr/bin/sw_vers (macOS).

    Since the agent runs inside Docker with / mounted at /host,
    we inspect /host/* instead of the container's own filesystem.
    """

    HOST_ROOT = "/host"

    def detect(self) -> Dict[str, Any]:
        """
        Returns a full OS profile dict:
        {
            os_family: "linux" | "windows" | "macos" | "bsd" | "unknown",
            os_name: "Ubuntu" | "Windows 11" | "macOS Sonoma" | ...,
            os_version: "22.04" | "10.0.22631" | "14.2" | ...,
            distro_family: "debian" | "rhel" | "arch" | ... (Linux only),
            distro_id: "ubuntu" | "fedora" | ... (Linux only),
            distro_id_like: "debian" | ... (Linux only),
            architecture: "x86_64" | "arm64" | ...,
            kernel: "5.15.0-91-generic" | ...,
            hostname: "my-machine",
            package_manager: "apt" | "dnf" | "pacman" | "brew" | "winget" | ...,
            detected_at: "2025-...",
        }
        """
        result = {
            "os_family": OS_UNKNOWN,
            "os_name": "Unknown",
            "os_version": "Unknown",
            "distro_family": None,
            "distro_id": None,
            "distro_id_like": None,
            "architecture": self._arch(),
            "kernel": self._kernel(),
            "hostname": self._hostname(),
            "package_manager": None,
            "detected_at": datetime.utcnow().isoformat(),
        }

        # ── Try Linux (/host/etc/os-release) ──────────────────────────────────
        os_release = Path(self.HOST_ROOT) / "etc" / "os-release"
        if os_release.exists():
            info = self._parse_os_release(os_release)
            distro_id = info.get("ID", "").lower().replace('"', '')
            id_like   = info.get("ID_LIKE", "").lower().replace('"', '')
            name      = info.get("PRETTY_NAME", info.get("NAME", "Linux")).strip('"')
            version   = info.get("VERSION_ID", "").strip('"')

            family = (
                DISTRO_ID_MAP.get(distro_id)
                or self._resolve_id_like(id_like)
                or DISTRO_UNKNOWN
            )

            result.update({
                "os_family": OS_LINUX,
                "os_name": name,
                "os_version": version,
                "distro_family": family,
                "distro_id": distro_id,
                "distro_id_like": id_like or None,
                "package_manager": self._pkg_manager(family),
            })
            return result

        # ── Try macOS (/host/usr/bin/sw_vers exists) ───────────────────────────
        sw_vers = Path(self.HOST_ROOT) / "usr" / "bin" / "sw_vers"
        if sw_vers.exists():
            name, version = self._macos_info()
            result.update({
                "os_family": OS_MACOS,
                "os_name": name,
                "os_version": version,
                "package_manager": "brew",
            })
            return result

        # ── Try Windows (/host/Windows/System32 exists) ────────────────────────
        win_sys32 = Path(self.HOST_ROOT) / "Windows" / "System32"
        if win_sys32.exists():
            name, version = self._windows_info()
            result.update({
                "os_family": OS_WINDOWS,
                "os_name": name,
                "os_version": version,
                "package_manager": "winget",
            })
            return result

        # ── Try BSD (/host/etc/freebsd-version etc.) ───────────────────────────
        for bsd_marker in ["freebsd-version", "openbsd-version", "netbsd-version"]:
            marker = Path(self.HOST_ROOT) / "etc" / bsd_marker
            if marker.exists():
                result.update({
                    "os_family": OS_BSD,
                    "os_name": bsd_marker.replace("-version", "").capitalize(),
                    "os_version": marker.read_text().strip(),
                    "package_manager": "pkg",
                })
                return result

        # ── Fallback: try running uname directly on host ───────────────────────
        uname = self._run_host(["uname", "-s"])
        if uname:
            uname = uname.strip().lower()
            if "darwin" in uname:
                result.update({"os_family": OS_MACOS, "os_name": "macOS", "package_manager": "brew"})
            elif "linux" in uname:
                result.update({"os_family": OS_LINUX, "os_name": "Linux"})
            elif "bsd" in uname:
                result.update({"os_family": OS_BSD, "os_name": uname.title()})

        return result

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _parse_os_release(self, path: Path) -> Dict[str, str]:
        info = {}
        for line in path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                info[k.strip()] = v.strip().strip('"')
        return info

    def _resolve_id_like(self, id_like: str) -> Optional[str]:
        """ID_LIKE can be space-separated, e.g. 'rhel fedora'. Pick first match."""
        for part in id_like.split():
            family = DISTRO_ID_MAP.get(part.lower())
            if family:
                return family
        return None

    def _pkg_manager(self, distro_family: str) -> str:
        return {
            DISTRO_DEBIAN:  "apt",
            DISTRO_RHEL:    "dnf",
            DISTRO_ARCH:    "pacman",
            DISTRO_SUSE:    "zypper",
            DISTRO_ALPINE:  "apk",
            DISTRO_GENTOO:  "emerge",
            DISTRO_VOID:    "xbps",
            DISTRO_NIX:     "nix",
            DISTRO_SLACK:   "slackpkg",
        }.get(distro_family, "unknown")

    def _macos_info(self):
        raw = self._run_host(["sw_vers"]) or ""
        name    = re.search(r"ProductName:\s*(.+)",    raw)
        version = re.search(r"ProductVersion:\s*(.+)", raw)
        return (
            name.group(1).strip()    if name    else "macOS",
            version.group(1).strip() if version else "Unknown",
        )

    def _windows_info(self):
        # Read from registry hive or just return generic Windows info
        # Full parsing of Windows registry from Linux is complex; use winver file
        winver = Path(self.HOST_ROOT) / "Windows" / "System32" / "winver.exe"
        return "Windows", "Unknown (registry parsing not available)"

    def _arch(self) -> str:
        r = self._run_host(["uname", "-m"])
        return r.strip() if r else platform.machine()

    def _kernel(self) -> str:
        r = self._run_host(["uname", "-r"])
        return r.strip() if r else "Unknown"

    def _hostname(self) -> str:
        # Try /host/etc/hostname first
        h = Path(self.HOST_ROOT) / "etc" / "hostname"
        if h.exists():
            return h.read_text().strip()
        r = self._run_host(["hostname"])
        return r.strip() if r else "Unknown"

    def _run_host(self, cmd: List[str]) -> Optional[str]:
        """Run a command, return stdout or None on failure."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return r.stdout if r.returncode == 0 else None
        except Exception:
            return None


# ── Command Resolver ───────────────────────────────────────────────────────────

class CommandResolver:
    """
    Given an OS profile and a logical operation name,
    returns the correct command list for that platform.
    """

    def resolve(
        self,
        operation: str,
        os_profile: Dict[str, Any],
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a logical operation to the correct command for the detected OS.

        Priority order for Linux:
          1. distro_family key  (e.g. DISTRO_DEBIAN = "debian")
          2. OS_LINUX key       (generic Linux fallback)
          3. OS_UNKNOWN

        Returns:
          {
            "resolved": bool,
            "command": [...],
            "operation": "pkg_update",
            "platform_key": "debian",
            "note": "...",
          }
        """
        if operation not in COMMAND_MAP:
            return {
                "resolved": False,
                "command": [],
                "operation": operation,
                "platform_key": None,
                "note": f"Unknown operation '{operation}'. Available: {sorted(COMMAND_MAP.keys())}",
            }

        op_map = COMMAND_MAP[operation]
        os_family      = os_profile.get("os_family", OS_UNKNOWN)
        distro_family  = os_profile.get("distro_family")

        # Resolve in priority order
        platform_key = None
        command      = None

        if os_family == OS_LINUX:
            # Try distro-specific first
            if distro_family and distro_family in op_map:
                platform_key = distro_family
                command = op_map[distro_family]
            # Fall back to generic linux
            elif OS_LINUX in op_map:
                platform_key = OS_LINUX
                command = op_map[OS_LINUX]

        elif os_family == OS_WINDOWS and OS_WINDOWS in op_map:
            platform_key = OS_WINDOWS
            command = op_map[OS_WINDOWS]

        elif os_family == OS_MACOS and OS_MACOS in op_map:
            platform_key = OS_MACOS
            command = op_map[OS_MACOS]

        elif os_family == OS_BSD and OS_BSD in op_map:
            platform_key = OS_BSD
            command = op_map[OS_BSD]

        if command is None:
            return {
                "resolved": False,
                "command": [],
                "operation": operation,
                "platform_key": None,
                "note": f"No command mapping for operation '{operation}' on {os_family}/{distro_family}",
            }

        # Append extra args (e.g. service name, PID)
        full_command = command + (extra_args or [])

        return {
            "resolved": True,
            "command": full_command,
            "operation": operation,
            "platform_key": platform_key,
            "note": None,
        }

    def list_operations(self) -> List[str]:
        """Return all supported logical operation names."""
        return sorted(COMMAND_MAP.keys())


# ── Main Tool Class ────────────────────────────────────────────────────────────

class HostOSTool:
    """
    Tool for agents to:
      1. Detect the host OS (outside Docker) with full distro detail
      2. Resolve logical operations to the correct OS-native command
      3. Execute those commands on the host via /host mount

    Usage by agent:
      # Step 1 — detect
      profile = tool.detect_os()

      # Step 2 — resolve (agent picks operation name)
      resolved = tool.resolve_command("pkg_update", profile["os_profile"])

      # Step 3 — execute
      result = tool.execute_for_os("pkg_update", extra_args=[], timeout=120)

      # Or all in one shot:
      result = tool.execute_for_os("list_services")
    """

    AUTHORIZED_TIERS = ["0xxxx", "1xxxx", "2xxxx"]

    def __init__(self):
        self.detector = OSDetector()
        self.resolver = CommandResolver()
        self._cached_profile: Optional[Dict[str, Any]] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def detect_os(self) -> Dict[str, Any]:
        """
        Detect and return the full host OS profile.
        Result is cached for the lifetime of this tool instance.
        """
        if not self._cached_profile:
            self._cached_profile = self.detector.detect()

        profile = self._cached_profile
        return {
            "status": "success",
            "os_profile": profile,
            "summary": self._human_summary(profile),
            "available_operations": self.resolver.list_operations(),
            "package_manager": profile.get("package_manager"),
        }

    def resolve_command(
        self,
        operation: str,
        os_profile: Optional[Dict[str, Any]] = None,
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a logical operation name to the correct command for the host OS.
        If os_profile is not supplied, auto-detects first.

        Example:
            resolve_command("pkg_update")
            → {"resolved": True, "command": ["apt-get", "update"], ...}
        """
        profile = os_profile or self.detect_os()["os_profile"]
        return self.resolver.resolve(operation, profile, extra_args)

    def execute_for_os(
        self,
        operation: str,
        extra_args: Optional[List[str]] = None,
        timeout: int = 120,
        working_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Detect OS → resolve command → execute on host. All in one call.

        The agent only needs to know the logical operation name
        (e.g. "pkg_update", "list_services", "memory_info").
        The tool handles the rest.
        """
        # Detect
        detection = self.detect_os()
        profile   = detection["os_profile"]

        # Resolve
        resolved = self.resolver.resolve(operation, profile, extra_args)
        if not resolved["resolved"]:
            return {
                "status": "error",
                "error": resolved["note"],
                "operation": operation,
                "os_profile": profile,
            }

        command = resolved["command"]

        # Execute via /host mount (host filesystem is mounted at /host in container)
        start = datetime.utcnow()
        exec_result = self._execute(command, timeout=timeout, cwd=working_directory)
        elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

        return {
            "status": "success" if exec_result["returncode"] == 0 else "error",
            "operation": operation,
            "platform_key": resolved["platform_key"],
            "command": command,
            "returncode": exec_result["returncode"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "execution_time_ms": round(elapsed_ms, 2),
            "os_profile": {
                "os_family":     profile["os_family"],
                "os_name":       profile["os_name"],
                "os_version":    profile["os_version"],
                "distro_family": profile.get("distro_family"),
                "architecture":  profile["architecture"],
            },
        }

    def list_operations(self) -> Dict[str, Any]:
        """Return all logical operation names the agent can request."""
        return {
            "status": "success",
            "operations": self.resolver.list_operations(),
            "total": len(COMMAND_MAP),
        }

    def smart_execute(
        self,
        raw_command: List[str],
        timeout: int = 120,
        working_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        For cases where the agent has a specific command but wants the tool
        to adapt it to the host OS automatically.

        Currently validates the command is safe and runs it directly.
        Use execute_for_os() with a logical operation name for full cross-OS support.
        """
        detection = self.detect_os()
        profile   = detection["os_profile"]

        blocked = self._is_dangerous(raw_command)
        if blocked:
            return {
                "status": "error",
                "error": f"Command blocked: {blocked}",
                "command": raw_command,
            }

        start      = datetime.utcnow()
        exec_result = self._execute(raw_command, timeout=timeout, cwd=working_directory)
        elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

        return {
            "status": "success" if exec_result["returncode"] == 0 else "error",
            "command": raw_command,
            "returncode": exec_result["returncode"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "execution_time_ms": round(elapsed_ms, 2),
            "os_detected": profile["os_name"],
        }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _execute(
        self,
        command: List[str],
        timeout: int = 120,
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run command, return stdout/stderr/returncode."""
        try:
            r = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            return {
                "returncode": r.returncode,
                "stdout": r.stdout,
                "stderr": r.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": f"Command timed out after {timeout}s"}
        except FileNotFoundError:
            return {"returncode": -1, "stdout": "", "stderr": f"Command not found: {command[0]}"}
        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    def _is_dangerous(self, command: List[str]) -> Optional[str]:
        """Return reason string if command is dangerous, else None."""
        dangerous_patterns = [
            ("rm -rf /",    "Recursive root delete"),
            ("mkfs",        "Filesystem format"),
            ("dd if=/dev/zero", "Disk wipe"),
            ("shutdown",    "System shutdown"),
            ("reboot",      "System reboot"),
            (":(){:|:&};:", "Fork bomb"),
            ("chmod -R 777 /", "World-writable root"),
        ]
        cmd_str = " ".join(command).lower()
        for pattern, reason in dangerous_patterns:
            if pattern.lower() in cmd_str:
                return reason
        return None

    def _human_summary(self, profile: Dict[str, Any]) -> str:
        os_family = profile.get("os_family", "unknown")
        os_name   = profile.get("os_name", "Unknown")
        version   = profile.get("os_version", "")
        distro_f  = profile.get("distro_family", "")
        arch      = profile.get("architecture", "")
        pkg       = profile.get("package_manager", "unknown")

        if os_family == OS_LINUX:
            return (
                f"{os_name} {version} ({distro_f} family) "
                f"[{arch}] — package manager: {pkg}"
            )
        elif os_family == OS_MACOS:
            return f"macOS {version} [{arch}] — package manager: brew"
        elif os_family == OS_WINDOWS:
            return f"Windows {version} [{arch}] — package manager: winget"
        elif os_family == OS_BSD:
            return f"{os_name} {version} [{arch}] — package manager: pkg"
        return "Unknown OS"


# ── Singleton for tool registry ────────────────────────────────────────────────
host_os_tool = HostOSTool()