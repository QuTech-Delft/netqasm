import pytest

from netqasm.util.string import group_by_word, is_float, is_number, is_variable_name


@pytest.mark.parametrize(
    "string, seperator, brackets, expected",
    [
        ("hello", " ", "()", ["hello"]),
        ("hello world", " ", "()", ["hello", "world"]),
        ("hello world", "o", "()", ["hell", " w", "rld"]),
        ("(hello world)", " ", "()", ["(hello world)"]),
        ("(hello world)", " ", "[]", ["(hello", "world)"]),
        ("hello (world)", " ", "()", ["hello", "(world)"]),
        ("hello (wo(rld)", " ", "()", ["hello", "(wo(rld)"]),
        ("hello (wo)rld)", " ", "()", ["hello", "(wo)rld)"]),
        ("hello (wo rld)", " ", "()", ["hello", "(wo rld)"]),
        ("hello wo rld", " ", "()", ["hello", "wo", "rld"]),
        ("hello (wo rld)", " ", None, ["hello", "(wo", "rld)"]),
    ],
)
def test_group_by_word(string, seperator, brackets, expected):
    assert expected == group_by_word(string, seperator=seperator, brackets=brackets)


@pytest.mark.parametrize(
    "string, seperator, brackets, error",
    [
        ("", " ", "(){}", ValueError),  # More than to brackets
        ("", " ", "((", ValueError),  # Non-unique brackets
        ("", "(", "()", ValueError),  # Seperator in brackets
        ("", "", "()", ValueError),  # No character seperator
        ("", None, "()", TypeError),  # Not valid seperator type
        ("", " ", ["(", ")"], TypeError),  # Not valid brackets type
        ("(hello", " ", "()", ValueError),  # No closing bracket
        ("(hello) (world", " ", "()", ValueError),  # No closing bracket
    ],
)
def test_group_by_word_errors(string, seperator, brackets, error):
    with pytest.raises(error):
        group_by_word(string, seperator=seperator, brackets=brackets)


@pytest.mark.parametrize(
    "variable, expected",
    [
        ("name", True),
        ("var_name", True),
        ("var_name12", True),
        ("Var_nAme12", True),
        ("var name", False),
        ("1name", False),
        ("var-name", False),
        ("var_name!", False),
    ],
)
def test_is_variable_name(variable, expected):
    assert is_variable_name(variable) == expected


@pytest.mark.parametrize(
    "number, expected",
    [
        ("1", True),
        ("-1", True),
        ("0123", True),
        ("0123456789", True),
        ("321891204189", True),
        ("-321891204189", True),
        ("a12", False),
        ("o", False),
        ("O", False),
        ("!", False),
    ],
)
def test_is_number(number, expected):
    assert is_number(number) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1.", True),
        (".1", True),
        (".", False),
        ("1", False),
        ("01.23", True),
        ("01234.56789", True),
        ("32.1891204189", True),
        ("a12.", False),
        (".a12.", False),
        ("o.", False),
        ("O.", False),
        ("!.", False),
        (".o", False),
        (".O", False),
        (".!", False),
    ],
)
def test_is_float(value, expected):
    assert is_float(value) == expected
