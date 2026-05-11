#!/usr/bin/env python3

import time
import typing as t
import asyncio
import pyais


HOST = "hera.navimetrix.com"
PORT = 5000
MESSAGE = "LAT 48.7 LON -4.0 RADIUS 50.0 AGE 2880\n"


class Multipart:
    def __init__(self, count: int, number: int, message: bytes):
        self.time = time.time()
        self.parts = [None] * count
        self.parts[number - 1] = message


class Multiparts:
    def __init__(self):
        self.map = dict()

    def __call__(self, message: bytes) -> t.Optional[t.List[bytes]]:

        values = message.split(b",")

        if values[0] != b"!AIVDM":
            return None

        count = int(values[1])
        number = int(values[2])
        id = values[3]

        if count == 1 or number < 1 or number > count:
            return [message]

        now = time.time()
        key = (id, count)

        mp: Multipart = self.map.get(key)

        if (
            mp is None  # init multipart message
            or len(mp.parts) != count  # we want the same part count
            or (now - mp.time) > 1  # not too old
            or mp.parts[number - 1] is not None  # part should not be set
        ):
            self.map[key] = Multipart(count, number, message)
            return None
        else:
            # save current part
            mp.parts[number - 1] = message

        # if complete, return all parts
        if all(m is not None for m in mp.parts):
            self.map.pop(key)
            return mp.parts

        return None


async def tcp_client():
    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
        print(f"Connecté à {HOST}:{PORT}")

        writer.write(MESSAGE.encode())
        await writer.drain()

        multiparts = Multiparts()

        while True:
            nmea = await reader.readline()
            if not nmea:
                break

            # print(nmea.decode().rstrip())

            parts = multiparts(nmea)
            if parts:
                message = pyais.decode(*parts)
                print(message)
                print()

        writer.close()
        await writer.wait_closed()

    except Exception as e:
        print(f"Erreur : {e}")


if __name__ == "__main__":
    try:
        asyncio.run(tcp_client())
    except KeyboardInterrupt:
        pass
