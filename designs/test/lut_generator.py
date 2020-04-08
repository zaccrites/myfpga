
import sys
import json
import argparse
import networkx as nx

from dataclasses import dataclass
from typing import List

from enum import Enum


@dataclass
class LogicGate:
    inputs: 'list of logic gates'
    output: 'logic gate'
    function: str



from collections import namedtuple

Net = namedtuple('Net', ['id'])







def get_cell_edges(cell):
    """Find directed graph edges for a given cell to determine dependencies."""
    connections = cell['connections']
    if cell['type'] == '$_AND_':
        inputs = connections['A'] + connections['B']
        outputs = connections['Y']
        assert len(inputs) == 2
    elif cell['type'] == '$_NOT_':
        inputs = connections['A']
        outputs = connections['Y']
        assert len(inputs) == 1
    # elif cell['type'] == '$_DFF_P_':
    #     # inputs = connections['C'] + connections['D']
    #     # outputs = connections['D']
    #     # assert len(inputs) == 2
    #     pass
    else:
        raise NotImplementedError(cell['type'])

    assert len(outputs) == 1
    output_bit_id = outputs[0]

    for input_bit_id in inputs:
        # Ignore constants
        if isinstance(input_bit_id, int):
            yield (input_bit_id, output_bit_id)


def get_cell_output(cell):
    if cell['type'] in {'$_AND_', '$_NOT_'}:
        return cell['connections']['Y'][0]
    elif cell['type'] == '$_DFF_P_':
        return cell['connections']['Q'][0]
    else:
        raise NotImplementedError(cell['type'])




class Design:

    def __init__(self, raw_design):
        modules = list(raw_design['modules'].values())
        if len(modules) != 1:
            raise ValueError('Expected exactly one module definition')
        self.ports = modules[0]['ports']
        self.cells = modules[0]['cells']

        # TODO
        self.net_drivers = {}
        for raw_name, cell in modules[0]['cells'].items():
            name = f"{cell['type']}{raw_name.split('$')[-1]}"
            self.net_drivers[get_cell_output(cell)] = name

        # self.input_bits = {}
        self.output_bits = {}
        for name, port in modules[0]['ports'].items():
            if port['direction'] == 'input':
                for i, bit_id in enumerate(port['bits']):
                    self.net_drivers[bit_id] = f'{name}[{i}]'
            else:
                assert port['direction'] == 'output'
                for i, bit_id in enumerate(port['bits']):
                    self.output_bits[bit_id] = f'{name}[{i}]'

        # TODO: Find a better way of dealing with flip flops.
        # They're *like* module outputs, but only in that they
        # are edges for what to consider within a single clock cycle.
        for raw_name, cell in modules[0]['cells'].items():
            if 'DFF' in cell['type']:
                # Ugh, they're not output bits. More like "termination bits" or something.
                name = f"{cell['type']}{raw_name.split('$')[-1]}"
                self.output_bits[get_cell_output(cell)] = name

        # import pdb; pdb.set_trace();  # TODO: remove me
        pass



    @classmethod
    def load(cls, f):
        return cls(json.load(f))

    def build_combinational_logic_dependency_graph(self):
        edges = []
        for cell in self.cells.values():
            if 'DFF' not in cell['type']:

                # for edge in get_cell_edges(cell):
                #     if edge[0] not in self.input_bits:
                #         edges.append(edge)

                edges.extend(get_cell_edges(cell))

        # TODO: Handle flip flops. What about inputs and outputs?

        return nx.DiGraph(edges)




    def construct_lookup_tables(self):
        pass






class Circuit:

    def __init__(self):
        pass


def path_to_edge_list(path):
    """Convert e.g. [3, 10, 11] into [(3, 10), (10, 11)]."""
    last_node = None
    for node in path:
        if last_node is not None:
            yield (last_node, node)
        last_node = node





def run(args):
    with open(args.design_file, 'r') as f:
        design = Design.load(f)

    graph = design.build_combinational_logic_dependency_graph()


    # TODO: Handle constants in the logic as well. Currently an output
    # fed by a constant doesn't appear in the output.
    #
    # A constant should appear as a True or False node in the
    # function evaluation stack.


    # TODO: This strategy may not produce efficient results if a single
    # shared signal is used by multiple outputs. If computing that shared
    # signal is expensive to compute and not fed into a flip flop,
    # the logic needed to compute it will be duplicated for each output
    # it feeds.

    # I think the solution is to break the graph at any place where
    # the signal is used by a FF input OR a module output, because if
    # e.g. a signal marked as an output is used as an input to another
    # signal, it will have in_degree != 0. If we consider it a
    # termination and a new starting point for the logic that follows
    # we can be certain that the correct logic function will be evaluated
    # for the output, and we can also be certain that the following logic
    # will not have to duplicate an expensive computation.


    # TODO: Move this logic into the Design class

    # Find the transitive closure of the graph so that later we can determine
    # which input nodes connect to a given output node.
    transitive_closure = nx.transitive_closure(graph)

    # First, find nodes with out_degree=0. These are the logic outputs
    # for which we will construct the LUT.
    logic_output_nodes = [node for node in transitive_closure if transitive_closure.out_degree[node] == 0]

    # Now find all edges starting from a node with in_degree=0 and at a logic output.
    # These nodes are the inputs to the logic function.
    for logic_output_node in logic_output_nodes:
        logic_input_nodes = [
            edge_start for edge_start, edge_end in transitive_closure.edges
            if edge_end == logic_output_node and transitive_closure.in_degree(edge_start) == 0
        ]

        # Find all path edges between the input nodes and the output nodes.
        # Note that we do NOT use the transitive closure here, as we want
        # to find the path through the original graph, not including the
        # additional direct paths added by the transitive closure.
        subgraph_edges = []
        for logic_input_node in logic_input_nodes:
            for path in nx.all_simple_paths(graph, logic_input_node, logic_output_node):
                subgraph_edges.extend(path_to_edge_list(path))


        # Do a topological sort to find function evaluation order.
        subgraph = nx.DiGraph(subgraph_edges)
        subgraph_node_ordering = list(nx.topological_sort(subgraph))

        # TODO: Clean up the whole input/ff interface issue here
        # TODO: Handle constants
        nodelist = [design.net_drivers[bit_id] for bit_id in subgraph_node_ordering]

        # TODO: This is another consequence of this bad interface.
        # Since the input to a FF and a module output are both termination nodes,
        # we have to try two different ways of getting its name.
        try:
            # In case we're feeding a module output
            output_node_name = design.output_bits[logic_output_node]
        except KeyError:
            # In case we're feeding the input of a flip flop
            output_node_name = design.net_drivers[logic_output_node]

        # TODO: Use this logic to find termination nodes and make it a feature
        # of the Design class
        # ===============================================
        # print('Output Termination Nodes')
        # for node in graph:
        #     if graph.out_degree[node] == 0:
        #         print(node)
        # ===============================================

        print(output_node_name, '->', ', '.join(nodelist), '\n')

        # Use Tseytin transformation to convert the design into CNF and
        # feed to Minisat to solve for the LUT entries. In that case it
        # may be better to use the normal techmap logic gates instead of
        # the AIG ones (even if NAND is allowed) because any logic gates
        # can be converted into CNF, not just AND and NOT gates.
        # The MUX CNF sub expression isn't given on Wikipedia,
        # but I can derive it and consider it as another logic gate type.
        # https://en.wikipedia.org/wiki/Tseytin_transformation
        #
        # I still need to figure out how constants will affect the derived
        # CNF expressions. For now I'm assuming it will just remove variables
        # in clauses related to the affected gates.
        #
        # TODO

        # Reduce truth table to LUT width, creating new LUTs as needed.
        # 4-input LUTs seems like a good idea
        # https://electronics.stackexchange.com/a/169535
        # TODO

        # Don't bother trying to simulate anything until the logic cells
        # are generated.

        # Place and route
        # https://www.intel.com/content/dam/www/programmable/us/en/pdfs/literature/wp/wp-01003.pdf




class CombinationalCircuit:

    def __init__(self):
        pass


class Constant(CombinationalCircuit):

    pass




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('design_file')
    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
