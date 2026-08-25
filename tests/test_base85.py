import random

from whoosh.codec.whoosh2 import sortable_int_to_text
from whoosh.support.base85 import b85chars, from_base85, to_base85

# 85 ** 5 and 85 ** 10 -- one past the largest value each width can hold.
INT_LIMIT = 85**5
LONG_LIMIT = 85**10


def test_roundtrip_int():
    for x in (0, 1, 84, 85, 86, 7225, 123456, INT_LIMIT - 1):
        assert from_base85(to_base85(x)) == x


def test_roundtrip_long():
    for x in (0, 1, INT_LIMIT, INT_LIMIT + 1, LONG_LIMIT - 1):
        assert from_base85(to_base85(x, True)) == x


def test_fixed_width():
    # Fixed width is what makes the encoding sortable: a shorter string must
    # never compare less than a longer one just for being shorter.
    assert all(len(to_base85(x)) == 5 for x in (0, 1, INT_LIMIT - 1))
    assert all(len(to_base85(x, True)) == 10 for x in (0, 1, LONG_LIMIT - 1))


def test_alphabet_is_in_ascii_order():
    # The whole point of the custom alphabet -- the stdlib base64.b85 alphabet
    # is not ordered, so it cannot be substituted here.
    assert list(b85chars) == sorted(b85chars)
    assert len(set(b85chars)) == 85


def test_encoding_preserves_order():
    numbers = sorted(random.sample(range(INT_LIMIT), 200))
    encoded = [to_base85(x) for x in numbers]
    assert encoded == sorted(encoded)


def test_encoding_preserves_order_long():
    # randrange rather than sample: range(85 ** 10) is too large for
    # random.sample to take a len() of.
    numbers = sorted(random.randrange(LONG_LIMIT) for _ in range(200))
    encoded = [to_base85(x, True) for x in numbers]
    assert encoded == sorted(encoded)


def test_sortable_int_to_text_preserves_order():
    # The property whoosh2 actually depends on, exercised through its own API.
    numbers = sorted(random.sample(range(INT_LIMIT), 100))
    encoded = [sortable_int_to_text(x) for x in numbers]
    assert encoded == sorted(encoded)
