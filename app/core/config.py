"""Application configuration using Pydantic Settings."""


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    PROJECT_NAME: str = "OpenStack VM Lifecycle API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["*"]

    # OpenStack Auth
    OS_AUTH_URL: str = "http://localhost:5000/v3"
    OS_USERNAME: str = "admin"
    OS_PASSWORD: str = "secret"
    OS_PROJECT_NAME: str = "admin"
    OS_USER_DOMAIN_NAME: str = "Default"
    OS_PROJECT_DOMAIN_NAME: str = "Default"
    OS_REGION_NAME: str = "RegionOne"
    OS_IDENTITY_API_VERSION: int = 3

    # Compute
    OS_COMPUTE_API_VERSION: str = "2.87"
    OS_NOVA_URL: str = ""  # Auto-discovered from catalog if empty

    # Connection
    OS_CONNECT_TIMEOUT: int = 10
    OS_READ_TIMEOUT: int = 30
    OS_MAX_RETRIES: int = 3

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Mock mode (for demo/testing without real OpenStack)
    MOCK_MODE: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
