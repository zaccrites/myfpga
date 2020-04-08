
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




# def parse_design(raw_design):
    # modules = list(raw_design['modules'].values())
    # assert len(modules) == 1

    # ports = modules[0]['ports']
    # cells = modules[0]['cells']


    # graph_edges = []






    # import pdb; pdb.set_trace();  # TODO: remove me
    # pass



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

    # import pdb; pdb.set_trace();  # TODO: remove me
    pass



    # TODO: Move this logic into the Design class
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

        # Find all edges between the input nodes and the output nodes.
        # Note that we do NOT use the transitive closure here.
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
        # print('Output Termination Nodes')
        # for node in graph:
        #     if graph.out_degree[node] == 0:
        #         print(node)

        print(output_node_name, '->', ', '.join(nodelist), '\n')

        # Push nodes onto a stack to evaluate the function for all
        # possible inputs (2**number_of_inputs))
        # to build a truth table.
        # TODO
        import itertools
        variables = len(logic_input_nodes)
        for inputs in itertools.product([True, False], repeat=variables):
            assert len(inputs) == variables


        # Reduce truth table to LUT width, creating new LUTs as needed.
        # 4-input LUTs seems like a good idea
        # TODO




class CombinationalCircuit:

    def __init__(self):
        pass


class Constant(CombinationalCircuit):

    pass



# import subprocess
# def run_minisat():

#     script_lines = [
#         'p cnf 3 2',

#     ]

#     clauses = [
#         (1, 2, 0),
#         (-2, 3, 0),
#     ]

#     solutions = []

#     while True:
#         # with open('minisat2.txt', 'w') as f:
#         #     f.write('\n'.join(script_lines))

#         # script_lines = [f'p cnf {len(clauses[0])} {len(clauses)}']
#         script_lines = []
#         for clause in clauses:
#             script_lines.append(' '.join(str(term) for term in clause))
#         script = '\n'.join(script_lines).encode('utf-8')

#         cmd = ['minisat', 'minisat2.txt', 'minisat2_output.txt']
#         p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#         p.communicate(input=script)

#         assert p.returncode in {10, 20}
#         is_satisfiable = p.returncode == 10

#         if not is_satisfiable:
#             return solutions

#         with open('minisat2_output.txt') as f:
#             contents = f.read()
#             try:
#                 solution = tuple(int(term) for term in contents.splitlines()[1].split())
#             except IndexError:
#                 # import pdb; pdb.set_trace();  # TODO: remove me
#                 raise

#         solutions.append(solution)
#         clauses.append(tuple(-term for term in solution))

#         if solution in solutions:
#             import pdb; pdb.set_trace();  # TODO: remove me
#             pass





def main():

    # from satispy import Variable, Cnf
    # from satispy.solver import Minisat

    # v1 = Variable('v1')
    # v2 = Variable('v2')
    # v3 = Variable('v3')

    # exp = v1 & v2 | v3

    # solver = Minisat()

    # solution = solver.solve(exp)

    # if solution.success:
    #     print( "Found a solution:")
    #     print( v1, solution[v1])
    #     print( v2, solution[v2])
    #     print( v3, solution[v3])
    # else:
    #     print( "The expression cannot be satisfied")

    # return


    parser = argparse.ArgumentParser()
    parser.add_argument('design_file')
    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
