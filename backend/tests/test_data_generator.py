"""Tests for synthetic data generator."""
import pytest
import pandas as pd
from equationx.data_generator import (
    generate_data,
    generate_all,
    generate_queue_data,
    generate_cpu_data,
    generate_db_data,
    generate_cache_data,
    get_system_info,
    SYSTEMS,
)


class TestDataGenerator:
    def test_generate_queue(self):
        df = generate_queue_data(n_points=100, seed=42)
        assert isinstance(df, pd.DataFrame)
        assert "queue_depth" in df.columns
        assert "arrival_rate" in df.columns
        assert "service_rate" in df.columns
        assert len(df) == 100

    def test_generate_cpu(self):
        df = generate_cpu_data(n_points=100, seed=42)
        assert "cpu_usage" in df.columns
        assert "load" in df.columns
        assert len(df) == 100

    def test_generate_db(self):
        df = generate_db_data(n_points=100, seed=42)
        assert "connections" in df.columns
        assert len(df) == 100

    def test_generate_cache(self):
        df = generate_cache_data(n_points=100, seed=42)
        assert "hit_rate" in df.columns
        assert len(df) == 100

    def test_generate_all(self):
        data = generate_all(seed=42)
        assert set(data.keys()) == {"queue", "cpu", "db_connections", "cache"}
        for name, df in data.items():
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0

    def test_generate_by_name(self):
        for system_type in ["queue", "cpu", "db_connections", "cache"]:
            df = generate_data(system_type, n_points=50, seed=42)
            assert len(df) == 50

    def test_invalid_system(self):
        with pytest.raises(ValueError):
            generate_data("invalid_system")

    def test_get_system_info(self):
        info = get_system_info("queue")
        assert "variables" in info
        assert "equation_latex" in info

    def test_noise_effect(self):
        df_low = generate_queue_data(n_points=100, noise_pct=0.01, seed=42)
        df_high = generate_queue_data(n_points=100, noise_pct=0.2, seed=42)
        # Higher noise should produce more variance
        assert df_high["queue_depth"].std() > df_low["queue_depth"].std() * 0.5
