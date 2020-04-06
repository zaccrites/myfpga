
import sys
import json
import argparse
import functools



# Instead of function "cells", just convert all Yosys primitives into
# LUTs in a first pass. The second pass converts LUTs and flip flops into
# logic cells.



class Circuit:

    def __init__(self, raw_design):
        self.bits = {}
        self.cells = []

        self.dff_clock_states = {}
        self.dff_data_states = {}

        # TODO
        raw_design = raw_design['modules']['my_design']

        # self.input_values = {}
        self.input_bits = {}
        for name, info in raw_design['ports'].items():
            if info['direction'] == 'input':
                # self.input_values[name] = False
                self.input_bits[name] = info['bits'][0]
                assert len(info['bits']) == 1, 'multi bit inputs?'

        # self.output_values = {}
        self.output_bits = {}
        for name, info in raw_design['ports'].items():
            if info['direction'] == 'output':
                # self.output_values[name] = False
                self.output_bits[name] = info['bits'][0]
                assert len(info['bits']) == 1, 'multi bit inputs?'

        self.cell_names = {}

        def get_bit_id(raw_bit_id):
            if isinstance(raw_bit_id, str):
                assert len(raw_bit_id) == 1, 'multi bit constants?'
                return raw_bit_id == '1'
            else:
                assert isinstance(raw_bit_id, int)
                return raw_bit_id

        for name, raw_cell in raw_design['cells'].items():
            for cell_connection_bits in raw_cell['connections'].values():
                assert len(cell_connection_bits) == 1, 'need to support multi bit cells?'
                self.bits[cell_connection_bits[0]] = False

            if raw_cell['type'] == '$_MUX_':
                assert raw_cell['port_directions'] == {'A': 'input', 'B': 'input', 'S': 'input', 'Y': 'output'}
                self.cells.append(functools.partialmethod(self._mux_cell,
                    a_id=get_bit_id(raw_cell['connections']['A'][0]),
                    b_id=get_bit_id(raw_cell['connections']['B'][0]),
                    s_id=get_bit_id(raw_cell['connections']['S'][0]),
                    y_id=get_bit_id(raw_cell['connections']['Y'][0]),
                ))

            elif raw_cell['type'] == '$_AND_':
                assert raw_cell['port_directions'] == {'A': 'input', 'B': 'input', 'Y': 'output'}
                self.cells.append(functools.partialmethod(self._and_cell,
                    a_id=get_bit_id(raw_cell['connections']['A'][0]),
                    b_id=get_bit_id(raw_cell['connections']['B'][0]),
                    y_id=get_bit_id(raw_cell['connections']['Y'][0]),
                ))

            elif raw_cell['type'] == '$_OR_':
                assert raw_cell['port_directions'] == {'A': 'input', 'B': 'input', 'Y': 'output'}
                self.cells.append(functools.partialmethod(self._or_cell,
                    a_id=get_bit_id(raw_cell['connections']['A'][0]),
                    b_id=get_bit_id(raw_cell['connections']['B'][0]),
                    y_id=get_bit_id(raw_cell['connections']['Y'][0]),
                ))

            elif raw_cell['type'] == '$_XOR_':
                assert raw_cell['port_directions'] == {'A': 'input', 'B': 'input', 'Y': 'output'}
                self.cells.append(functools.partialmethod(self._xor_cell,
                    a_id=get_bit_id(raw_cell['connections']['A'][0]),
                    b_id=get_bit_id(raw_cell['connections']['B'][0]),
                    y_id=get_bit_id(raw_cell['connections']['Y'][0]),
                ))

            elif raw_cell['type'] == '$_NOT_':
                assert raw_cell['port_directions'] == {'A': 'input', 'Y': 'output'}
                self.cells.append(functools.partialmethod(self._not_cell,
                    a_id=get_bit_id(raw_cell['connections']['A'][0]),
                    y_id=get_bit_id(raw_cell['connections']['Y'][0]),
                ))

            elif raw_cell['type'] == '$_DFF_P_':
                assert raw_cell['port_directions'] == {'C': 'input', 'D': 'input', 'Q': 'output'}
                q_id = get_bit_id(raw_cell['connections']['Q'][0])
                self.cells.append(functools.partialmethod(self._dff_cell,
                    c_id=get_bit_id(raw_cell['connections']['C'][0]),
                    d_id=get_bit_id(raw_cell['connections']['D'][0]),
                    q_id=q_id,
                ))
                self.dff_data_states[q_id] = False
                self.dff_clock_states[q_id] = False

            else:
                raise NotImplementedError(raw_cell['type'])

            self.cell_names[self.cells[-1]] = name

        # import pdb; pdb.set_trace();  # TODO: remove me
        pass

        # Now that we have the cells, we need to figure out the order in which
        # to evaluate them.

        # Some cells will not have any inputs, or will have inputs that are
        # inputs to th entire module. These must be evaluated first, with
        # cells relying on them going after.

        # TODO: Use an object for a cell instead of this hack
        from collections import defaultdict

        bit_drivers = {}
        for input in self.input_bits:
            pass

        bit_needs = defaultdict(list)
        for output in self.output_bits:
            pass


        flip_flop_outputs = []
        for cell in self.cells:
            if 'y_id' in cell.keywords:
                bit_drivers[cell.keywords['y_id']] = cell


            if 'a_id' in cell.keywords:
                bit_needs[cell].append(cell.keywords['a_id'])
            if 'b_id' in cell.keywords:
                bit_needs[cell].append(cell.keywords['b_id'])
            if 's_id' in cell.keywords:
                bit_needs[cell].append(cell.keywords['s_id'])


            # On an evaluation, we need to update the state of the flip flops
            # first because they will feed the new output state of the
            # combinational circuits that will give the flip flops their new
            # value on the next clock edge. Therefore, we omit the outputs
            # of flip flops for purposes of determining graph sort order.
            if 'q_id' in cell.keywords:
                # bit_drivers[cell.keywords['q_id']] = cell
                flip_flop_outputs.append(cell.keywords['q_id'])

            if 'c_id' in cell.keywords:
                bit_needs[cell].append(cell.keywords['c_id'])
            if 'd_id' in cell.keywords:
                bit_needs[cell].append(cell.keywords['d_id'])


        graph = []
        for input_cell, input_bit_ids in bit_needs.items():
            for input_bit_id in input_bit_ids:
                # Skip constants
                if isinstance(input_bit_id, bool):
                    continue

                try:
                    driver_cell = bit_drivers[input_bit_id]
                except KeyError:
                    is_input_bit = input_bit_id in self.input_bits.values()
                    is_flop_flop_bit = input_bit_id in flip_flop_outputs
                    assert is_input_bit or is_flop_flop_bit, repr(input_bit_id)
                else:
                    graph.append((driver_cell, input_cell))

        # For any cells we skipped (maybe because all of their input bits
        # are constants or module inputs), just add them to the front.
        # They can be evaluated in any order because they have no dependencies.
        skipped_cells = set(self.cells)
        for driver_cell, input_cell in graph:
            skipped_cells.discard(driver_cell)
            skipped_cells.discard(input_cell)


        # import pdb; pdb.set_trace();  # TODO: remove me
        pass

        import networkx as nx
        # graph = nx.DiGraph([
        #     (1, 3),
        #     (2, 3),
        #     (3, 6),
        #     (6, 7),
        #     (4, 5),
        #     (5, 6),
        #     (5, 8),
        #     (9, 8),
        #     (5, 3),
        #     (8, 4),
        # ])
        graph = nx.DiGraph(graph)
        try:
            sorted_cells = list(nx.topological_sort(graph))
        except nx.exception.NetworkXUnfeasible:
            print('Cannot solve network order for evaluation')

            import pdb; pdb.set_trace();  # TODO: remove me
            pass

            # For the purposes of solving the graph, we must allow
            # DFF cells to break the flow. A cycle involving a DFF is okay
            # because it won't change value until the next clock.


            raise

        sorted_cells = list(skipped_cells) + sorted_cells

        for cell in sorted_cells:
            print(self.cell_names[cell], repr(cell))
        self.cells = sorted_cells

        # import pdb; pdb.set_trace();  # TODO: remove me
        pass


    def eval(self):
        for cell in self.cells:
            # call the cell function
            try:
                # cell()  # doesn't work for some reason
                cell.func(*cell.args, **cell.keywords)  # but this works
                # print('DFF DATA STATES: ', self.dff_data_states,  'bits: ', self.bits)

            except TypeError:
                import pdb; pdb.set_trace();  # TODO: remove me
                raise

        # All DFF bits have to update simultaneously
        for bit_id, value in self.dff_data_states.items():
            # import pdb; pdb.set_trace();  # TODO: remove me
            # print('DFF DATA STATES: ', self.dff_data_states)
            self._set_bit(bit_id, value)


    def tick(self):
        self.set_input('i_Clock', 1)
        self.eval()
        self.set_input('i_Clock', 0)
        self.eval()

    def get_output(self, name):
        bit_id = self.output_bits[name]
        return self.bits[bit_id]

    def set_input(self, name, value):
        bit_id = self.input_bits[name]
        self.bits[bit_id] = value



    # TODO: This is very naive. I will need to find a way of combining
    # gates into LUTs, and LUTs with FFs into logic blocks.

    def _get_bit(self, bit_id):
        # Return constants straight off
        if isinstance(bit_id, bool):
            return bit_id
        else:

            # for input_name, input_bit_id in self.input_bits.items():
            #     if bit_id == input_bit_id:
            #         return self.input_values[input_name]

            # Default value is reset (could be configurable per DFF)
            # return self.bits.get(bit_id, False)
            try:
                return self.bits[bit_id]
            except KeyError:
                import pdb; pdb.set_trace();  # TODO: remove me
                pass

    def _set_bit(self, bit_id, value):
        # for output_name, output_bit_id in self.output_bits.items():
            # if bit_id == output_bit_id:
                # print(f'Writing {value} to output "{output_name}"')
                # self.output_values[output_name] = value
                # return
        self.bits[bit_id] = bool(value)

    def _mux_cell(self, a_id, b_id, s_id, y_id):
        a = self._get_bit(a_id)
        b = self._get_bit(b_id)
        s = self._get_bit(s_id)
        self._set_bit(y_id, b if s else a)

    def _and_cell(self, a_id, b_id, y_id):
        a = self._get_bit(a_id)
        b = self._get_bit(b_id)
        self._set_bit(y_id, a and b)

    def _or_cell(self, a_id, b_id, y_id):
        a = self._get_bit(a_id)
        b = self._get_bit(b_id)
        self._set_bit(y_id, a or b)

    def _xor_cell(self, a_id, b_id, y_id):
        a = self._get_bit(a_id)
        b = self._get_bit(b_id)
        self._set_bit(y_id, (a and not b) or (b and not a))

    def _not_cell(self, a_id, y_id):
        a = self._get_bit(a_id)
        self._set_bit(y_id, not a)

    def _dff_cell(self, c_id, d_id, q_id):
        last_clock_state = self.dff_clock_states[q_id]

        c = self._get_bit(c_id)
        d = self._get_bit(d_id)

        # Only set data on rising clock
        if c and not last_clock_state:
            self.dff_data_states[q_id] = d

        self.dff_clock_states[q_id] = c






class LookUpTable:

    def __init__(self, a, b, c, y):
        """Configure a LUT.

        a, b, and c are inputs

        y is the output

        """





def main():

    with open('my_design_3.json', 'r') as f:
        raw_design = json.load(f)

    circuit = Circuit(raw_design)

    for i in range(16):
        circuit.set_input('i_Address3', i & 8)
        circuit.set_input('i_Address2', i & 4)
        circuit.set_input('i_Address1', i & 2)
        circuit.set_input('i_Address0', i & 1)

        circuit.set_input('i_DataIn3', i & 8)
        circuit.set_input('i_DataIn2', i & 4)
        circuit.set_input('i_DataIn1', i & 2)
        circuit.set_input('i_DataIn0', i & 1)
        circuit.set_input('i_WriteEnable', 1)

        circuit.tick()
        output_bits = [circuit.get_output(f'o_Output{i}') for i in range(4)]
        print(i, ':', ' '.join(f'{x:d}' for x in reversed(output_bits)))


    for i in range(16):
        circuit.set_input('i_Address3', i & 8)
        circuit.set_input('i_Address2', i & 4)
        circuit.set_input('i_Address1', i & 2)
        circuit.set_input('i_Address0', i & 1)

        # circuit.set_input('i_DataIn3', i & 8)
        # circuit.set_input('i_DataIn2', i & 4)
        # circuit.set_input('i_DataIn1', i & 2)
        # circuit.set_input('i_DataIn0', i & 1)
        circuit.set_input('i_WriteEnable', 0)

        circuit.tick()
        output_bits = [circuit.get_output(f'o_Output{i}') for i in range(4)]
        print(i, ':', ' '.join(f'{x:d}' for x in reversed(output_bits)))


if __name__ == '__main__':
    sys.exit(main())
