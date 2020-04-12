
import math
# import functools
from dataclasses import dataclass

# from z3 import BitVec, Solver, If, Int, BitVecVal
from z3 import (
    Solver,
    If,
    Int, BitVec,
    Bool,
)


def add_mux(solver, name, inputs, output):
    if len(inputs) < 2:
        raise ValueError('Must have at least two inputs')

    num_selector_bits = math.ceil(math.log2(len(inputs)))
    selector = BitVec(f'{name}_selector', num_selector_bits)

    expr = If(selector == len(inputs) - 2, inputs[-2], inputs[-1])
    stack = [(input, selector == i) for i, input in enumerate(inputs[:-2])]
    while stack:
        input, selector_check = stack.pop()
        expr = If(selector_check, input, expr)

    solver.add(expr == output)
    return selector


@dataclass
class SwitchBlockPort:
    """For communication with other switch blocks, not logic cells (yet)."""
    # direction: SwitchBlockPortDirection
    input: Int
    output: Int
    mux_selector: BitVec


@dataclass
class SwitchBlock:
    north: SwitchBlockPort
    south: SwitchBlockPort
    east: SwitchBlockPort
    west: SwitchBlockPort
    # north_west_logic_cell: ...
    # ...


def add_switch_block(solver, name):
    # TODO: Extend to three wires in each direction

    directions = ['north', 'south', 'east', 'west']
    switch_block_inputs = {
        direction: Int(f'{name}_{direction}_input')
        for direction in directions
    }
    switch_block_outputs = {
        direction: Int(f'{name}_{direction}_output')
        for direction in directions
    }

    switch_mux_selectors = {}
    for direction in directions:
        mux_inputs = [switch_block_inputs[direction] for direction in directions]
        mux_output = switch_block_outputs[direction]
        mux_selector = add_mux(solver, f'{name}_{direction}_mux', mux_inputs, mux_output)
        switch_mux_selectors[direction] = mux_selector

    switch_block_ports = {
        direction: SwitchBlockPort(
            input=switch_block_inputs[direction],
            output=switch_block_outputs[direction],
            mux_selector=switch_mux_selectors[direction],
        )
        for direction in directions
    }
    return SwitchBlock(**switch_block_ports)


_next_unique_id = 0


def next_unique_id():
    global _next_unique_id
    _next_unique_id += 1
    assert _next_unique_id < 10000, 'out of unique IDs!'
    return _next_unique_id


solver = Solver()

GREEN_SIGNAL = 10001
BLUE_SIGNAL = 10002
ORANGE_SIGNAL = 10003
YELLOW_SIGNAL = 10004


# # Create routing switch blocks
switch_blocks = [add_switch_block(solver, f'switch_block{i}') for i in range(4)]

# Create logic cell inputs
logic_cell_mux_selectors = {}
logic_cell_inputs = [Int(f'logic_cell_0_0_input_{i}') for i in range(4)]
for i, logic_cell_input in enumerate(logic_cell_inputs):
    northbound_signal = switch_blocks[3].north.output
    southbound_signal = switch_blocks[1].south.output
    eastbound_signal = switch_blocks[1].east.output
    westbound_signal = switch_blocks[2].west.output

    # This ordering is subject to change, it's just how I have it drawn now.
    logic_cell_mux_inputs = [
        eastbound_signal,
        westbound_signal,
        southbound_signal,
        northbound_signal,
    ]

    logic_cell_mux_selectors = {}
    name = f'logic_cell_0_0_input_mux_{i}'
    selector = add_mux(solver, name, logic_cell_mux_inputs, logic_cell_input)
    logic_cell_mux_selectors[name] = selector


# If system is not satisfiable,
# try removing the clauses which set inputs to "next unique ID"

# Wire switch blocks together.
solver.add(
    switch_blocks[0].north.input == next_unique_id(),  # I/O perimeter
    switch_blocks[0].south.input == next_unique_id(),  # I/O perimeter
    switch_blocks[0].east.input == switch_blocks[1].west.output,
    switch_blocks[0].west.input == ORANGE_SIGNAL,  # I/O perimeter

    switch_blocks[1].north.input == BLUE_SIGNAL,  # I/O perimeter
    switch_blocks[1].south.input == switch_blocks[3].north.output,
    switch_blocks[1].east.input == switch_blocks[2].west.output,
    switch_blocks[1].west.input == switch_blocks[0].east.output,

    switch_blocks[2].north.input == next_unique_id(),  # I/O perimeter
    switch_blocks[2].south.input == next_unique_id(),  # I/O perimeter
    switch_blocks[2].east.input == YELLOW_SIGNAL,  # I/O perimeter
    switch_blocks[2].west.input == switch_blocks[1].east.output,

    switch_blocks[3].north.input == switch_blocks[1].south.output,
    switch_blocks[3].south.input == GREEN_SIGNAL,  # I/O perimeter
    switch_blocks[3].east.input == next_unique_id(),  # I/O perimeter
    switch_blocks[3].west.input == next_unique_id(),  # I/O perimeter
)

# Set desired connections
solver.add(
    logic_cell_inputs[0] == ORANGE_SIGNAL,
    logic_cell_inputs[1] == GREEN_SIGNAL,
    logic_cell_inputs[2] == YELLOW_SIGNAL,
    logic_cell_inputs[3] == BLUE_SIGNAL,
)

with open('solver.txt', 'w') as f:
    f.write(solver.sexpr())

if str(solver.check()) == 'sat':
    model = solver.model()

    with open('model.txt', 'w') as f:
        model_lines = sorted(
            line.strip().lstrip('[').rstrip(',').rstrip(']')
            for line in str(model).splitlines()
        )

        for line in model_lines:
            keywords = [
                'block3_north_mux',
                'block3_north_output',
                'block1_east_output',
                'logic_cell_0_0_input_mux_0',
                'logic_cell_0_0_input_0',
            ]
            if any(keyword in line for keyword in keywords):
                print(line)
            print(line, file=f)

    # print(model)

    # for name, variable in mux_selectors.items():
    # print(f'{name}: {model[variable]}')
else:
    print('unsat')
    # print(solver.sexpr())

# routing_network_wires = [
#     Int('rn_north_to_east'),
#     Int('rn_north_to_west'),
#     Int('rn_west_to_south'),
#     Int('rn_west_to_north'),
# ]

# solver.add(
#     logic_cell_inputs[0] == routing_network_wires[0],
#     logic_cell_inputs[1] == routing_network_wires[3],
#     logic_cell_inputs[2] == routing_network_wires[1],
#     logic_cell_inputs[3] == routing_network_wires[2],
# )

# # Assign net IDs. This will force the solver to make connections to keep
# # the net IDs the same through all the multiplexers.
# solver.add(
#     routing_network_wires[0] == 1001,
#     routing_network_wires[1] == 2002,
#     routing_network_wires[2] == 3003,
#     routing_network_wires[3] == 4004,
# )
