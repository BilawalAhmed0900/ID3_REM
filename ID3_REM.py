from __future__ import print_function

from os import remove, rename
from sys import exit
from io import BufferedReader
from argparse import ArgumentParser, Namespace


SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2


def main() -> None:
    parser = ArgumentParser(description='Remove ID3 tag from mp3')
    parser.add_argument('Input',  action='store', help='Input file')

    parser.add_argument('-o', dest='Output',
                        default='', action='store', help='Output file')

    args = parser.parse_args()

    try:
        process(args)
    except KeyboardInterrupt:
        print("Ctrl-C detected, exiting...")
        exit(-1)


def unsynchsafe(number: int) -> int:
    out = 0
    mask = 0x7F000000

    while (mask):
        out >>= 1
        out |= number & mask
        mask >>= 8

    return out


# ID3v2_tag
class ID3v2_TAG:
    IDENT = ""
    version_major = 0
    version_minor = 0
    flags = 0
    unsynchronisation = 0
    ext_header = 0
    compression = 0
    experimental = 0
    footer = 0
    size = 0
    t_size = 0

    def __init__(self, input: BufferedReader) -> 'ID3v2_TAG':
        # 'ID3'
        self.IDENT = input.read(3).decode('utf-8')

        # v2.version_major.version_minor
        self.version_major = int.from_bytes(input.read(1), byteorder='little')
        self.version_minor = int.from_bytes(input.read(1), byteorder='little')

        # each version_major has different use of flags
        self.flags = int.from_bytes(input.read(1), byteorder='little')

        # present in 2.2, 2.3 and 2.4, its the 7th bit
        self.unsynchronisation = self.flags and (1 << (7 - 1))

        ''' is_compression_used for 2.2
        else is_extended_found for 2.3 and 2.4, 6th bit'''
        if (self.version_major == 2):
            self.compression = self.flags and (1 << (6 - 1))
        else:
            self.ext_header = self.flags and (1 << (6 - 1))

        # only for 2.3 and 2.4, its 5th bit
        if (self.version_major != 2):
            self.experimental = self.flags and (1 << (5 - 1))

        # only for 2.4, its 4th bit
        if (self.version_major == 4):
            self.footer = self.flags and (1 << (4 - 1))

        # big-endien, so that original bytes can be re-obtained
        self.size = int.from_bytes(input.read(4), byteorder='big')
        self.size = unsynchsafe(self.size)

        '''
            Total size =
                self.size +
                if footer present then 10 i.e sizeof(footer) +
                size read already i.e 10 i.e sizeof(header)
        '''
        self.t_size = self.size + (self.footer * 10) + 10


NoTag = 0
IDEv1 = 1
IDEv1_1 = 2
IDEv2 = 3


class Versions:
    isID3v1 = False
    isID3v1_1 = False
    isID3v2 = False
    isNone = False

    def __init__(self) -> 'Versions':
        self.isID3v1 = False
        self.isID3v1_1 = False
        self.isID3v2 = False
        self.isNone = True


def checkID3version(input: BufferedReader) -> Versions:
    vers = Versions()

    # ID3v1 tag is of 128bytes from the end
    input.seek(-1 * 128, SEEK_END)
    vers.isID3v1 = input.read(3) == b'TAG'

    # ID3v1.1 tag is of 227bytes from the end
    input.seek(-1 * 227, SEEK_END)
    vers.isID3v1_1 = input.read(4) == b'TAG+'

    # ID3v2 tag is of variable bytes, see class above
    input.seek(0, SEEK_SET)
    vers.isID3v2 = input.read(3) == b'ID3'

    if vers.isID3v1 or \
       vers.isID3v1_1 or \
       vers.isID3v2:
        vers.isNone = False

    return vers


def process(args: Namespace):
    istmp = False

    '''
        input -> input.tmp
        output -> input
    '''
    if (args.Output == ''):
        istmp = True
        args.Output = args.Input
        args.Input = args.Input + '.tmp'
        rename(args.Output, args.Input)

    input_name = args.Input
    output_name = args.Output

    input = open(input_name, 'rb+')
    output = open(output_name, 'wb+')

    vers = checkID3version(input)
    input.seek(0, 0)
    if vers.isNone:
        for buffer in input:
            output.write(buffer)
    elif (vers.isID3v1 or vers.isID3v1_1 or vers.isID3v2):
        ID3v2_size = 0
        if vers.isID3v2:
            ID3 = ID3v2_TAG(input)
            ID3v2_size = ID3.t_size

        input.seek(0, SEEK_END)
        total_size = input.tell()

        input.seek(ID3v2_size, 0)
        to_read = total_size - ID3v2_size

        if vers.isID3v1:
            to_read -= 127
        elif vers.isID3v1_1:
            to_read -= 227

        buffer = input.read(to_read)
        output.write(buffer)

    input.close()
    output.close()

    if istmp:
        remove(args.Input)


if __name__ == '__main__':
    main()