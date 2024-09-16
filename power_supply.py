# power_supply.py
"""This module provides a class to control a power supply using
VISA protocol."""

import logging
import pyvisa


class PowerSupplyController:
    """This class provides methods to control a power supply using
    VISA protocol"""

    def __init__(self, ip_address, protocol, max_voltage, max_current):
        self.ip_address = ip_address
        self.protocol = protocol
        self.max_voltage = max_voltage
        self.max_current = max_current
        self.rm = None
        self.psu = None

    def connect(self):
        """Connect to the power supply"""
        try:
            self.rm = pyvisa.ResourceManager('@py')
            resource_string = f'TCPIP::{self.ip_address}::{self.protocol}'
            self.psu = self.rm.open_resource(resource_string)
            self.psu.timeout = 10000
            logging.info("Connected to power supply.")
        except pyvisa.VisaIOError as e:
            logging.error('VISA Error: %s', e)
            raise

    def set_voltage(self, channel, voltage):
        """Sets voltage on the power supply.

        :param channel: this is the channel number on the power supply
        :param voltage: this is the voltage to be set on the power supply
        """
        if voltage < 0 or voltage > self.max_voltage:
            raise ValueError(
                f"Voltage must be between 0 and {self.max_voltage} V.")
        self.psu.write(f'APPL CH{channel}, {voltage}, {self.max_current}')

    def output_on(self, channel):
        """Turns on the channel on the power supply.

        :param channel: this is the channel number on the power supply
        """
        self.psu.write(f'OUTP ON, (@{channel})')
        logging.info('Channel %s turned ON.', channel)

    def output_off(self, channel):
        """Turns off the channel on the power supply.

        :param channel: this is the channel number on the power supply
        """
        self.psu.write(f'OUTP OFF, (@{channel})')
        logging.info('Channel %s turned OFF.', channel)

    def close(self):
        """Close the connection to the power supply"""
        if self.psu:
            self.psu.close()
            logging.info("Power supply connection closed.")
