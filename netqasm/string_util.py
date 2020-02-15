ALPHA_LOWER = "abcdefghijklmnopqrstuvwxyz"
ALPHA_CAPITAL = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ALPHA_ALL = ALPHA_LOWER + ALPHA_CAPITAL
NUM = "0123456789"
ALPHA_NUM = ALPHA_ALL + NUM


def group_by_word(line, seperator=' ', brackets=None):
    """Groups a string by words and contents within brackets"""
    line = line.strip()
    line += seperator  # This makes it easer to find the last word
    _assert_valid_seperator(seperator)
    if brackets is not None:
        _assert_valid_brackets(seperator, brackets)
        start_bracket, end_bracket = brackets
    words = []
    while len(line) > 0:
        if brackets is not None and line[0] == start_bracket:
            end_string = f"{end_bracket}{seperator}"
        else:
            end_string = seperator
        # Find the closing string
        end = line.find(end_string)
        if end == -1:
            raise ValueError("Not a valid string, could not find a closing bracket")
        word = line[len(end_string) - 1:end]
        words.append(word)
        line = line[end + len(end_string):]
    return words


def is_variable_name(variable):
    if not isinstance(variable, str):
        return False  # Should be a string
    if variable[0] not in ALPHA_ALL:
        return False  # Should start with a letter
    if not set(variable) < set(ALPHA_NUM + '_'):
        return False  # Should only contain letters, digits and underscore
    return True


def is_number(number):
    return set(number) <= set(NUM)


def _assert_valid_seperator(seperator):
    if not isinstance(seperator, str):
        raise TypeError("seperator should be a string")
    if len(seperator) == 0:
        raise ValueError("seperator should contain at least one character")


def _assert_valid_brackets(seperator, brackets):
    if not isinstance(brackets, str):
        raise TypeError("brackets should be a string")
    if not (len(brackets) == 2 and len(set(brackets)) == 2):
        raise ValueError("brackets should be two unique characters")
    if seperator in brackets:
        raise ValueError("seperator should not be part of brackets")
