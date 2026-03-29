import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass
class HardwareProfile:
    platform: str
    chip_description: str
    total_ram_gb: float
    cpu_cores: int
    is_apple_silicon: bool
    perf_cores: int
    cuda_devices: list[dict]


@dataclass
class ModelRecommendation:
    summarization_model: str
    embedding_model: str
    reason: str


def _sysctl_int(key: str) -> Optional[int]:
    try:
        out = subprocess.check_output(["sysctl", "-n", key], stderr=subprocess.DEVNULL)
        return int(out.strip())
    except Exception:
        return None


def detect_hardware() -> HardwareProfile:
    current_platform = sys.platform
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
    total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)

    if current_platform == "darwin":
        proc = platform.processor()
        is_apple_silicon = "arm" in proc.lower() or _is_arm_mac()
        chip_desc = _darwin_chip_description(is_apple_silicon)
        perf_cores = _sysctl_int("hw.perflevel0.physicalcpu") or cpu_cores
        return HardwareProfile(
            platform="darwin",
            chip_description=chip_desc,
            total_ram_gb=round(total_ram_gb, 1),
            cpu_cores=cpu_cores,
            is_apple_silicon=is_apple_silicon,
            perf_cores=perf_cores,
            cuda_devices=[],
        )
    else:
        cuda_devices = _detect_cuda_devices()
        chip_desc = f"Linux — {platform.processor() or 'CPU'}"
        return HardwareProfile(
            platform="linux",
            chip_description=chip_desc,
            total_ram_gb=round(total_ram_gb, 1),
            cpu_cores=cpu_cores,
            is_apple_silicon=False,
            perf_cores=cpu_cores,
            cuda_devices=cuda_devices,
        )


def _is_arm_mac() -> bool:
    try:
        out = subprocess.check_output(
            ["uname", "-m"], stderr=subprocess.DEVNULL
        ).decode().strip()
        return out == "arm64"
    except Exception:
        return False


def _darwin_chip_description(is_apple_silicon: bool) -> str:
    if not is_apple_silicon:
        return f"Intel Mac — {platform.processor()}"
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if out:
            return out
    except Exception:
        pass
    # Fallback: read from system_profiler
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"],
            stderr=subprocess.DEVNULL,
        ).decode()
        for line in out.splitlines():
            if "Chip" in line or "Processor" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "Apple Silicon"


def _detect_cuda_devices() -> list[dict]:
    try:
        import torch
        devices = []
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            devices.append({
                "name": props.name,
                "vram_gb": round(props.total_memory / (1024 ** 3), 1),
            })
        return devices
    except Exception:
        return []



SUPPORTED_SUMMARIZATION_MODELS = [
    "sshleifer/distilbart-cnn-6-6",
    "sshleifer/distilbart-cnn-12-6",
    "facebook/bart-large-cnn",
    "google/pegasus-large",
]

SUPPORTED_EMBEDDING_MODELS = [
    "all-MiniLM-L6-v2",
    "all-mpnet-base-v2",
]


def recommend_models(profile: HardwareProfile) -> ModelRecommendation:
    ram = profile.total_ram_gb

    if profile.platform == "darwin" and profile.is_apple_silicon:
        if ram >= 32:
            return ModelRecommendation(
                summarization_model="facebook/bart-large-cnn",
                embedding_model="all-mpnet-base-v2",
                reason=f"Apple Silicon with {ram:.0f}GB unified memory — full BART-large and mpnet supported.",
            )
        elif ram >= 16:
            return ModelRecommendation(
                summarization_model="sshleifer/distilbart-cnn-12-6",
                embedding_model="all-MiniLM-L6-v2",
                reason=f"Apple Silicon with {ram:.0f}GB unified memory — balanced distilBART-12-6 recommended.",
            )
        else:
            return ModelRecommendation(
                summarization_model="sshleifer/distilbart-cnn-6-6",
                embedding_model="all-MiniLM-L6-v2",
                reason=f"Apple Silicon with {ram:.0f}GB unified memory — lightweight distilBART-6-6 for efficiency.",
            )

    if profile.platform == "darwin" and not profile.is_apple_silicon:
        return ModelRecommendation(
            summarization_model="sshleifer/distilbart-cnn-6-6",
            embedding_model="all-MiniLM-L6-v2",
            reason="Intel Mac — lightweight models for best performance.",
        )

    # Linux
    if profile.cuda_devices:
        max_vram = max(d["vram_gb"] for d in profile.cuda_devices)
        if max_vram >= 16:
            return ModelRecommendation(
                summarization_model="google/pegasus-large",
                embedding_model="all-mpnet-base-v2",
                reason=f"Linux GPU with {max_vram:.0f}GB VRAM — Pegasus-large for best quality.",
            )
        elif max_vram >= 8:
            return ModelRecommendation(
                summarization_model="facebook/bart-large-cnn",
                embedding_model="all-mpnet-base-v2",
                reason=f"Linux GPU with {max_vram:.0f}GB VRAM — BART-large recommended.",
            )
        else:
            return ModelRecommendation(
                summarization_model="sshleifer/distilbart-cnn-12-6",
                embedding_model="all-MiniLM-L6-v2",
                reason=f"Linux GPU with {max_vram:.0f}GB VRAM — distilBART-12-6 fits comfortably.",
            )

    # Linux CPU only
    return ModelRecommendation(
        summarization_model="sshleifer/distilbart-cnn-6-6",
        embedding_model="all-MiniLM-L6-v2",
        reason="Linux CPU-only — lightweight models for reasonable speed.",
    )


def human_readable_profile(profile: HardwareProfile) -> str:
    parts = [profile.chip_description]
    parts.append(f"{profile.total_ram_gb:.0f}GB {'unified ' if profile.is_apple_silicon else ''}memory")
    if profile.is_apple_silicon and profile.perf_cores != profile.cpu_cores:
        parts.append(f"{profile.perf_cores} performance cores")
    else:
        parts.append(f"{profile.cpu_cores} CPU cores")
    if profile.cuda_devices:
        gpu_names = ", ".join(
            f"{d['name']} ({d['vram_gb']:.0f}GB VRAM)" for d in profile.cuda_devices
        )
        parts.append(f"GPU: {gpu_names}")
    return " — ".join(parts)
