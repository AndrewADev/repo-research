from core.config import get_config


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_with_kwargs(self):
        """Test get_config with model override kwargs."""
        config = get_config(model_name="llama3.1:8b")
        assert config.model_name == "llama3.1:8b"
