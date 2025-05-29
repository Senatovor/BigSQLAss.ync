import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс настроек к вашей базы данных.
    Model_config - расположение вашего .env
    """
    DB_PORT: str
    DB_PORT: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    )

    def get_db_url(self) -> str:
        """Выдает ссылку на вашу базу данных"""
        return (f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@'
                f'{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}')


settings = Settings()
