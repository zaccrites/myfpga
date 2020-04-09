"""myfpga toolchain.

Consumes Yosys JSON netlist output to simulate a Verilog design.
The plain Yosys gates and flip flops are converted into a representation
of the myfpga architecture logic elements and simulates their operation.

TODO: Perform a place-and-route of this representation and generate a bitstream.

"""

import sys
import json
import argparse
import functools
from collections import namedtuple, defaultdict

import networkx as nx



# TODO: Instead of function "cells", just convert all Yosys primitives into
# LUTs in a first pass. The second pass converts LUTs and flip flops into
# logic cells.

# A truth table can be expressed as an eight bit number.
# Here are some samples for the simple version we'll build first.
#
# a b c | y  | NOT a | a AND b | a OR b | a XOR b | b if c else a (MUX)
# ----- + -- + ----- | ------- + ------ + ------- + -------------------
# 0 0 0 | y0 |   1   |    0    |   0    |    0    |         0
# 0 0 1 | y1 |   1   |    0    |   0    |    0    |         0
# 0 1 0 | y2 |   1   |    0    |   1    |    1    |         0
# 0 1 1 | y3 |   1   |    0    |   1    |    1    |         1
# 1 0 0 | y4 |   0   |    0    |   1    |    1    |         1
# 1 0 1 | y5 |   0   |    0    |   1    |    1    |         0
# 1 1 0 | y6 |   0   |    1    |   1    |    0    |         1
# 1 1 1 | y7 |   0   |    1    |   1    |    0    |         1
# ----- + -- + ----- | ------- + ------ + ------- + -------------------
#               0x0f     0xc0     0xfc      0x3c          0xd8
#
# With three inputs we can combine at least two sequential gates
# implement a half adder, etc. but these aren't exposed as directly
# as the basic gates that Yosys emits after techmap.
# Any logical function of three variables with a single outpuit
# can be represented by the LUT.
#

# Assuming that the LUT is wired using a, b, and c in the table above.
# Note that that may not be most efficient.
# A future enhancement may try a different routing algorithm and LUT config.
NOT_GATE_LUT_CONFIG = 0x0f
AND_GATE_LUT_CONFIG = 0xc0
OR_GATE_LUT_CONFIG = 0xfc
XOR_GATE_LUT_CONFIG = 0x3c
MUX_LUT_CONFIG = 0xd8


LookUpTable = namedtuple('LookUpTable', [
    'config',
    'a_bit_id',
    'b_bit_id',
    'c_bit_id',
    'y_bit_id',
])

FlipFlop = namedtuple('FlipFlop', [
    'c_bit_id',
    'd_bit_id',
    'q_bit_id',
])

Port = namedtuple('Port', ['is_output', 'bits'])


def parse_design(raw_design):
    for module in raw_design['modules'].values():
        if module['attributes']['top']:
            break
    else:
        raise RuntimeError('Could not find top module')

    planner = CircuitPlanner()

    for name, attrs in module['ports'].items():
        assert attrs['direction'] in {'input', 'output'}
        port = Port(is_output=attrs['direction'] == 'output', bits=attrs['bits'])
        planner.add_port(name, port)

    def _get_connection_bits(cell_attrs):
        for key, bits in cell_attrs['connections'].items():
            assert len(bits) == 1
            bit_id = bits[0]
            if isinstance(bit_id, str):
                # For constants, just use True and False
                assert bit_id in {'0', '1'}
                bit_id = bit_id == '1'
            yield key, bit_id

    lut_configs = {
        '$_MUX_': MUX_LUT_CONFIG,
        '$_AND_': AND_GATE_LUT_CONFIG,
        '$_OR_': OR_GATE_LUT_CONFIG,
        '$_XOR_': XOR_GATE_LUT_CONFIG,
        '$_NOT_': NOT_GATE_LUT_CONFIG,
    }
    for name, attrs in module['cells'].items():
        cell_type = attrs['type']
        connections = dict(_get_connection_bits(attrs))
        if cell_type == '$_MUX_':
            planner.add_lut(name, LookUpTable(
                config=MUX_LUT_CONFIG,
                a_bit_id=connections['A'],
                b_bit_id=connections['B'],
                c_bit_id=connections['S'],
                y_bit_id=connections['Y'],
            ))
        elif cell_type == '$_AND_':
            planner.add_lut(name, LookUpTable(
                config=AND_GATE_LUT_CONFIG,
                a_bit_id=connections['A'],
                b_bit_id=connections['B'],
                c_bit_id=None,
                y_bit_id=connections['Y'],
            ))
        elif cell_type == '$_OR_':
            planner.add_lut(name, LookUpTable(
                config=OR_GATE_LUT_CONFIG,
                a_bit_id=connections['A'],
                b_bit_id=connections['B'],
                c_bit_id=None,
                y_bit_id=connections['Y'],
            ))
        elif cell_type == '$_XOR_':
            planner.add_lut(name, LookUpTable(
                config=XOR_GATE_LUT_CONFIG,
                a_bit_id=connections['A'],
                b_bit_id=connections['B'],
                c_bit_id=None,
                y_bit_id=connections['Y'],
            ))
        elif cell_type == '$_NOT_':
            planner.add_lut(name, LookUpTable(
                config=XOR_GATE_LUT_CONFIG,
                a_bit_id=connections['A'],
                b_bit_id=None,
                c_bit_id=None,
                y_bit_id=connections['Y'],
            ))
        elif cell_type == '$_DFF_P_':
            planner.add_ff(name, FlipFlop(
                c_bit_id=connections['C'],
                d_bit_id=connections['D'],
                q_bit_id=connections['Q'],
            ))
        else:
            raise NotImplementedError(cell_type)

    return planner.resolve()


class CircuitPlanner:

    def __init__(self):
        self.lookup_tables = {}
        self.flip_flops = {}
        self.outputs = {}
        self.inputs = {}

        self.bit_drivers = {}
        self.bit_readers = defaultdict(set)

    def _add_bit_reader(self, bit_id, name):
        if isinstance(bit_id, int):
            self.bit_readers[bit_id].add(name)

    def _add_bit_driver(self, bit_id, name):
        if bit_id is not None:
            try:
                driving_cell_name = self.bit_drivers[bit_id]
            except KeyError:
                self.bit_drivers[bit_id] = name
            else:
                raise RuntimeError(f'Bit {bit_id} is already driven by {driving_cell_name}!')

    def add_port(self, name, port):
        """Add a module-level input or output to the design."""
        if port.is_output:
            for bit in port.bits:
                self._add_bit_reader(bit, None)
            self.outputs[name] = port
        else:
            for bit in port.bits:
                self._add_bit_driver(bit, None)
            self.inputs[name] = port

    def add_lut(self, name, lut):
        """Add a lookup table to the design."""
        self._add_bit_reader(lut.a_bit_id, name)
        self._add_bit_reader(lut.b_bit_id, name)
        self._add_bit_reader(lut.c_bit_id, name)
        self._add_bit_driver(lut.y_bit_id, name)
        self.lookup_tables[name] = lut

    def add_ff(self, name, ff):
        """Add a flip flop to the design."""
        self._add_bit_reader(ff.c_bit_id, name)
        self._add_bit_reader(ff.d_bit_id, name)
        # Sequential elements like flip flops are a barrier in the
        # combinational cell evaluation order, so their outputs should not
        # be included in the graph.
        # Any combinational subcircuit using the output of a flip flop
        # will not create a cycle by feeding its output back to the
        # same flip flop (or leading to it in the chain) because the
        # output can only change on a clock edge.
        self._add_bit_driver(ff.q_bit_id, None)
        self.flip_flops[name] = ff

    def resolve(self):
        """Resolve connections and create a circuit."""
        # TODO: Create logic cells instead of discrete LUTs and flip-flops.

        # We represent combinational circuits as a directed acyclic graph,
        # where there is an edge between the output of a driver of a net
        # and all nodes which use that net as an input.
        graph_edges = []
        for input_bit_id, reading_cell_names in self.bit_readers.items():
            # Skip constants
            if isinstance(input_bit_id, bool):
                continue

            # Skip flip flops and module inputs and outputs as they do not
            # contribute directly to the evaluation order of the circuit
            # combinational elements.
            driving_cell_name = self.bit_drivers[input_bit_id]
            if driving_cell_name is None:
                continue

            for reading_cell_name in reading_cell_names:
                graph_edges.append((driving_cell_name, reading_cell_name))

        graph = nx.DiGraph(graph_edges)
        try:
            sorted_cell_names = list(nx.topological_sort(graph))
        except nx.exception.NetworkXUnfeasible:
            print('Cannot solve graph order for evaluation')
            raise

        cell_collections = [dict(self.lookup_tables), dict(self.flip_flops)]

        sorted_cells = []
        for cell_name in sorted_cell_names:
            for collection in cell_collections:
                try:
                    cell = collection.pop(cell_name)
                except KeyError:
                    continue
                else:
                    sorted_cells.append(cell)
                    break

        skipped_cells = []
        for collection in cell_collections:
            skipped_cells.extend(collection.values())
        assert not skipped_cells, 'Some cells were skipped!'
        # TODO: Can they be added to the beginning, or is this not needed anymore?
        # sorted_cells = skipped_cells + sorted_cells

        return Circuit(self.inputs, self.outputs, sorted_cells)


class Circuit:

    def __init__(self, inputs, outputs, cells):
        self.inputs = inputs
        self.outputs = outputs
        self.cells = cells
        self.bits = {}
        self.flip_flop_clock_states = {}

    def _get_bit(self, bit_id):
        # Constants
        if isinstance(bit_id, bool):
            return bit_id
        return self.bits.get(bit_id, False)

    def _set_bit(self, bit_id, value):
        assert isinstance(bit_id, int)
        self.bits[bit_id] = value

    def tick(self):
        self.set_input('i_Clock', 1)
        self.eval()
        self.set_input('i_Clock', 0)
        self.eval()

    def eval(self):
        # We assume that the cells are already in the right order to evaluate.
        flip_flop_updates = []
        for cell in self.cells:
            if isinstance(cell, LookUpTable):
                self._eval_lookup_table(cell)
            elif isinstance(cell, FlipFlop):
                flip_flop_update = self._eval_flip_flop(cell)
                if flip_flop_update is not None:
                    flip_flop_updates.append(flip_flop_update)
            else:
                raise NotImplementedError(cell)

        # All flip flops must update simultaneously,
        # as far as the rest of the simulation is concerned.
        for bit_id, value in flip_flop_updates:
            self._set_bit(bit_id, value)

    def _eval_lookup_table(self, lut):
        a_input = int(self._get_bit(lut.a_bit_id))
        b_input = int(self._get_bit(lut.b_bit_id))
        c_input = int(self._get_bit(lut.c_bit_id))
        lut_config_index = (a_input << 2) | (b_input << 1) | (c_input << 0)
        lut_config_mask = 2**lut_config_index
        self._set_bit(lut.y_bit_id, bool(lut.config & lut_config_mask))

    def _eval_flip_flop(self, ff):
        last_clock_state = self.flip_flop_clock_states.get(ff.q_bit_id, False)
        new_clock_state = self._get_bit(ff.c_bit_id)
        data_input = self._get_bit(ff.d_bit_id)
        self.flip_flop_clock_states[ff.q_bit_id] = new_clock_state

        # Trigger on rising edge only
        if new_clock_state and not last_clock_state:
            return ff.q_bit_id, data_input
        else:
            return None


    def set_input(self, name, value):
        port = self.inputs[name]
        for i, bit_id in enumerate(port.bits):
            bit_value = value & (1 << i)
            self._set_bit(bit_id, bool(bit_value))

    def get_output(self, name):
        result = 0
        port = self.outputs[name]
        for i, bit_id in enumerate(port.bits):
            bit_value = int(self._get_bit(bit_id))
            result |= bit_value << i
        return result


def run(args):
    with open(args.design_file, 'r') as f:
        raw_json = f.read()

        # Create a function which takes as input a combinational circuit
        # and composes it as a structure of LUTs? Are FFs part of that
        # as well? I should look at what the structure of the 16-bit adder
        # and mux look like, as these will map nicely to the LUTs.
        # A shift register would be good too, but this will likely just
        # be a chain of logic cells with one feeding the next, as well
        # as a reset signal and a zero.

        # TODO: Create some very simple designs (one or two bits)
        # and see what the AIG output looks like.



        # Instead of getting individual bit-level gates from techmap,
        # try parsing the output of the "memory" step with AIG output
        # turned on.
        #
        # https://github.com/mvcisback/py-aiger
        # http://www.clifford.at/yosys/cmd_write_aiger.html
        # https://github.com/YosysHQ/yosys/issues/350
        # See also "aigmap", instead of techmap (which if the memory thing doesn't work could be easier than trying to combine XOR,MUX,AND,OR,and NOT)
        #
        #
        # The cell ports are wide now, but these could be split up.
        # We also don't need to hard-code the LUT configs for different cell
        # types because the AIG models included in the JSON file tell us how
        # they should work.
        #
        # The "show" output from the memory step is also much easier to
        # visualize and follow.

        import re
        # Yosys inserts comments into the JSON AIG section for some reason
        clean_json = re.sub(r'/\*.*\*/', '', raw_json)
        raw_design = json.loads(clean_json)

    circuit = parse_design(raw_design)

    amount = 0
    for i in range(32):
        circuit.set_input('i_Reset', 1 if i == 10 else 0)
        circuit.set_input('i_Amount', amount)
        circuit.tick()
        result = circuit.get_output('o_Output')
        print(f'{i} (+{amount}): {result}')
        amount += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('design_file', help='Yosys JSON output file')
    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
