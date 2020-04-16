"""myfpga synthesis toolchain"""

import sys
import argparse

from myfpga.synthesis import Design
from myfpga.implementation import Implementation
from myfpga.simulation import Simulator
from myfpga.routing import DeviceTopology, route_design


# Process:
#   - Pre-synthesis simulation: Verilator
#   - Synthesis: Yosys
#   - Implementation: custom toolchain
#   - Post-implementation simulation: custom simulator
#   - Place and Route: custom toolchain via simulated annealing
#   - Bitstream Generation: custom toolchain
#   - Operation: Load bitstream into simulated FPGA running within Verilator
#                or into the simulated FPGA running within a real FPGA.


# TODO: Remove this

class MyDesignSimulator(Simulator):

    def tick(self):
        self.set_input('i_Clock', 1)
        self.eval()
        self.set_input('i_Clock', 0)
        self.eval()


def run(args):
    with open(args.design_file, 'r') as f:
        design = Design.load(f)

    implementation = Implementation(design)
    # simulator = MyDesignSimulator(implementation)

    # for i in range(16):
    #     # TODO: This fails if i_Reset is not used in the implemented design.
    #     # simulator.set_input('i_Reset', 1 if i == 4 else 0)

    #     simulator.tick()
    #     data = simulator.get_output('o_Data')
    #     print(f'Clock {i+1}: o_Data = {data}')

    device_topology = DeviceTopology(width=3, height=3)
    routed_design = route_design(implementation, device_topology)


def main():
    parser = argparse.ArgumentParser(description='myfpga synthesis toolchain')
    parser.add_argument('design_file')
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == '__main__':
    main()
