from sqlalchemy import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from typing import Optional, Type, Sequence

from app.database.model import Base


class QueryWrapper:
    """
    Упрощенная обертка для выполнения SQLAlchemy запросов.

    Предоставляет базовые методы для выполнения запросов и получения результатов
    с автоматическим логированием выполняемых запросов.

    Args:
        query: SQLAlchemy запрос для выполнения.

    Примеры использования:
        wrapper = QueryWrapper(select(User).where(User.id == 1))
        user = await wrapper.scalar_one_or_none(session)
        users = await wrapper.all(session)
    """
    def __init__(self, query):
        """
        Инициализация обертки запроса.

        Args:
            query: SQLAlchemy запрос.
        """
        self.query = query

    async def execute(self, session: AsyncSession) -> Result:
        """
        Выполняет запрос в переданной сессии.

        Args:
            session (AsyncSession): Асинхронная сессия SQLAlchemy.

        Returns:
            Result: Результат выполнения запроса SQLAlchemy.
        """
        logger.info(f'Выполняется query: {self.query}')
        result = await session.execute(self.query)
        return result

    async def scalar_one_or_none(self, session: AsyncSession) -> Optional[Type[Base]]:
        """
        Выполняет запрос и возвращает один скалярный результат или None.

        Используется для запросов, возвращающих единственное значение
        или объект.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Optional[Type[Base]]: Один объект модели или скалярное значение,
                                 или None, если результат пустой.
        """
        result = await self.execute(session)
        return result.scalar_one_or_none()

    async def first(self, session: AsyncSession) -> Optional[Type[Base]]:
        """
        Выполняет запрос и возвращает первую строку результата или None.

        Отличается от scalar_one_or_none тем, что возвращает Row объект
        вместо скалярного значения.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Optional[Type[Base]]: Первая строка результата или None.
        """
        result = await self.execute(session)
        return result.first()

    async def all(self, session: AsyncSession) -> Sequence[Type[Base]]:
        """
        Выполняет запрос и возвращает все строки результата.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Sequence[Type[Base]]: Последовательность строк результата.
        """
        result = await self.execute(session)
        return result.all()

    async def scalars(self, session: AsyncSession):
        """
        Выполняет запрос и возвращает объект ScalarResult для итерации.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            ScalarResult: Итератор скалярных значений.
        """
        result = await self.execute(session)
        return result.scalars()


def sql_manager(query) -> QueryWrapper:
    """
    Фабричная функция для создания QueryWrapper.

    Создает и возвращает экземпляр QueryWrapper для переданного запроса.

    Args:
        query: SQLAlchemy запрос.

    Returns:
        QueryWrapper: Обертка для выполнения запроса.

    Пример:
        query = select(User)
        wrapper = sql_manager(query)
        result = await wrapper.all(session)

        # Или в одну строку:
        users = await sql_manager(select(User)).all(session)
    """
    return QueryWrapper(query)
