from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    """
    Lớp Service cơ sở (Business Logic Layer).
    Chịu trách nhiệm thực thi các quy tắc nghiệp vụ, điều phối transactions,
    và kiểm tra quyền sở hữu / trạng thái trước khi tương tác với Repository.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

