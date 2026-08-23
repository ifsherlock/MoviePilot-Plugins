from __future__ import annotations

from typing import Any, List, Optional

from app.db.models.transferhistory import TransferHistory
from app.db.oper.transferhistory import TransferHistoryOper


class TransferHistoryReader(TransferHistoryOper):
    """为插件提供带宿主数据库会话的只读整理历史分页查询。"""

    def list_by_page(
        self,
        *,
        page: int = 1,
        count: int = 30,
        status: Optional[bool] = None,
    ) -> List[Any]:
        # V3 的 DbOper 只保留同步写事务执行器；模型的 db_query 装饰器会在
        # 未传入会话时创建并释放独立同步会话，适合本地资源后台刷新线程。
        return TransferHistory.list_by_page(
            self._db,
            page=page,
            count=count,
            status=status,
        )


__all__ = ["TransferHistoryReader"]
