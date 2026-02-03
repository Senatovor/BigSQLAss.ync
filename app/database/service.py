from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, Select, Result, ColumnElement
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload, aliased, Query, RelationshipProperty
from typing import Sequence, TypeVar, Generic, List, Type, Tuple, Optional, Any, Dict
from pydantic import BaseModel
from uuid import UUID
from loguru import logger

from app.database.model import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class QueryWrapper:
    """
    Обертка для запроса с поддержкой цепочки вызовов и ленивого выполнения.
    """

    def __init__(self, query, model_name: str = ""):
        self.query = query
        self.model_name = model_name
        self.log_prefix = f"[{model_name}] " if model_name else ""

    async def execute(self, session: AsyncSession) -> Result:
        try:
            logger.debug(f"{self.log_prefix}Выполнение запроса")
            result = await session.execute(self.query)
            return result
        except SQLAlchemyError as e:
            logger.error(f"{self.log_prefix}Ошибка при выполнении запроса: {e}")
            raise e

    async def scalar_one_or_none(self, session: AsyncSession) -> Optional[ModelType]:
        result = await self.execute(session)
        return result.scalar_one_or_none()

    async def scalars_all(self, session: AsyncSession) -> Sequence[ModelType]:
        result = await self.execute(session)
        return result.scalars().all()

    async def scalars_first(self, session: AsyncSession) -> Optional[ModelType]:
        result = await self.execute(session)
        return result.scalars().first()

    async def scalar(self, session: AsyncSession) -> Any:
        result = await self.execute(session)
        return result.scalar()

    def to_query(self) -> Query:
        return self.query

    def __str__(self) -> str:
        return str(self.query)


class DBManager(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        if not model or not issubclass(model, Base):
            raise ValueError("Модель должна быть указана и наследоваться от Base")
        self.model = model

    def _add_loads(self, query: Select, load_options: Optional[List[Any]] = None) -> Select:
        """
        Добавляет опции загрузки через SQLAlchemy опции.

        Примеры:
        - load_options=[selectinload(HomeWork.answers)]
        - load_options=[selectinload(Course.groups), selectinload(Course.teachers)]
        """
        if not load_options:
            return query

        query = query.options(*load_options)
        return query

    def _add_joins(self, query: Select, joins: Optional[List[Any]] = None) -> Select:
        """
        Добавляет JOIN к запросу через SQLAlchemy атрибуты.

        Примеры:
        - joins=[HomeWork.groups, Group.users]
        - joins=[Course.teachers]
        """
        if not joins:
            return query

        for join_attr in joins:
            query = query.join(join_attr)
            logger.debug(f"Добавлен JOIN: {join_attr}")

        return query

    async def add(self, session: AsyncSession, values: CreateSchemaType) -> ModelType:
        values_dict = values.model_dump(exclude_unset=True)
        logger.info(f"Добавление записи {self.model.__name__} с параметрами: {values_dict}")
        try:
            new_object = self.model(**values_dict)
            session.add(new_object)
            await session.flush()
            await session.refresh(new_object)
            logger.info(f"Запись {self.model.__name__} успешно добавлена с ID: {getattr(new_object, 'id', 'N/A')}")
            return new_object
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении записи {self.model.__name__}: {e}")
            await session.rollback()
            raise e

    async def add_all(self, session: AsyncSession, instances: List[CreateSchemaType]) -> Sequence[ModelType]:
        instances_list = [instance.model_dump(exclude_unset=True) for instance in instances]
        logger.info(f"Добавление {len(instances)} записей {self.model.__name__}")
        try:
            new_objects = [self.model(**values) for values in instances_list]
            session.add_all(new_objects)
            await session.flush()
            for obj in new_objects:
                await session.refresh(obj)
            logger.info(f"Успешно добавлено {len(new_objects)} записей {self.model.__name__}")
            return new_objects
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при массовом добавлении записей {self.model.__name__}: {e}")
            await session.rollback()
            raise e

    def find_by_id(
            self,
            index: UUID,
            load_options: Optional[List[Any]] = None
    ) -> QueryWrapper:
        if not index:
            raise ValueError("ID записи не может быть пустым")
        query = select(self.model).where(self.model.id == index)
        query = self._add_loads(query, load_options)

        logger.debug(f"{self.model.__name__}: Создан запрос для поиска по ID: {index}")
        return QueryWrapper(query, self.model.__name__)

    def find_one_by(
            self,
            filters: Optional[List[ColumnElement]] = None,
            load_options: Optional[List[Any]] = None,
            joins: Optional[List[Any]] = None,
            distinct: bool = False
    ) -> QueryWrapper:
        """
        Создает запрос для поиска одной записи.

        Пример:
        await DBManager(HomeWork).find_one_by(
            filters=[User.id == user_id],
            joins=[HomeWork.groups, Group.users],
            load_options=[selectinload(HomeWork.answers)],
            distinct=True
        ).scalar_one_or_none(session)
        """
        logger.debug(f"{self.model.__name__}: Создание запроса для поиска одной записи")

        query = select(self.model)
        query = self._add_joins(query, joins)
        query = self._add_filters(query, filters)
        query = self._add_loads(query, load_options)
        query = self._add_distinct(query, distinct)

        return QueryWrapper(query, self.model.__name__)
