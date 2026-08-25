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
        def query(session: Any) -> List[Any]:
            return TransferHistory.list_by_page(
                session,
                page=page,
                count=count,
                status=status,
            )

        if self._db is not None:
            return query(self._db)

        # 后台刷新线程没有请求级 Session，必须显式创建并释放只读会话；
        # 不能依赖全局事务 runner，也不能把 None 传给模型。
        try:
            from app.db.session import SessionFactory
        except ImportError as exc:
            raise RuntimeError("MoviePilot V3 未提供可用的同步数据库会话入口") from exc
        session = SessionFactory()
        try:
            return query(session)
        finally:
            session.close()


__all__ = ["TransferHistoryReader"]
