import struct
import os

for f in os.listdir("."):
    if f.endswith(".pcap"):
        try:
            with open(f, "rb") as fh:
                header = fh.read(24)
                if len(header) >= 24:
                    linktype = struct.unpack("<I", header[20:24])[0]
                    print(f"{f}: LinkType={linktype}")
        except Exception as e:
            print(f"{f}: Error - {e}")