from app.signals.sizing import buy_size, round_tranche, trim_size


def test_rounding():
    assert round_tranche(103.72) == 100


def test_buy_size_capped():
    assert buy_size(10000, 4000, False, 0.015) <= 150


def test_trim_size_capped():
    assert trim_size(10000, 4000, True, 0.015) <= 150
