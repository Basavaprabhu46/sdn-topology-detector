# topology.py
# Custom Mininet topology: 3 switches, 4 hosts
#
#   h1 - s1 - s2 - s3
#   h2 /       \   \ h4
#             h3

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink


class CustomTopo(Topo):
    def build(self):
        # Switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')

        # Hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        h4 = self.addHost('h4', ip='10.0.0.4/24')

        # Host-Switch links
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s2)
        self.addLink(h4, s3)

        # Switch-Switch links (linear, no loops)
        self.addLink(s1, s2)
        self.addLink(s2, s3)


# ── run() is OUTSIDE the class ─────────────────────────────────
def run():
    topo = CustomTopo()
    net = Mininet(
        topo=topo,
        controller=None,
        link=TCLink,
        autoSetMacs=True
    )
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    net.start()

    print("\n[INFO] Topology started. Use CLI to test.\n")
    print("  pingall                     — test all host connectivity")
    print("  link s1 s2 down            — bring s1-s2 link down")
    print("  link s1 s2 up              — bring s1-s2 link up")
    print("  sh ovs-ofctl dump-flows s1 — view flow table on s1")
    print("  iperf h1 h3                — bandwidth test\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
