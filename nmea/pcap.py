#!/usr/bin/env python3

import logging
import struct
from datetime import datetime
from pathlib import Path

import click


def hexdump(data, print_function=print):
    """Hex dump."""

    def group(a, *ns):
        for n in ns:
            a = [a[i : i + n] for i in range(0, len(a), n)]
        return a

    def join(a, *cs):
        return [cs[0].join(join(t, *cs[1:])) for t in a] if cs else a

    toHex = lambda c: f"{c:02X}"
    toChr = lambda c: chr(c) if 32 <= c < 127 else "."
    make = lambda f, *cs: join(group(list(map(f, data)), 8, 2), *cs)
    hs = make(toHex, "  ", " ")
    cs = make(toChr, " ", "")
    for i, (h, c) in enumerate(zip(hs, cs)):
        print_function(f"{i * 16:010X}: {h:48}  {c:16}")


def eth_ntoa(data):
    return ":".join(map(lambda x: f"{x:02X}", data))


def ipv4_ntoa(data):
    a, b, c, d = struct.unpack(">BBBB", data)
    return f"{a}.{b}.{c}.{d}"


def parse_options(block):
    offset = 0
    while offset < len(block):
        option_type, option_length = struct.unpack("<HH", block[offset : 4 + offset])

        value = block[offset + 4 : offset + 4 + option_length]
        if option_type == 0:
            value = "opt_endofopt"
        elif option_type == 1:
            value = "opt_comment=" + value.decode()
        # else:
        #     value = block[offset + 4 : offset + 4 + option_length]

        yield option_type, option_length, value
        offset += 4 + ((option_length + 3) // 4) * 4


def parse_shb(block):
    """Parse the Section Header Block (SHB).
    [reference](https://www.ietf.org/staging/draft-tuexen-opsawg-pcapng-02.html#name-section-header-block)
    """
    byte_order, major, minor, length = struct.unpack("<IHHi", block[:12])
    logging.debug(f"0x0A0D0D0A SHB magic=0x{byte_order:08x}, version={major}.{minor}, section_length={length}")
    assert byte_order == 0x1A2B3C4D
    for option_type, option_length, option_value in parse_options(block[16:]):
        logging.debug(f"    SHB option type={option_type}, length={option_length}, {option_value}")


def parse_idb(block):
    """Parse an Interface Description Block (IDB).
    [reference](https://www.ietf.org/staging/draft-tuexen-opsawg-pcapng-02.html#name-interface-description-block)
    """
    link_type, _, snap_len = struct.unpack("<HHI", block[:8])
    logging.debug(f"0x00000001 IDB link_type={link_type}, snap_len={snap_len}")
    for option_type, option_length, option_value in parse_options(block[8:]):
        if option_type == 2:
            option_value = f"if_name={option_value.decode('utf-8')}"
        logging.debug(f"    IDB option type={option_type}, length={option_length}, {option_value}")
    hexdump(block, logging.debug)


def parse_epb(block):
    """Parse an Enhanced Packet Block (EPB).
    [reference](https://www.ietf.org/staging/draft-tuexen-opsawg-pcapng-02.html#name-enhanced-packet-block)"""

    interface_id, timestamp_high, timestamp_low, cap_len, pkt_len = struct.unpack("<IIIII", block[:20])

    timestamp = (timestamp_high << 32) + timestamp_low
    timestamp = datetime.fromtimestamp(timestamp / 1000000).isoformat()

    logging.debug(
        f"0x00000006 EPB interface_id={interface_id}, timestamp={timestamp}, cap_len={cap_len}, pkt_len={pkt_len}"
    )
    data = block[20 : 20 + cap_len]
    offset = 20 + ((cap_len + 3) // 4) * 4
    for option_type, option_length, option_value in parse_options(block[offset:]):
        logging.debug(f"    EPB option {option_type} {option_value}")
    hexdump(data, logging.debug)

    mac_dest, mac_src, proto = struct.unpack(">6s6sH", data[:14])
    logging.debug(f"    MAC {eth_ntoa(mac_src)} → {eth_ntoa(mac_dest)} proto {proto:04x}")

    if proto == 0x0800:
        ip_header = struct.unpack(">BBHHHBBH4s4s", data[14:34])
        assert ip_header[0] // 16 == 0x4  # IPv4 header

        if ip_header[6] == 17:  # IPPROTO_UDP
            assert ip_header[0] == 0x45  # IP header sans extension, 20 octets

            saddr = ipv4_ntoa(ip_header[8])
            daddr = ipv4_ntoa(ip_header[9])

            sport, dport, length, checksum = struct.unpack(">HHHH", data[34:42])
            if sport == 11101:
                logging.debug(f"    UDP {saddr}:{sport} → {daddr}:{dport} length {length}")
                for line in data[42 : 42 + length - 8].decode().splitlines():
                    print(timestamp, line)
                return

    # print(f"{timestamp} skip")


def parse_dpeb(block):
    """Darwin Process Event Block.
    [reference](https://github.com/wireshark/wireshark/blob/master/epan/dissectors/file-pcapng.c#L273)
    """

    logging.debug("DPEB")
    hexdump(block, logging.debug)

    process_id = struct.unpack("<I", block[:4])[0]
    logging.debug(f"    process_id={process_id}")
    for option_type, option_length, option_value in parse_options(block[4:]):
        if option_type == 2:
            option_value = f"darwin_proc_name={option_value.decode('utf-8')}"
        elif option_type == 4:
            assert option_length == 16
            option_value = f"darwin_proc_uuid={option_value.hex()}"
        logging.debug(f"    DPEB type={option_type}, length={option_length}, {option_value}")


@click.command(help="Extrait les trames UDP port 11101 d'une capture (Python version)")
@click.argument("filename")
@click.argument("output", default="")
def main(filename, output):
    p = Path(filename).open("rb")

    magic = p.read(4)
    p.seek(0)
    magic = struct.unpack("I", magic)[0]
    if magic == 0xA0D0D0A:
        # https://www.ietf.org/staging/draft-tuexen-opsawg-pcapng-02.html
        logging.debug("pcapng file")
    else:
        # https://tools.ietf.org/id/draft-gharris-opsawg-pcap-00.html
        logging.error(f"pcap file (magic 0x{magic:04x})")
        exit(2)

    while True:
        block_header = p.read(8)
        if block_header is None or len(block_header) == 0:
            break
        block_type, block_length = struct.unpack("II", block_header)
        assert block_length % 4 == 0

        block = p.read(block_length - 12)
        block_length2 = struct.unpack("I", p.read(4))[0]
        assert block_length == block_length2

        if block_type == 0x0A0D0D0A:  # Section Header Block (SHB)
            parse_shb(block)
        elif block_type == 0x00000001:  # Interface Description Block (IDB)
            parse_idb(block)

        elif block_type == 0x00000006:  # Enhanced Packet Block (EPB)
            parse_epb(block)

        elif block_type == 0x80000001:  # Darwin Process Event Block (DPEB)
            # parse_dpeb(block)
            pass

        elif block_type == 0x00000005:  # Interface Statistics Block (ISB)
            pass

        else:
            logging.error(f"0x{block_type:08x} UNKNOWN BLOCK TYPE length: {block_length}")
            hexdump(block, logging.error)
            break


if __name__ == "__main__":
    main()
