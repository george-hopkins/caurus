import crcmod.predefined
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.hmac import HMAC
from cryptography.hazmat.primitives import ciphers

_VERSION = 3

STYLE_BOLD = 'S'
STYLE_BLACK = 'K'
STYLE_BLUE = 'B'
STYLE_GREEN = 'G'
STYLE_RED = 'R'

_STYLES = [
    STYLE_BOLD,
    STYLE_BLACK,
    STYLE_BLUE,
    STYLE_GREEN,
    STYLE_RED,
]

_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ =&%'

_ESCAPED = {
    33: '!',
    35: '#',
    36: '$',
    37: '%',
    38: '&',
    39: '\'',
    40: '(',
    41: ')',
    42: '*',
    43: '+',
    44: ',',
    45: '-',
    46: '.',
    47: '/',
    58: ':',
    60: '<',
    61: '=',
    62: '>',
    63: '?',
    64: '@',
    95: '_',
    123: '{',
    125: '}',
    132: '\u2026',
    163: '\u00a3',
    164: '\u20ac',
    167: '\u00a7',
    170: '\u00aa',
    171: '\u00ab',
    186: '\u00ba',
    187: '\u00bb',
    188: '\u0152',
    190: '\u0178',
    192: '\u00c0',
    194: '\u00c2',
    196: '\u00c4',
    199: '\u00c7',
    200: '\u00c8',
    201: '\u00c9',
    202: '\u00ca',
    203: '\u00cb',
    204: '\u00cc',
    206: '\u00ce',
    207: '\u00cf',
    210: '\u00d2',
    211: '\u00d3',
    212: '\u00d4',
    214: '\u00d6',
    217: '\u00d9',
    219: '\u00db',
    220: '\u00dc',
    223: '\u00df',
}

_UNESCAPED = {v: k for k, v in _ESCAPED.items()}

_ALIGNMENT = [
    ([0, 0, 0], 8),
    ([0, 3, 0], 8),
    ([0, 0, 3, 0, 3, 0], 8),
    ([0, 0, 0], 9),
    ([0, 0, 0, 0, 0], 222),
    ([0, 0], 9),
    ([0, 0, 0], 9),
    ([0, 0, 3, 0], 9),
    ([0, 3, 0], 9),
    ([0, 3, 0, 0], 9),
    ([0, 0, 0], 9),
    ([0, 0], 225),
    ([0, 0], 9),
    ([0, 0, 0], 9),
    ([0, 0, 3, 0, 0], 8),
    ([0, 3, 0], 8),
    ([3, 0, 3], 0),
]


_CODE_SHUFFLE = {
    6: [5, 4, 3, 1, 2, 0],
    7: [5, 4, 3, 1, 6, 0, 2],
}

_CODE_DESHUFFLE = {
    6: [5, 3, 4, 2, 1, 0],
    7: [5, 3, 6, 2, 1, 0, 4],
}

_crc24 = crcmod.predefined.mkCrcFun('crc-24')


def _random_bytes(size, context):
    # to be replaced by secret.token_bytes()
    return bytes([context.random.getrandbits(8) for _ in range(size)])


def _hmac(key, message, context):
    hmac = HMAC(key, SHA256(), context.crypto)
    hmac.update(message)
    return hmac.finalize()


def _derive(key, id, salt, n, context):
    data = b'\0\0\0\x01' + id + b'\0cronto-v3\0' + salt + (n * 8).to_bytes(4, 'big')
    return _hmac(key, data, context)[:n]


def _aes_ctr_encrypt(key, message, context):
    nonce = context.random.getrandbits(128).to_bytes(16, 'big')
    encryptor = ciphers.Cipher(ciphers.algorithms.AES(key), ciphers.modes.CTR(nonce), context.crypto).encryptor()
    return nonce + encryptor.update(message) + encryptor.finalize()


def _escape(string, alphabet, escaped):
    result = ''
    for char in string:
        if char in escaped:
            result += '%{:02X}'.format(escaped[char])
        elif char in alphabet:
            result += char
    return result


def _pack_string(string, alphabet, n):
    result = b''
    symbol_bits = len(bin(len(alphabet) ** n)) - 2
    symbol_bytes = (symbol_bits + 7) // 8
    for i in range(0, len(string), n):
        symbol = 0
        for j in range(n):
            symbol *= len(alphabet)
            if i + j < len(string):
                symbol += alphabet.index(string[i + j])
        result += symbol.to_bytes(symbol_bytes, 'big')
    return result


def _pack_pad_string(string, alphabet, n, padding, length):
    result = b''
    symbol_bits = len(bin(len(alphabet) ** n)) - 2
    symbol_bytes = (symbol_bits + 7) // 8
    if length % symbol_bytes:
        raise Exception('Invalid length')
    padding_index = alphabet.index(padding)
    for i in range(length // symbol_bytes):
        symbol = 0
        for j in range(n):
            symbol *= len(alphabet)
            if i * n + j < len(string):
                symbol += alphabet.index(string[i * n + j])
            else:
                symbol += padding_index
        result += symbol.to_bytes(symbol_bytes, 'big')
    return result
