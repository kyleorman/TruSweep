# main.py
"""This module contains the main application code for the TruSweep GUI."""

# Import the required modules
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from queue import Queue
import json
import os
import sys
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from power_supply import PowerSupplyController
from uart_controller import UARTController
from voltage_sweep_manager import VoltageSweepManager

# Configure logging
logging.basicConfig(
    filename='voltage_sweep.log',
    level=logging.WARNING,  # Allow setting via GUI
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Global variables
config_data = {
    'uart_port': '/dev/ttyUSB0',
    'uart_baud_rate': 9600,
    'device_ip': '10.1.120.107',
    'device_protocol': 'INSTR',
    'max_voltage': 30.0,
    'max_current': 5.0,
    'logging_level': 'WARNING',  # New configurable logging level
}


# Helper function to get the application path
def resource_path(relative_path):
    """Get the absolute path to a resource file for PyInstaller

    :param relative_path: The relative path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores the path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# GUI Application Class
class TruSweepApp:
    """TruSweepApp class for the TruSweep GUI application."""

    def __init__(self, root):
        self.root = root
        self.root.title("TruSweep")
        self.gui_queue = Queue()
        self.stop_event = threading.Event()
        self.data_log = []

        # Initialize plot-related variables
        self.plot_window = None  # To hold the plot window reference
        self.figure = None
        self.ax = None
        self.line = None
        self.canvas = None

        self.create_widgets()
        self.process_queue()

    def create_widgets(self):
        """Create the widgets for the main application window."""
        # Create the menu bar
        self.create_menu()

        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky='NSEW')

        # Configure grid weights for self.main_frame
        for i in range(15):  # Adjust range based on the number of rows
            self.main_frame.rowconfigure(i, weight=1)
        for i in range(4):  # Adjust range based on the number of columns
            self.main_frame.columnconfigure(i, weight=1)

        # Configure root window to expand with content
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Input fields and labels
        ttk.Label(self.main_frame, text="Channel 1 Voltage (V):").grid(
            row=0, column=0, sticky='E')
        self.entry_ch1 = ttk.Entry(self.main_frame)
        self.entry_ch1.grid(row=0, column=1, sticky='W')

        ttk.Label(self.main_frame, text="Channel 2 Voltage (V):").grid(
            row=1, column=0, sticky='E')
        self.entry_ch2 = ttk.Entry(self.main_frame)
        self.entry_ch2.grid(row=1, column=1, sticky='W')

        ttk.Label(self.main_frame, text="Channel 3 Voltage (V):").grid(
            row=2, column=0, sticky='E')
        self.entry_ch3 = ttk.Entry(self.main_frame)
        self.entry_ch3.grid(row=2, column=1, sticky='W')

        # Channel to sweep
        ttk.Label(self.main_frame, text="Channel to Sweep:").grid(
            row=3, column=0, sticky='E')
        self.var_channel = tk.IntVar(value=1)
        ttk.Radiobutton(self.main_frame, text="Channel 1",
                        variable=self.var_channel, value=1).grid(
            row=3, column=1, sticky='E')
        ttk.Radiobutton(self.main_frame, text="Channel 2",
                        variable=self.var_channel, value=2).grid(
            row=3, column=2, sticky='W')
        ttk.Radiobutton(self.main_frame, text="Channel 3",
                        variable=self.var_channel, value=3).grid(
            row=3, column=3, sticky='W')

        # Sweep parameters
        ttk.Label(self.main_frame, text="Starting Voltage (V):").grid(
            row=4, column=0, sticky='E')
        self.entry_start_voltage = ttk.Entry(self.main_frame)
        self.entry_start_voltage.grid(row=4, column=1, sticky='W')

        ttk.Label(self.main_frame, text="End Voltage (V):").grid(
            row=5, column=0, sticky='E')
        self.entry_end_voltage = ttk.Entry(self.main_frame)
        self.entry_end_voltage.grid(row=5, column=1, sticky='W')

        ttk.Label(self.main_frame, text="Increment Step Size (V):").grid(
            row=6, column=0, sticky='E')
        self.entry_step_size = ttk.Entry(self.main_frame)
        self.entry_step_size.grid(row=6, column=1, sticky='W')

        self.label_increment_time = ttk.Label(
            self.main_frame, text="Time Between Increments (s):")
        self.entry_increment_time = ttk.Entry(self.main_frame)

        # UART and power cycling options
        self.uart_control_var = tk.BooleanVar()
        ttk.Checkbutton(self.main_frame, text="Enable UART Control",
                        variable=self.uart_control_var,
                        command=self.toggle_uart_control).grid(
            row=8, column=0, columnspan=2, sticky='W')

        self.power_cycle_var = tk.BooleanVar()
        ttk.Checkbutton(self.main_frame, text="Enable Power Cycling",
                        variable=self.power_cycle_var,
                        command=self.toggle_power_cycling).grid(
            row=9, column=0, columnspan=2, sticky='W')

        # Power cycling fields
        self.label_off_time = ttk.Label(
            self.main_frame, text="Power Off Duration (s):")
        self.entry_off_time = ttk.Entry(self.main_frame)
        self.label_on_time = ttk.Label(
            self.main_frame, text="Power On Duration (s):")
        self.entry_on_time = ttk.Entry(self.main_frame)

        # Progress bar
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(
            self.main_frame, orient='horizontal', length=200, mode='determinate',
            variable=self.progress_var)
        self.progress_bar.grid(
            row=12, column=0, columnspan=4, pady=10, sticky='EW')

        # Run and Stop buttons
        self.run_button = ttk.Button(
            self.main_frame, text="Run Voltage Sweep",
            command=self.run_voltage_sweep)
        self.run_button.grid(row=13, column=0, sticky='W')
        self.stop_button = ttk.Button(
            self.main_frame, text="Stop", command=self.stop_voltage_sweep)
        self.stop_button.grid(row=13, column=1, sticky='W')

        # Show Plot Option
        self.show_plot_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.main_frame, text="Show Plot",
                        variable=self.show_plot_var,
                        command=self.toggle_plot_visibility).grid(
            row=13, column=2, sticky='W')

        # Initialize GUI state
        self.toggle_power_cycling()
        self.toggle_uart_control()

    def create_menu(self):
        """Create the menu bar for the main application window."""
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        # Settings menu
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(
            label="Configure", command=self.open_configuration)
        settings_menu.add_command(
            label="Load Profile", command=self.load_profile)
        settings_menu.add_command(
            label="Save Profile", command=self.save_profile)
        settings_menu.add_separator()
        settings_menu.add_command(label="Exit", command=self.root.quit)

        # Help menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="UART Setup Instructions",
                              command=self.show_uart_instructions)
        help_menu.add_command(
            label="About", command=lambda: messagebox.showinfo(
                "About", "TruSweep\nVersion 0.1.0"))

    def toggle_power_cycling(self):
        """Toggle the visibility of power cycling fields based on the checkbox."""
        if self.power_cycle_var.get():
            if not self.uart_control_var.get():
                self.label_off_time.grid(row=10, column=0, sticky='E')
                self.entry_off_time.grid(row=10, column=1, sticky='W')
                self.label_on_time.grid(row=11, column=0, sticky='E')
                self.entry_on_time.grid(row=11, column=1, sticky='W')
            else:
                self.label_off_time.grid_remove()
                self.entry_off_time.grid_remove()
                self.label_on_time.grid_remove()
                self.entry_on_time.grid_remove()
            self.label_increment_time.grid_remove()
            self.entry_increment_time.grid_remove()
        else:
            self.label_off_time.grid_remove()
            self.entry_off_time.grid_remove()
            self.label_on_time.grid_remove()
            self.entry_on_time.grid_remove()
            if not self.uart_control_var.get():
                self.label_increment_time.grid(row=7, column=0, sticky='E')
                self.entry_increment_time.grid(row=7, column=1, sticky='W')
            else:
                self.label_increment_time.grid_remove()
                self.entry_increment_time.grid_remove()

    def toggle_uart_control(self):
        """Toggle the visibility of UART control fields based on the checkbox."""
        if self.uart_control_var.get():
            self.label_increment_time.grid_remove()
            self.entry_increment_time.grid_remove()
            if self.power_cycle_var.get():
                self.label_off_time.grid_remove()
                self.entry_off_time.grid_remove()
                self.label_on_time.grid_remove()
                self.entry_on_time.grid_remove()
        else:
            if not self.power_cycle_var.get():
                self.label_increment_time.grid(row=7, column=0, sticky='E')
                self.entry_increment_time.grid(row=7, column=1, sticky='W')
            if self.power_cycle_var.get():
                self.label_off_time.grid(row=10, column=0, sticky='E')
                self.entry_off_time.grid(row=10, column=1, sticky='W')
                self.label_on_time.grid(row=11, column=0, sticky='E')
                self.entry_on_time.grid(row=11, column=1, sticky='W')

    def toggle_plot_visibility(self):
        """Toggle the visibility of the plot window based on the checkbox."""
        if self.show_plot_var.get():
            # Show the plot in a new window
            self.open_plot_window()
        else:
            # Close the plot window if it exists
            self.close_plot_window()

    def open_plot_window(self):
        """Open the plot window to display the voltage sweep plot."""
        if self.plot_window is None or not self.plot_window.winfo_exists():
            # Create a new Toplevel window for the plot
            self.plot_window = tk.Toplevel(self.root)
            self.plot_window.title("Voltage Sweep Plot")
            self.plot_window.protocol(
                "WM_DELETE_WINDOW", self.on_plot_window_close)

            # Create the plot
            self.figure = plt.Figure(figsize=(6, 4), dpi=100)
            self.ax = self.figure.add_subplot(111)
            self.line, = self.ax.plot([], [], 'b-')
            self.ax.set_xlabel('Time (s)')
            self.ax.set_ylabel('Voltage (V)')
            self.canvas = FigureCanvasTkAgg(
                self.figure, master=self.plot_window)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.pack(fill='both', expand=True)

            # Redraw the canvas
            self.canvas.draw()

    def close_plot_window(self):
        """Close the plot window if it exists."""
        if self.plot_window is not None and self.plot_window.winfo_exists():
            self.plot_window.destroy()
            self.plot_window = None

    def on_plot_window_close(self):
        """On close event for the plot window."""
        # Uncheck the Show Plot checkbox when the plot window is closed
        self.show_plot_var.set(False)
        self.close_plot_window()

    def run_voltage_sweep(self):
        """Run the voltage sweep in a separate thread."""
        def voltage_sweep_thread():
            try:
                # Disable the run button
                self.gui_queue.put(('button_state', 'disabled'))
                self.data_log = []
                # Load configuration
                config = self.load_sweep_configuration()
                # Create controller instances
                psu_controller = PowerSupplyController(
                    ip_address=config_data['device_ip'],
                    protocol=config_data['device_protocol'],
                    max_voltage=config_data['max_voltage'],
                    max_current=config_data['max_current']
                )
                psu_controller.connect()

                uart_controller = None
                if config['uart_control']:
                    uart_controller = UARTController(
                        port=config_data['uart_port'],
                        baud_rate=config_data['uart_baud_rate']
                    )
                    uart_controller.connect()

                # Create VoltageSweepManager instance
                sweep_manager = VoltageSweepManager(
                    psu_controller=psu_controller,
                    uart_controller=uart_controller,
                    gui_queue=self.gui_queue,
                    stop_event=self.stop_event
                )

                # Perform the sweep
                sweep_manager.perform_sweep(config)

                # Save data log
                self.data_log = sweep_manager.data_log
                sweep_manager.save_data_log('data_log.csv')

                # Close connections
                psu_controller.close()
                if uart_controller:
                    uart_controller.close()

                # Notify completion
                self.gui_queue.put(
                    ('info', "Voltage sweep completed successfully."))

            except Exception as e:
                logging.error("An error occurred: %s", e)
                self.gui_queue.put(('error', f"An error occurred: {e}"))
            finally:
                # Re-enable the run button
                self.gui_queue.put(('button_state', 'normal'))

        # Start the voltage sweep in a new thread
        self.stop_event.clear()
        thread = threading.Thread(target=voltage_sweep_thread)
        thread.start()

    def stop_voltage_sweep(self):
        """Stop the voltage sweep by setting the stop event."""
        self.stop_event.set()
        logging.info("Voltage sweep has been stopped by the user.")

    def process_queue(self):
        """Process the GUI queue to update the UI."""
        try:
            while True:
                message = self.gui_queue.get_nowait()
                if message[0] == 'progress':
                    self.progress_var.set(message[1])
                elif message[0] == 'error':
                    messagebox.showerror("Error", message[1])
                elif message[0] == 'info':
                    messagebox.showinfo("Success", message[1])
                elif message[0] == 'data_log':
                    self.update_plot(message[1])
                elif message[0] == 'button_state':
                    self.run_button.config(state=message[1])
        except:
            pass
        self.root.after(100, self.process_queue)

    def update_plot(self, data_point):
        """Update the plot with the latest data point.

        :param data_point: The latest data point to be added to the plot
        """
        if not self.show_plot_var.get():
            return  # Do not update the plot if it's hidden
        if self.plot_window is None or not self.plot_window.winfo_exists():
            return  # Plot window is closed
        # Update the data log
        self.data_log.append(data_point)
        times = [entry['timestamp'] - self.data_log[0]['timestamp']
                 for entry in self.data_log]
        voltages = [entry['voltage'] for entry in self.data_log]
        self.line.set_xdata(times)
        self.line.set_ydata(voltages)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def load_sweep_configuration(self):
        """Load the sweep configuration from the GUI fields."""
        # Get values from the GUI
        config = {}
        try:
            config['ch1_voltage'] = float(self.entry_ch1.get())
            config['ch2_voltage'] = float(self.entry_ch2.get())
            config['ch3_voltage'] = float(self.entry_ch3.get())
            config['start_voltage'] = float(self.entry_start_voltage.get())
            config['end_voltage'] = float(self.entry_end_voltage.get())
            config['step_size'] = float(self.entry_step_size.get())
            config['channel'] = self.var_channel.get()
            config['power_cycle'] = self.power_cycle_var.get()
            config['uart_control'] = self.uart_control_var.get()

            if config['power_cycle']:
                if not config['uart_control']:
                    config['off_time'] = float(self.entry_off_time.get())
                    config['on_time'] = float(self.entry_on_time.get())
            elif not config['uart_control']:
                config['increment_time'] = float(
                    self.entry_increment_time.get())

        except ValueError as e:
            self.gui_queue.put(('error', f"Invalid input: {e}"))
            raise

        # Additional validation can be added here
        return config

    def open_configuration(self):
        """Open the configuration settings window."""
        def save_configuration():
            try:
                config_data['uart_port'] = uart_port_var.get()
                config_data['uart_baud_rate'] = int(uart_baud_rate_entry.get())
                config_data['device_ip'] = device_ip_entry.get()
                config_data['device_protocol'] = device_protocol_entry.get()
                config_data['max_voltage'] = float(max_voltage_entry.get())
                config_data['max_current'] = float(max_current_entry.get())
                config_data['logging_level'] = logging_level_var.get()

                # Update logging level
                logging.getLogger().setLevel(config_data['logging_level'])

                messagebox.showinfo("Configuration Saved",
                                    "Settings have been updated.")
                config_window.destroy()
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {e}")

        def load_configuration_from_file():
            """Load configuration settings from a JSON file."""
            file_path = filedialog.askopenfilename(
                title="Load Configuration",
                filetypes=[("JSON Files", "*.json")])
            if file_path:
                try:
                    with open(file_path, 'r', encoding="utf-8") as f:
                        loaded_config = json.load(f)
                        # Update the entries with loaded config
                        uart_port_var.set(loaded_config.get(
                            'uart_port', config_data['uart_port']))
                        uart_baud_rate_entry.delete(0, tk.END)
                        uart_baud_rate_entry.insert(0, str(loaded_config.get(
                            'uart_baud_rate', config_data['uart_baud_rate'])))
                        device_ip_entry.delete(0, tk.END)
                        device_ip_entry.insert(0, loaded_config.get(
                            'device_ip', config_data['device_ip']))
                        device_protocol_entry.delete(0, tk.END)
                        device_protocol_entry.insert(0, loaded_config.get(
                            'device_protocol', config_data['device_protocol']))
                        max_voltage_entry.delete(0, tk.END)
                        max_voltage_entry.insert(0, str(loaded_config.get(
                            'max_voltage', config_data['max_voltage'])))
                        max_current_entry.delete(0, tk.END)
                        max_current_entry.insert(0, str(loaded_config.get(
                            'max_current', config_data['max_current'])))
                        logging_level_var.set(loaded_config.get(
                            'logging_level', config_data['logging_level']))
                        messagebox.showinfo(
                            "Configuration Loaded",
                            "Configuration loaded successfully.")
                except Exception as e:
                    messagebox.showerror(
                        "Error", f"Failed to load configuration: {e}")

        def save_configuration_to_file():
            """Save configuration settings to a JSON file."""
            file_path = filedialog.asksaveasfilename(
                title="Save Configuration", defaultextension=".json",
                filetypes=[("JSON Files", "*.json")])
            if file_path:
                try:
                    to_save = {
                        'uart_port': uart_port_var.get(),
                        'uart_baud_rate': int(uart_baud_rate_entry.get()),
                        'device_ip': device_ip_entry.get(),
                        'device_protocol': device_protocol_entry.get(),
                        'max_voltage': float(max_voltage_entry.get()),
                        'max_current': float(max_current_entry.get()),
                        'logging_level': logging_level_var.get(),
                    }
                    with open(file_path, 'w', encoding="utf-8") as f:
                        json.dump(to_save, f, indent=4)
                    messagebox.showinfo(
                        "Configuration Saved",
                        "Configuration saved successfully.")
                except Exception as e:
                    messagebox.showerror(
                        "Error", f"Failed to save configuration: {e}")

        config_window = tk.Toplevel(self.root)
        config_window.title("Configuration Settings")

        # UART Settings
        tk.Label(config_window, text="UART Port:").grid(
            row=0, column=0, sticky='E')
        uart_port_var = tk.StringVar(value=config_data['uart_port'])
        uart_port_combo = ttk.Combobox(
            config_window, textvariable=uart_port_var)
        uart_port_combo['values'] = UARTController.list_ports()
        uart_port_combo.grid(row=0, column=1, sticky='W')

        tk.Label(config_window, text="UART Baud Rate:").grid(
            row=1, column=0, sticky='E')
        uart_baud_rate_entry = ttk.Entry(config_window)
        uart_baud_rate_entry.grid(row=1, column=1, sticky='W')
        uart_baud_rate_entry.insert(0, str(config_data['uart_baud_rate']))

        # Device Settings
        tk.Label(config_window, text="Device IP Address:").grid(
            row=2, column=0, sticky='E')
        device_ip_entry = ttk.Entry(config_window)
        device_ip_entry.grid(row=2, column=1, sticky='W')
        device_ip_entry.insert(0, config_data['device_ip'])

        tk.Label(config_window, text="Device Protocol:").grid(
            row=3, column=0, sticky='E')
        device_protocol_entry = ttk.Entry(config_window)
        device_protocol_entry.grid(row=3, column=1, sticky='W')
        device_protocol_entry.insert(0, config_data['device_protocol'])

        # Safety Limits
        tk.Label(config_window, text="Max Voltage (V):").grid(
            row=4, column=0, sticky='E')
        max_voltage_entry = ttk.Entry(config_window)
        max_voltage_entry.grid(row=4, column=1, sticky='W')
        max_voltage_entry.insert(0, str(config_data['max_voltage']))

        tk.Label(config_window, text="Max Current (A):").grid(
            row=5, column=0, sticky='E')
        max_current_entry = ttk.Entry(config_window)
        max_current_entry.grid(row=5, column=1, sticky='W')
        max_current_entry.insert(0, str(config_data['max_current']))

        # Logging Level
        tk.Label(config_window, text="Logging Level:").grid(
            row=6, column=0, sticky='E')
        logging_level_var = tk.StringVar(value=config_data['logging_level'])
        logging_level_combo = ttk.Combobox(
            config_window, textvariable=logging_level_var)
        logging_level_combo['values'] = [
            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        logging_level_combo.grid(row=6, column=1, sticky='W')

        # Buttons
        save_button = ttk.Button(
            config_window, text="Save", command=save_configuration)
        save_button.grid(row=7, column=0, pady=10)
        load_button = ttk.Button(
            config_window, text="Load from File",
            command=load_configuration_from_file)
        load_button.grid(row=7, column=1)
        save_file_button = ttk.Button(
            config_window, text="Save to File",
            command=save_configuration_to_file)
        save_file_button.grid(row=7, column=2)

    def load_profile(self):
        """Load a voltage sweep profile from a JSON file."""
        file_path = filedialog.askopenfilename(
            title="Load Profile", filetypes=[("JSON Files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'r', encoding="utf-8") as f:
                    profile = json.load(f)
                    # Update GUI fields with profile data
                    self.entry_ch1.delete(0, tk.END)
                    self.entry_ch1.insert(
                        0, str(profile.get('ch1_voltage', '')))
                    self.entry_ch2.delete(0, tk.END)
                    self.entry_ch2.insert(
                        0, str(profile.get('ch2_voltage', '')))
                    self.entry_ch3.delete(0, tk.END)
                    self.entry_ch3.insert(
                        0, str(profile.get('ch3_voltage', '')))
                    self.entry_start_voltage.delete(0, tk.END)
                    self.entry_start_voltage.insert(
                        0, str(profile.get('start_voltage', '')))
                    self.entry_end_voltage.delete(0, tk.END)
                    self.entry_end_voltage.insert(
                        0, str(profile.get('end_voltage', '')))
                    self.entry_step_size.delete(0, tk.END)
                    self.entry_step_size.insert(
                        0, str(profile.get('step_size', '')))
                    self.var_channel.set(profile.get('channel', 1))
                    self.power_cycle_var.set(profile.get('power_cycle', False))
                    self.uart_control_var.set(
                        profile.get('uart_control', False))
                    self.toggle_power_cycling()
                    self.toggle_uart_control()
                    if self.power_cycle_var.get() and not self.uart_control_var.get():
                        self.entry_off_time.delete(0, tk.END)
                        self.entry_off_time.insert(
                            0, str(profile.get('off_time', '')))
                        self.entry_on_time.delete(0, tk.END)
                        self.entry_on_time.insert(
                            0, str(profile.get('on_time', '')))
                    elif (
                        not self.power_cycle_var.get() and
                        not self.uart_control_var.get()
                    ):
                        self.entry_increment_time.delete(0, tk.END)
                        self.entry_increment_time.insert(
                            0, str(profile.get('increment_time', '')))
                    messagebox.showinfo(
                        "Profile Loaded", "Profile loaded successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load profile: {e}")

    def save_profile(self):
        """Save the current voltage sweep profile to a JSON file."""
        file_path = filedialog.asksaveasfilename(
            title="Save Profile", defaultextension=".json",
            filetypes=[("JSON Files", "*.json")])
        if file_path:
            try:
                profile = self.load_sweep_configuration()
                with open(file_path, 'w', encoding="utf-8") as f:
                    json.dump(profile, f, indent=4)
                messagebox.showinfo(
                    "Profile Saved", "Profile saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save profile: {e}")

    def show_uart_instructions(self):
        """Display UART setup instructions in a new window. Needs to be modified based on the specific setup."""
        instructions = """
        UART Setup Instructions for VHDL Testbench in Vivado:

        1. **Create a VHDL Testbench:**
           - Open Vivado and create a new project.
           - Add your UART VHDL module to the project.
           - Right-click on the module and select "Create File" -> "VHDL Test Bench".

        2. **Instantiate the UART Module:**
           - In the testbench, instantiate your UART module.
           - Connect the UART signals (e.g., tx, rx, clk, reset).

        3. **Configure Simulation Settings:**
           - Set up the clock signal in your testbench:
             ```vhdl
             clk_process : process
             begin
                 clk <= '0';
                 wait for 5 ns;
                 clk <= '1';
                 wait for 5 ns;
             end process;
             ```
           - Initialize the reset signal:
             ```vhdl
             reset <= '1';
             wait for 20 ns;
             reset <= '0';
             ```

        4. **Simulate UART Transmission:**
           - To simulate sending data over UART, toggle the `rx` line according to the UART protocol (start bit, data bits, parity bit, stop bit).
           - Example of sending a byte (0x49 for 'I'):
             ```vhdl
             process
             begin
                 -- Start bit
                 rx <= '0';
                 wait for bit_period;

                 -- Data bits (LSB first)
                 rx <= '1'; -- Bit 0
                 wait for bit_period;
                 rx <= '0'; -- Bit 1
                 -- Continue for remaining bits

                 -- Stop bit
                 rx <= '1';
                 wait for bit_period;

                 wait;
             end process;
             ```

        5. **Set Up UART on the FPGA:**
           - Assign the UART pins to the appropriate FPGA pins in the constraints file (.xdc).
           - Ensure the FPGA is programmed with the UART module.

        6. **Connect to the PC:**
           - Use a USB-UART adapter connected to the FPGA UART pins.
           - Install necessary drivers on the PC.

        7. **Testing with the Python Script:**
           - Run the Python script with UART control enabled.
           - Ensure the UART settings (port and baud rate) match between the FPGA and the script.

        **Additional Tips:**
        - Use a logic analyzer to verify UART signals.
        - Consult the FPGA and UART module documentation for specific implementation details.
        """
        # Create a new window to display the instructions
        instruction_window = tk.Toplevel(self.root)
        instruction_window.title("UART Setup Instructions")

        # Add a Text widget with a scrollbar
        text_area = tk.Text(instruction_window,
                            wrap='word', width=80, height=30)
        text_area.insert(tk.END, instructions)
        text_area.config(state='disabled')
        text_area.pack(side='left', fill='both', expand=True)

        scrollbar = ttk.Scrollbar(instruction_window, command=text_area.yview)
        scrollbar.pack(side='right', fill='y')
        text_area['yscrollcommand'] = scrollbar.set


if __name__ == '__main__':
    root = tk.Tk()
    app = TruSweepApp(root)
    root.resizable(False, False)
    root.mainloop()
