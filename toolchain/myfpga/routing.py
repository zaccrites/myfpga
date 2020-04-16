"""Place and route a design."""

import math
import itertools
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict

import z3

from myfpga.implementation import LogicCell
from myfpga.implementation import ModulePort


# FUTURE: Make this configurable
LUT_WIDTH = 4


SignalId = z3.Int


class CardinalDirection(Enum):

    """Device cardinal directions.

    The greater the X coordinate, the further east.
    The greater the Y coordinate, the further south.

    """

    north = 0
    south = 1
    west = 2
    east = 3

    @property
    def opposite(self):
        return {
            CardinalDirection.north: CardinalDirection.south,
            CardinalDirection.south: CardinalDirection.north,
            CardinalDirection.west: CardinalDirection.east,
            CardinalDirection.east: CardinalDirection.west,
        }[self]


class IntercardinalDirection(Enum):

    """Device intercardinal directions."""

    northwest = 0
    northeast = 1
    southwest = 2
    southeast = 3

    @property
    def opposite(self):
        return {
            IntercardinalDirection.northwest: IntercardinalDirection.southeast,
            IntercardinalDirection.northeast: IntercardinalDirection.southwest,
            IntercardinalDirection.southwest: IntercardinalDirection.southeast,
            IntercardinalDirection.southeast: IntercardinalDirection.northwest,
        }[self]


@dataclass
class DeviceTopology:

    """Device resource topology.

    width: number of logic cells wide
    height: number of logic cells high

    """

    width: int
    height: int

    def adjacent_switch_blocks(self, coords):
        """Find switch blocks adjacent to a given switch block's coordinates.

        Switch blocks are adjacent at their sides.

        """
        if coords.y > 0:
            yield CardinalDirection.north, SwitchBlockCoordinates(coords.x, coords.y - 1)
        if coords.y < self.height:
            yield CardinalDirection.south, SwitchBlockCoordinates(coords.x, coords.y + 1)
        if coords.x > 0:
            yield CardinalDirection.west, SwitchBlockCoordinates(coords.x - 1, coords.y)
        if coords.x < self.width:
            yield CardinalDirection.east, SwitchBlockCoordinates(coords.x + 1, coords.y)

    def adjacent_logic_cells(self, coords):
        """Find logic cells adjacent to a given switch block's coordinates.

        Switch blocks are adjacent to logic cells at their corners.

        """
        if coords.x == 2 and coords.y == 2:
            # import pdb; pdb.set_trace();  # TODO: remove me
            pass

        if coords.y > 0 and coords.x > 0:
            yield IntercardinalDirection.northwest, LogicCellCoordinates(coords.x - 1, coords.y - 1)
        if coords.y > 0 and coords.x < self.width:
            yield IntercardinalDirection.northeast, LogicCellCoordinates(coords.x, coords.y - 1)
        if coords.y < self.height and coords.x > 0:
            yield IntercardinalDirection.southwest, LogicCellCoordinates(coords.x - 1, coords.y)
        if coords.y < self.height and coords.x < self.width:
            yield IntercardinalDirection.southeast, LogicCellCoordinates(coords.x, coords.y)

    def adjacent_io_blocks(self, coords):
        """Find I/O blocks adjacent to a given switch block's coordinates.

        Switch blocks are adjacent to I/O blocks on their sides.
        Only switch blocks at the perimeter will have adjacent
        I/O blocks.

        """
        if coords.y == 0:
            yield CardinalDirection.north, IoBlockCoordinates(CardinalDirection.north, coords.x)
        if coords.y == self.height:
            yield CardinalDirection.south, IoBlockCoordinates(CardinalDirection.south, coords.x)
        if coords.x == 0:
            yield CardinalDirection.west, IoBlockCoordinates(CardinalDirection.west, coords.y)
        if coords.x == self.width:
            yield CardinalDirection.east, IoBlockCoordinates(CardinalDirection.east, coords.y)

    def iter_switch_block_coords(self):
        """Iterate all switch block coordinates."""
        for x, y in itertools.product(range(self.width + 1), range(self.height + 1)):
            yield SwitchBlockCoordinates(x, y)

    def iter_logic_cell_coords(self):
        """Iterate all logic cell coordinates."""
        for x, y in itertools.product(range(self.width), range(self.height)):
            yield LogicCellCoordinates(x, y)

    def iter_io_block_coords(self):
        """Iterate all I/O block coordinates."""
        for i in range(self.width + 1):
            yield IoBlockCoordinates(CardinalDirection.north, i)
            yield IoBlockCoordinates(CardinalDirection.south, i)
        for i in range(self.height + 1):
            yield IoBlockCoordinates(CardinalDirection.west, i)
            yield IoBlockCoordinates(CardinalDirection.east, i)


@dataclass(frozen=True, eq=True)
class LogicCellCoordinates:
    x: int
    y: int

    @property
    def name(self):
        return f'$cell[{self.x},{self.y}]'


@dataclass(frozen=True, eq=True)
class SwitchBlockCoordinates:
    x: int
    y: int

    @property
    def name(self):
        return f'$junction[{self.x},{self.y}]'


@dataclass(frozen=True, eq=True)
class IoBlockCoordinates:
    direction: CardinalDirection
    index: int

    @property
    def name(self):
        return f'$io_{self.direction.name}[{self.index}]'


@dataclass
class LogicCellModelInput:
    port: SignalId
    mux_inputs: List[SignalId]
    mux_selector: z3.BitVec


@dataclass
class LogicCellModelOutput:
    port: SignalId


@dataclass
class LogicCellModel:
    coords: LogicCellCoordinates
    inputs: List[LogicCellModelInput]
    output: LogicCellModelOutput


@dataclass
class SwitchBlockModelSide:
    """Z3 model for where switch blocks connect to one another.

    I/O blocks also connect to switch blocks via these ports.

    `mux_selector` is an output of the model to be encoded in the bitstream.

    """

    input_port: SignalId
    output_port: SignalId
    mux_selector: z3.BitVec


@dataclass
class SwitchBlockModelCorner:
    """Z3 model for where logic cells connect to a switch block."""

    port: SignalId


@dataclass
class SwitchBlockModel:
    coords: SwitchBlockCoordinates
    sides: Dict[CardinalDirection, SwitchBlockModelSide]
    corners: Dict[IntercardinalDirection, SwitchBlockModelCorner]

    # north: SwitchBlockModelSide
    # south: SwitchBlockModelSide
    # west: SwitchBlockModelSide
    # east: SwitchBlockModelSide

    # northwest: SwitchBlockModelCorner
    # northeast: SwitchBlockModelCorner
    # southwest: SwitchBlockModelCorner
    # southeast: SwitchBlockModelCorner


class IoBlockFunction(Enum):
    none = None
    input = 'input'
    output = 'output'


@dataclass
class IoBlockModel:
    coords: IoBlockCoordinates
    function: IoBlockFunction
    # Note that the "input port" here is a signal input which
    # will then be sent outside the device. The reverse is
    # true for the output port, which receives a signal from the outside.
    input_port: SignalId
    output_port: SignalId


class Solver:

    def __init__(self):
        self.solver = z3.Solver()

    def check(self):
        return self.solver.check()

    def model(self):
        return self.solver.model()

    def _add_mux(self, name, inputs, output):
        if len(inputs) < 2:
            raise ValueError('Must have at least two inputs')

        num_selector_bits = math.ceil(math.log2(len(inputs)))
        selector = z3.BitVec(f'{name}_sel', num_selector_bits)

        expr = z3.If(selector == len(inputs) - 2, inputs[-2], inputs[-1])
        stack = [(input, selector == i) for i, input in enumerate(inputs[:-2])]
        while stack:
            input, selector_check = stack.pop()
            expr = z3.If(selector_check, input, expr)

        self.solver.add(expr == output)
        return selector

    def add_switch_block(self, coords):
        inputs = {
            direction: SignalId(f'{coords.name}_{direction.name}_input')
            for direction in CardinalDirection
        }
        outputs = {
            direction: SignalId(f'{coords.name}_{direction.name}_output')
            for direction in CardinalDirection
        }
        corners = {
            direction: SignalId(f'{coords.name}_{direction.name}_input')
            for direction in IntercardinalDirection
        }

        # The order here matters, as it will influence the mux selector
        # bit pattern generated. It doesn't *have* to be the same for each
        # mux (if it is better for it to be so in the device implementation).
        # In simulation it probably doesn't matter. In a real FPGA there is
        # probably a routing advantage to be gained by choosing mux selector
        # and input order which varies per port for its position and orientation.
        mux_inputs = [
            inputs[CardinalDirection.north],
            inputs[CardinalDirection.south],
            inputs[CardinalDirection.west],
            inputs[CardinalDirection.east],
            corners[IntercardinalDirection.northwest],
            corners[IntercardinalDirection.northeast],
            corners[IntercardinalDirection.southwest],
            corners[IntercardinalDirection.southeast],
        ]

        def _make_side(direction):
            name = f'{coords.name}_{direction.name}'
            return SwitchBlockModelSide(
                input_port=inputs[direction],
                output_port=outputs[direction],
                mux_selector=self._add_mux(name, mux_inputs, outputs[direction]),
            )
        sides = {direction: _make_side(direction) for direction in CardinalDirection}
        corners = {direction: SwitchBlockModelCorner(port=port) for direction, port in corners.items()}
        return SwitchBlockModel(
            coords=coords,
            sides=sides,
            corners=corners,
        )

    def add_logic_cell(self, coords):
        cell_inputs = []
        for input_index in range(LUT_WIDTH):
            name = f'{coords.name}_input{input_index}'
            mux_inputs = [
                # TODO: Need 2x or 3x inputs for each direction for wider routing channels
                SignalId(f'{name}_mux_input_{direction}')
                for direction in ['northbound', 'southbound', 'eastbound', 'westbound']
            ]
            cell_input = SignalId(name)
            cell_inputs.append(LogicCellModelInput(
                port=cell_input,
                mux_inputs=mux_inputs,
                mux_selector=self._add_mux(name, mux_inputs, cell_input),
            ))
        return LogicCellModel(
            coords=coords,
            inputs=cell_inputs,
            output=LogicCellModelOutput(port=SignalId(f'{coords.name}_output')),
        )

    def add_io_block(self, coords):
        name = f'$io_{coords.direction.name}[{coords.index}]'
        return IoBlockModel(
            coords=coords,
            function=IoBlockFunction.none,
            input_port=SignalId(f'{name}_input'),
            output_port=SignalId(f'{name}_output'),
        )

    def connect_switch_block(self, switch_block, other_switch_block, direction):
        # Each switch block only connects its output to its neighbor's input.
        # The neighbor will be responsible for creating the reverse connection.
        output_port = switch_block.sides[direction].output_port
        input_port = other_switch_block.sides[direction.opposite].input_port
        self.solver.add(output_port == input_port)

    def connect_logic_cell(self, switch_block, logic_cell, direction):
        input_port = switch_block.corners[direction].port
        self.solver.add(logic_cell.output.port == input_port)

    def connect_io_block(self, switch_block, io_block, direction):
        # Connect both ports of I/O blocks, because they only have
        # one switch block neighbor.
        input_port = switch_block.sides[direction].input_port
        output_port = switch_block.sides[direction].output_port
        self.solver.add(io_block.output_port == input_port)
        self.solver.add(io_block.input_port == output_port)


class RoutingError(RuntimeError):
    pass


class Router:

    def __init__(self, device_topology):
        self.device_topology = device_topology
        self.solver = Solver()

        self.switch_block_models = {
            coords: self.solver.add_switch_block(coords)
            for coords in self.device_topology.iter_switch_block_coords()
        }
        self.logic_cell_models = {
            coords: self.solver.add_logic_cell(coords)
            for coords in self.device_topology.iter_logic_cell_coords()
        }
        self.io_block_models = {
            coords: self.solver.add_io_block(coords)
            for coords in self.device_topology.iter_io_block_coords()
        }
        self._connect_all()

        self.module_port_coords = {}
        self.logic_cell_coords = {
            coords: None for coords in self.device_topology.iter_logic_cell_coords()
        }

    def _connect_all(self):
        for switch_block_coords, switch_block_model in self.switch_block_models.items():
            for direction, neighbor_coords in self.device_topology.adjacent_switch_blocks(switch_block_coords):
                neighbor_model = self.switch_block_models[neighbor_coords]
                self.solver.connect_switch_block(switch_block_model, neighbor_model, direction)

            for direction, logic_cell_coords in self.device_topology.adjacent_logic_cells(switch_block_coords):

                # if switch_block_coords.x == 2 and switch_block_coords.y == 2 and direction is IntercardinalDirection.northeast

                logic_cell_model = self.logic_cell_models[logic_cell_coords]
                self.solver.connect_logic_cell(switch_block_model, logic_cell_model, direction)

            for direction, io_block_coords in self.device_topology.adjacent_io_blocks(switch_block_coords):
                io_block_model = self.io_block_models[io_block_coords]
                self.solver.connect_io_block(switch_block_model, io_block_model, direction)


    # def _next_unique_id(self):
    #     try:
    #         result = self._next_unique_id + 1
    #     except AttributeError:
    #         result = self._next_unique_id = 1
    #     else:
    #         self._next_unique_id += 1
    #     return result



    # TODO: Make it easy to find signal path through switch blocks.
    # Perhaps use networkx for jumps between switchblock ports?
    # This will make it easier to generate the visualization AND
    # to calculate the cost for purposes of simulated annealing optimization.
    # I know z3 can do optimization, but SA is probably better in this case
    # and I want to be able to say that I've used it.

    def add_module_port(self, module_port, coords):
        model = self.io_block_models[coords]
        model.function = IoBlockFunction.input if module_port.is_input else IoBlockFunction.output
        self.module_port_coords[coords] = module_port
        return model

    def add_logic_cell(self, logic_cell):
        # For now just assign the cells randomly.
        import random
        choices = [coords for coords, value in self.logic_cell_coords.items() if value is None]
        coords = random.choice(choices)
        model = self.logic_cell_models[coords]
        self.logic_cell_coords[coords] = model
        return model

    def route(self):
        if self.solver.check():
            return RoutingSolution(self.solver.model())
        else:
            raise RoutingError('Constraints are not satisfiable')


class RoutingSolution:

    def __init__(self, model):
        self.model = model

    def get_value(self, variable):
        value = self.model[variable]
        return None if value is None else value.as_long()

    def get_all_values(self):
        for variable in sorted(self.model.decls(), key=lambda var: var.name()):
            yield variable.name(), self.get_value(variable)


def route_design(implementation, device_topology):
    import random
    random.seed(1000)  # TODO: Remove

    router = Router(device_topology)

    models = {}
    for node in implementation.graph.nodes:
        if isinstance(node, ModulePort):
            # TODO: Constraints file or something
            if node.name == 'i_Data':
                coords = IoBlockCoordinates(direction=CardinalDirection.west, index=0)
            elif node.name == 'i_Reset':
                coords = IoBlockCoordinates(direction=CardinalDirection.west, index=1)
            elif node.name == 'o_DataFF':
                coords = IoBlockCoordinates(direction=CardinalDirection.north, index=0)
            elif node.name == 'o_DataOp':
                coords = IoBlockCoordinates(direction=CardinalDirection.north, index=1)
            elif node.name == 'o_DataPassthrough':
                coords = IoBlockCoordinates(direction=CardinalDirection.north, index=2)
            elif node.name == 'i_Clock':
                continue  # TODO
            else:
                raise NotImplementedError(node.name)
            models[node] = router.add_module_port(node, coords)
        elif isinstance(node, LogicCell):
            models[node] = router.add_logic_cell(node)
        else:
            raise NotImplementedError(node)

    from collections import defaultdict
    all_nets = set()
    connected_nets = defaultdict(set)
    for source, sink, port in implementation.graph.edges.data('port'):
        if port != 'clock':
            connected_nets[source].add((sink, port))
            all_nets.add((sink, port))
    unconnected_nets = {source: all_nets - nets for source, nets in connected_nets.items()}

    # import pdb; pdb.set_trace();  # TODO: remove me
    # pass

    # TODO: Rename this
    def _iter_port_connections(net_relationships):
        for source, nets in net_relationships.items():
            source_model = models[source]
            for sink, port in nets:
                if isinstance(source_model, LogicCellModel):
                    output_var = source_model.output.port
                elif isinstance(source_model, IoBlockModel):
                    assert source_model.function is IoBlockFunction.input
                    output_var = source_model.output_port
                else:
                    raise NotImplementedError(source_model)

                sink_model = models[sink]
                if isinstance(sink_model, LogicCellModel):
                    input_var = sink_model.inputs[port].port
                elif isinstance(sink_model, IoBlockModel):
                    assert sink_model.function is IoBlockFunction.output
                    input_var = sink_model.input_port
                else:
                    raise NotImplementedError(sink_model)
            yield input_var, output_var

    # TODO: Don't feed the solver directly
    for input_var, output_var in _iter_port_connections(connected_nets):
        router.solver.solver.add(input_var == output_var)
    for input_var, output_var in _iter_port_connections(unconnected_nets):
        router.solver.solver.add(input_var != output_var)

    solution = router.route()

    with open('model.txt', 'w') as f:
        for var, val in solution.get_all_values():
            print(f'{var} = {val}', file=f)


    import json
    routing_data = {
        'topology': {
            'width': device_topology.width,
            'height': device_topology.height,
        },
        'switch_blocks': {},
        'logic_cells': {},
        'io_blocks': {},
    }
    for coords in device_topology.iter_switch_block_coords():
        sb_model = router.switch_block_models[coords]
        routing_data['switch_blocks'][coords.name] = {
            'coords': {'x': coords.x, 'y': coords.y},
            'neighbors': {
                'switch_blocks': [
                    {'direction': direction.name, 'name': neighbor_coords.name}
                    for direction, neighbor_coords in device_topology.adjacent_switch_blocks(coords)
                ],
                'logic_cells': [
                    {'direction': direction.name, 'name': neighbor_coords.name}
                    for direction, neighbor_coords in device_topology.adjacent_logic_cells(coords)
                ],
                'io_blocks': [
                    {'direction': direction.name, 'name': neighbor_coords.name}
                    for direction, neighbor_coords in device_topology.adjacent_io_blocks(coords)
                ]
            },
            'sides': {
                direction.name: {
                    'input': solution.get_value(side.input_port),
                    'output': solution.get_value(side.output_port),
                }
                for direction, side in sb_model.sides.items()
            },
            'corners': {
                direction.name: solution.get_value(corner.port)
                for direction, corner in sb_model.corners.items()
            },
        }

    for coords in device_topology.iter_logic_cell_coords():
        # For now, skip empty logic cell locations
        if router.logic_cell_coords[coords] is None:
            continue

        # TODO: Draw muxes as well? Probably not helpful once it's working.
        # Lots of added noise.
        lc_model = router.logic_cell_models[coords]
        routing_data['logic_cells'][coords.name] = {
            'coords': {'x': coords.x, 'y': coords.y},
            'inputs': [solution.get_value(input.port) for input in lc_model.inputs],
            'output': solution.get_value(lc_model.output.port),
        }

    for coords in device_topology.iter_io_block_coords():
        if coords not in router.module_port_coords:
            continue
        module_port = router.module_port_coords[coords]

        iob_model = router.io_block_models[coords]
        routing_data['io_blocks'][coords.name] = {
            'coords': {
                'direction': coords.direction.name,
                'i': coords.index,
            },
            'module_port_name': f'{module_port.name}[{module_port.bit_index}]',
            'function': None if iob_model.function is None else iob_model.function.name,
            'input': solution.get_value(iob_model.input_port),
            'output': solution.get_value(iob_model.output_port),
        }

    with open('routing_info.json', 'w') as f:
        json.dump(routing_data, f, sort_keys=True, indent=4)
