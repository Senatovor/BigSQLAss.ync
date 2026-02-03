from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class DatabaseConfig(BaseSettings):
    """Класс конфигурации базы данных.

    Загружает настройки из .env файла или переменных окружения.

    Attributes:
        DB_HOST: Хост базы данных
        DB_PORT: Порт базы данных
        DB_NAME: Имя базы данных
        DB_USER: Пользователь БД
        DB_PASSWORD: Пароль пользователя БД
    """
    # Настройки базы данных
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )

    @property
    def database_url_posgresql(self) -> str:
        """Генерирует URL для подключения к PostgreSQL с использованием asyncpg."""
        return (f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@'
                f'{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}')

settings = DatabaseConfig() # type: ignore
