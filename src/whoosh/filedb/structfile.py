# Copyright 2009 Matt Chaput. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY MATT CHAPUT ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL MATT CHAPUT OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of Matt Chaput.

from __future__ import annotations

import types
from array import array
from collections.abc import Callable
from copy import copy
from io import BytesIO
from pickle import dump, load
from struct import calcsize
from typing import Any, BinaryIO

from whoosh.system import (
    _FLOAT_SIZE,
    _INT_SIZE,
    _LONG_SIZE,
    _SHORT_SIZE,
    IS_LITTLE,
    pack_byte,
    pack_float,
    pack_int,
    pack_long,
    pack_sbyte,
    pack_uint,
    pack_uint_le,
    pack_ulong,
    pack_ushort,
    pack_ushort_le,
    unpack_byte,
    unpack_float,
    unpack_int,
    unpack_long,
    unpack_sbyte,
    unpack_uint,
    unpack_uint_le,
    unpack_ulong,
    unpack_ushort,
    unpack_ushort_le,
)
from whoosh.util.varints import decode_signed_varint, read_varint, signed_varint, varint

_SIZEMAP = {typecode: calcsize(typecode) for typecode in "bBiIhHqQf"}
_ORDERMAP = {"little": "<", "big": ">"}

_types = (("sbyte", "b"), ("ushort", "H"), ("int", "i"), ("long", "q"), ("float", "f"))


# Main function


class StructFile:
    """Returns a "structured file" object that wraps the given file object and
    provides numerous additional methods for writing structured data, such as
    "write_varint" and "write_long".
    """

    def __init__(
        self,
        fileobj: BinaryIO,
        name: str | None = None,
        onclose: Callable[[StructFile], None] | None = None,
    ) -> None:
        self.file = fileobj
        self._name = name
        self.onclose = onclose
        self.is_closed = False

        self.is_real = hasattr(fileobj, "fileno")
        if self.is_real:
            self.fileno = fileobj.fileno

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._name!r})"

    def __str__(self) -> str:
        return self._name

    def __enter__(self) -> StructFile:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()

    def __iter__(self) -> Any:
        return iter(self.file)

    def raw_file(self) -> BinaryIO:
        return self.file

    def read(self, *args: Any, **kwargs: Any) -> Any:
        return self.file.read(*args, **kwargs)

    def readline(self, *args: Any, **kwargs: Any) -> Any:
        return self.file.readline(*args, **kwargs)

    def write(self, *args: Any, **kwargs: Any) -> Any:
        return self.file.write(*args, **kwargs)

    def tell(self, *args: Any, **kwargs: Any) -> Any:
        return self.file.tell(*args, **kwargs)

    def seek(self, *args: Any, **kwargs: Any) -> Any:
        return self.file.seek(*args, **kwargs)

    def truncate(self, *args: Any, **kwargs: Any) -> Any:
        return self.file.truncate(*args, **kwargs)

    def flush(self) -> None:
        """Flushes the buffer of the wrapped file. This is a no-op if the
        wrapped file does not have a flush method.
        """

        if hasattr(self.file, "flush"):
            self.file.flush()

    def close(self) -> None:
        """Closes the wrapped file."""

        if self.is_closed:
            raise Exception("This file is already closed")
        if self.onclose:
            self.onclose(self)
        if hasattr(self.file, "close"):
            self.file.close()
        self.is_closed = True

    def subset(self, offset: int, length: int, name: str | None = None) -> StructFile:
        from whoosh.filedb.compound import SubFile

        name = name or self._name
        return StructFile(SubFile(self.file, offset, length), name=name)

    def write_string(self, s: bytes) -> None:
        """Writes a string to the wrapped file. This method writes the length
        of the string first, so you can read the string back without having to
        know how long it was.
        """
        self.write_varint(len(s))
        self.write(s)

    def write_string2(self, s: bytes) -> None:
        self.write(pack_ushort(len(s)) + s)

    def write_string4(self, s: bytes) -> None:
        self.write(pack_int(len(s)) + s)

    def read_string(self) -> bytes:
        """Reads a string from the wrapped file."""
        return self.read(self.read_varint())

    def read_string2(self) -> bytes:
        line = self.read_ushort()
        return self.read(line)

    def read_string4(self) -> bytes:
        line = self.read_int()
        return self.read(line)

    def get_string2(self, pos: int) -> tuple[bytes, int]:
        line = self.get_ushort(pos)
        base = pos + _SHORT_SIZE
        return self.get(base, line), base + line

    def get_string4(self, pos: int) -> tuple[bytes, int]:
        line = self.get_int(pos)
        base = pos + _INT_SIZE
        return self.get(base, line), base + line

    def skip_string(self) -> None:
        line = self.read_varint()
        self.seek(line, 1)

    def write_varint(self, i: int) -> None:
        """Writes a variable-length unsigned integer to the wrapped file."""
        self.write(varint(i))

    def write_svarint(self, i: int) -> None:
        """Writes a variable-length signed integer to the wrapped file."""
        self.write(signed_varint(i))

    def read_varint(self) -> int:
        """Reads a variable-length encoded unsigned integer from the wrapped
        file.
        """
        return read_varint(self.read)

    def read_svarint(self) -> int:
        """Reads a variable-length encoded signed integer from the wrapped
        file.
        """
        return decode_signed_varint(read_varint(self.read))

    def write_tagint(self, i: int) -> None:
        """Writes a sometimes-compressed unsigned integer to the wrapped file.
        This is similar to the varint methods but uses a less compressed but
        faster format.
        """

        # Store numbers 0-253 in one byte. Byte 254 means "an unsigned 16-bit
        # int follows." Byte 255 means "An unsigned 32-bit int follows."
        if i <= 253:
            self.write(chr(i))
        elif i <= 65535:
            self.write("\xfe" + pack_ushort(i))
        else:
            self.write("\xff" + pack_uint(i))

    def read_tagint(self) -> int:
        """Reads a sometimes-compressed unsigned integer from the wrapped file.
        This is similar to the varint methods but uses a less compressed but
        faster format.
        """

        tb = ord(self.read(1))
        if tb == 254:
            return self.read_ushort()
        elif tb == 255:
            return self.read_uint()
        else:
            return tb

    def write_byte(self, n: int) -> None:
        """Writes a single byte to the wrapped file, shortcut for
        ``file.write(chr(n))``.\
        """
        self.write(pack_byte(n))

    def read_byte(self) -> int:
        return ord(self.read(1))

    def write_pickle(self, obj: Any, protocol: int = -1) -> None:
        """Writes a pickled representation of obj to the wrapped file."""
        dump(obj, self.file, protocol)

    def read_pickle(self) -> Any:
        """Reads a pickled object from the wrapped file."""
        return load(self.file)

    def write_sbyte(self, n: int) -> None:
        self.write(pack_sbyte(n))

    def write_int(self, n: int) -> None:
        self.write(pack_int(n))

    def write_uint(self, n: int) -> None:
        self.write(pack_uint(n))

    def write_uint_le(self, n: int) -> None:
        self.write(pack_uint_le(n))

    def write_ushort(self, n: int) -> None:
        self.write(pack_ushort(n))

    def write_ushort_le(self, n: int) -> None:
        self.write(pack_ushort_le(n))

    def write_long(self, n: int) -> None:
        self.write(pack_long(n))

    def write_ulong(self, n: int) -> None:
        self.write(pack_ulong(n))

    def write_float(self, n: float) -> None:
        self.write(pack_float(n))

    def write_array(self, arry: array) -> None:
        if IS_LITTLE:
            arry = copy(arry)
            arry.byteswap()
        if self.is_real:
            arry.tofile(self.file)
        else:
            self.write(arry.tobytes())

    def read_sbyte(self) -> int:
        return unpack_sbyte(self.read(1))[0]

    def read_int(self) -> int:
        return unpack_int(self.read(_INT_SIZE))[0]

    def read_uint(self) -> int:
        return unpack_uint(self.read(_INT_SIZE))[0]

    def read_uint_le(self) -> int:
        return unpack_uint_le(self.read(_INT_SIZE))[0]

    def read_ushort(self) -> int:
        return unpack_ushort(self.read(_SHORT_SIZE))[0]

    def read_ushort_le(self) -> int:
        return unpack_ushort_le(self.read(_SHORT_SIZE))[0]

    def read_long(self) -> int:
        return unpack_long(self.read(_LONG_SIZE))[0]

    def read_ulong(self) -> int:
        return unpack_ulong(self.read(_LONG_SIZE))[0]

    def read_float(self) -> float:
        return unpack_float(self.read(_FLOAT_SIZE))[0]

    def read_array(self, typecode: str, length: int) -> array:
        a = array(typecode)
        if self.is_real:
            a.fromfile(self.file, length)
        else:
            a.frombytes(self.read(length * _SIZEMAP[typecode]))
        if IS_LITTLE:
            a.byteswap()
        return a

    def get(self, position: int, length: int) -> bytes:
        self.seek(position)
        return self.read(length)

    def get_byte(self, position: int) -> int:
        return unpack_byte(self.get(position, 1))[0]

    def get_sbyte(self, position: int) -> int:
        return unpack_sbyte(self.get(position, 1))[0]

    def get_int(self, position: int) -> int:
        return unpack_int(self.get(position, _INT_SIZE))[0]

    def get_uint(self, position: int) -> int:
        return unpack_uint(self.get(position, _INT_SIZE))[0]

    def get_ushort(self, position: int) -> int:
        return unpack_ushort(self.get(position, _SHORT_SIZE))[0]

    def get_long(self, position: int) -> int:
        return unpack_long(self.get(position, _LONG_SIZE))[0]

    def get_ulong(self, position: int) -> int:
        return unpack_ulong(self.get(position, _LONG_SIZE))[0]

    def get_float(self, position: int) -> float:
        return unpack_float(self.get(position, _FLOAT_SIZE))[0]

    def get_array(self, position: int, typecode: str, length: int) -> array:
        self.seek(position)
        return self.read_array(typecode, length)


class BufferFile(StructFile):
    def __init__(
        self,
        buf: bytes | bytearray | memoryview,
        name: str | None = None,
        onclose: Callable[[StructFile], None] | None = None,
    ) -> None:
        self._buf = buf
        self._name = name
        self.file = BytesIO(buf)
        self.onclose = onclose

        self.is_real = False
        self.is_closed = False

    def close(self) -> None:
        """Closes the file and releases the underlying buffer.

        For memoryview-backed buffers (e.g. slices of an mmap in a
        :class:`whoosh.filedb.compound.CompoundStorage`), explicitly releasing
        the memoryview here is what allows the parent mmap to be closed cleanly
        instead of raising ``BufferError`` and leaking a file descriptor. See
        https://github.com/priya-sundaram-dev/whoosh — "too many open files"
        under heavy indexing.
        """
        if self.is_closed:
            raise Exception("This file is already closed")
        if self.onclose:
            self.onclose(self)
        # BytesIO holds a reference to the same buffer; close it first.
        if hasattr(self.file, "close"):
            self.file.close()
        # Release the memoryview so exported pointers no longer block the
        # parent mmap from closing.
        buf = self._buf
        self._buf = None
        if isinstance(buf, memoryview):
            try:
                buf.release()
            except (ValueError, BufferError):
                # Already released, or still exported by a subset view.
                pass
        self.is_closed = True

    def subset(self, position: int, length: int, name: str | None = None) -> BufferFile:
        name = name or self._name
        return BufferFile(self.get(position, length), name=name)

    def get(self, position: int, length: int) -> bytes:
        return bytes(self._buf[position : position + length])

    def get_array(self, position: int, typecode: str, length: int) -> array:
        a = array(typecode)
        a.frombytes(self.get(position, length * _SIZEMAP[typecode]))
        if IS_LITTLE:
            a.byteswap()
        return a


class ChecksumFile(StructFile):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        StructFile.__init__(self, *args, **kwargs)
        self._check = 0
        self._crc32 = __import__("zlib").crc32

    def __iter__(self) -> Any:
        for line in self.file:
            self._check = self._crc32(line, self._check)
            yield line

    def seek(self, *args: Any) -> None:
        raise Exception("Cannot seek on a ChecksumFile")

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        b = self.file.read(*args, **kwargs)
        self._check = self._crc32(b, self._check)
        return b

    def write(self, b: bytes) -> None:
        self._check = self._crc32(b, self._check)
        self.file.write(b)

    def checksum(self) -> int:
        return self._check & 0xFFFFFFFF
