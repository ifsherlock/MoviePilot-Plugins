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

        # 最新 V3 通过组合根登记无会话事务执行器；不能把 None 传给模型，
        # 否则 TransferHistory.list_by_page 会在 db.execute 处崩溃。
        try:
            from app.db.uow import run_sync_transaction
        except ImportError:
            run_sync_transaction = None
        if run_sync_transaction is not None:
            return run_sync_transaction(query)

        # 兼容尚未提供 uow 执行器的早期 V3：显式创建并释放一个只读会话。
        try:
            from app.db.session import ScopedSession
        except ImportError as exc:
            raise RuntimeError("MoviePilot V3 未提供可用的同步数据库会话入口") from exc
        session = ScopedSession()
        try:
            return query(session)
        finally:
            session.close()


__all__ = ["TransferHistoryReader"]
