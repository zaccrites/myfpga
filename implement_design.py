"""Implement a synthesized design."""

import sys
import json
import argparse
import operator
import functools
from typing import List
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


@dataclass
class FlipFlopConfig:
    rising_edge_trigger: bool
    clock_bit: int
    data_input_bit: int
    output_bit: int


@dataclass(frozen=True, eq=True)
class FlipFlop:
    name: str
    rising_edge_trigger: bool


class FlipFlopInputPort(Enum):
    clock = 0
    data = 1


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
            raise ValueError(
                f'For a {len(self.input_bits)}-LUT, '
                f'the configuration value must be at most 0x{config_max_value:x}'
            )


@dataclass(frozen=True, eq=True)
class LookUpTable:
    name: str
    config: int


@dataclass(frozen=True, eq=True)
class ModulePort:
    name: str
    bit_index: int
    is_input: bool


@dataclass(frozen=True, eq=True)
class LogicCell:
    lut: LookUpTable
    ff: FlipFlop


@dataclass(frozen=True, eq=True)
class LogicCellInputConnection:
    lut_port: int
    logic_cell: LogicCell


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
                module_port = ModulePort(name=name, bit_index=i, is_input=True)
                connection_outputs[bit] = module_port

        for name, bits in self.outputs.items():
            for i, bit in enumerate(bits):
                module_port = ModulePort(name=name, bit_index=i, is_input=False)
                connection_inputs[bit].append((module_port, {}))

        for name, ff_config in self.flip_flops.items():
            assert ff_config.output_bit not in connection_outputs
            ff = FlipFlop(name=name, rising_edge_trigger=ff_config.rising_edge_trigger)
            connection_inputs[ff_config.clock_bit].append(
                (ff, {'port': FlipFlopInputPort.clock}))
            connection_inputs[ff_config.data_input_bit].append(
                (ff, {'port': FlipFlopInputPort.data}))
            connection_outputs[ff_config.output_bit] = ff

        for name, lut_config in self.lookup_tables.items():
            assert lut_config.output_bit not in connection_outputs
            lut = LookUpTable(name=name, config=lut_config.config)
            for i, input_bit in enumerate(lut_config.input_bits):
                connection_inputs[input_bit].append((lut, {'port': i}))
            connection_outputs[lut_config.output_bit] = lut

        graph = nx.DiGraph()
        for bit_id, source in connection_outputs.items():
            for sink, attrs in connection_inputs[bit_id]:
                graph.add_edge(source, sink, **attrs)
        return graph

    def __str__(self):
        return self.name


class ImplementationError(RuntimeError):
    # FUTURE: Take reference to object which caused the error for better reporting
    # FUTURE: Report errors using verilog source file and line where possible
    pass


class Implementation:

    def __init__(self, design):
        self.design = design
        source_graph = self.design.build_graph()
        self.clock_input_port = self._sanity_check_flip_flops(source_graph)
        self.graph = self._create_logic_cells(source_graph)

    @staticmethod
    def _sanity_check_flip_flops(graph):
        """Verify that flip flops are configured as expected.

        At this time only a single clock domain is supported.
        If there is clocked logic in the design, it must come from a
        module input port and all flip flops must use it.
        This module port is returned if found, or None if there is
        no clocked logic in the design.

        """
        clock_input_port = None
        for source, sink, port in graph.edges.data('port'):
            if isinstance(sink, FlipFlop) and port is FlipFlopInputPort.clock:
                # At this time FFs must be clocked by a dedicated clock tree,
                # not from programmable logic.
                if not (isinstance(source, ModulePort) and source.is_input):
                    raise ImplementationError(
                        f'{sink.ff.name} clocked from non-module input {source.name}'
                    )

                if clock_input_port is None:
                    clock_input_port = source
                elif source is not clock_input_port:
                    raise ImplementationError(
                        f'{sink.ff.name} should be clocked by main clock source '
                        f'{clock_input_port.name}, not {source.name}'
                    )
        return clock_input_port

    @classmethod
    def _create_logic_cells(cls, source_graph):
        """Merge LUTs and flip flops in the design into combined logic cells.

        Sometimes this cannot be done, such as when an input feeds directly
        into a flip flop or when the output of a LUT is used before it
        passes into a flip flop. In that case additional logic cells are
        created with passthrough LUTs or which bypass their flip flop as needed.

        """
        graph = nx.DiGraph()

        # When we replace nodes with a logic cell, this is how we will
        # reconstruct the connections in the new graph.
        node_replacements = dict()

        # First pass: find LUTs which feed directly into a single FF
        # We cannot merge a LUT and flip flop if anything other than the
        # FF input is using the LUT output.
        for source, sink, port in list(source_graph.edges.data('port')):
            criteria = (
                isinstance(source, LookUpTable)
                and isinstance(sink, FlipFlop)
                and port is FlipFlopInputPort.data
                and source_graph.out_degree(source) == 1
            )
            if criteria:
                logic_cell = LogicCell(lut=source, ff=sink)
                node_replacements[source] = logic_cell
                node_replacements[sink] = logic_cell
                source_graph.remove_edge(source, sink)

        # Second pass: convert the remaining LUTs and FFs into standlone logic cells.
        for source, sink, port in source_graph.edges.data('port'):
            source = cls._replace_node(source, node_replacements, is_source=True)
            sink = cls._replace_node(sink, node_replacements, is_source=False)

            # Strip off FF input ports since they're not useful anymore.
            if isinstance(port, int):
                graph.add_edge(source, sink, port=port)
            elif port is FlipFlopInputPort.clock:
                graph.add_edge(source, sink, port='clock')
            else:
                graph.add_edge(source, sink)

        return graph

    @classmethod
    def _replace_node(cls, node, node_replacements, *, is_source):
        # Logic cells of combined LUT and FF are already in node_replacements
        if node in node_replacements:
            return node_replacements[node]
        elif isinstance(node, LookUpTable):
            # Otherwise we can create a new logic cell with a bypassed flip flop
            logic_cell = LogicCell(lut=node, ff=None)
            node_replacements[node] = logic_cell
            return logic_cell
        elif isinstance(node, FlipFlop):
            # ... or with a passthrough LUT.
            logic_cell = LogicCell(lut=None, ff=node)
            node_replacements[node] = logic_cell
            return logic_cell
        elif isinstance(node, ModulePort):
            # At this point the design, all ports are outputs.
            # They should map directly to I/O cells as-is.
            assert is_source == node.is_input
            return node
        elif not isinstance(node, LogicCell):
            raise NotImplementedError(node)


class Simulator:

    def __init__(self, implementation):
        self.implementation = implementation
        graph = implementation.graph.copy()

        # Keep track of net states for the simulation.
        # We include module inputs as these drive nets,
        # but not module outputs as these are driven by other nets.
        self.net_states = {
            node: False for node in graph.nodes
            if not (isinstance(node, ModulePort) and not node.is_input)
        }
        self.last_clock_state = False
        self.current_clock_state = False
        self.pending_flip_flop_updates = {}

        # Keep track of each node's source for the simulation,
        # including the output nodes we remove later.
        self.node_sources = {
            node: self._find_node_sources(graph, node)
            for node in graph.nodes
        }

        # Remove module port nodes since they are not useful as simulation
        # nodes, only for mapping a name to a net state.
        self.inputs = self._find_module_ports(graph, inputs=True)
        self.outputs = self._find_module_ports(graph, inputs=False)
        for node in list(graph.nodes):
            if isinstance(node, ModulePort):
                graph.remove_node(node)

        # We have to break the graph wherever a logic cell uses its
        # flip flop output in order to guarantee that this is a DAG.
        edges_to_remove = [
            (source, sink) for source, sink in graph.edges
            if (isinstance(source, LogicCell) and source.ff is not None)
        ]
        for source, sink in edges_to_remove:
            graph.remove_edge(source, sink)

        # At this point we should just have a list of logic cells to evaluate.
        self.eval_order = list(nx.topological_sort(graph))
        assert all(isinstance(node, LogicCell) for node in self.eval_order)

    @staticmethod
    def _find_node_sources(graph, node):
        edges = [
            (source, attrs.get('port'))
            for source, _sink, attrs in graph.in_edges(node, data=True)
        ]
        # For the simulation we only care about flip flop data inputs
        # FUTURE: Will need to revisit this if adding support for more clock domains.
        edges = [(source, port) for source, port in edges if port != 'clock']
        # Sort by port number
        edges.sort(key=lambda edge: edge[1])
        if isinstance(node, LogicCell):
            return [source for source, port in edges]
        elif isinstance(node, ModulePort):
            if node.is_input:
                # Input nodes should never have input sources
                assert not edges
            else:
                # Output nodes should always have exactly one input source
                assert len(edges) == 1
                return [edges[0][0]]
        else:
            raise NotImplementedError(node)

    @staticmethod
    def _find_module_ports(graph, *, inputs):
        result = {}
        ports = [
            node for node in graph.nodes
            if isinstance(node, ModulePort) and node.is_input == inputs
        ]
        ports.sort(key=lambda port: (port.name, port.bit_index))
        for port in ports:
            result.setdefault(port.name, []).append(port)
        return result

    def set_input(self, name, value):
        try:
            ports = self.inputs[name]
        except KeyError as exc:
            raise RuntimeError(f'No such input port "{name}"') from exc
        else:
            for i, port in enumerate(ports):
                bit_value = value & (1 << i)
                self.net_states[port] = bool(bit_value)

    def get_output(self, name):
        try:
            ports = self.outputs[name]
        except KeyError as exc:
            raise RuntimeError(f'No such output port "{name}"') from exc
        else:
            result = 0
            for i, port in enumerate(ports):
                port_sources = self.node_sources[port]
                assert len(port_sources) == 1
                result |= int(self.net_states[port_sources[0]]) << i
            return result

    @property
    def is_rising_clock_edge(self):
        return self.current_clock_state and not self.last_clock_state

    @property
    def is_falling_clock_edge(self):
        return self.last_clock_state and not self.current_clock_state

    def _simulate_logic_cell(self, logic_cell):
        # Simulate the LUT
        input_sources = self.node_sources[logic_cell]
        input_bits = [self.net_states[source] for source in input_sources]
        bit_masks = [(1 << i if bit_set else 0) for i, bit_set in enumerate(input_bits)]
        config_index = functools.reduce(operator.or_, bit_masks)
        config_mask = 1 << config_index
        lut_output = logic_cell.lut.config & config_mask != 0

        # Simulate the flip flop and select an output.
        # If the flip flop is selected then the output won't change until
        # the simulation step is finished.
        if logic_cell.ff is not None:
            triggered = (
                (logic_cell.ff.rising_edge_trigger and self.is_rising_clock_edge) or
                (not logic_cell.ff.rising_edge_trigger and self.is_falling_clock_edge)
            )
            if triggered:
                self.pending_flip_flop_updates[logic_cell] = lut_output
        else:
            self.net_states[logic_cell] = lut_output

    def eval(self):
        self.current_clock_state = self.net_states[self.implementation.clock_input_port]

        for logic_cell in self.eval_order:
            self._simulate_logic_cell(logic_cell)

        # Update all clocked elements (i.e. flip flops) simultaneously
        # at the end of the simulation step.
        self.net_states.update(self.pending_flip_flop_updates)
        self.pending_flip_flop_updates.clear()

        self.last_clock_state = self.current_clock_state


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
    simulator = MyDesignSimulator(implementation)

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
