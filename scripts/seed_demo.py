"""Khởi tạo tài khoản Quản trị viên và dữ liệu danh mục, địa điểm mẫu."""
import argparse
from getpass import getpass

from pwdlib import PasswordHash
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Category, Location, User

CATEGORIES = ('Giấy tờ', 'Điện tử', 'Phụ kiện', 'Khác')
LOCATIONS = ('Thư viện', 'Giảng đường', 'Căn tin', 'Khu tự học')


def main():
    parser = argparse.ArgumentParser(description='Khởi tạo Admin, danh mục và địa điểm mẫu')
    parser.add_argument('--admin-email', required=True, help='Email của tài khoản Quản trị viên')
    parser.add_argument('--admin-name', required=True, help='Họ và tên Quản trị viên')
    args = parser.parse_args()
    email = args.admin_email.strip()
    name = args.admin_name.strip()
    if not email or not name:
        parser.error('Email và họ tên Admin không được để trống')
    password = getpass('Mật khẩu Admin (tối thiểu 8 ký tự): ')
    if len(password) < 8:
        parser.error('Mật khẩu Admin phải có ít nhất 8 ký tự')
    if password != getpass('Xác nhận lại mật khẩu Admin: '):
        parser.error('Mật khẩu xác nhận không khớp')

    engine = create_engine(settings.sync_database_url)
    try:
        with Session(engine) as session, session.begin():
            if session.scalar(select(User.id).where(func.lower(User.email) == email.lower())):
                raise ValueError('Email Quản trị viên đã tồn tại; tài khoản không thay đổi')
            session.add(User(email=email, full_name=name, role='ADMIN',
                             password_hash=PasswordHash.recommended().hash(password)))
            for model, names in ((Category, CATEGORIES), (Location, LOCATIONS)):
                for item_name in names:
                    session.execute(insert(model).values(name=item_name).on_conflict_do_nothing())
        print('Đã khởi tạo thành công tài khoản Quản trị viên, danh mục và địa điểm mẫu.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
