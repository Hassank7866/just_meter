"""Print schema/import counts for verification without exposing registry contents."""
import json
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from .database import get_engine, Base
from . import db_models


def report():
    with Session(get_engine()) as session:
        return {
            "database": get_engine().dialect.name,
            "migration": session.scalar(text("SELECT version_num FROM alembic_version")),
            "counts": {table.name: session.scalar(select(func.count()).select_from(table))
                       for table in Base.metadata.sorted_tables},
            "imports": [{"source": batch.source, "rows": batch.row_count, "sha256": batch.checksum}
                        for batch in session.scalars(select(db_models.ImportBatch))],
        }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
