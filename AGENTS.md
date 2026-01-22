# AGENTS.md

This file contains guidelines for agentic coding assistants working in the case_auto_hub repository.

## Build / Lint / Test Commands

### Running the Application
- **Development mode**: `python3 run.py` (runs uvicorn with reload on 127.0.0.1:5050)
- **Production mode**: `gunicorn -c gunicorn_conf.py main:hub`
- **Docker**: `docker-compose up --build` (includes MySQL, Redis, and app services)

### Testing
- **Run all tests**: `pytest` (pytest 8.4.1 available)
- **Run single test**: `pytest path/to/test_file.py::test_function_name`
- **Run with coverage**: `pytest --cov=.`
- **Note**: No dedicated test directory found - tests appear to be integrated within controller files

### Dependencies
- **Install**: `pip3 install -r requirment.txt` (note the typo in filename - preserved)
- **Python version**: 3.11.6 (verified)
- **Key dependencies**: FastAPI, SQLAlchemy, aiomysql, Redis, APScheduler, Playwright, Loguru

## Code Style Guidelines

### File Headers
Every Python file should include:
```python
#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : YYYY/M/D
# @Author : cyq
# @File : filename
# @Software: PyCharm
# @Desc:
```

### Import Organization
1. Standard library imports
2. Third-party imports
3. Local application imports (`from app.*`, `from common.*`, `from utils.*`, `from enums.*`)

Example:
```python
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.mapper import Mapper
from utils import log
from enums import BaseEnum
```

### Naming Conventions
- **Classes**: PascalCase (`TestRunner`, `HttpxClient`)
- **Functions/Methods**: snake_case (`get_user`, `save_case`)
- **Variables**: snake_case (`user_id`, `api_response`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_LENGTH`, `DEFAULT_HEADERS`)
- **Private methods**: underscore prefix (`_internal_method`)
- **Database tables**: SQLAlchemy models in PascalCase
- **API routes**: lowercase with underscores (`/hub/cases/insert`)

### Type Hints
- Use type hints for all function signatures
- Import from `typing` module: `List`, `Dict`, `Optional`, `Any`, `TypeVar`, `Generic`
- Use union types with `|` operator: `str | None`
- Use `TypeVar` for generic types: `M = TypeVar('M', bound=BaseModel)`

### Async/Await Patterns
- Database operations use async/await with SQLAlchemy
- HTTP clients use async/await with httpx
- Use `AsyncSession` for database sessions
- All I/O operations should be async

```python
async def get_user(user_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
```

### Error Handling
- Define custom exceptions in `app/exception/__init__.py`
- Inherit from `BaseError` for HTTP errors
- Use `ValueError` for parameter validation
- Use `Exception` for runtime errors
- Log errors with `log.error()`

```python
class CustomError(BaseError):
    def __init__(self, message: str):
        super().__init__(message)
    
    def add_raise(self):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"code": 1, "data": None, "msg": self.message}
        )
```

### Database Models
- Inherit from `BaseModel` (defined in `app/model/basic.py`)
- Use SQLAlchemy ORM with async support
- All models have: `id`, `uid`, `create_time`, `update_time`, `creator`, `creatorName`, `updater`, `updaterName`
- Use `to_dict(exclude=...)` method for serialization

```python
from app.model.basic import BaseModel
from sqlalchemy import Column, INTEGER, String

class MyModel(BaseModel):
    __tablename__ = "my_table"
    name = Column(String(50))
    value = Column(INTEGER)
```

### Mappers (Data Access Layer)
- Inherit from `Mapper[M]` generic base class
- Set `__model__` class variable to the model type
- Use provided CRUD methods: `save`, `get_by_id`, `update`, `page_query`
- Session management is handled by base class

```python
class MyMapper(Mapper[MyModel]):
    __model__ = MyModel
```

### Pydantic Schemas
- Inherit from `BaseModel` for request/response validation
- Use `Field` for validation and description
- Define separate schemas for create/update operations
- Use `model_dump(exclude_unset=True)` for updates

```python
from pydantic import BaseModel, Field

class CreateSchema(BaseModel):
    name: str = Field(..., description="Name")
    value: Optional[int] = Field(None)

class UpdateSchema(BaseModel):
    id: int
    name: Optional[str] = None
```

### API Controllers
- Use `APIRouter` with prefix and tags
- Dependency injection for authentication: `user: User = Depends(Authentication())`
- Use `Response.success(data)` and `Response.error(msg)` for responses
- Log incoming data with `log.info()`

```python
from fastapi import APIRouter, Depends
from app.response import Response

router = APIRouter(prefix="/endpoint", tags=['Tag'])

@router.post("/action")
async def action(data: CreateSchema, user: User = Depends(Authentication())):
    result = await MyMapper.save(creator_user=user, **data.model_dump())
    return Response.success(result)
```

### Logging
- Use `from utils import log` (MyLoguru instance)
- Levels: `log.debug()`, `log.info()`, `log.warning()`, `log.error()`
- Log important operations and errors
- Logs are written to `logs/` directory with rotation

### Enums
- Inherit from `BaseEnum` (extends `IntEnum`) for integer enums
- Provide `enum(value)`, `getValue(name)`, `names()`, `values()` class methods
- Define in `enums/` directory

```python
from enums._basic import BaseEnum

class MyEnum(BaseEnum):
    VALUE_1 = 1
    VALUE_2 = 2
```

### Configuration
- Import from `config` module: `from config import Config`
- Access config values as attributes: `Config.SERVER_HOST`
- Configuration classes: `BaseConfig`, `LocalConfig`

### Utility Classes
- `Tools`: Common utility methods
- `GenerateTools`: UID generation, timestamp formatting
- `VariableTrans`: Variable substitution with `{{var}}` pattern
- `JsonExtract`: JSON path extraction using jmespath

### WebSocket Communication
- Use `UIStarter` or `APIStarter` for WebSocket messaging
- Call `await starter.send(message)` to send messages to clients
- Events: `"api_message"`, `"ui_message"`

## Project Structure

```
case_auto_hub/
├── app/
│   ├── controller/       # FastAPI route handlers
│   ├── mapper/          # Data access layer
│   ├── model/           # SQLAlchemy models
│   ├── schema/          # Pydantic schemas
│   ├── exception/       # Custom exceptions
│   ├── response/        # Response utilities
│   └── middware/        # Middleware
├── common/              # Shared utilities
├── enums/               # Enumerations
├── interface/           # API automation logic
├── play/                # UI automation logic
├── utils/               # Utility functions
├── config.py            # Configuration
├── main.py              # FastAPI app factory
└── run.py               # Development server entry point
```

## Important Notes

- The project uses FastAPI with async patterns
- MySQL with aiomysql for async database operations
- Redis for caching and job storage
- APScheduler for scheduled tasks
- Playwright for UI automation
- Loguru for logging with custom MyLoguru wrapper
- No formal linting/formatting configured - maintain consistency with existing code
- The dependency file is named `requirment.txt` (typo preserved)
- Python 3.11.6 is the verified version
- Docker setup includes MySQL 8.0 and Redis 6.0 services
- Application runs on port 5050 by default