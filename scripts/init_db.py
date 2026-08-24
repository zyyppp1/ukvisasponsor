"""建表脚本:在数据库里创建 sponsors 表(及其索引)。

    python scripts/init_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import DATABASE_URL, init_db

if __name__ == "__main__":
    print(f"连接:{DATABASE_URL}")
    init_db()
    print("已创建表 sponsors(及 normalized_name 索引)。")
