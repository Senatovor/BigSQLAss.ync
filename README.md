# Быстрый асинхронный старт с SQLAlchemy 🌪️

---

Данный мини-проект рассчитан на быстрый старт для работы с базой данных в асинхронном режиме с возможностью его расширить под ваши нужды.  
В проекте следующий стэк:  
1. SQLAlchemy
2. Pydantic
3. Alembic

И перед тем, как вы ознакомитесь с проектом, хочу поблагодарить [Yakovenko Oleksii](https://github.com/Yakvenalex) за его статьи на [Хабре](https://habr.com/ru/users/yakvenalex/).  
Благодаря его статьям и вышел данный проект)

---

## ️📂 Обзор структуры проекта  
```text
📦 project-root/
├── 📂 app/                  # Основное приложение
│   ├── 📂 database/         # Основные файлы для работы с бд
│   │   ├── model.py         # Базовая модель SQLAlchemy
│   │   ├── service.py       # Базовый сервис с универсальными методами
│   │   └── session.py       # Управление сессиями
│   ├── 📂 enums/            # Папка для хранения ваших Enum моделей
│   ├── 📂 models/           # Папка для хранения ваших SQLAlchemy моделей
│   ├── 📂 schemes/          # Схемы Pydantic
│   ├── 📂 services/         # Папка ваших сервисов
│   ├── config.py            # Конфигурация приложения
│   └── main.py              # Точка входа
│
├── 📂 migration/            # Миграции базы данных
│   ├── 📂 versions/         # Файлы миграций
│   └── env.py               # Настройки Alembic
│
├── 📜 .env                  # Переменные окружения
├── 📜 .gitignore            # Игнорируемые файлы
├── 📜 .alembic.ini          # Конфиг Alembic
├── 📜 .requirements.txt     # Зависимости
└── 📖 README.md             # Документация
```

## 🚀 Быстрый старт за 5 шагов

### 1. Установка зависимостей
```bash
pip install -r .requirements.txt
```
### 2. Настройка окружения
Заполните файл .env по типу:
```text
DB_HOST=""
DB_PORT=""
DB_NAME=""
DB_USER=""
DB_PASSWORD=""
```
### 3. Создание моделей
Добавьте ORM-модели в `app/models` и импортируйте её в `migration/env.py`.  
Если что, модели выглядят так:
```python
class SetupModel(Base):
    """Пример одного из ваших моделей"""
    title: Mapped[str] = mapped_column(String(20), nullable=False)
    number: Mapped[SetupEnum] = mapped_column(default=SetupEnum.ONE, server_default=text("'ONE'"))
```
А так выглядит добавление в env:
```python
from app.database.model import Base
from app.database.session import SQL_DATABASE_URL
from app.models.setup_model import SetupModel      # ДОБАВЛЯЕМ МОДЕЛЬ

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", SQL_DATABASE_URL)
```
### 4. Генерация миграций
```bash
alembic revision --autogenerate -m "init"
```
### 5. Применение миграций
```bash
alembic upgrade head
```
### МОЛОДЦЫ! ТЕПЕРЬ МОЖНО ПИСАТЬ КОД В main.py!

## 🔍 Пример работы и небольшие пояснения

### 1. Создаем Enum модель для перечисления
```python
import enum


class SetupEnum(str, enum.Enum):
    """
    Пример одного из вашего обьектов Enum.
    Для примера, Enum вы можете использовать для создания типов полей таблицы
    """
    ONE = 'один'
    TWO = 'два'
    THREE = 'три'
```
### 2. Создаем модель ORM с перечислением Enum для создания типа в SQL
```python
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.model import Base
from app.enums.setup_enum import SetupEnum


class SetupModel(Base):
    """Пример одного из ваших моделей"""
    title: Mapped[str] = mapped_column(String(20), nullable=False)
    number: Mapped[SetupEnum] = mapped_column(default=SetupEnum.ONE, server_default=text("'ONE'"))
```
**Не забываем делать миграции! А также добавлять новые модели в `migration/env.py:`**
```python
from app.database.model import Base
from app.database.session import SQL_DATABASE_URL
from app.models.setup_model import SetupModel      # ДОБАВЛЯЕМ МОДЕЛЬ

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", SQL_DATABASE_URL)
```
### 3. Заготавливаем модель Pydantic для работы
```python
from pydantic import BaseModel, ConfigDict
from app.enums.setup_enum import SetupEnum


class SetupScheme(BaseModel):
    """Пример одного из ваших моделей Pydantic для фильтров, значений обьектов и тд"""
    title: str
    number: SetupEnum

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

```
### 4. Создаем сервис для нашей модели
```python
from app.models.setup_model import SetupModel
from app.database.service import BaseService


class SetupService(BaseService[SetupModel]):
    """Пример одного из ваших сервисов"""
    model = SetupModel
```
### 5. Пример работы
```python
from app.database.session import session_manager
from app.services.setup_service import SetupService
from app.enums.setup_enum import SetupEnum
from app.schemes.setup_scheme import SetupScheme
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import create_model
import asyncio


@session_manager.connection(commit=True)
async def test(title: str, number: SetupEnum, session: AsyncSession):
    """Пример работы"""

    NewObject = create_model(
        'NewObject',
        title=(str, ...),
        number=(SetupEnum, ...)
    )

    new_object = await SetupService.add(session, NewObject(title=title, number=number))

    print('Обьект:\n'
          f'{SetupScheme.model_validate(new_object).model_dump()}\n'
          'Был создан!')

asyncio.run(test('Привет Мир!', 'один'))
```