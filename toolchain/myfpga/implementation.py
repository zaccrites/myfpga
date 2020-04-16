"""Implement a design.

Convert discrete lookup tables and flip flops to logic cells.

"""

from dataclasses import dataclass

import networkx as nx

from myfpga.synthesis import LookUpTable, FlipFlop, ModulePort, FlipFlopInputPort


@dataclass(frozen=True, eq=True)
class LogicCell:
    lut: LookUpTable
    ff: FlipFlop


@dataclass(frozen=True, eq=True)
class LogicCellInputConnection:
    lut_port: int
    logic_cell: LogicCell


class ImplementationError(RuntimeError):
    # FUTURE: Take reference to object which caused the error for better reporting
    # FUTURE: Report errors using verilog source file and line where possible
    pass


class Implementation:

    # def __init__(self, design, device_config):
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

            # TODO: Find a better way of handling this
            # We basically have to redirect from the port of the now-merged
            # flip flop into the passthrough port of the LUT attached to it.
            if port is FlipFlopInputPort.data and isinstance(sink, LogicCell) and sink.lut.name == '!passthrough_lut':
                port = 0

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
            PASSTHROUGH_CONFIG = 0x1010101010101010  # assume port 0 for the connection
            lut = LookUpTable(name='!passthrough_lut', config=PASSTHROUGH_CONFIG)
            logic_cell = LogicCell(lut=lut, ff=node)
            node_replacements[node] = logic_cell
            return logic_cell
        elif isinstance(node, ModulePort):
            # At this point the design, all ports are outputs.
            # They should map directly to I/O cells as-is.
            assert is_source == node.is_input
            return node
        elif not isinstance(node, LogicCell):
            raise NotImplementedError(node)
