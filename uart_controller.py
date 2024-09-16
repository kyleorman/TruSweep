# uart_controller.py
"""This module provides a UARTController class to handle UART communication."""

import logging
import serial
import serial.tools.list_ports


class UARTController:
    """UARTController provides methods to handle UART communication."""

    def __init__(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        self.uart = None

    def connect(self):
        """Handles the connection to the UART."""
        try:
            self.uart = serial.Serial(self.port, self.baud_rate)
            logging.info('Connected to UART on port %s.', self.port)
        except serial.SerialException as e:
            logging.error('Serial Error: %s', e)
            raise

    def wait_for_signal(self, stop_event):
        """Waits for a signal on the UART.

        :param stop_event: Event to stop the waiting.
            If set, the method will return None.
        """
        logging.info("Waiting for UART signal...")
        while not stop_event.is_set():
            if self.uart.in_waiting > 0:
                message = self.uart.read().decode().strip()
                logging.debug('Received UART message: %s', message)
                return message
        return None

    def close(self):
        """Closes the UART connection."""
        if self.uart and self.uart.is_open:
            self.uart.close()
            logging.info('UART connection closed.')

    @staticmethod
    def list_ports():
        """Lists the available serial ports."""
        return [port.device for port in serial.tools.list_ports.comports()]
