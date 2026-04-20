# topology_detector.py

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event as topo_event
from ryu.topology.api import get_link
import logging
import os
import datetime

# ── Logging setup ──────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, 'topology_changes.log')

# Force-clear any existing handlers to prevent duplicates
logger = logging.getLogger('TopologyDetector')
logger.setLevel(logging.INFO)
logger.propagate = False          # stop Ryu root logger from double-printing
logger.handlers.clear()           # wipe handlers from previous runs

formatter = logging.Formatter('%(message)s')

fh = logging.FileHandler(log_file)
fh.setFormatter(formatter)
logger.addHandler(fh)

sh = logging.StreamHandler()
sh.setFormatter(formatter)
logger.addHandler(sh)


def ts():
    return datetime.datetime.now().strftime('%H:%M:%S')


# ── Main App ───────────────────────────────────────────────────
class TopologyDetector(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologyDetector, self).__init__(*args, **kwargs)

        self.topology_map = {
            'switches': {},
            'links': {}
        }
        self.mac_table = {}
        self._last_printed = {'switches': [], 'links': []}

        logger.info("\n=== Topology Detector Started ===\n")

    # ── LINK UPDATE ────────────────────────────────────────────
    def update_links(self):
        links_list = get_link(self, None)
        new_links = {}
        for link in links_list:
            src = link.src.dpid
            dst = link.dst.dpid
            new_links[(src, dst)] = link.src.port_no
        self.topology_map['links'] = new_links

    # ── SWITCH FEATURES ────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=0, match=match, instructions=inst)
        dp.send_msg(mod)

    # ── SWITCH ENTER ───────────────────────────────────────────
    @set_ev_cls(topo_event.EventSwitchEnter)
    def switch_enter(self, ev):
        switch = ev.switch
        dpid = switch.dp.id
        ports = [p.port_no for p in switch.ports if p.port_no < 65534]

        self.topology_map['switches'][dpid] = ports
        logger.info(f"[SWITCH UP] {dpid} ports={ports} ({ts()})")

        self.update_links()
        self._print_topology()

    # ── SWITCH LEAVE ───────────────────────────────────────────
    @set_ev_cls(topo_event.EventSwitchLeave)
    def switch_leave(self, ev):
        dpid = ev.switch.dp.id

        self.topology_map['switches'].pop(dpid, None)
        self.mac_table.pop(dpid, None)
        self.topology_map['links'] = {
            k: v for k, v in self.topology_map['links'].items()
            if k[0] != dpid and k[1] != dpid
        }

        logger.info(f"[SWITCH DOWN] {dpid} ({ts()})")
        self._print_topology()

    # ── LINK ADD ───────────────────────────────────────────────
    @set_ev_cls(topo_event.EventLinkAdd)
    def link_add_handler(self, ev):
        src = ev.link.src.dpid
        dst = ev.link.dst.dpid
        logger.info(f"[LINK UP] {src} <--> {dst} ({ts()})")

        self.update_links()
        self._print_topology()

    # ── LINK DELETE ────────────────────────────────────────────
    @set_ev_cls(topo_event.EventLinkDelete)
    def link_delete_handler(self, ev):
        src = ev.link.src.dpid
        dst = ev.link.dst.dpid
        logger.info(f"[LINK DOWN] {src} <--> {dst} ({ts()})")

        self.update_links()
        self._print_topology()

    # ── PORT STATUS ────────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        port = msg.desc

        link_down = bool(port.state & ofp.OFPPS_LINK_DOWN)
        status = 'DOWN' if link_down else 'UP'
        logger.info(f"[PORT] sw={dp.id} port={port.port_no} {status} ({ts()})")
        # intentionally NOT calling _print_topology here

    # ── PACKET IN ──────────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        parser = dp.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth_list = pkt.get_protocols(ethernet.ethernet)
        if not eth_list:
            return
        eth = eth_list[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst
        dpid = dp.id
        in_port = msg.match['in_port']

        self.mac_table.setdefault(dpid, {})
        self.mac_table[dpid][src] = in_port

        out_port = self.mac_table[dpid].get(dst, ofp.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
            self.add_flow(dp, 1, match, actions)

        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        dp.send_msg(out)

    def add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match, instructions=inst)
        dp.send_msg(mod)

    # ── PRINT TOPOLOGY — only if changed ──────────────────────
    def _print_topology(self):
        switches = sorted(self.topology_map['switches'].keys())
        links = sorted(self.topology_map['links'].keys())

        if switches == self._last_printed['switches'] and links == self._last_printed['links']:
            return

        self._last_printed['switches'] = switches
        self._last_printed['links'] = links

        logger.info("\n--- TOPOLOGY ---")
        logger.info(f"Switches: {switches}")
        if links:
            for l in links:
                logger.info(f"Link: {l[0]} <--> {l[1]}")
        else:
            logger.info("Links: None")
        logger.info("----------------\n")
