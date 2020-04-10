
import sys
import json
import argparse
import operator
import functools
from enum import Enum

import networkx as nx


# Process:
#   - Pre-synthesis simulation: Verilator
#   - Synthesis: Yosys
#   - Implementation: custom toolchain
#   - Post-implementation simulation: custom simulator
#   - Place and Route: custom toolchain via simulated annealing
#   - Bitstream Generation: custom toolchain
#   - Operation: Load bitstream into simulated FPGA running within Verilator
#                or into the simulated FPGA running within a real FPGA.


class FlipFlop:

    def __init__(self, *, name, clock, input, output, rising_edge_trigger=True):
        self.name = name
        self.clock = clock
        self.input = input
        self.output = output
        self.rising_edge_trigger = rising_edge_trigger

    def simulate(self, net_states, last_net_states):
        """Return the new value of the flip flop at the end of this clock cycle."""
        last_clock_state = last_net_states[self.clock]
        new_clock_state = net_states[self.clock]
        is_rising_clock_edge = not last_clock_state and new_clock_state
        is_falling_clock_edge = last_clock_state and not new_clock_state
        triggered = (
            (self.rising_edge_trigger and is_rising_clock_edge) or
            (not self.rising_edge_trigger and is_falling_clock_edge)
        )
        if triggered:
            return net_states[self.input]
        else:
            return last_net_states[self.output]

    def __str__(self):
        return self.name

    def __repr__(self):
        fmt = '{}(name={!r}, clock={!r}, input={!r}, output={!r}'
        return fmt.format(self.__class__.__name__, self.name, self.clock, self.input, self.output)


class LookUpTable:

    def __init__(self, *, name, config, inputs, output):
        if not (0 <= config <= 0xffff):
            raise ValueError('Config must be a 16 bit unsigned number')
        if len(inputs) > 4:
            raise ValueError('LUT must have 4 or fewer inputs')
        self.name = name
        self.config = config
        self.inputs = inputs
        self.output = output

    def simulate(self, net_states):
        """Return the new value of the driven net at this moment in time."""
        input_bits = [net_states[bit_id] for bit_id in self.inputs]
        bit_masks = [(1 << i if bit_set else 0) for i, bit_set in enumerate(input_bits)]
        config_index = functools.reduce(operator.or_, bit_masks)
        config_mask = 1 << config_index
        return self.config & config_mask != 0

    def __str__(self):
        return self.name

    def __repr__(self):
        config = f'0b{self.config:0{2**len(self.inputs)}b}'
        fmt = '{}(name={!r}, config={}, inputs={!r}, output={!r})'
        return fmt.format(self.__class__.__name__, self.name, config, self.inputs, self.output)


class Design:

    def __init__(self, data):
        for name, module in data['modules'].items():
            if module['attributes']['top']:
                self.name = name
                break
        else:
            raise ValueError('No module found')

        self.inputs = {}
        self.outputs = {}
        for name, port in module['ports'].items():
            assert port['direction'] in {'input', 'output'}
            if port['direction'] == 'input':
                self.inputs[name] = port['bits']
            else:
                self.outputs[name] = port['bits']

        self.lookup_tables = []
        self.flip_flops = []
        for raw_name, cell in module['cells'].items():
            if cell['type'] == '$lut':
                name = f'$lut${raw_name.split("$")[-1]}'
                self.lookup_tables.append(LookUpTable(
                    name=name,
                    config=int(cell['parameters']['LUT'], 2),
                    inputs=cell['connections']['A'],
                    output=cell['connections']['Y'][0],
                ))
            elif cell['type'] == '$_DFF_P_':
                name = f'$dff_p${raw_name.split("$")[-1]}'
                self.flip_flops.append(FlipFlop(
                    name=name,
                    clock=cell['connections']['C'][0],
                    input=cell['connections']['D'][0],
                    output=cell['connections']['Q'][0],
                    rising_edge_trigger=True,
                ))
            elif cell['type'] == '$_DFF_N_':
                name = f'$dff_n${raw_name.split("$")[-1]}'
                self.flip_flops.append(FlipFlop(
                    name=name,
                    clock=cell['connections']['C'][0],
                    input=cell['connections']['D'][0],
                    output=cell['connections']['Q'][0],
                    rising_edge_trigger=False,
                ))
            else:
                raise NotImplementedError(cell['type'])

    @classmethod
    def load(cls, f):
        return cls(json.load(f))

    def build_graph(self):
        """Build a DAG representing this design."""
        graph = nx.DiGraph()

        for name, bits in self.inputs.items():
            for i, bit in enumerate(bits):
                port_bit_name = name if len(bits) == 1 else f'{name}[{i}]'
                graph.add_node(bit, is_module_port=True, name=port_bit_name)

        for lut in self.lookup_tables:
            graph.add_node(lut.output, is_module_port=False, driver=lut, clocked=False)
        for ff in self.flip_flops:
            graph.add_node(ff.output, is_module_port=False, driver=ff, clocked=True)

        for lut in self.lookup_tables:
            for input in lut.inputs:
                graph.add_edge(input, lut.output)

        # We do NOT add edges for the flip flop outputs
        # as each combinational segment of the design should be considered
        # separately.

        if not nx.is_directed_acyclic_graph(graph):
            raise RuntimeError('Could not construct a DAG for this design')
        return graph

    def __str__(self):
        return self.name


class Simulator:

    def __init__(self, design):
        self.design = design
        self.graph = self.design.build_graph()
        self.eval_order = [(node, self.graph.nodes[node]) for node in nx.topological_sort(self.graph)]

        self.net_states = {node: False for node in self.graph.nodes}
        self.previous_net_states = dict(self.net_states)
        self.clock_states = {
            node: False for node in self.graph.nodes
            if self.graph.nodes[node].get('clocked')
        }

    def set_input(self, name, value):
        try:
            port = self.design.inputs[name]
        except KeyError as exc:
            raise RuntimeError(f'No such input port "{name}"') from exc
        else:
            for i, bit in enumerate(port):
                bit_value = value & (1 << i)
                self.net_states[bit] = bool(bit_value)

    def get_output(self, name):
        try:
            port = self.design.outputs[name]
        except KeyError as exc:
            raise RuntimeError(f'No such output port "{name}"') from exc
        else:
            result = 0
            for i, bit in enumerate(port):
                bit_value = (bit == '1') if isinstance(bit, str) else int(self.net_states[bit])
                result |= bit_value << i
            return result

    def eval(self):
        clocked_bit_updates = {}
        for node, attrs in self.eval_order:
            if not attrs['is_module_port']:
                driver = attrs['driver']
                if attrs['clocked']:
                    clocked_bit_updates[node] = driver.simulate(self.net_states, self.previous_net_states)
                else:
                    self.net_states[node] = driver.simulate(self.net_states)

        # Update all clocked elements (i.e. flip flops) simultaneously
        # at the end of the simulation step.
        self.net_states.update(clocked_bit_updates)

        self.previous_net_states = dict(self.net_states)


class MyDesignSimulator(Simulator):

    def tick(self):
        self.set_input('i_Clock', 1)
        self.eval()
        self.set_input('i_Clock', 0)
        self.eval()


def run(args):
    with open(args.design_file, 'r') as f:
        design = Design.load(f)

    simulator = MyDesignSimulator(design)

    for i in range(16):
        simulator.set_input('i_Reset', 1 if i == 4 else 0)
        simulator.tick()
        data = simulator.get_output('o_Data')
        print(f'Clock {i+1}: o_Data = {data}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('design_file')
    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
