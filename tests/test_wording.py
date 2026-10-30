from app.wording import amount_to_pay


def test_amount_is_the_total_not_the_first_price():
    text = "Wireless Mouse Rs 799 USB-C Cable Rs 700 Total Rs 1,499 Invoice amount Rs 1,499.00"
    assert amount_to_pay(text) == "Rs 1,499"


def test_amount_falls_back_to_the_first_price_or_nothing():
    assert amount_to_pay("Only item Rs 250") == "Rs 250"
    assert amount_to_pay("no prices here") == ""
