# config.py
import os
import yaml
from typing import Dict, Any

class Config:
    def __init__(self, config_path: str):
        # Load YAML config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Override with environment variables
        self._override_from_env()
    
    def _override_from_env(self):
        # Override Kafka settings
        if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
            self.config["kafka"]["bootstrap_servers"] = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        
        # Override Alpaca credentials
        if os.getenv("ALPACA_KEY"):
            self.config["alpaca"]["key"] = os.getenv("ALPACA_KEY")
        if os.getenv("ALPACA_SECRET"):
            self.config["alpaca"]["secret"] = os.getenv("ALPACA_SECRET")
        
        # Add more overrides as needed
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get config value using dot notation (e.g., 'kafka.topic')"""
        try:
            value = self.config
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default