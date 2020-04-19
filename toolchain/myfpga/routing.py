
import itertools
from enum import Enum
from dataclasses import dataclass

import networkx as nx

import myfpga.pathfinder as pathfinder


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

    def build_network(self):
        graph = nx.DiGraph()

        # TODO: Alter costs to encourage the algorithm to select routes
        # inside a switch block instead of routing around one?

        # Set costs higher for other channels to encourage the algorithm
        # to use a single channel where possible.

        for switch_block_coords in self.iter_switch_block_coords():
            for side in switch_block_coords.sides:
                for other_side in switch_block_coords.sides:
                    if side.direction != other_side.direction:
                        for input, output in itertools.product(side.inputs, other_side.outputs):
                            # Internal to the switch block, an input will be
                            # directed to an output.
                            graph.add_edge(input, output, cost=output.channel + 1)
                for corner in switch_block_coords.corners:
                    for output in side.outputs:
                        graph.add_edge(corner, output, cost=output.channel + 1)

            for direction, other_switch_block_coords in self.adjacent_switch_blocks(switch_block_coords):
                # Only add the outgoing side, since the other switch block
                # will add its output back to this block once its turn in the
                # outer loop comes up.
                side = switch_block_coords.side(direction)
                other_side = other_switch_block_coords.side(direction.opposite)
                for input, output in zip(other_side.inputs, side.outputs):
                    # External to the switch block, an output will always
                    # drive another's input.
                    graph.add_edge(output, input, cost=output.channel + 1)

            for direction, logic_cell_coords in self.adjacent_logic_cells(switch_block_coords):
                corner = switch_block_coords.corner(direction)
                graph.add_edge(logic_cell_coords.output, corner, cost=1)

                # TODO: Extract
                for input in logic_cell_coords.inputs:
                    # Switch blocks may not connect to the inputs of logic cells
                    # to their northwest.
                    if direction is IntercardinalDirection.northeast:
                        side = switch_block_coords.side(CardinalDirection.north)
                        for output in side.outputs:
                            graph.add_edge(output, input, cost=output.channel + 1)
                    elif direction is IntercardinalDirection.southwest:
                        side = switch_block_coords.side(CardinalDirection.west)
                        for output in side.outputs:
                            graph.add_edge(output, input, cost=output.channel + 1)
                    elif direction is IntercardinalDirection.southeast:
                        side = switch_block_coords.side(CardinalDirection.south)
                        for output in side.outputs:
                            graph.add_edge(output, input, cost=output.channel + 1)
                        side = switch_block_coords.side(CardinalDirection.east)
                        for output in side.outputs:
                            graph.add_edge(output, input, cost=output.channel + 1)

            for direction, io_block_coords in self.adjacent_io_blocks(switch_block_coords):
                side = switch_block_coords.side(direction)
                for input in side.inputs:
                    graph.add_edge(io_block_coords, input, cost=100*input.channel + 1)
                for output in side.outputs:
                    graph.add_edge(output, io_block_coords, cost=100*output.channel + 1)

        return graph

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

    def input(self, port):
        return LogicCellInput(coords=self, port=port)

    @property
    def inputs(self):
        for port in range(4):
            yield self.input(port)

    @property
    def output(self):
        return LogicCellOutput(coords=self)

    @property
    def name(self):
        return f'$cell[{self.x},{self.y}]'


@dataclass(frozen=True, eq=True)
class LogicCellInput:
    coords: LogicCellCoordinates
    port: int


@dataclass(frozen=True, eq=True)
class LogicCellOutput:
    coords: LogicCellCoordinates


@dataclass(frozen=True, eq=True)
class SwitchBlockCoordinates:
    x: int
    y: int

    @property
    def name(self):
        return f'$junction[{self.x},{self.y}]'

    def corner(self, direction):
        return SwitchBlockCorner(coords=self, direction=direction)

    @property
    def corners(self):
        for direction in IntercardinalDirection:
            yield self.corner(direction)

    def side(self, direction):
        return SwitchBlockSide(coords=self, direction=direction)

    @property
    def sides(self):
        for direction in CardinalDirection:
            yield self.side(direction)


# Each switch block output mux will need 3N + 4 inputs
# (assuming that inputs from the same direction cannot be sent back
# out the same side), where N is the number of channels, to accommodate
# the other three sides' inputs and the four corners.
#
#   N  | Inputs | Mux Config Bits Needed
# -----+--------+-----------------------
#   1  |   7    |     3
#   2  |   10   |     4
#   3  |   13   |     4
#   4  |   16   |     4
#
# Four bits seems to strike a nice balance between complexity and flexibility
# while also maximizing the usefulness of the configuration bits.
#
SWITCH_BLOCK_CHANNELS = 4


@dataclass(frozen=True, eq=True)
class SwitchBlockSide:
    coords: SwitchBlockCoordinates
    direction: CardinalDirection

    def input(self, channel):
        return SwitchBlockSideInput(side=self, channel=channel)

    @property
    def inputs(self):
        for channel in range(SWITCH_BLOCK_CHANNELS):
            yield SwitchBlockSideInput(side=self, channel=channel)

    def output(self, channel):
        return SwitchBlockSideOutput(side=self, channel=channel)

    @property
    def outputs(self):
        for channel in range(SWITCH_BLOCK_CHANNELS):
            yield SwitchBlockSideOutput(side=self, channel=channel)


@dataclass(frozen=True, eq=True)
class SwitchBlockSideInput:
    side: SwitchBlockSide
    channel: int


@dataclass(frozen=True, eq=True)
class SwitchBlockSideOutput:
    side: SwitchBlockSide
    channel: int


@dataclass(frozen=True, eq=True)
class SwitchBlockCorner:
    coords: SwitchBlockCoordinates
    direction: IntercardinalDirection


@dataclass(frozen=True, eq=True)
class IoBlockCoordinates:
    direction: CardinalDirection
    index: int

    @property
    def name(self):
        return f'$io_{self.direction.name}[{self.index}]'

#     @property
#     def input(self):
#         return IoBlockInput(coords=self)

#     @property
#     def output(self):
#         return IoBlockOutput(coords=self)


# @dataclass(frozen=True, eq=True)
# class IoBlockOutput:
#     coords: IoBlockCoordinates


# @dataclass(frozen=True, eq=True)
# class IoBlockInput:
#     coords: IoBlockCoordinates



def route_design(implementation, topology):
    import random
    random.seed(3)

    from myfpga.implementation import LogicCell, ModulePort

    logic_cells = [node for node in implementation.graph if isinstance(node, LogicCell)]
    all_logic_cell_coords = list(topology.iter_logic_cell_coords())
    random.shuffle(all_logic_cell_coords)
    logic_cell_coords = {
        logic_cell: coords for logic_cell, coords
        in zip(logic_cells, all_logic_cell_coords)
    }

    module_ports = [node for node in implementation.graph if isinstance(node, ModulePort)]
    all_io_block_coords = list(topology.iter_io_block_coords())
    random.shuffle(all_io_block_coords)
    module_port_coords = {
        module_port: coords for module_port, coords
        in zip(module_ports, all_io_block_coords)
    }


    network = topology.build_network()

    route_graph = nx.DiGraph()
    nets = {}

    for source, sink, port in implementation.graph.edges.data('port'):
        if port == 'clock':
            continue

        if isinstance(source, LogicCell):
            source = logic_cell_coords[source].output
        elif isinstance(source, ModulePort):
            source = module_port_coords[source]
        else:
            raise NotImplementedError(source)

        if isinstance(sink, LogicCell):
            assert isinstance(port, int)
            sink = logic_cell_coords[sink].input(port)
        elif isinstance(sink, ModulePort):
            sink = module_port_coords[sink]
        else:
            raise NotImplementedError(sink)

        route_graph.add_edge(source, sink)
        print(source, f'--{port}-->', sink)

        nets.setdefault(source, set()).add(sink)


    routes = pathfinder.route(network, nets)

    for source, route in routes.items():
        print(source)
        print('-----------------------------------------------------')
        for x in route:
            print(x)
        print('-----------------------------------------------------\n')






