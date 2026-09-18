"""Tests for the pure-Python soundex helpers in ``whoosh.lang.phonetic``.

These cover the normal coding paths plus the "unencodable input" edge cases
that used to raise (a word with no a-z letters, an empty Arabic word, or an
Arabic word containing characters outside the code map).
"""

from whoosh.lang.phonetic import soundex_ar, soundex_en, soundex_esp


def test_soundex_en_basic():
    assert soundex_en("Robert") == "r01063"
    assert soundex_en("") == ""


def test_soundex_en_no_letters_does_not_raise():
    # Words with no a-z letters (digits, punctuation, non-Latin scripts) used
    # to raise ``TypeError: NoneType + str``. They should code to "".
    assert soundex_en("12345") == ""
    assert soundex_en("...") == ""
    assert soundex_en("\u043f\u0440\u0438\u0432\u0435\u0442") == ""  # Cyrillic


def test_soundex_esp_basic():
    # A word with no Spanish letters falls through to the literal characters.
    assert soundex_esp("123") == "123"
    assert isinstance(soundex_esp("Rodriguez"), str)


def test_soundex_ar_empty_does_not_raise():
    # An empty word used to raise IndexError on ``word[0]``.
    assert soundex_ar("") == "0"


def test_soundex_ar_unmapped_chars_do_not_raise():
    # A word whose characters aren't in the Arabic code map used to raise
    # UnboundLocalError; unmapped characters are now skipped.
    assert soundex_ar("\u0628 x") == "0"


def test_soundex_ar_codes_real_word():
    # A real Arabic word still produces a stable numeric code.
    assert soundex_ar("\u0645\u062d\u0645\u062f") == "053"
