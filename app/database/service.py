from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError
from typing import Sequence, TypeVar, Generic
from pydantic import BaseModel
from app.database.model import Base
from uuid import UUID


T = TypeVar('T', bound=Base)


class BaseService(Generic[T]):
    """
    Базовый класс сервиса, который наследуется в другие. Имеет базовые универсальные методы.
    В методах подразумевается, что в values и filters вы используете Pydantic классы.
    """
    model = type[T]

    @classmethod
    async def add(cls, session: AsyncSession, values: BaseModel) -> model:
        """Добавление модели"""
        values_dict = values.model_dump(exclude_unset=True)
        new_object = cls.model(**values_dict)
        session.add(new_object)
        try:
            await session.flush()
        except SQLAlchemyError as e:
            raise e
        return new_object

    @classmethod
    async def add_all(cls, session: AsyncSession, instances: list[BaseModel]) -> Sequence[model]:
        """Добавление списка моделей"""
        instances_list = [instance.model_dump(exclude_unset=True) for instance in instances]
        new_objects = [cls.model(**values) for values in instances_list]
        session.add_all(new_objects)
        try:
            await session.flush()
        except SQLAlchemyError as e:
            raise e
        return new_objects

    @classmethod
    async def find(cls, session: AsyncSession, index: int | UUID) -> model:
        """Нахождение модели по id"""
        try:
            return await session.get(cls.model, index)
        except SQLAlchemyError as e:
            raise e

    @classmethod
    async def find_all(cls, session: AsyncSession, filters: BaseModel | None = None) -> Sequence[model]:
        """Нахождение моделей по фильтрам. В противном случе выдает все модели"""
        if filters:
            filters_dict = filters.model_dump(exclude_unset=True)
        else:
            filters_dict = {}
        try:
            query = select(cls.model).filter_by(**filters_dict)
            result = await session.execute(query)
            find_objects = result.scalars().all()
            return find_objects
        except SQLAlchemyError as e:
            raise e

    @classmethod
    async def update(cls, session: AsyncSession, index: int | UUID, values: BaseModel):
        """Обновляет модель по id"""
        values_dict = values.model_dump(exclude_unset=True)
        try:
            find_object = await session.get(cls.model, index)
            for key, value in values_dict.items():
                setattr(find_object, key, value)
            await session.flush()
        except SQLAlchemyError as e:
            raise e

    @classmethod
    async def update_all(cls, session: AsyncSession, values: BaseModel, filters: BaseModel | None = None):
        """Обновляет все модели по фильтрам. В противном случе обновляет все модели"""
        values_dict = values.model_dump(exclude_unset=True)
        if filters:
            filters_dict = filters.model_dump(exclude_unset=True)
        else:
            filters_dict = {}
        try:
            query = update(cls.model).where(**filters_dict).values(**values_dict)
            await session.execute(query)
            await session.flush()
        except SQLAlchemyError as e:
            raise e

    @classmethod
    async def delete(cls, session: AsyncSession, index: int | UUID):
        """Удаляет модель по id"""
        try:
            delete_object = await session.get(cls.model, index)
            await session.delete(delete_object)
            await session.flush()
        except SQLAlchemyError as e:
            raise e

    @classmethod
    async def delete_all(cls, session, filters: BaseModel | None = None):
        """Удаление моделей по фильтру. В противном случе удаляет все модели"""
        if filters:
            filters_dict = filters.model_dump(exclude_unset=True)
        else:
            filters_dict = {}
        try:
            query = delete(cls.model).filter_by(**filters_dict)
            await session.execute(query)
            await session.flush()
        except SQLAlchemyError as e:
            raise e
