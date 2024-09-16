library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity uart_testbench is
end uart_testbench;

architecture Behavioral of uart_testbench is

    -- UART configuration constants
    constant CLK_FREQ    : integer := 100_000_000; -- System clock frequency (100 MHz)
    constant BAUD_RATE   : integer := 9600;
    constant BIT_PERIOD  : time    := 1 sec / BAUD_RATE;
    constant CLK_PERIOD  : time    := 1 sec / CLK_FREQ;

    -- Signals
    signal clk          : std_logic := '0';
    signal reset_n      : std_logic := '0';
    signal tx           : std_logic := '1'; -- UART transmit line (from testbench to FPGA)
    signal rx           : std_logic := '1'; -- UART receive line (from FPGA to testbench)
    signal tx_data      : std_logic_vector(7 downto 0);
    signal tx_start     : std_logic := '0';
    signal tx_busy      : std_logic := '0';

begin

    ---------------------------------------------------------------------------
    -- Clock generation process
    ---------------------------------------------------------------------------
    clk_process : process
    begin
        clk <= '0';
        wait for CLK_PERIOD / 2;
        clk <= '1';
        wait for CLK_PERIOD / 2;
    end process clk_process;

    ---------------------------------------------------------------------------
    -- UART transmission process
    ---------------------------------------------------------------------------
    uart_transmit_process : process
        procedure uart_send_byte(data : in std_logic_vector(7 downto 0)) is
        begin
            -- Start bit
            tx <= '0';
            wait for BIT_PERIOD;

            -- Data bits (LSB first)
            for i in 0 to 7 loop
                tx <= data(i);
                wait for BIT_PERIOD;
            end loop;

            -- Stop bit
            tx <= '1';
            wait for BIT_PERIOD;

            -- Inter-byte delay
            wait for BIT_PERIOD * 2;
        end procedure uart_send_byte;

    begin
        -- Initialize reset
        reset_n <= '0';
        wait for 100 ns;
        reset_n <= '1';
        wait for 100 ns;

        -- Send 'I' character (ASCII 0x49) for Increment command
        uart_send_byte(x"49"); -- 'I'

        -- Wait between commands
        wait for 500 ms;

        -- Send '0' character (ASCII 0x30) for Power Off command
        uart_send_byte(x"30"); -- '0'

        -- Wait between commands
        wait for 500 ms;

        -- Send '1' character (ASCII 0x31) for Power On command
        uart_send_byte(x"31"); -- '1'

        -- Wait for simulation to end
        wait;
    end process uart_transmit_process;

    ---------------------------------------------------------------------------
    -- Instantiate your UART receiver (DUT)
    ---------------------------------------------------------------------------
    -- uart_receiver_inst : entity work.uart_receiver
    --     port map (
    --         clk       => clk,
    --         reset_n   => reset_n,
    --         rx        => tx,    -- Connect testbench tx to DUT rx
    --         data_out  => open,
    --         data_valid => open
    --     );

end Behavioral;
