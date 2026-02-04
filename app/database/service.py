from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, Select, Result, ColumnElement, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query
from typing import Sequence, TypeVar, Generic, List, Type, Optional, Any, Dict
from pydantic import BaseModel
from uuid import UUID
from loguru import logger

from app.database.model import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class QueryWrapper:
    """
    Обертка для безопасного выполнения SQL-запросов с логированием.

    Предоставляет удобные методы для выполнения запросов и получения результатов
    в различных форматах (скалярные значения, списки, единичные объекты).

    Атрибуты:
        query: SQLAlchemy запрос (Select, Update, Delete и т.д.).
        model_name (str): Имя модели для логирования (опционально).
        log_prefix (str): Префикс для лог-сообщений на основе model_name.

    Args:
        query: SQLAlchemy запрос.
        model_name (str, optional): Имя модели для контекста логирования.
    """
    def __init__(self, query, model_name: str = ""):
        """
        Инициализация обертки запроса.

        Args:
            query: SQLAlchemy запрос.
            model_name (str, optional): Имя модели для логирования.
        """
        self.query = query
        self.model_name = model_name
        self.log_prefix = f"[{model_name}] " if model_name else ""

    async def execute(self, session: AsyncSession) -> Result:
        """
        Выполняет обернутый запрос в переданной сессии.

        Args:
            session (AsyncSession): Асинхронная сессия SQLAlchemy.

        Returns:
            Result: Результат выполнения запроса.

        Raises:
            SQLAlchemyError: При ошибке выполнения запроса.
        """
        try:
            logger.debug(f"{self.log_prefix}Выполнение запроса")
            result = await session.execute(self.query)
            return result
        except SQLAlchemyError as e:
            logger.error(f"{self.log_prefix}Ошибка при выполнении запроса: {e}")
            raise e

    async def scalar_one_or_none(self, session: AsyncSession) -> Optional[ModelType]:
        """
        Выполняет запрос и возвращает один результат или None.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Optional[ModelType]: Один объект модели или None, если не найдено.

        Идеально подходит для запросов, где ожидается максимум один результат.
        """
        result = await self.execute(session)
        return result.scalar_one_or_none()

    async def scalars_all(self, session: AsyncSession) -> Sequence[ModelType]:
        """
        Выполняет запрос и возвращает все результаты в виде последовательности.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Sequence[ModelType]: Последовательность объектов модели.
        """
        result = await self.execute(session)
        return result.scalars().all()

    async def scalars_first(self, session: AsyncSession) -> Optional[ModelType]:
        """
        Выполняет запрос и возвращает первый результат или None.

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Optional[ModelType]: Первый объект модели или None.
        """
        result = await self.execute(session)
        return result.scalars().first()

    async def scalar(self, session: AsyncSession) -> Any:
        """
        Выполняет запрос и возвращает скалярное значение.

        Полезно для агрегатных функций (COUNT, SUM, AVG и т.д.).

        Args:
            session (AsyncSession): Асинхронная сессия.

        Returns:
            Any: Скалярное значение.
        """
        result = await self.execute(session)
        return result.scalar()

    def to_query(self) -> Query:
        """
        Возвращает исходный SQLAlchemy запрос.

        Returns:
            Query: Исходный запрос SQLAlchemy.
        """
        return self.query

    def __str__(self) -> str:
        return str(self.query)


class DBManager(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Универсальный менеджер для CRUD операций над моделями базы данных.

    Предоставляет типизированные методы для создания, чтения, обновления и удаления
    записей с поддержкой фильтрации, джойнов, загрузки связей и логирования.

    Generic:
        ModelType: Класс SQLAlchemy модели.
        CreateSchemaType: Pydantic схема для создания записи.
        UpdateSchemaType: Pydantic схема для обновления записи.

    Args:
        model (Type[ModelType]): Класс модели SQLAlchemy.

    Raises:
        ValueError: Если модель не указана или не наследуется от Base.
    """
    def __init__(self, model: Type[ModelType]):
        """
        Инициализация менеджера для работы с конкретной моделью.

        Args:
            model (Type[ModelType]): Класс модели SQLAlchemy.

        Raises:
            ValueError: Если модель не указана или не наследуется от Base.
        """
        if not model or not issubclass(model, Base):
            raise ValueError("Модель должна быть указана и наследоваться от Base")
        self.model = model

    def _add_filters_dict(self, query: Select, filters: Optional[Dict[str, Any]] = None) -> Select:
        """
        Добавляет простые фильтры по атрибутам модели через словарь.

        Фильтры применяются через оператор равенства (==).

        Args:
            query (Select): Исходный SQLAlchemy запрос.
            filters (Optional[Dict[str, Any]]): Словарь фильтров {поле: значение}.

        Returns:
            Select: Запрос с добавленными фильтрами.

        Raises:
            ValueError: Если указанное поле не существует в модели.

        Пример:
            filters={'username': 'John', 'is_active': True}
            # Преобразуется в: WHERE username = 'John' AND is_active = True
        """
        if not filters:
            return query
        conditions = []
        for key, value in filters.items():
            if hasattr(self.model, key):
                field = getattr(self.model, key)
                conditions.append(field == value)
            else:
                raise ValueError(f"Поле {key} не найдено в модели {self.model.__name__}")
        if conditions:
            if len(conditions) == 1:
                query = query.where(conditions[0])
            else:
                query = query.where(and_(*conditions))
        return query

    @staticmethod
    def _add_filters_columns(query: Select, filters: Optional[List[ColumnElement]] = None) -> Select:
        """
        Добавляет сложные фильтры через SQLAlchemy выражения ColumnElement.

        Позволяет использовать полный функционал SQLAlchemy для фильтрации.

        Args:
            query (Select): Исходный запрос.
            filters (Optional[List[ColumnElement]]): Список SQLAlchemy условий.

        Returns:
            Select: Запрос с добавленными фильтрами.

        Пример:
            filters=[
                User.age >= 18,
                User.email.ilike('%@gmail.com'),
                or_(User.status == 'active', User.status == 'pending')
            ]
        """
        if not filters:
            return query
        query = query.where(and_(*filters))
        return query

    @staticmethod
    def _add_loads(query: Select, load_options: Optional[List[Any]] = None) -> Select:
        """
        Добавляет опции eager loading для загрузки связанных данных.

        Args:
            query (Select): Исходный запрос.
            load_options (Optional[List[Any]]): Список опций загрузки SQLAlchemy.

        Returns:
            Select: Запрос с добавленными опциями загрузки.

        Пример:
            load_options=[
                selectinload(User.orders),
                joinedload(User.profile)
            ]
        """
        if not load_options:
            return query
        query = query.options(*load_options)
        return query

    @staticmethod
    def _add_joins(query: Select, joins: Optional[List[Any]] = None) -> Select:
        """
        Добавляет JOIN выражения к запросу.

        Args:
            query (Select): Исходный запрос.
            joins (Optional[List[Any]]): Список атрибутов для JOIN.

        Returns:
            Select: Запрос с добавленными JOIN.

        Пример:
            joins=[User.orders, Order.items]
            # Создает: JOIN orders ON ... JOIN order_items ON ...
        """
        if not joins:
            return query
        for join_attr in joins:
            query = query.join(join_attr)
        return query

    async def add(self, session: AsyncSession, values: CreateSchemaType) -> ModelType:
        """
        Создает новую запись в базе данных.

        Args:
            session (AsyncSession): Асинхронная сессия.
            values (CreateSchemaType): Pydantic схема с данными для создания.

        Returns:
            ModelType: Созданный объект модели с заполненными полями (включая ID).

        Raises:
            SQLAlchemyError: При ошибке вставки в БД.
        """
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
        """
        Массовое создание записей в базе данных.

        Args:
            session (AsyncSession): Асинхронная сессия.
            instances (List[CreateSchemaType]): Список схем для создания.

        Returns:
            Sequence[ModelType]: Список созданных объектов.

        Raises:
            SQLAlchemyError: При ошибке массовой вставки.
        """
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

    async def find_by_id(
            self,
            session: AsyncSession,
            index: UUID,
            load_options: Optional[List[Any]] = None
    ) -> Optional[ModelType]:
        """
        Находит запись по UUID идентификатору.

        Args:
            session (AsyncSession): Асинхронная сессия.
            index (UUID): Уникальный идентификатор записи.
            load_options (Optional[List[Any]]): Опции загрузки связанных данных.

        Returns:
            Optional[ModelType]: Найденный объект или None.

        Raises:
            ValueError: Если index пустой.
            SQLAlchemyError: При ошибке запроса.
        """
        if not index:
            raise ValueError("ID записи не может быть пустым")
        query = select(self.model).where(self.model.id == index)
        query = self._add_loads(query, load_options)

        logger.debug(f"{self.model.__name__}: Создан запрос для поиска по ID: {index}")
        result = await session.execute(query)
        return result.scalar_one_or_none()

    def find(
            self,
            filters_dict: Optional[Dict[str, Any]] = None,
            filters_columns: Optional[List[ColumnElement]] = None,
            joins: Optional[List[Any]] = None,
            load_options: Optional[List[Any]] = None
    ) -> QueryWrapper:
        """
        Создает гибкий запрос для поиска записей с поддержкой фильтров и джойнов.

        Возвращает QueryWrapper для последующего выполнения.

        Args:
            filters_dict (Optional[Dict[str, Any]]): Простые фильтры по равенству.
            filters_columns (Optional[List[ColumnElement]]): Сложные SQLAlchemy фильтры.
            joins (Optional[List[Any]]): Список атрибутов для JOIN.
            load_options (Optional[List[Any]]): Опции загрузки связанных данных.

        Returns:
            QueryWrapper: Обертка для выполнения запроса.

        Пример:
            wrapper = manager.find(
                filters_dict={"category": "books"},
                filters_columns=[Product.price > 100],
                joins=[Product.category],
                load_options=[selectinload(Product.reviews)]
            )
            products = await wrapper.scalars_all(session)
        """
        logger.debug(f"{self.model.__name__}: Создание запроса для поиска одной записи")

        query = select(self.model)
        query = self._add_filters_dict(query, filters_dict)
        query = self._add_joins(query, joins)
        query = self._add_filters_columns(query, filters_columns)
        query = self._add_loads(query, load_options)

        return QueryWrapper(query, self.model.__name__)

    async def update_by_id(self, session: AsyncSession, index: UUID, values: UpdateSchemaType) -> Optional[ModelType]:
        """
        Обновляет запись по UUID идентификатору.

        Args:
            session (AsyncSession): Асинхронная сессия.
            index (UUID): Идентификатор обновляемой записи.
            values (UpdateSchemaType): Схема с данными для обновления.

        Returns:
            Optional[ModelType]: Обновленный объект или None, если запись не найдена.

        Raises:
            SQLAlchemyError: При ошибке обновления.
        """
        values_dict = values.model_dump(exclude_unset=True, exclude_none=True)
        if not values_dict:
            logger.warning(f"Нет данных для обновления записи {self.model.__name__} по ID: {index}")
            return None
        logger.info(f"Обновление записи {self.model.__name__} по ID: {index}")
        try:
            find_object = await session.get(self.model, index)
            if not find_object:
                logger.warning(f"Запись {self.model.__name__} с ID {index} не найдена для обновления")
                return None
            for key, value in values_dict.items():
                if hasattr(find_object, key):
                    setattr(find_object, key, value)
                else:
                    logger.warning(f"Поле {key} не существует в модели {self.model.__name__}")
            await session.flush()
            await session.refresh(find_object)
            logger.info(f"Запись {self.model.__name__} с ID {index} успешно обновлена")
            return find_object
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении записи {self.model.__name__} с ID {index}: {e}")
            await session.rollback()
            raise e

    async def update_all(
            self,
            session: AsyncSession,
            values: UpdateSchemaType,
            filters_dict: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Массовое обновление записей по фильтрам.

        Args:
            session (AsyncSession): Асинхронная сессия.
            values (UpdateSchemaType): Схема с данными для обновления.
            filters_dict (Optional[Dict[str, Any]]): Фильтры для выбора обновляемых записей.

        Returns:
            None

        Raises:
            SQLAlchemyError: При ошибке массового обновления.
        """
        values_dict = values.model_dump(exclude_unset=True, exclude_none=True)
        try:
            query = update(self.model)
            if filters_dict:
                query = query.filter_by(**filters_dict)
            query = query.values(**values_dict)
            result = await session.execute(query)
            await session.flush()
            logger.info(f"Обновлено {result.rowcount} записей {self.model.__name__}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении записей {self.model.__name__}: {e}")
            raise e

    async def delete_by_id(self, session: AsyncSession, index: UUID) -> None:
        """
        Удаляет запись по UUID идентификатору.

        Args:
            session (AsyncSession): Асинхронная сессия.
            index (UUID): Идентификатор удаляемой записи.

        Raises:
            SQLAlchemyError: При ошибке удаления.
        """
        logger.info(f"Удаление записи {self.model.__name__} по ID: {index}")
        try:
            delete_object = await session.get(self.model, index)
            await session.delete(delete_object)
            await session.flush()
            logger.info(f"Запись {self.model.__name__} с ID {index} удалена")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении записи {self.model.__name__} с ID {index}: {e}")
            raise e

    async def delete_all(self, session: AsyncSession, filters_dict: Optional[Dict[str, Any]] = None) -> None:
        """
        Массовое удаление записей по фильтрам.

        Args:
            session (AsyncSession): Асинхронная сессия.
            filters_dict (Optional[Dict[str, Any]]): Фильтры для выбора удаляемых записей.

        Returns:
            None

        Raises:
            SQLAlchemyError: При ошибке массового удаления.
        """
        logger.info(f"Удаление записей {self.model.__name__} по фильтрам")
        try:
            query = delete(self.model)
            if filters_dict:
                query = query.filter_by(**filters_dict)
            result = await session.execute(query)
            await session.flush()
            logger.info(f"Удалено {result.rowcount} записей {self.model.__name__}")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении записей {self.model.__name__}: {e}")
            raise e

    async def count(
            self,
            session: AsyncSession,
            filters_dict: Optional[Dict[str, Any]] = None,
            filters_columns: Optional[List[ColumnElement]] = None,
            joins: Optional[List[Any]] = None,
    ) -> int:
        """
        Подсчитывает количество записей, соответствующих фильтрам.

        Args:
            session (AsyncSession): Асинхронная сессия.
            filters_dict (Optional[Dict[str, Any]]): Простые фильтры.
            filters_columns (Optional[List[ColumnElement]]): Сложные фильтры.
            joins (Optional[List[Any]]): Джойны для подсчета.

        Returns:
            int: Количество записей.

        Raises:
            SQLAlchemyError: При ошибке подсчета.
        """
        logger.debug(f"Подсчет количества записей {self.model.__name__}")

        try:
            query = select(func.count(self.model.id))

            query = self._add_filters_dict(query, filters_dict)
            query = self._add_joins(query, joins)
            query = self._add_filters_columns(query, filters_columns)

            result = await session.execute(query)
            count = result.scalar() or 0

            logger.debug(f"Найдено {count} записей {self.model.__name__}")
            return count

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при подсчете записей {self.model.__name__}: {e}")
            raise e

    @staticmethod
    async def add_relation(
            session: AsyncSession,
            instance: ModelType,
            relation_name: str,
            related_instance: Base
    ) -> None:
        """
        Добавляет связь между объектами.

        Поддерживает как связи один-ко-многим (списки), так и один-к-одному.

        Args:
            session (AsyncSession): Асинхронная сессия.
            instance (ModelType): Основной объект.
            relation_name (str): Имя атрибута связи.
            related_instance (Base): Связанный объект.

        Raises:
            ValueError: Если связь с указанным именем не существует.
            SQLAlchemyError: При ошибке сохранения.

        Пример:
            # Для связи один-ко-многим
            await DBManager.add_relation(session, user, "roles", admin_role)

            # Для связи один-к-одному
            await DBManager.add_relation(session, user, "profile", user_profile)
        """
        if not hasattr(instance, relation_name):
            raise ValueError(f"Связь {relation_name} не найдена")

        relation = getattr(instance, relation_name)

        if isinstance(relation, list):
            if related_instance not in relation:
                relation.append(related_instance)
        else:
            setattr(instance, relation_name, related_instance)

        await session.flush()

    @staticmethod
    async def remove_relation(
            session: AsyncSession,
            instance: ModelType,
            relation_name: str,
            related_instance: Base
    ) -> None:
        """
        Удаляет связь между объектами.

        Args:
            session (AsyncSession): Асинхронная сессия.
            instance (ModelType): Основной объект.
            relation_name (str): Имя атрибута связи.
            related_instance (Base): Удаляемый связанный объект.

        Raises:
            ValueError: Если связь с указанным именем не существует.
            SQLAlchemyError: При ошибке сохранения.

        Особенности:
            - Для списковых связей удаляет элемент из списка
            - Для скалярных связей устанавливает значение в None
        """
        if not hasattr(instance, relation_name):
            raise ValueError(f"Связь {relation_name} не найдена")

        relation = getattr(instance, relation_name)

        if isinstance(relation, list):
            if related_instance in relation:
                relation.remove(related_instance)
        else:
            if getattr(instance, relation_name) == related_instance:
                setattr(instance, relation_name, None)

        await session.flush()
