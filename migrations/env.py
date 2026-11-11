from alembic import context
from sqlalchemy import pool

from backend.database import get_engine, Base
from backend import db_models

if context.is_offline_mode():
    import os
    context.configure(url=os.environ["DATABASE_URL"], target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
