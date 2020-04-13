"""Simulate an implemented design."""

import functools
import operator

from myfpga.synthesis import ModulePort
from myfpga.implementation import LogicCell

import networkx as nx


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
