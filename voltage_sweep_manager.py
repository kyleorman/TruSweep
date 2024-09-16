# voltage_sweep_manager.py
"""This module contains the VoltageSweepManager class."""

import time
import logging
from threading import Event, Lock
import csv
import os
import tempfile
from typing import Any, Dict, List, Optional
from queue import Queue


class VoltageSweepManager:
    """VoltageSweepManager class for controlling voltage sweep operations."""

    def __init__(
        self,
        psu_controller: Any,
        uart_controller: Optional[Any] = None,
        gui_queue: Optional[Queue] = None,
        stop_event: Optional[Event] = None
    ):
        """
        Initializes the VoltageSweepManager.

        :param psu_controller: The power supply unit controller instance.
        :param uart_controller: (Optional) The UART controller instance.
        :param gui_queue: (Optional) The GUI queue for inter-thread communication.
        :param stop_event: (Optional) An event to signal stopping the operation.
        """
        self.psu = psu_controller
        self.uart = uart_controller
        self.gui_queue = gui_queue
        self.stop_event = stop_event or Event()
        self.data_log: List[Dict[str, Any]] = []
        self.data_log_lock = Lock()

    def perform_sweep(self, config: Dict[str, Any]) -> None:
        """
        Performs a voltage sweep operation based on the given configuration.

        :param config:
        A dictionary containing configuration for the voltage sweep operation.
            - start_voltage (float): The starting voltage.
            - end_voltage (float): The ending voltage.
            - step_size (float): The voltage increment/decrement step size.
            - channel (int): The PSU channel to control.
            - increment_time (float): Time to wait between steps (in seconds).
            - power_cycle (bool): Whether to power cycle between steps.
            - uart_control (bool): Whether to wait for UART signals.
            - off_time (float): Time to wait after turning off (in seconds).
            - on_time (float): Time to wait after turning on (in seconds).
        """
        try:
            # Validate required configuration parameters
            required_keys = ['start_voltage',
                             'end_voltage', 'step_size', 'channel']
            for key in required_keys:
                if key not in config:
                    raise ValueError(
                        f"Missing required config parameter: {key}")

            # Unpack configuration
            ch1_voltage = config['ch1_voltage']
            ch2_voltage = config['ch2_voltage']
            ch3_voltage = config['ch3_voltage']
            start_voltage = config['start_voltage']
            end_voltage = config['end_voltage']
            step_size = config['step_size']
            channel = config['channel']
            increment_time = config.get('increment_time', 0)
            power_cycle = config.get('power_cycle', False)
            uart_control = config.get('uart_control', False)
            off_time = config.get('off_time', 0)
            on_time = config.get('on_time', 0)

            total_steps = int(
                abs((end_voltage - start_voltage) / step_size)
            ) + (1 if step_size != 0 else 1)
            current_step = 0
            current_voltage = start_voltage

            # Determine voltage condition and step size direction
            if start_voltage < end_voltage:
                def voltage_condition(cv):
                    return cv <= end_voltage
                if step_size <= 0:
                    raise ValueError(
                        "For increasing voltage, step_size must be positive.")
            elif start_voltage > end_voltage:
                def voltage_condition(cv):
                    return cv >= end_voltage
                if step_size >= 0:
                    step_size = -step_size  # Ensure step_size is negative
            else:
                # Start voltage equals end voltage, perform one iteration
                def voltage_condition(cv):
                    return current_step == 0

            self.psu.set_voltage(1, ch1_voltage)
            self.psu.set_voltage(2, ch2_voltage)
            self.psu.set_voltage(3, ch3_voltage)
            
            self.psu.output_on(1)
            self.psu.output_on(2)
            self.psu.output_on(3)
            
            while voltage_condition(current_voltage) and not self.stop_event.is_set():
                # Perform voltage setting and control logic
                self.psu.set_voltage(channel, current_voltage)
                logging.info("Set channel %s voltage to %s V.",
                             channel, current_voltage)

                # Data logging
                timestamp = time.time()
                with self.data_log_lock:
                    self.data_log.append(
                        {'timestamp': timestamp, 'voltage': current_voltage})
                if self.gui_queue:
                    self.gui_queue.put(
                        ('data_log', {
                            'timestamp': timestamp, 'voltage': current_voltage}))

                # Update progress
                current_step += 1
                progress = int((current_step / total_steps) * 100)
                if self.gui_queue:
                    self.gui_queue.put(('progress', progress))

                # Control flow based on modes
                if power_cycle:
                    self.psu.output_off(channel)
                    if uart_control and self.uart:
                        try:
                            self.wait_for_uart_signal(['ON'], timeout=30)
                        except TimeoutError as e:
                            logging.error(
                                "Timeout waiting for UART signal 'ON': %s", e)
                            if self.gui_queue:
                                self.gui_queue.put(
                                    (
                                        'error',
                                        f"Timeout waiting for UART signal 'ON': {e}"))
                            break
                    else:
                        self._sleep_with_stop_check(off_time)
                    self.psu.output_on(channel)
                    if uart_control and self.uart:
                        try:
                            self.wait_for_uart_signal(['I'], timeout=30)
                        except TimeoutError as e:
                            logging.error(
                                "Timeout waiting for UART signal 'I': %s", e)
                            if self.gui_queue:
                                self.gui_queue.put(
                                    ('error', f"Timeout waiting for UART signal 'I': {e}"))
                            break
                    else:
                        self._sleep_with_stop_check(on_time)
                elif uart_control and self.uart:
                    try:
                        self.wait_for_uart_signal(['I'], timeout=30)
                    except TimeoutError as e:
                        logging.error(
                            "Timeout waiting for UART signal 'I': %s", e)
                        if self.gui_queue:
                            self.gui_queue.put(
                                ('error', f"Timeout waiting for UART signal 'I': {e}"))
                        break
                else:
                    self._sleep_with_stop_check(increment_time)

                current_voltage += step_size

            self.psu.output_off(1)
            self.psu.output_off(2)
            self.psu.output_off(3)

            logging.info("Voltage sweep on channel %s completed.", channel)
            
            if self.gui_queue:
                self.gui_queue.put(('progress', 100))
                self.gui_queue.put(('done', None))
        except Exception as e:
            logging.exception("Error during voltage sweep:")
            if self.gui_queue:
                self.gui_queue.put(
                    ('error', f"Error during voltage sweep: {e}"))

    def wait_for_uart_signal(self, expected_signals: List[str], timeout: float = 30) -> Optional[str]:
        """
        Waits for a UART signal from the expected signals list, with a timeout.

        :param expected_signals: A list of expected signals to wait for.
        :param timeout: The maximum time to wait for the signal (in seconds).
        :return: The received signal if it's in the expected signals list.
        :raises TimeoutError: If the signal is not received within the timeout.
        """
        start_time = time.time()
        while not self.stop_event.is_set():
            if time.time() - start_time > timeout:
                raise TimeoutError("UART signal wait timed out.")
            signal = self.uart.wait_for_signal(self.stop_event)
            if signal in expected_signals:
                return signal
        return None

    def save_data_log(self, file_path: str) -> None:
        """
        Saves the data log to a CSV file.

        :param file_path: The file path to save the data log.
        """
        try:
            dir_name = os.path.dirname(file_path) or '.'
            with tempfile.NamedTemporaryFile('w', newline='', encoding='utf-8',
                                             dir=dir_name, delete=False) as tmpfile:
                fieldnames = ['timestamp', 'voltage']
                writer = csv.DictWriter(tmpfile, fieldnames=fieldnames)
                writer.writeheader()
                with self.data_log_lock:
                    for entry in self.data_log:
                        writer.writerow(entry)
                tempname = tmpfile.name
            os.replace(tempname, file_path)
            logging.info("Data log saved to %s.", file_path)
        except Exception as e:
            logging.exception('Failed to save data log: %s', e)
            raise

    def _sleep_with_stop_check(self, duration: float) -> None:
        """
        Sleeps for a given duration, periodically checking for the stop event.

        :param duration: The total duration to sleep (in seconds).
        """
        sleep_interval = 0.1  # Check stop_event every 0.1 seconds
        end_time = time.time() + duration
        while time.time() < end_time:
            if self.stop_event.is_set():
                break
            time.sleep(min(sleep_interval, end_time - time.time()))
