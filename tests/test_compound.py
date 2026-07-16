import os

import pytest

from whoosh.filedb.compound import CompoundStorage
from whoosh.filedb.filestore import RamStorage
from whoosh.util.testing import TempStorage


def _test_simple_compound(st):
    alist = [1, 2, 3, 5, -5, -4, -3, -2]
    blist = [1, 12, 67, 8, 2, 1023]
    clist = [100, -100, 200, -200]

    with st.create_file("a") as af:
        for x in alist:
            af.write_int(x)
    with st.create_file("b") as bf:
        for x in blist:
            bf.write_varint(x)
    with st.create_file("c") as cf:
        for x in clist:
            cf.write_int(x)

    f = st.create_file("f")
    CompoundStorage.assemble(f, st, ["a", "b", "c"])

    f = CompoundStorage(st.open_file("f"))
    with f.open_file("a") as af:
        for x in alist:
            assert x == af.read_int()
        assert af.read() == b""

    with f.open_file("b") as bf:
        for x in blist:
            assert x == bf.read_varint()
        assert bf.read() == b""

    with f.open_file("c") as cf:
        for x in clist:
            assert x == cf.read_int()
        assert cf.read() == b""


def test_simple_compound_mmap():
    with TempStorage("compound") as st:
        assert st.supports_mmap
        _test_simple_compound(st)


def test_simple_compound_nomap():
    st = RamStorage()
    _test_simple_compound(st)


def _make_compound(st):
    with st.create_file("a") as af:
        af.write(b"alfa")
    with st.create_file("b") as bf:
        bf.write(b"bravo")
    CompoundStorage.assemble(st.create_file("f"), st, ["a", "b"])


def test_unclosed_mmap_does_not_error():
    # Closing a CompoundStorage while a memory-mapped subfile is still open
    # must not raise BufferError.
    with TempStorage("unclosed") as st:
        assert st.supports_mmap
        _make_compound(st)
        cs = CompoundStorage(st.open_file("f"))
        sub = cs.open_file("a")  # holds a live memoryview into the mmap
        assert sub.read() == b"alfa"
        # Do not close ``sub`` first; closing the storage must still succeed.
        cs.close()
        assert cs.is_closed


def test_bufferfile_close_releases_memoryview():
    with TempStorage("bufclose") as st:
        assert st.supports_mmap
        _make_compound(st)
        cs = CompoundStorage(st.open_file("f"))
        sub = cs.open_file("a")
        assert sub.read() == b"alfa"
        sub.close()
        assert sub._buf is None
        cs.close()


def test_compound_close_does_not_leak_fds():
    # Regression: previously, closing a CompoundStorage whose subfile views
    # were still alive leaked one file descriptor per close ("too many open
    # files" on long-running servers). See structfile.BufferFile.close.
    import gc

    fd_dir = "/proc/self/fd"
    if not os.path.isdir(fd_dir):
        pytest.skip("no /proc/self/fd on this platform")

    with TempStorage("fdleak") as st:
        if not st.supports_mmap:
            pytest.skip("mmap not supported")
        _make_compound(st)

        gc.collect()
        base = len(os.listdir(fd_dir))
        for _ in range(25):
            cs = CompoundStorage(st.open_file("f"))
            sub = cs.open_file("a")
            del sub
            cs.close()
        gc.collect()
        delta = len(os.listdir(fd_dir)) - base
        assert delta <= 1, f"leaked {delta} file descriptors"
