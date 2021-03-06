"""
    Initialization
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
from .ygate import \
    Ygate, compress_position, format_position, \
    decode_ascii, is_internet, b91_encode, b91_decode, cnv_ch, mic_e_decode, \
    print_wrap
