"""Small, read-only hardware inventory for model fit guidance."""

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SystemResources:
    architecture: str
    cpu_threads: int | None
    total_ram_bytes: int | None
    available_ram_bytes: int | None


def detect_resources() -> SystemResources:
    memory: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                memory[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return SystemResources(
        platform.machine(), os.cpu_count(), memory.get("MemTotal"), memory.get("MemAvailable")
    )


def model_memory_warning(size_bytes: int, available_bytes: int | None) -> str:
    if available_bytes is not None and size_bytes > 0 and size_bytes >= available_bytes:
        return "Selected model is larger than available RAM; responses may be very slow."
    return ""
