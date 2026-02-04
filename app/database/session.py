import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession, AsyncEngine
from functools import wraps
from typing import AsyncIterator
from loguru import logger
from datetime import datetime
from contextlib import asynccontextmanager

from app.config import settings

SQL_DATABASE_URL = settings.database_url_posgresql


class DatabaseSessionManager:
    """
    Менеджер для управления асинхронными сессиями базы данных.

    Обеспечивает создание, настройку и безопасное закрытие сессий,
    поддержку транзакций с различными уровнями изоляции и автоматическое
    логирование операций.

    Args:
        database_url (str): URL для подключения к БД.
        session_factory (async_sessionmaker[AsyncSession] | None, optional):
            Существующая фабрика сессий. Defaults to None.
        engine (AsyncEngine | None, optional):
            Существующий движок базы данных. Defaults to None.
    """
    def __init__(
            self,
            database_url: str,
            session_factory: async_sessionmaker[AsyncSession] | None = None,
            engine: AsyncEngine | None = None
    ) -> None:
        """Инициализация менеджера сессий.

        Args:
            database_url: URL для подключения к БД
            session_factory: Опциональная фабрика сессий
            engine: Опциональный существующий движок
        """
        self.database_url = database_url
        self.engine = engine
        self.session_factory = session_factory

    async def init(self):
        """
        Инициализирует движок базы данных и фабрику сессий.

        Создает асинхронный движок с переданным URL и настраивает фабрику сессий
        с отключенным autoflush и expire_on_commit для лучшего контроля над сессиями.
        Должен вызываться при начале работы приложения.
        """
        self.engine = create_async_engine(
            url=self.database_url,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False
        )

    async def close(self):
        """
        Закрывает соединения с базой данных.

        Освобождает все соединения пула, созданные движком.
        Должен вызываться при завершении работы приложения.
        """
        if self.engine:
            await self.engine.dispose()

    @asynccontextmanager
    async def session(
            self,
            isolation_level: str | None = None,
            commit: bool = False
    ) -> AsyncIterator[AsyncSession]:
        """
        Асинхронный контекстный менеджер для работы с сессиями БД.

        Создает новую сессию, при необходимости устанавливает уровень изоляции,
        автоматически обрабатывает коммит и откат транзакций, логирует время выполнения.

        Args:
            isolation_level (str | None, optional):
                Уровень изоляции транзакции (например, "READ COMMITTED", "REPEATABLE READ").
                Defaults to None.
            commit (bool, optional):
                Автоматически коммитить транзакцию при успешном завершении.
                Defaults to False.

        Yields:
            AsyncSession: Асинхронная сессия SQLAlchemy.

        Raises:
            Exception: Любое исключение, возникшее в контексте сессии,
                       приводит к откату транзакции и пробрасывается дальше.
        """
        start_time = datetime.now()
        logger.info(f"Создание новой сессии. Изоляция: {isolation_level}, Автокоммит: {commit}")
        async with self.session_factory() as session:
            try:
                if isolation_level:
                    logger.debug(f"Установка уровня изоляции: {isolation_level}")
                    await session.execute(
                        text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
                    )
                yield session
                if commit:
                    await session.commit()
                    logger.info("Изменения успешно закоммичены")
            except Exception as e:
                logger.error(f"Ошибка в сессии: {str(e)}", exc_info=True)
                await session.rollback()
                logger.info("Выполнен откат транзакции")
                raise
            finally:
                await session.close()
                exec_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Сессия закрыта. Время выполнения: {exec_time:.2f} сек")

    def connection(self, isolation_level: str | None = None, commit: bool = False):
        """
        Декоратор для оборачивания методов в транзакцию БД.

        Автоматически инжектирует сессию в качестве ключевого аргумента 'session'
        в декорируемый метод, управляет жизненным циклом транзакции.

        Args:
            isolation_level (str | None, optional):
                Уровень изоляции транзакции. Defaults to None.
            commit (bool, optional):
                Автоматически коммитить транзакцию. Defaults to False.

        Returns:
            decorator: Декоратор, который оборачивает асинхронный метод.

        Warning:
            Декорируемый метод должен принимать параметр 'session' в своей сигнатуре.
        """
        def decorator(method):
            @wraps(method)
            async def wrapper(*args, **kwargs):
                start_time = datetime.now()
                logger.info(
                    f"Начало транзакции для {method.__name__}. Изоляция: {isolation_level}, Автокоммит: {commit}")
                async with self.session_factory() as session:  # type: ignore
                    try:
                        if isolation_level:
                            logger.debug(f"Установка уровня изоляции: {isolation_level}")
                            await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                        result = await method(*args, session=session, **kwargs)
                        if commit:
                            await session.commit()
                            logger.info("Изменения успешно закоммичены")
                        return result
                    except Exception as e:
                        logger.error(f"Ошибка в транзакции {method.__name__}: {str(e)}", exc_info=True)
                        await session.rollback()
                        logger.info("Выполнен откат транзакции")
                        raise
                    finally:
                        await session.close()
                        exec_time = (datetime.now() - start_time).total_seconds()
                        logger.info(f"Транзакция завершена. Время выполнения: {exec_time:.2f} сек")

            return wrapper

        return decorator


# Глобальный экземпляр менеджера сессий
session_manager = DatabaseSessionManager(SQL_DATABASE_URL)
asyncio.run(session_manager.init())
