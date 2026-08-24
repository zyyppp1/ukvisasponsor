"""数据库连接:engine(连接池)、session(会话)、建表。

- DATABASE_URL:连接串,格式 postgresql+psycopg://用户:密码@主机:端口/库名。
  默认连我们 Docker 里那个本地 Postgres;上线时用环境变量覆盖成云上的库。
- engine:SQLAlchemy 的连接入口(内部维护连接池)。
- SessionLocal:开一次"会话"来读写数据(每次操作用一个 session)。
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:devpass@localhost:5433/ukvisasponsor",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """按 models.py 里的定义,在数据库里建好还不存在的表(和索引)。"""
    Base.metadata.create_all(engine)
