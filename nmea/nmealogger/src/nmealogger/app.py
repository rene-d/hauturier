import toga
from toga.style import Pack
from toga.constants import COLUMN
import asyncio
from datetime import datetime
from pathlib import Path
import json


class NmeaProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        super().__init__()
        self.count = 0
        self.last = []
        self.size = 0

    def connection_made(self, transport):
        self.transport = transport

        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        print("started", now)

        self.filename = Path("/storage/emulated/0/Download") / Path(f"nmea_{now}.json")
        if not self.filename.parent.is_dir():
            self.filename = Path(f"nmea_{now}.json")

        self.f = self.filename.open("w")
        self.f.write("[\n")

    def connection_lost(self, exc):
        self.f.write("\n]\n")
        self.f.close()

    def datagram_received(self, data, addr):
        # print(f"Received message: {data}")

        if self.count != 0:
            self.f.write(",\n")

        frame = {"time": datetime.now().isoformat(), "data": data.decode()}
        json.dump(frame, self.f)

        lines = data.decode().splitlines()

        self.last.extend(f"{n} {line}" for n, line in enumerate(lines, self.count + 1))
        self.last = self.last[-30:]
        self.count += len(lines)
        self.size += len(data)

    def info(self):
        if self.count == 0:
            return "No messages received yet"
        else:
            return f"Frame count: {self.count} size: {self.size}"


class HandlerApp(toga.App):
    async def do_background_task(self, widget, **kwargs):

        loop = asyncio.get_event_loop()

        transport, protocol = await loop.create_datagram_endpoint(NmeaProtocol, local_addr=("0.0.0.0", 1456))

        while self.capturing:
            self.label.text = protocol.info()
            self.table.data = protocol.last
            await asyncio.sleep(1)

        transport.close()
        self.label.text = f"Stopped - saved into {protocol.filename.stem}"
        self.button.enabled = True

    def button_handler(self, widget):

        self.capturing = not self.capturing
        self.button.label = "Capturing..." if self.capturing else "Start"
        if self.capturing:
            self.add_background_task(self.do_background_task)
        else:
            self.button.enabled = False

    def startup(self):
        self.capturing = False

        # Set up main window
        self.main_window = toga.MainWindow(title=self.name)

        self.button = toga.Button("Start", on_press=self.button_handler)
        self.button.style.flex = 1

        self.label = toga.Label("Ready.", style=Pack(padding=5))

        self.table = toga.Table(
            headings=["Last messages"],
            missing_value="",
            data=[],
            style=Pack(
                flex=1,
                padding_right=5,
                font_family="monospace",
                font_size=10,
                font_style="normal",
            ),
            multiple_select=False,
        )
        font = toga.Font("monospace", 10, "normal")
        self.table._impl.set_font(font)

        box = toga.Box(
            children=[
                self.button,
                self.label,
                self.table,
            ],
            style=Pack(flex=1, direction=COLUMN, padding=10),
        )

        # Add the content on the main window
        self.main_window.content = box

        # Show the main window
        self.main_window.show()


def main():
    return HandlerApp()
