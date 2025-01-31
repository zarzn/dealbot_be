import os
from functools import lru_cache
from .development import DevelopmentConfig
from .production import ProductionConfig

@lru_cache()
def get_settings():
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        return ProductionConfig()
    
    return DevelopmentConfig() 