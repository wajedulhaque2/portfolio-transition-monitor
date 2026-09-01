from app.signals.safety import abnormal_drop, cash_purchase_allowed


def test_abnormal():
    assert abnormal_drop(-0.18, 0.15)


def test_cash_floor():
    assert not cash_purchase_allowed(140, 50, 100)
    assert cash_purchase_allowed(250, 100, 100)
