import base64
import hashlib
import functools
from typing import Union, Tuple, Optional
from ctypes import (
    byref, c_byte, c_int, c_uint, c_char_p, c_size_t, c_void_p, create_string_buffer,
    CFUNCTYPE, POINTER, cast
)



def get_ecdh(priv: bytes, pub: bytes) -> bytes:
    pt = ECPubkey(pub) * string_to_number(priv)
    return sha256(pt.get_public_key_bytes())


def string_to_number(b: bytes) -> int:
    return int.from_bytes(b, byteorder='big', signed=False)