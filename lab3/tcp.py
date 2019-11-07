#!/use/bin/env python3
import logging

from bene.sim import Sim
from bene.tcp import TCP as TCPStub
from bene.tcp import logger, sender_logger, receiver_logger


class TCP(TCPStub):
    """ A TCP connection between two hosts."""

    def __init__(self, transport, source_address, source_port,
                 destination_address, destination_port, app=None, window=1000,drop=[], ack_count=0, fast=False, com_seq_num=None, increment=0, ssthresh=100000):
        super(TCP, self).__init__(transport, source_address, source_port,
                            destination_address, destination_port, app, window, drop)
        self.ack_count = ack_count
        self.fast = fast
        sender_logger.debug("com_seq_num = %s" % (com_seq_num))
        if com_seq_num is not None:
            seq_list = list(map(int, com_seq_num.split(",")))
            self.com_seq_num = seq_list
        else:
            self.com_seq_num = None
        self.increment = increment
        self.ssthresh = ssthresh

    ''' Sender '''

    def send(self, data):
        self.send_buffer.put(data)
        while (self.send_buffer.available() > 0 and self.send_buffer.outstanding() < self.cwnd):
            next_data, next_seq = self.send_buffer.get(self.mss)
            self.send_packet(next_data, next_seq)

    def handle_ack(self, packet):
        """ Handle an incoming ACK. """
        self.plot_sequence(packet.ack_number - packet.length,'ack')
#        sender_logger.debug("%s (%s) received ACK from %s for %d" % (
#            self.node.hostname, packet.destination_address, packet.source_address, packet.ack_number))
#        sender_logger.debug("Using fast retransmit: %r" % (self.fast))
#new down
        if self.cwnd < self.ssthresh:
            self.cwnd += self.mss
        else:
            self.increment += (self.mss*packet.length)/self.cwnd
            if self.increment >= self.mss:
                self.cwnd += self.mss
                self.increment -= self.mss
#new up
        if self.sequence == packet.ack_number:
            self.ack_count += 1
#            sender_logger.debug("self.ack_count = %d" % (self.ack_count))
        if self.ack_count == 3 and self.send_buffer.outstanding() != 0:
#            sender_logger.debug("3 transmits")
#            sender_logger.debug("fast-b Out: %d and Ava: %d" % (
#                self.send_buffer.outstanding(), self.send_buffer.available()))
            re_data, re_seq = self.send_buffer.resend(self.mss)
#new down
            self.ssthresh = max([self.cwnd/2,self.mss])
            remainder = self.ssthresh % self.mss
            self.ssthresh -= remainder
            self.cwnd = self.mss
            self.increment = 0
#new up
            self.send_packet(re_data, re_seq)
#            sender_logger.debug("fast-e Out: %d and Ava: %d" % (
#                self.send_buffer.outstanding(), self.send_buffer.available()))
        if self.sequence < packet.ack_number:
            self.ack_count = 0
            self.send_buffer.slide(packet.ack_number)
            self.sequence = packet.ack_number
#            sender_logger.debug("ACKb Out: %d and Ava: %d" % (
#                self.send_buffer.outstanding(), self.send_buffer.available()))
            if self.send_buffer.outstanding() == 0:
                self.cancel_timer()
            while (self.send_buffer.available() > 0 and self.send_buffer.outstanding() < self.cwnd):
                next_data, next_seq = self.send_buffer.get(self.mss)
                self.send_packet(next_data, next_seq)
#            sender_logger.debug("ACKe Out: %d and Ava: %d" % (
#                self.send_buffer.outstanding(), self.send_buffer.available()))

    def retransmit(self, event):
        """ Retransmit data. """
        sender_logger.warning("%s (%s) retransmission timer fired" % (self.node.hostname, self.source_address))
#new down
        self.ssthresh = max([self.cwnd/2,self.mss])
        remainder = self.ssthresh % self.mss
        self.ssthresh -= remainder
        self.cwnd = self.mss
        self.increment = 0
#new up
        re_data, re_seq = self.send_buffer.resend(self.mss)
        self.timer = None
        self.send_packet(re_data, re_seq)

    ''' Receiver '''

    def handle_data(self, packet):
        """ Handle incoming data."""
#        sender_logger.debug("%s (%s) received TCP segment from %s for %d" % (
#            self.node.hostname, packet.destination_address, packet.source_address, packet.sequence))
        self.receive_buffer.put(packet.body, packet.sequence)
        ack_data, ack_start = self.receive_buffer.get()
        self.app.receive_data(ack_data)
        self.app.packet_stats(packet)
        self.ack = ack_start + len(ack_data)
        self.send_ack()

