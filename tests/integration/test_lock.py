from app.db.locks import release_lock, try_acquire_lock
from app.db.session import Database


def test_lock(tmp_path):
    db = Database(f"sqlite:///{tmp_path}/x.db")

    try:
        db.init()
        assert try_acquire_lock(db)
        assert not try_acquire_lock(db)

        release_lock(db)
        assert try_acquire_lock(db)
        release_lock(db)
    finally:
        db.close()
