
# myfpga

A work-in-progress DIY FPGA Architecture

The FPGA will be implemented in SystemVerilog and simulated using a Verilator
model linked against a C++ launcher.

Designs meant to run on myfpga within the simulation are written in Verilog-2005
and may be simulated themselves using Verilator or using the simulator
built into the myfpga toolchain.
The toolchain will perform place-and-route and generate a bitstream,
which the myfpga simulation C++ launcher will load into the simulated FPGA.


## Development

The main toolchain is implemented in Rust and can be
[installed via rustup](https://www.rust-lang.org/learn/get-started).
Some supplementary tools are also required to build the simulator
and to do target design synthesis.

```
apt install build-essential cmake ninja-build verilator yosys
```
