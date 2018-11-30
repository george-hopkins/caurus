import reedsolo
import caurus
from bitstring import Bits, BitArray


_BLOCK_SIZE = 142
_ECC_SYMBOLS = 50


def _shuffle_code(code, length):
    shuffle = caurus._CODE_SHUFFLE[length]
    digits = [0] * len(shuffle)
    for s in shuffle[::-1]:
        digits[s] = code % 10
        code //= 10
    return ''.join(map(str, digits))


def _deshuffle_code(code):
    deshuffle = caurus._CODE_DESHUFFLE[len(code)]
    result = 0
    for i, c in enumerate(code):
        result += int(c) * 10 ** (len(code) - deshuffle[i] - 1)
    return result


def _code_c(code, a, b_shift, length):
    max = 1000000 if length == 6 else 10000000
    a = int.from_bytes(a, 'big')
    return (code - a) % max % (1 << b_shift)


def _code(a, b, b_shift, c, length):
    max = 1000000 if length == 6 else 10000000
    a = int.from_bytes(a, 'big') % max
    b_mod = (max - (1 << b_shift)) // (1 << b_shift) + 1
    b = int.from_bytes(b, 'big') % b_mod * (1 << b_shift)
    return (a + b + c) % max


def encode_barcode(data):
    crc = caurus._crc24(data)
    data += crc.to_bytes(3, 'big')

    if len(data) != _BLOCK_SIZE - _ECC_SYMBOLS:
        raise Exception('Unsupported size')

    rs = reedsolo.RSCodec(nsym=_ECC_SYMBOLS, nsize=_BLOCK_SIZE, fcr=1)
    data = rs.encode(data)

    modules = []
    for i in range(_BLOCK_SIZE):
        for block in range(len(data) // _BLOCK_SIZE):
            for j in range(0, 8, 2)[::-1]:
                modules.append((data[block * _BLOCK_SIZE + i] >> j) & 0b11)
    modules[-3] = 0

    result = []
    offset = 0
    for alignment, take in caurus._ALIGNMENT:
        result += alignment
        result += modules[offset:offset + take]
        offset += take
    return result


def build_barcode(type, account, payload, encryption_key, mac_key, context):
    if isinstance(payload, Bits):
        if len(payload) > 476:
            raise Exception('Maximum payload length exceeded')
        payload = payload.tobytes()
    elif len(payload) > 59:  # last byte gets truncated
        raise Exception('Maximum payload length exceeded')
    payload += b'\0' * (60 - len(payload))
    encrypted = caurus._aes_ctr_encrypt(encryption_key, payload, context)

    message = BitArray()
    message += Bits(uint=caurus._VERSION, length=8)
    message += Bits(uint=type, length=4)
    message += Bits(uint=context.service_id, length=6)
    message += Bits(uint=account, length=25)
    message += Bits(bool=True)
    message += Bits(length=64)
    message += Bits(bytes=encrypted, length=604)

    mac = caurus._hmac(mac_key, message.bytes, context)[:8]
    message.overwrite(Bits(bytes=mac), 44)

    return message.bytes


def start_activation(context, account=None):
    if account is None:
        account = context.random.getrandbits(10)
    elif not (0 <= account < (1 << 10)):
        raise ValueError('Invalid account number')
    id = caurus._random_bytes(16, context)
    key = caurus._random_bytes(16, context)

    payload = key + id + b'\0'
    barcode = build_barcode(1, account, payload, context.service_key, context.service_mac, context)

    kres = caurus._derive(key, b'KRES', b'', 16, context)
    c = 2
    b_data = BitArray(bytes=barcode)
    b_data.overwrite(Bits(length=len(b_data) - 44), 44)
    b_data += Bits(uint=c, length=16)
    b = caurus._hmac(kres, b_data.bytes, context)
    code = _shuffle_code(_code(b'', b, 3, c, 7), 7)

    return account, id, key, code, encode_barcode(barcode)


def continue_activation(account, id, key, context):
    salt_server = caurus._random_bytes(16, context)
    payload = salt_server + id
    account_key = caurus._derive(key, b'KENC', b'', 16, context)
    account_mac = caurus._derive(key, b'KMAC', b'', 16, context)
    barcode = build_barcode(2, account, payload, account_key, account_mac, context)
    return (salt_server, barcode), encode_barcode(barcode)


def complete_activation(key, state, code, context):
    code = _deshuffle_code(code)
    a = Bits(bytes=state[1])[108:108 + 128].bytes
    c = _code_c(code, a, 13, 7)
    if c % 8 != 2:
        pass  # raise Exception('Malformed code')
    seed = c // 8

    salt = seed.to_bytes(2, 'big') + state[0]
    kder = caurus._derive(key, b'KDER', b'', 16, context)
    kdres = caurus._derive(kder, b'KDRES', salt, 16, context)

    b_data = state[1] + c.to_bytes(2, 'big')
    b = caurus._hmac(kdres, b_data, context)

    code_expected = _code(a, b, 13, c, 7)
    if code == code_expected:
        return salt
    else:
        return None


def transaction(account, key, salt, message, context):
    if isinstance(message, list):
        def escape(styled):
            if isinstance(styled, tuple):
                text, style = styled
            else:
                text, style = styled, None
            escaped = caurus._escape(text.upper(), caurus._ALPHABET, caurus._UNESCAPED)
            if style:
                return '%%' + style + escaped
            else:
                return escaped
        message = [row if isinstance(row, tuple) else ((row, None),) for row in message]
        message = '&'.join(['='.join(map(escape, row)) for row in message])

    message = caurus._pack_pad_string(message, caurus._ALPHABET, 3, ' ', 58)

    payload = BitArray()
    payload += Bits(bool=False)  # no amount
    payload += Bits(length=11)
    payload += Bits(bytes=message)
    if len(payload) != 476:
        raise AssertionError()

    kenc = caurus._derive(key, b'KENC', b'', 16, context)
    kmac = caurus._derive(key, b'KMAC', b'', 16, context)
    kder = caurus._derive(key, b'KDER', b'', 16, context)
    kdres = caurus._derive(kder, b'KDRES', salt, 16, context)

    barcode = build_barcode(0, account, payload, kenc, kmac, context)

    a = Bits(bytes=barcode)[108:108 + 128].bytes
    c = 3
    b_data = barcode + c.to_bytes(2, 'big')
    b = caurus._hmac(kdres, b_data, context)
    code = _shuffle_code(_code(a, b, 2, c, 6), 6)

    return code, encode_barcode(barcode)
