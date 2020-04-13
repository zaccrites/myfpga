
# myfpga

A DIY FPGA Architecture

The FPGA is implemented in SystemVerilog and simulated using a Verilator
model linked against a C++ launcher.

Designs meant to run on myfpga within the simulation are written in Verilog-2005
and may be simulated themselves using Verilator or using the simulator
built into the myfpga toolchain.
The toolchain will perform place-and-route and generate a bitstream,
which the myfpga simulation C++ launcher will load into the simulated FPGA.


## Development

TODO

```
apt install build-essential cmake ninja verilator yosys z3
```
