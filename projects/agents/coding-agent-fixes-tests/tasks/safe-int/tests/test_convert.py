from forms.convert import safe_int


def test_good():
    assert safe_int("12") == 12
    assert safe_int(" -7 ") == -7


def test_bad_inputs_use_default():
    assert safe_int("abc") == 0
    assert safe_int("3.5", default=-1) == -1
    assert safe_int(None, default=5) == 5
    assert safe_int("") == 0
