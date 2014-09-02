"""
util.py

Copyright 2014 ETH Zurich

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging
from os.path import sys
import socket
import struct

from lib.packet.host_addr import IPv4HostAddr
from lib.packet.opaque_field import InfoOpaqueField
from lib.packet.path import PathType, CorePath, CrossOverPath, PeerPath


def get_paths(dst_isd, src_aid, dst_aid):
    """
    Requests paths for dst_aid in dst_isd from the path translation server.

    The path translation server is currently emulated by the clientdaemon. The
    communication uses UDP and the src/dst ports are set to be (5550 + ADID)/
    (3330 + ADID) (e.g for AD6 this would be 5556/3336).
    """
    paths = {}
    data = struct.pack("HH", dst_isd, dst_aid)
    # print str(data)
    # Send data to local client-daemon
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 5550 + src_aid))
    sock.settimeout(2)
    socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(
        data, ("127.0.0.1", 3330 + src_aid))
    try:
        while True:
            data, addr = sock.recvfrom(1024)
            # format of received path is \x00|ISD|AID|path|FirstHop-IP
            if data[0] == 0:
                offset = 11
                info = InfoOpaqueField(
                    data[offset:offset + InfoOpaqueField.LEN])
                if info.info == PathType.CORE:
                    path = CorePath(data[offset:-4])
                elif info.info == PathType.CROSS_OVER:
                    path = CrossOverPath(data[offset:-4])
                elif info.info == PathType.PEER_LINK:
                    path = PeerPath(data[offset:-4])
                else:
                    logging.info("Can not parse path in packet: "
                                 "Unknown type %x", info.info)
                first_hop = IPv4HostAddr(data[-4:])
                if (dst_isd, dst_aid) not in paths:
                    paths[(dst_isd, dst_aid)] = [(path, first_hop)]
                else:
                    paths[(dst_isd, dst_aid)].append((path, first_hop))
                # packed = path.pack()
            elif data[0] == 4:
                # Received last path
                logging.info("Received all paths for AD %u", dst_aid)
                break
    except socket.timeout:
        logging.info("Socket timed out.")
    except:
        logging.warning("Unexpected error: %s", sys.exc_info()[0])
    finally:
#         logging.info("Got the following paths for AD %lu: %s",
#                      dst_aid, str(paths))
        sock.close()

    return paths