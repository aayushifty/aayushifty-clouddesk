"""
System Monitor Module - Aayushifty CloudDesk 2.0
Lightweight, non-blocking telemetry engine for CPU, RAM, GPU, Disks, and Processes.
Optimized with 0.1ms non-blocking CPU queries and cached process inspection.
"""
from __future__ import annotations

import os
import time
import psutil
from typing import Any, Dict, List, Optional

# Attempt NVIDIA NVML initialization for GPU metrics
_nvml_initialized = False
try:
    import pynvml
    pynvml.nvmlInit()
    _nvml_initialized = True
except Exception:
    _nvml_initialized = False

# Cache for top processes to prevent high CPU overhead from repeated process iteration
_cached_processes: List[Dict[str, Any]] = []
_last_proc_scan: float = 0.0
_PROC_CACHE_TTL = 3.0  # seconds


class SystemMonitor:
    """Collects real-time hardware telemetry with sub-millisecond execution overhead."""

    @staticmethod
    def get_cpu_metrics() -> Dict[str, Any]:
        """Returns non-blocking CPU usage percentage and core counts."""
        try:
            # interval=None is non-blocking (0.0001s), comparing against last system tick
            percent = psutil.cpu_percent(interval=None)
            logical_cores = psutil.cpu_count(logical=True) or 0
            physical_cores = psutil.cpu_count(logical=False) or 0
            freq = psutil.cpu_freq()
            current_freq = round(freq.current, 1) if freq else 0.0

            return {
                "percent": percent,
                "logical_cores": logical_cores,
                "physical_cores": physical_cores,
                "frequency_mhz": current_freq,
                "status": "warning" if percent > 85 else "healthy"
            }
        except Exception as e:
            return {"percent": 0.0, "error": str(e), "status": "unknown"}

    @staticmethod
    def get_memory_metrics() -> Dict[str, Any]:
        """Returns physical RAM metrics and memory pressure level."""
        try:
            mem = psutil.virtual_memory()
            total_gb = round(mem.total / (1024 ** 3), 2)
            used_gb = round(mem.used / (1024 ** 3), 2)
            free_gb = round(mem.available / (1024 ** 3), 2)
            percent = mem.percent

            # Determine pressure
            if percent >= 90:
                pressure = "critical"
            elif percent >= 80:
                pressure = "elevated"
            else:
                pressure = "optimal"

            return {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "percent": percent,
                "pressure": pressure
            }
        except Exception as e:
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0, "pressure": "unknown", "error": str(e)}

    @staticmethod
    def get_gpu_metrics() -> Dict[str, Any]:
        """Returns NVIDIA RTX 3050 utilization, VRAM usage, and temperatures."""
        global _nvml_initialized
        if not _nvml_initialized:
            return {
                "available": False,
                "name": "N/A or Integrated Graphics",
                "vram_total_mb": 0,
                "vram_used_mb": 0,
                "vram_free_mb": 0,
                "vram_percent": 0.0,
                "gpu_util_percent": 0,
                "temperature_c": 0
            }

        try:
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count == 0:
                return {"available": False, "name": "No NVIDIA GPU detected"}

            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_mb = round(mem_info.total / (1024 ** 2), 1)
            used_mb = round(mem_info.used / (1024 ** 2), 1)
            free_mb = round(mem_info.free / (1024 ** 2), 1)
            vram_percent = round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0.0

            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = util.gpu

            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = 0

            return {
                "available": True,
                "name": name,
                "vram_total_mb": total_mb,
                "vram_used_mb": used_mb,
                "vram_free_mb": free_mb,
                "vram_percent": vram_percent,
                "gpu_util_percent": gpu_util,
                "temperature_c": temp
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    @staticmethod
    def get_disk_metrics() -> List[Dict[str, Any]]:
        """Returns drive usage for all mounted drives (C:, D:, E:, G:, etc.)."""
        drives = []
        try:
            partitions = psutil.disk_partitions(all=False)
            for p in partitions:
                if "cdrom" in p.opts or not p.mountpoint:
                    continue

                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    drive_letter = p.mountpoint.replace("\\", "")
                    total_gb = round(usage.total / (1024 ** 3), 2)
                    used_gb = round(usage.used / (1024 ** 3), 2)
                    free_gb = round(usage.free / (1024 ** 3), 2)
                    percent = usage.percent

                    is_cloud = "google" in p.device.lower() or "g:" in drive_letter.lower() or "google drive" in p.opts.lower()

                    status = "warning" if percent > 90 and not is_cloud else "healthy"

                    drives.append({
                        "drive": drive_letter,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                        "total_gb": total_gb,
                        "used_gb": used_gb,
                        "free_gb": free_gb,
                        "percent": percent,
                        "is_cloud": is_cloud,
                        "status": status
                    })
                except (PermissionError, FileNotFoundError):
                    continue
        except Exception as e:
            drives.append({"drive": "Error", "error": str(e)})

        return drives

    @staticmethod
    def get_top_processes(limit: int = 8) -> List[Dict[str, Any]]:
        """Returns top memory-consuming processes using cached execution to safeguard 8 GB RAM."""
        global _cached_processes, _last_proc_scan
        now = time.time()
        if _cached_processes and (now - _last_proc_scan) < _PROC_CACHE_TTL:
            return _cached_processes[:limit]

        procs = []
        try:
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    info = p.info
                    if info.get('memory_info'):
                        mem_mb = round(info['memory_info'].rss / (1024 ** 2), 1)
                        procs.append({
                            "pid": info['pid'],
                            "name": info['name'],
                            "ram_mb": mem_mb
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            procs.sort(key=lambda x: x['ram_mb'], reverse=True)
            _cached_processes = procs
            _last_proc_scan = now
            return procs[:limit]
        except Exception:
            return []

    @classmethod
    def get_full_telemetry(cls) -> Dict[str, Any]:
        """Aggregate snapshot of all system telemetry."""
        return {
            "cpu": cls.get_cpu_metrics(),
            "memory": cls.get_memory_metrics(),
            "gpu": cls.get_gpu_metrics(),
            "disks": cls.get_disk_metrics(),
            "top_processes": cls.get_top_processes(8)
        }
