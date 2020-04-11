"""Implement a synthesized design."""

import sys
import json
import argparse
import operator
import functools
from enum import Enum
from collections import defaultdict
from dataclasses import dataclass

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


# class FlipFlop:

#     def __init__(self, *, name, clock, input, output, rising_edge_trigger=True):
#         self.name = name
#         self.clock = clock
#         self.input = input
#         self.output = output
#         self.rising_edge_trigger = rising_edge_trigger

#     def simulate(self, net_states, last_net_states):
#         """Return the new value of the flip flop at the end of this clock cycle."""
#         last_clock_state = last_net_states[self.clock]
#         new_clock_state = net_states[self.clock]
#         is_rising_clock_edge = not last_clock_state and new_clock_state
#         is_falling_clock_edge = last_clock_state and not new_clock_state
#         triggered = (
#             (self.rising_edge_trigger and is_rising_clock_edge) or
#             (not self.rising_edge_trigger and is_falling_clock_edge)
#         )
#         if triggered:
#             return net_states[self.input]
#         else:
#             return last_net_states[self.output]

#     def __str__(self):
#         return self.name

#     def __repr__(self):
#         fmt = '{}(name={!r}, clock={!r}, input={!r}, output={!r}'
#         return fmt.format(self.__class__.__name__, self.name, self.clock, self.input, self.output)


@dataclass(frozen=True, eq=True)
class FlipFlop:
    name: str
    rising_edge_trigger: bool


from typing import List


@dataclass
class FlipFlopConfig:
    rising_edge_trigger: bool
    clock_bit: int
    data_input_bit: int
    output_bit: int


@dataclass
class LookUpTableConfig:
    config: int
    input_bits: List[int]
    output_bit: int

    def __post_init__(self):
        if len(self.input_bits) > 4:
            raise ValueError('LUT must have 4 or fewer inputs')

        num_entries = 2 ** len(self.input_bits)
        config_max_value = 2 ** num_entries - 1
        if not (0 <= self.config <= config_max_value):
            raise ValueError(f'For a {len(self.input_bits)}-LUT, the configuration value must be at most 0x{config_max_value:x}')


@dataclass(frozen=True, eq=True)
class LookUpTable:
    name: str
    config: int




# class LookUpTable:

#     def __init__(self, *, name, config, inputs, output):
#         if not (0 <= config <= 0xffff):
#             raise ValueError('Config must be a 16 bit unsigned number')
#         if len(inputs) > 4:
#             raise ValueError('LUT must have 4 or fewer inputs')
#         self.name = name
#         self.config = config
#         self.inputs = inputs
#         self.output = output

#     def simulate(self, net_states):
#         """Return the new value of the driven net at this moment in time."""
#         input_bits = [net_states[bit_id] for bit_id in self.inputs]
#         bit_masks = [(1 << i if bit_set else 0) for i, bit_set in enumerate(input_bits)]
#         config_index = functools.reduce(operator.or_, bit_masks)
#         config_mask = 1 << config_index
#         return self.config & config_mask != 0

#     def __str__(self):
#         return self.name

#     def __repr__(self):
#         config = f'0b{self.config:0{2**len(self.inputs)}b}'
#         fmt = '{}(name={!r}, config={}, inputs={!r}, output={!r})'
#         return fmt.format(self.__class__.__name__, self.name, config, self.inputs, self.output)


@dataclass(frozen=True, eq=True)
class ModulePort:
    name: str
    is_input: bool




class FlipFlopInputPort(Enum):
    clock = 0
    data = 1

# @dataclass(frozen=True, eq=True)
# class FlipFlopInputConnection:
#     ff: FlipFlop
#     port: FlipFlopInputPort


# @dataclass(frozen=True, eq=True)
# class LookUpTableInputConnection:
#     lut: LookUpTable
#     port: int


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

        self.lookup_tables = {}
        self.flip_flops = {}
        for raw_name, cell in module['cells'].items():
            name, lut_config = self._read_lut_config(raw_name, cell)
            if lut_config is not None:
                self.lookup_tables[name] = lut_config
                continue
            name, ff_config = self._read_ff_config(raw_name, cell)
            if ff_config is not None:
                self.flip_flops[name] = ff_config
                continue
            raise NotImplementedError(cell['type'])

    @staticmethod
    def _read_lut_config(raw_name, cell):
        if cell['type'] != '$lut':
            return None, None
        name = f'$lut${raw_name.split("$")[-1]}'
        try:
            return name, LookUpTableConfig(
                config=int(cell['parameters']['LUT'], 2),
                input_bits=cell['connections']['A'],
                output_bit=cell['connections']['Y'][0],
            )
        except ValueError as exc:
            raise ValueError(f'LUT {name}: {exc}') from exc

    @staticmethod
    def _read_ff_config(raw_name, cell):
        if cell['type'] == '$_DFF_P_':
            name = f'$dff_p${raw_name.split("$")[-1]}'
            rising_edge_trigger = True
        elif cell['type'] == '$_DFF_N_':
            name = f'$dff_n${raw_name.split("$")[-1]}'
            rising_edge_trigger = False
        else:
            return None, None
        return name, FlipFlopConfig(
            rising_edge_trigger=rising_edge_trigger,
            clock_bit=cell['connections']['C'][0],
            data_input_bit=cell['connections']['D'][0],
            output_bit=cell['connections']['Q'][0],
        )


    @classmethod
    def load(cls, f):
        return cls(json.load(f))

    def build_graph(self):
        """Build a directed graph representing this design.

        The graph may be made acyclic by removing edges at flip flop outputs.

        """
        connection_inputs = defaultdict(list)
        connection_outputs = dict()

        for name, bits in self.inputs.items():
            for i, bit in enumerate(bits):
                assert bit not in connection_outputs
                port_bit_name = name if len(bits) == 1 else f'{name}[{i}]'
                module_port = ModulePort(name=port_bit_name, is_input=True)
                connection_outputs[bit] = module_port

        for name, bits in self.outputs.items():
            for i, bit in enumerate(bits):
                port_bit_name = name if len(bits) == 1 else f'{name}[{i}]'
                module_port = ModulePort(name=port_bit_name, is_input=False)
                connection_inputs[bit].append((module_port, {}))

        for name, ff_config in self.flip_flops.items():
            # assert ff_config.output_bit not in connection_outputs
            # ff = FlipFlop(name=name, rising_edge_trigger=ff_config.rising_edge_trigger)
            # ff_clock = FlipFlopInputConnection(ff=ff, port=FlipFlopInputPort.clock)
            # ff_data_input = FlipFlopInputConnection(ff=ff, port=FlipFlopInputPort.data)
            # connection_inputs[ff_config.clock_bit].add(ff_clock)
            # connection_inputs[ff_config.data_input_bit].add(ff_data_input)
            # connection_outputs[ff_config.output_bit] = ff

            assert ff_config.output_bit not in connection_outputs
            ff = FlipFlop(name=name, rising_edge_trigger=ff_config.rising_edge_trigger)
            connection_inputs[ff_config.clock_bit].append((ff, {'port': FlipFlopInputPort.clock}))
            connection_inputs[ff_config.data_input_bit].append((ff, {'port': FlipFlopInputPort.data}))
            connection_outputs[ff_config.output_bit] = ff

        for name, lut_config in self.lookup_tables.items():
            # assert lut_config.output_bit not in connection_outputs
            # lut = LookUpTable(name=name, config=lut_config.config)
            # for i, input_bit in enumerate(lut_config.input_bits):
            #     lut_input = LookUpTableInputConnection(lut=lut, port=i)
            #     connection_inputs[input_bit].add(lut_input)
            # connection_outputs[lut_config.output_bit] = lut

            assert lut_config.output_bit not in connection_outputs
            lut = LookUpTable(name=name, config=lut_config.config)
            for i, input_bit in enumerate(lut_config.input_bits):
                # lut_input = LookUpTableInputConnection(lut=lut, port=i)
                connection_inputs[input_bit].append((lut, {'port': i}))
            connection_outputs[lut_config.output_bit] = lut


        graph = nx.DiGraph()
        for bit_id, source in connection_outputs.items():
            for sink, attrs in connection_inputs[bit_id]:
                graph.add_edge(source, sink, **attrs)
        return graph

    def __str__(self):
        return self.name


@dataclass(frozen=True, eq=True)
class LogicCell:
    lut: LookUpTable
    ff: FlipFlop


@dataclass(frozen=True, eq=True)
class LogicCellInputConnection:
    lut_port: int
    logic_cell: LogicCell


class ImplementationError(RuntimeError):
    # TODO: Take reference to object which caused the error
    # TODO: Report errors using verilog source file and line where possible
    pass



class Implementation:

    def __init__(self, design):
        self.design = design

        # Create a new graph with logic cells instead of discrete
        # LUTs and flip flops.
        source_graph = self.design.build_graph()
        self.graph = nx.DiGraph()

        # If this is still None at the end of the process then it just
        # means that there is no clocked logic in the design. That's okay.
        self.clock_input_port = None

        # Sanity check flip flop clocks before doing anything else.
        for source, sink, port in source_graph.edges.data('port'):
            if isinstance(sink, FlipFlop) and port is FlipFlopInputPort.clock:
                # At this time FFs must be clocked by a dedicated clock tree,
                # not from programmable logic.
                if not (isinstance(source, ModulePort) and source.is_input):
                    raise ImplementationError(f'{sink.ff.name} clocked from non-module input {source.name}')

                # At this time only a single clock domain is supported
                if self.clock_input_port is None:
                    self.clock_input_port = source
                elif source is not self.clock_input_port:
                    raise ImplementationError(f'{sink.ff.name} should be clocked by main clock source {self.clock_input_port.name}, not {source.name}')

        # When we replace nodes with a logic cell, this is how we will
        # reconstruct the connections in the new graph.
        node_replacements = dict()
        merged_nodes = set()

        # First pass: find LUTs which feed directly into a single FF
        # We cannot merge a LUT and flip flop if anything other than the
        # FF input is using the LUT output.
        for source, sink, port in source_graph.edges.data('port'):
            criteria = (
                isinstance(source, LookUpTable)
                and isinstance(sink, FlipFlop)
                and port is FlipFlopInputPort.data
                and source_graph.out_degree(source) == 1
            )
            if criteria:
                logic_cell = LogicCell(lut=source, ff=sink)
                # self.graph.add_node(logic_cell)
                node_replacements[source] = logic_cell
                node_replacements[sink] = logic_cell
                merged_nodes.add((source, sink))

        def _replace_node(node, *, is_source):
            if node in node_replacements:
                return node_replacements[node]
            elif isinstance(node, LookUpTable):
                logic_cell = LogicCell(lut=node, ff=None)
                node_replacements[node] = logic_cell
                return logic_cell
            elif isinstance(node, FlipFlop):
                logic_cell = LogicCell(lut=None, ff=node)
                node_replacements[node] = logic_cell
                return logic_cell
            elif isinstance(node, ModulePort):
                assert is_source == node.is_input
                return node
            elif not isinstance(node, LogicCell):
                raise NotImplementedError(node)

        # Second pass: convert the remaining LUTs and FFs into standlone logic cells.
        for source, sink, port in source_graph.edges.data('port'):
            if (source, sink) in merged_nodes:
                continue
            source = _replace_node(source, is_source=True)
            sink = _replace_node(sink, is_source=False)

            # Strip off FF input ports since they're not useful anymore.
            if isinstance(port, int):
                self.graph.add_edge(source, sink, port=port)
            else:
                self.graph.add_edge(source, sink)



# Use MiniSat for solving routing. Each switch in each switchbox can be
# represented as a variable (or two, really-- one in each direction).
# The desired connections between logic and I/O blocks are the clauses,
# insisting that certain nodes be connected and others not connected.
# We only need a single solution in that case, but may ask the solver
# to generate a handful for purposes of selecting the most efficient.
# I can modify the minisat_driver to stop at N solutions, or just
# call the binary normally if only a single solution is required.
#
# See also https://codingnest.com/modern-sat-solvers-fast-neat-and-underused-part-2-of-n/
#
# This also means that we don't necessarily need a universal gate
# to make things easy. A disjoint gate will work too, we may just need
# to shuffle connections around to find the right way to connect things.
# The SAT solver may be able to solve for that too.
# We can also shuffle LUT inputs as needed.
#
# Sympy's boolean simplification may help here as there are likely to be
# many, many variables and clauses.

# Constraints:
'''
    1. A switch may be driven-left, driven-top, or closed (not driven).
       It may NOT be driven in both directions at the same time.

    2.

'''

# How do we avoid bad solutions like huge unnecessary loops?
# Do we include constraints that try to guide the solver to only using
# as few hops as possible, removing them when necessary if the system
# is not solvable? Or do we start with something general and add constraints
# to prod the solver to something more reasonable?
# Simulated annealing will probably help here, as it can add constraints
# and see if they help or hurt in each generation as it drives towards an
# optimal solution.




class Simulator:

    # TODO: Simulate implementation instead of Design
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

    implementation = Implementation(design)


    for source, sink, attrs in implementation.graph.edges.data():
        print('\n', source, '\n\t-> ', sink, '\n\t: ', attrs)


    return

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
