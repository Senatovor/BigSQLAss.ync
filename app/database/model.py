from sqlalchemy import Integer, func
from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column, class_mapper
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс таблицы, который наследуется в другие"""
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Перевод названия класса в название таблицы"""
        return cls.__name__.lower() + 's'

    def to_dict(self) -> dict:
        """Универсальный метод для конвертации объекта SQLAlchemy в словарь"""
        columns = class_mapper(self.__class__).columns
        return {column.key: getattr(self, column.key) for column in columns}

    def __repr__(self) -> str:
        """Строковое представление объекта """
        return f"<{self.__class__.__name__}(id={self.id})>"
