from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.config import settings
from functools import wraps

SQL_DATABASE_URL = settings.get_db_url()

engine = create_async_engine(url=SQL_DATABASE_URL)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


class DatabaseSessionManager:
    """Класс для работы с сессиями"""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.session_factory = session_maker

    def connection(self, isolation_level: str | None = None, commit: bool = False):
        """
        Декоратор. Создает сессию, самостоятельно её закрывает, делает rollback при ошибке.
        Имеет настройку авто-commit и уровня изоляции.
        """
        def decorator(method):
            @wraps(method)
            async def wrapper(*args, **kwargs):
                async with self.session_factory() as session:
                    try:
                        if isolation_level:
                            await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                        result = await method(*args, session=session, **kwargs)
                        if commit:
                            await session.commit()
                        return result
                    except Exception:
                        await session.rollback()
                        raise
                    finally:
                        await session.close()

            return wrapper

        return decorator


session_manager = DatabaseSessionManager(session_factory)

# Пример использования декоратора
#
# @session_manager.connection(commit=True)
# async def test(session: AsyncSession):
#     pass
