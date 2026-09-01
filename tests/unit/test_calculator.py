from app.portfolio.calculator import gbx_to_gbp, usd_to_gbp, weights
from app.portfolio.models import PortfolioState, Position


def test_gbx_conversion():
    assert gbx_to_gbp(100) == 1


def test_usd_conversion():
    assert usd_to_gbp(100, 0.75) == 75


def test_weights_and_groups():
    s = PortfolioState(
        1000, 100, [Position("VRT", 1, 200), Position("IREN", 1, 100), Position("UBER", 1, 600)]
    )
    w = weights(s, {"DATA_CENTRES": ["VRT", "IREN"]})
    assert (
        abs(w["CASH"] - 0.1) < 1e-9
        and abs(w["DATA_CENTRES"] - 0.3) < 1e-9
        and abs(w["UBER"] - 0.6) < 1e-9
    )
