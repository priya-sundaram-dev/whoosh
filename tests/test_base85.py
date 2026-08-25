from whoosh.support import base85
from whoosh.support.base85 import from_base85, to_base85


def test_integer_roundtrip():
    for x in [0, 1, 84, 85, 1000, 2**31, 85**5 - 1]:
        assert from_base85(to_base85(x)) == x

    for x in [0, 1, 2**31, 2**48, 85**10 - 1]:
        assert from_base85(to_base85(x, islong=True)) == x


def test_byte_codec_removed():
    # The Python-2-era byte codec could not run on Python 3 and was dead code;
    # make sure it is not reintroduced without a working implementation.
    assert not hasattr(base85, "b85encode")
    assert not hasattr(base85, "b85decode")
