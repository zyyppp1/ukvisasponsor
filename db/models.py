"""数据库表结构(schema),用 SQLAlchemy 的 ORM 方式定义。

ORM(对象关系映射):把"数据库里的表"和"Python 里的类"对应起来。一个类 = 一张表,
一个实例 = 表里的一行。这样我们用 Python 对象读写数据,而不用手拼 SQL 字符串。
"""

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有表模型的基类。SQLAlchemy 用它收集全部表定义。"""


class SponsorRow(Base):
    __tablename__ = "sponsors"

    # 主键(primary key):每行唯一标识,自增整数。
    id: Mapped[int] = mapped_column(primary_key=True)

    # 原始担保方名称(展示给用户看的)。
    organisation_name: Mapped[str] = mapped_column(String)

    # 归一化名。index=True 让数据库为这一列建**索引** —— 按它查找从"全表扫描"变成
    # "索引直达"(和我们内存里那个字典是一回事,只是持久化在数据库里、由数据库维护)。
    normalized_name: Mapped[str] = mapped_column(String, index=True)

    # 其余字段(消歧/展示用)。默认空串,避免 NULL。
    town: Mapped[str] = mapped_column(String, default="")
    county: Mapped[str] = mapped_column(String, default="")
    rating: Mapped[str] = mapped_column(String, default="")
    route: Mapped[str] = mapped_column(String, default="")

    def __repr__(self) -> str:
        return f"<SponsorRow {self.organisation_name!r} ({self.town})>"
