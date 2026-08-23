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
        return self._execute_sync_query(
            lambda session: TransferHistory.list_by_page(
                session,
                page=page,
                count=count,
                status=status,
            )
        )


__all__ = ["TransferHistoryReader"]
