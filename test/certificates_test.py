# Copyright 2014 ETH Zurich

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
:mod:`certificates_test` --- SCION certificates unit test
===========================================
"""

from infrastructure.cert_server import CertServer
from infrastructure.scion_elem import SCION_UDP_PORT, BUFLEN
from lib.crypto.asymcrypto import sign
from lib.crypto.certificate import verify_sig_chain_trc, CertificateChain, TRC
from lib.packet.host_addr import IPv4HostAddr, SCIONAddr
from lib.packet.scion import (SCIONPacket, get_type, PacketType as PT,
    CertChainRequest, CertChainReply, TRCRequest, TRCReply)
from lib.topology import Topology
from lib.util import (get_cert_chain_file_path, get_trc_file_path, read_file,
    get_sig_key_file_path, write_file)
import base64
import logging
import os
import select
import socket
import unittest


class TestCertificates(unittest.TestCase):
    """
    Unit tests for certificate.py and asymcrypto.py.
    """

    def test(self):
        """
        Create a certificate chain and verify it with a TRC file. Sign a message
        with the private key of the last certificate in the chain and verify it.
        """
        cert10 = CertificateChain(get_cert_chain_file_path(1, 10, 1, 10, 0))
        trc = TRC(get_trc_file_path(1, 10, 1, 0))
        print('TRC verification', trc.verify())
        print('Cert Chain verification:', cert10.verify('ISD:1-AD:10', trc, 0))

        sig_priv10 = read_file(get_sig_key_file_path(1, 10))
        sig_priv10 = base64.b64decode(sig_priv10)
        msg = b'abcd'
        sig = sign(msg, sig_priv10)
        print('Sig test:', verify_sig_chain_trc(msg, sig, 'ISD:1-AD:10', cert10,
            trc, 0))

        sig_priv13 = read_file(get_sig_key_file_path(1, 13))
        sig_priv13 = base64.b64decode(sig_priv13)
        msg = b'abd'
        sig = sign(msg, sig_priv13)
        chain = CertificateChain.from_values([])
        print('Sig test 2:', verify_sig_chain_trc(msg, sig, 'ISD:1-AD:13',
            cert10, trc, 0), '\n')

        topology = Topology("../topology/ISD1/topologies/ISD:1-AD:10.json")
        src_addr = SCIONAddr.from_values(topology.isd_id, topology.ad_id,
                                         IPv4HostAddr("127.0.0.1"))
        dst_addr = topology.certificate_servers[0].addr
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((str(src_addr.host_addr), SCION_UDP_PORT))
        
        print("Sending TRC request (ISD:1-V:0) to local CS.")
        msg = TRCRequest.from_values(PT.TRC_REQ_LOCAL, src_addr,
            topology.parent_edge_routers[0].interface.if_id, topology.isd_id,
            topology.ad_id, 1, 0).pack()
        sock.sendto(msg, (str(dst_addr), SCION_UDP_PORT))

        temp_file = './temp.txt'
        timeout = 5

        ready = select.select([sock], [], [], timeout)
        if not ready[0]:
            print("Error: no TRC reply was received!")
            sock.close()
            return

        data, _ = sock.recvfrom(BUFLEN)
        print("Received TRC reply from local CS.")
        trc_reply = TRCReply(data)
        write_file(temp_file, trc_reply.trc.decode('utf-8'))
        trc = TRC(temp_file)
        assert trc.verify()

        print("Sending cert chain request (ISD:1-AD:16-V:0) to local CS.")
        msg = CertChainRequest.from_values(PT.CERT_CHAIN_REQ_LOCAL, src_addr,
            topology.parent_edge_routers[0].interface.if_id, topology.isd_id,
            topology.ad_id, 1, 16, 0).pack()
        sock.sendto(msg, (str(dst_addr), SCION_UDP_PORT))

        ready = select.select([sock], [], [], timeout)
        if not ready[0]:
            print("Error: no cert chain reply was received!")
            sock.close()
            return

        data, _ = sock.recvfrom(BUFLEN)
        print("Received cert chain reply from local CS.")
        cert_chain_reply = CertChainReply(data)
        write_file(temp_file, cert_chain_reply.cert_chain.decode('utf-8'))
        cert_chain = CertificateChain(temp_file)
        assert cert_chain.verify('ISD:1-AD:16', trc, 0)

        os.remove(temp_file)
        sock.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()