import argparse
import base64
import configparser
import os
import random
import subprocess
import sys
import tempfile
from binascii import hexlify, unhexlify
from bitstring import Bits, BitArray
from collections import namedtuple
from cryptography.hazmat.backends import default_backend
import caurus
import caurus.barcode
import caurus.server


_UninitializedContext = namedtuple('_UninitializedContext', ['random', 'crypto'])
_Context = namedtuple('_Context', ['service_id', 'service_mac', 'service_key', 'accounts', 'random', 'crypto'])
_Account = namedtuple('_Account', ['id', 'key', 'salt'])


def serialize_barcode(barcode):
    result = BitArray()
    for b in barcode:
        result += Bits(uint=b, length=2)
    return base64.urlsafe_b64encode(result.tobytes()).decode().rstrip('=')


def deserialize_barcode(barcode):
    barcode = barcode + '=' * (-len(barcode) % 4)
    barcode = Bits(bytes=base64.urlsafe_b64decode(barcode))
    result = [barcode[i:i + 2].uint for i in range(0, len(barcode), 2)]
    size = int(len(result) ** 0.5)
    return result[:size * size]


def view_barcode(barcode, viewer):
    if viewer:
        path = None
        try:
            svg = caurus.barcode.to_svg(barcode, background=True)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
                path = f.name
                f.write(svg)
            subprocess.run([viewer, path])
            input('Press enter to continue after you scanned the barcode...')
        finally:
            if path:
                os.remove(path)
    else:
        print('Barcode: {}'.format(serialize_barcode(barcode)))


def input_code(length):
    while True:
        code = input('Code: ')
        if code == '':
            return None
        elif len(code) == length and code.isdigit():
            return code


def build_context(args):
    config = configparser.ConfigParser()
    config.read_file(args.config)

    accounts = {}
    for section in config.sections():
        if not section.startswith('account.'):
            continue
        accounts[int(section[8:])] = _Account(
            id=unhexlify(config[section]['id']),
            key=unhexlify(config[section]['key']),
            salt=unhexlify(config[section]['salt']),
        )

    return _Context(
        service_id=int(config['service']['id']),
        service_mac=unhexlify(config['service']['mac']),
        service_key=unhexlify(config['service']['key']),
        accounts=accounts,
        random=random.SystemRandom(),
        crypto=default_backend(),
    )


def barcode_svg(args):
    barcode = deserialize_barcode(args.barcode)
    print(caurus.barcode.to_svg(barcode, args.background))


def barcode_print(args):
    barcode = deserialize_barcode(args.barcode)
    size = int(len(barcode) ** 0.5)
    for y in range(size):
        print(''.join([str(barcode[y + x * size]) for x in range(size)]))


def server_init(args):
    context = _UninitializedContext(
        random=random.SystemRandom(),
        crypto=default_backend(),
    )
    config = configparser.ConfigParser()
    config['service'] = {}
    config['service']['id'] = str(args.id)
    config['service']['mac'] = hexlify(caurus._random_bytes(16, context)).decode()
    config['service']['key'] = hexlify(caurus._random_bytes(16, context)).decode()
    config.write(args.config)
    print('Ready!')


def server_activate(args):
    context = build_context(args)

    account, account_id, account_key, code, barcode = caurus.server.start_activation(context, args.account)
    view_barcode(barcode, args.viewer)
    if input_code(7) != code:
        print('Invalid code', file=sys.stderr)
        return 1

    state, barcode = caurus.server.continue_activation(account, account_id, account_key, context)
    view_barcode(barcode, args.viewer)
    code = input_code(7)
    if code is None:
        return 1

    account_salt = caurus.server.complete_activation(account_key, state, code, context)
    if not account_salt:
        print('Invalid code', file=sys.stderr)
        return 1

    print()
    print('Client successfully confirmed! To use your account, add the following to your configuration file:')
    print()
    config = configparser.ConfigParser()
    config['account.' + str(account)] = {
        'id': hexlify(account_id).decode(),
        'key': hexlify(account_key).decode(),
        'salt': hexlify(account_salt).decode(),
    }
    config.write(sys.stdout)


def server_transaction(args):
    context = build_context(args)
    if args.account not in context.accounts:
        print('Invalid account', file=sys.stderr)
        return 1
    account = context.accounts[args.account]

    message = []
    for row in args.message:
        row = row.split(':', 1)
        if len(row) == 1:
            key, value, style = row[0], '', None
        elif ':' in row[1]:
            key = row[0]
            value, style = row[1].rsplit(':', 1)
        else:
            key, value = row
            style = None
        if len(value) > 0:
            message.append(((key, style), (value, style)))
        else:
            message.append(((key, style),))

    code, barcode = caurus.server.transaction(args.account, account.key, account.salt, message, context)

    view_barcode(barcode, args.viewer)
    print('Code: {}'.format(code))


def main():
    def add_config_argument(parser, mode='r'):
        parser.add_argument(
            '--config',
            type=argparse.FileType(mode=mode),
            help='path to the configuration file',
            default='caurus.cfg')

    def add_viewer_argument(parser):
        parser.add_argument(
            '--viewer',
            help='path to a SVG viewer')

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()  # (required=True)

    parser_barcode = subparsers.add_parser('barcode', help='render barcodes')
    subparsers_barcode = parser_barcode.add_subparsers()

    parser_barcode_print = subparsers_barcode.add_parser('print')
    parser_barcode_print.set_defaults(func=barcode_print)
    parser_barcode_print.add_argument('barcode', type=str)

    parser_barcode_svg = subparsers_barcode.add_parser('svg')
    parser_barcode_svg.set_defaults(func=barcode_svg)
    parser_barcode_svg.add_argument('--background', action='store_true')
    parser_barcode_svg.add_argument('barcode', type=str)

    parser_server = subparsers.add_parser('server', help='server-side commands')
    subparsers_server = parser_server.add_subparsers()

    parser_server_init = subparsers_server.add_parser('init')
    parser_server_init.set_defaults(func=server_init)
    add_config_argument(parser_server_init, 'x')
    parser_server_init.add_argument('id', type=int, nargs='?', help='service ID', default=1)

    parser_server_activate = subparsers_server.add_parser('activate')
    parser_server_activate.set_defaults(func=server_activate)
    add_config_argument(parser_server_activate)
    add_viewer_argument(parser_server_activate)
    parser_server_activate.add_argument('account', type=int, nargs='?', help='account number')

    parser_server_transaction = subparsers_server.add_parser('transaction')
    parser_server_transaction.set_defaults(func=server_transaction)
    add_config_argument(parser_server_transaction)
    add_viewer_argument(parser_server_transaction)
    parser_server_transaction.add_argument('account', type=int, help='account number')
    parser_server_transaction.add_argument('message', nargs='*', help='message')

    args = parser.parse_args()
    if 'func' in args:
        args.prog = parser.prog
        return args.func(args)
    else:
        parser.print_usage()
        return 1


if __name__ == '__main__':
    sys.exit(main())
