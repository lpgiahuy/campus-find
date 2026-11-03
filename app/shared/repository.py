from typing import Any, Generic, List, Optional, Tuple, Type, TypeVar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Lớp Repository cơ sở (Data Access Layer) cung cấp các thao tác truy vấn chung.
    Các Repository con kế thừa từ lớp này để tái sử dụng và mở rộng các query phức tạp.
    """

    def __init__(self, db: AsyncSession, model: Type[ModelType]):
        self.db = db
        self.model = model

    async def get_by_id(self, entity_id: Any) -> Optional[ModelType]:
        """Truy vấn một thực thể theo Primary Key (ID)."""
        result = await self.db.execute(select(self.model).where(self.model.id == entity_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ModelType], int]:
        """Lấy danh sách các bản ghi có phân trang kèm tổng số lượng."""
        count_stmt = select(func.count()).select_from(self.model)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = select(self.model).offset(offset).limit(limit)
        items_result = await self.db.execute(stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def create(self, entity: ModelType) -> ModelType:
        """Thêm mới một bản ghi vào DB."""
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Xóa một bản ghi khỏi DB."""
        await self.db.delete(entity)
        await self.db.flush()

