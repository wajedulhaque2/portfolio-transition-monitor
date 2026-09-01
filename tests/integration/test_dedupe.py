from app.db.session import Database
from app.jobs.scan import Recommendation, record_alert, should_notify


def test_dedupe_persists(tmp_path):
    url = f"sqlite:///{tmp_path}/x.db"
    db = Database(url)
    db2 = Database(url)

    try:
        db.init()
        recommendation = Recommendation(
            "ROTATE",
            "GOOGL",
            "AAPL",
            100,
            90,
            "STRONG",
            "x",
        )

        assert should_notify(db, recommendation, 12)
        record_alert(db, recommendation, "x")
        assert not should_notify(db2, recommendation, 12)
    finally:
        db2.close()
        db.close()
