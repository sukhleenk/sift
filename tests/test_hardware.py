import pytest
from app.hardware import HardwareProfile, recommend_models


def _profile(**kwargs) -> HardwareProfile:
    defaults = dict(
        platform="darwin",
        chip_description="Test Chip",
        total_ram_gb=8.0,
        cpu_cores=8,
        is_apple_silicon=True,
        perf_cores=6,
        cuda_devices=[],
    )
    defaults.update(kwargs)
    return HardwareProfile(**defaults)


def test_apple_silicon_high_ram():
    rec = recommend_models(_profile(total_ram_gb=32.0))
    assert rec.summarization_model == "facebook/bart-large-cnn"
    assert rec.embedding_model == "all-mpnet-base-v2"


def test_apple_silicon_mid_ram():
    rec = recommend_models(_profile(total_ram_gb=16.0))
    assert rec.summarization_model == "sshleifer/distilbart-cnn-12-6"
    assert rec.embedding_model == "all-MiniLM-L6-v2"


def test_apple_silicon_low_ram():
    rec = recommend_models(_profile(total_ram_gb=8.0))
    assert rec.summarization_model == "sshleifer/distilbart-cnn-6-6"
    assert rec.embedding_model == "all-MiniLM-L6-v2"


def test_intel_mac():
    rec = recommend_models(_profile(is_apple_silicon=False, total_ram_gb=16.0))
    assert rec.summarization_model == "sshleifer/distilbart-cnn-6-6"
    assert rec.embedding_model == "all-MiniLM-L6-v2"


def test_linux_cpu_only():
    rec = recommend_models(_profile(platform="linux", is_apple_silicon=False, cuda_devices=[]))
    assert rec.summarization_model == "sshleifer/distilbart-cnn-6-6"
    assert rec.embedding_model == "all-MiniLM-L6-v2"


def test_linux_low_vram_gpu():
    rec = recommend_models(_profile(
        platform="linux",
        is_apple_silicon=False,
        cuda_devices=[{"name": "RTX 3060", "vram_gb": 6.0}],
    ))
    assert rec.summarization_model == "sshleifer/distilbart-cnn-12-6"


def test_linux_mid_vram_gpu():
    rec = recommend_models(_profile(
        platform="linux",
        is_apple_silicon=False,
        cuda_devices=[{"name": "RTX 3080", "vram_gb": 10.0}],
    ))
    assert rec.summarization_model == "facebook/bart-large-cnn"
    assert rec.embedding_model == "all-mpnet-base-v2"


def test_linux_high_vram_gpu():
    rec = recommend_models(_profile(
        platform="linux",
        is_apple_silicon=False,
        cuda_devices=[{"name": "A100", "vram_gb": 40.0}],
    ))
    assert rec.summarization_model == "google/pegasus-large"
    assert rec.embedding_model == "all-mpnet-base-v2"


def test_recommendation_has_reason():
    rec = recommend_models(_profile())
    assert len(rec.reason) > 0
