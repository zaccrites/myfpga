"""Place and route the design."""

import math
import random
import itertools
from enum import Enum
from collections import defaultdict
from dataclasses import dataclass
from typing import List

from z3 import Solver, If, Int, BitVec

# TODO: Address this better
from myfpga.implementation import LogicCell as ImplementationLogicCell
from myfpga.implementation import ModulePort as ImplementationModulePort


class Direction(Enum):
    north = 0
    south = 1
    east = 2
    west = 3


@dataclass
class DeviceConfig:
    width: int
    height: int
    lut_width: int = 4


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

    northwest_logic_cell_input: Int
    northeast_logic_cell_input: Int
    southwest_logic_cell_input: Int
    southeast_logic_cell_input: Int


@dataclass
class LogicCellInput:
    input: Int
    mux_selector: Int


@dataclass
class LogicCell:
    inputs: List[LogicCellInput]
    output: Int


@dataclass
class IoBlock:
    input: Int
    output: Int
    is_input: bool = True


class RoutingError(RuntimeError):
    pass


class Router:

    def __init__(self, implementation, device_config):
        self.implementation = implementation
        self.device_config = device_config
        self.solver = Solver()
        self.net_ids = {}
        self.switch_blocks = {}
        self.logic_cells = {}
        self.io_blocks = {}

    def _iter_logic_cell_coords(self):
        width = self.device_config.width
        height = self.device_config.height
        yield from itertools.product(range(width), range(height))

    def _iter_switch_block_coords(self):
        width = self.device_config.width + 1
        height = self.device_config.height + 1
        yield from itertools.product(range(width), range(height))

    def _iter_io_block_coords(self):
        width = self.device_config.width + 1
        height = self.device_config.height + 1
        yield from itertools.product([Direction.north, Direction.south], range(width))
        yield from itertools.product([Direction.west, Direction.east], range(height))

    def _create_unique_id(self):
        try:
            self._next_unique_id += 1
        except AttributeError:
            self._next_unique_id = 1
        return self._next_unique_id

    def _add_mux(self, name, inputs, output):
        if len(inputs) < 2:
            raise ValueError('Must have at least two inputs')

        num_selector_bits = math.ceil(math.log2(len(inputs)))
        selector = BitVec(f'{name}_sel', num_selector_bits)

        expr = If(selector == len(inputs) - 2, inputs[-2], inputs[-1])
        stack = [(input, selector == i) for i, input in enumerate(inputs[:-2])]
        while stack:
            input, selector_check = stack.pop()
            expr = If(selector_check, input, expr)

        self.solver.add(expr == output)
        return selector

    def _add_switch_block(self, x, y):
        # TODO: Extend to three wires in each direction
        name = f'junction[{x},{y}]'

        switch_block_inputs = {
            direction: Int(f'{name}_{direction.name}_input')
            for direction in Direction
        }
        switch_block_outputs = {
            direction: Int(f'{name}_{direction.name}_output')
            for direction in Direction
        }

        switch_mux_selectors = {}
        for direction in Direction:
            mux_inputs = [switch_block_inputs[direction] for direction in Direction]
            mux_output = switch_block_outputs[direction]
            mux_selector = self._add_mux(f'{name}_{direction.name}_mux', mux_inputs, mux_output)
            switch_mux_selectors[direction] = mux_selector

        switch_block_ports = {
            direction: SwitchBlockPort(
                input=switch_block_inputs[direction],
                output=switch_block_outputs[direction],
                mux_selector=switch_mux_selectors[direction],
            )
            for direction in Direction
        }
        self.switch_blocks[(x, y)] = SwitchBlock(
            north=switch_block_ports[Direction.north],
            south=switch_block_ports[Direction.south],
            east=switch_block_ports[Direction.east],
            west=switch_block_ports[Direction.west],

            northwest_logic_cell_input=Int(f'{name}_nw_cell_input'),
            northeast_logic_cell_input=Int(f'{name}_ne_cell_input'),
            southwest_logic_cell_input=Int(f'{name}_sw_cell_input'),
            southeast_logic_cell_input=Int(f'{name}_se_cell_input'),
        )

    def _add_logic_cell(self, x, y):
        name = f'cell[{x},{y}]'
        self.logic_cells[(x, y)] = LogicCell(
            inputs=[
                LogicCellInput(input=Int(f'{name}_input{i}'), mux_selector=None)
                for i in range(self.device_config.lut_width)
            ],
            output=Int(f'{name}_output'),
        )

    def _create_logic_cells(self):
        for x, y in self._iter_logic_cell_coords():
            self._add_logic_cell(x, y)

    def _add_io_block(self, direction, i):
        name = f'io_{direction.name}[{i}]'
        self.io_blocks[(direction, i)] = IoBlock(
            input=Int(f'{name}_input'),
            output=Int(f'{name}_output'),
        )

    def _create_io_blocks(self):
        for direction, i in self._iter_io_block_coords():
            self._add_io_block(direction, i)

    def _create_switch_blocks(self):
        for x, y in self._iter_switch_block_coords():
            self._add_switch_block(x, y)

    def _connect_switch_blocks(self, x, y):
        """Connect adjacent switch blocks to one another."""
        this_block = self.switch_blocks[(x, y)]
        if x > 0:
            west_block = self.switch_blocks[(x - 1, y)]
            self.solver.add(this_block.west.input == west_block.east.output)
        if x < self.device_config.width:
            east_block = self.switch_blocks[(x + 1, y)]
            self.solver.add(this_block.east.input == east_block.west.output)
        if y > 0:
            north_block = self.switch_blocks[(x, y - 1)]
            self.solver.add(this_block.north.input == north_block.south.output)
        if y < self.device_config.height:
            south_block = self.switch_blocks[(x, y + 1)]
            self.solver.add(this_block.south.input == south_block.north.output)

    def _connect_logic_cells(self, x, y):
        """Connect logic cells to adjacent switch blocks."""
        logic_cell = self.logic_cells[(x, y)]
        northwest_switch_block = self.switch_blocks[(x, y)]
        northeast_switch_block = self.switch_blocks[(x + 1, y)]
        southwest_switch_block = self.switch_blocks[(x, y + 1)]
        southeast_switch_block = self.switch_blocks[(x + 1, y + 1)]

        # Connect north and west switch blocks to the logic cell
        # input multiplexers.
        for i, logic_cell_input in enumerate(logic_cell.inputs):
            mux_inputs = [
                southwest_switch_block.north.output,  # northbound signal
                northwest_switch_block.south.output,  # southbound signal
                northwest_switch_block.east.output,  # eastbound signal
                northeast_switch_block.west.output,  # westbound signal
            ]
            logic_cell_input.mux_selector = self._add_mux(
                f'cell[{x},{y}]_input{i}_mux',
                mux_inputs,
                logic_cell_input.input,
            )

        # Connect the logic cell to all neighboring switch blocks'
        # logic cell inputs.
        self.solver.add(
            northwest_switch_block.southeast_logic_cell_input == logic_cell.output,
            northeast_switch_block.southwest_logic_cell_input == logic_cell.output,
            southwest_switch_block.northeast_logic_cell_input == logic_cell.output,
            southeast_switch_block.northwest_logic_cell_input == logic_cell.output,
        )

    def _connect_io_block(self, direction, i):
        io_block = self.io_blocks[(direction, i)]
        if direction is Direction.north:
            switch_block = self.switch_blocks[(i, 0)]
            self.solver.add(
                switch_block.north.output == io_block.input,
                switch_block.north.input == io_block.output,
            )

        elif direction is Direction.south:
            switch_block = self.switch_blocks[(i, self.device_config.height)]
            self.solver.add(
                switch_block.south.output == io_block.input,
                switch_block.south.input == io_block.output,
            )

        elif direction is Direction.east:
            switch_block = self.switch_blocks[(self.device_config.width, i)]
            self.solver.add(
                switch_block.east.output == io_block.input,
                switch_block.east.input == io_block.output,
            )

        else:
            assert direction is Direction.west
            switch_block = self.switch_blocks[(0, i)]
            self.solver.add(
                switch_block.west.output == io_block.input,
                switch_block.west.input == io_block.output,
            )

    def _connect_all(self):
        for x, y in self._iter_switch_block_coords():
            self._connect_switch_blocks(x, y)
        for x, y in self._iter_logic_cell_coords():
            self._connect_logic_cells(x, y)
        for direction, i in self._iter_io_block_coords():
            self._connect_io_block(direction, i)

    def place_and_route(self):
        # The device "width" and "height" is the size of the grid in
        # logic cells. There are switch blocks surrounding each logic cell,
        # and a layer of I/O blocks surrounding the outside layer of
        # switch blocks.

        self._create_switch_blocks()
        self._create_logic_cells()
        self._create_io_blocks()
        self._connect_all()

        all_nets = set()
        connected_nets = defaultdict(set)
        for source, sink, port in self.implementation.graph.edges.data('port'):
            if port != 'clock':
                connected_nets[source].add((sink, port))
                all_nets.add((sink, port))
        unconnected_nets = {key: all_nets - value for key, value in connected_nets.items()}

        # Randomly assign cells
        logic_cells = [node for node in self.implementation.graph.nodes if isinstance(node, ImplementationLogicCell)]
        all_coords = list(self._iter_logic_cell_coords())
        if len(all_coords) < len(logic_cells):
            raise RoutingError(f'Not enough logic cell locations (need {len(logic_cells)})')
        random.shuffle(all_coords)
        logic_cell_locations = dict(zip(logic_cells, all_coords))

        # Randomly assign IO blocks
        module_ports = [node for node in self.implementation.graph.nodes if isinstance(node, ImplementationModulePort)]
        all_coords = list(self._iter_io_block_coords())
        if len(all_coords) < len(module_ports):
            raise RoutingError(f'Not enough I/O block locations (need {len(module_ports)})')
        random.shuffle(all_coords)
        module_port_locations = dict(zip(module_ports, all_coords))

        # TODO: Put this in the class itself
        def _get_source_port(source):
            if isinstance(source, LogicCell):
                return source.output
            elif isinstance(source, IoBlock):
                return source.output
            else:
                raise NotImplementedError(source)

        def _get_sink_ports(sink):
            if isinstance(sink, LogicCell):
                return [input.input for input in sink.inputs]
            elif isinstance(sink, IoBlock):
                return [sink.input]
            else:
                raise NotImplementedError(sink)

        # TODO: Clean this up
        def _get_source_and_sink_ports(linked_nets):
            # This is meant to just get the real internal device
            # connections for a given implementation model.
            # This function (and a lot of other things, probably)
            # need to be renamed.
            #
            # The "linked" nets may be linked by virtue of sources directly
            # driving sinks or by explicitly NOT having that relationship,
            # so that the connection can be forbidden.
            for source, sinks in linked_nets.items():
                if isinstance(source, ImplementationLogicCell):
                    coords = logic_cell_locations[source]
                    logic_cell = self.logic_cells[coords]
                    source_port = _get_source_port(logic_cell)
                elif isinstance(source, ImplementationModulePort):
                    coords = module_port_locations[source]
                    io_block = self.io_blocks[coords]
                    source_port = _get_source_port(io_block)

                    assert source.is_input
                    io_block.is_input = True
                else:
                    raise NotImplementedError(source)

                for sink, port in sinks:
                    if isinstance(sink, ImplementationLogicCell):
                        coords = logic_cell_locations[sink]
                        logic_cell = self.logic_cells[coords]
                        sink_port = _get_sink_ports(logic_cell)[port]
                    elif isinstance(sink, ImplementationModulePort):
                        coords = module_port_locations[sink]
                        io_block = self.io_blocks[coords]
                        sink_port = _get_sink_ports(io_block)[0]

                        assert not sink.is_input
                        io_block.is_input = False
                    else:
                        raise NotImplementedError(sink)

                    yield source_port, sink_port

        for source_port, sink_port in _get_source_and_sink_ports(connected_nets):
            self.solver.add(source_port == sink_port)
        for source_port, sink_port in _get_source_and_sink_ports(unconnected_nets):
            self.solver.add(source_port != sink_port)

        with open('solver.txt', 'w') as f:
            f.write(self.solver.sexpr())

        # from pprint import pprint
        # pprint(dict(connected_nets))

        line_filters = [
            f'cell[{x},{y}]' for x, y in logic_cell_locations.values()
        ]
        line_filters.extend([
            f'io_{direction.name}[{i}]' for direction, i in module_port_locations.values()
        ])
        # TODO: Include junctions that touch other cells we're interested in

        if str(self.solver.check()) == 'unsat':
            raise RoutingError('Routing model is unsatisfiable')
        else:
            model = self.solver.model()

            model_variables = {}

            with open('model.txt', 'w') as f:
                variables = sorted(model.decls(), key=lambda var: var.name())
                for variable in variables:
                    value = model[variable]
                    line = f'{variable.name()} = {value}'

                    model_variables[variable.name()] = value.as_long()

                    if any(filter_word in line for filter_word in line_filters):
                        print(line)

                    print(line, file=f)

                print('----------')
                print(f'{len(variables)} variables')


            print('========================')
            for module_port, (direction, i) in module_port_locations.items():
                print(f'{module_port.name}: io_{direction.name}[{i}]')








            # def _encode_var(var):
            #     val = model[var]
            #     return None if val is None else val.as_long()

            # def _encode_port(port):
            #     return {
            #         'input': _encode_var(port.input),
            #         'output': _encode_var(port.output),
            #     }

            # for (x, y), switch_block in self.switch_blocks.items():
            #     all_info['switch_blocks'][f'{x},{y}'] = {
            #         'north': _encode_port(switch_block.north),
            #         'south': _encode_port(switch_block.south),
            #         'east': _encode_port(switch_block.east),
            #         'west': _encode_port(switch_block.west),

            #         'northwest': _encode_var(switch_block.northwest_logic_cell_input),
            #         'southwest': _encode_var(switch_block.southwest_logic_cell_input),
            #         'northeast': _encode_var(switch_block.northeast_logic_cell_input),
            #         'southeast': _encode_var(switch_block.southeast_logic_cell_input),
            #     }

            import json

            all_info = {
                'device_dims': {'width': self.device_config.width, 'height': self.device_config.height},
                'variables': model_variables,
                'module_ports': {
                    f'{port.name}[{port.bit_index}]': {'direction': direction.name, 'index': i}
                    for port, (direction, i) in module_port_locations.items()
                },
            }
            # import pdb; pdb.set_trace();  # TODO: remove me
            pass

            with open('all_info.json', 'w') as f:
                # json.dump(all_info, f, sort_keys=True, indent=4)
                json.dump(all_info, f, sort_keys=True, indent=4)




        # TODO: Force clock input to a specific global clock port


#
#
        return None






import jinja2
from jinja2 import StrictUndefined, Environment, PackageLoader, select_autoescape


class RoutingVisualization:

    """Visualize routing as an SVG diagram."""

    def __init__(self, router):
        self.jinja_env = jinja2.Environment(
            loader=jinja2.PackageLoader('myfpga', 'templates'),
            autoescape=jinja2.select_unescape(enabled_extensions=['html']),
            undefined=jinja2.StrictUndefined,
        )


        # # TODO: Clean this up. Just a quick prototype.

        # @dataclass
        # class Rectangle:
        #     x: int
        #     y: int
        #     width: int
        #     height: int
        #     stroke: str
        #     stroke_width: int
        #     fill: str

        # rectangles = []

        # SWITCH_BLOCK_SIZE = 75
        # LOGIC_CELL_SIZE = 50
        # IO_BLOCK_SIZE = LOGIC_CELL_SIZE
        # MARGIN = 20

        # for x, y in self._iter_switch_block_coords():
        #     rectangles.append(Rectangle(
        #         x=(MARGIN + IO_BLOCK_SIZE + MARGIN + x * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)),
        #         y=(MARGIN + IO_BLOCK_SIZE + MARGIN + y * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)),
        #         width=SWITCH_BLOCK_SIZE,
        #         height=SWITCH_BLOCK_SIZE,
        #         stroke='red',
        #         stroke_width=3,
        #         fill='transparent',
        #     ))

        # for x, y in self._iter_logic_cell_coords():
        #     rectangles.append(Rectangle(
        #         x=(MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + x * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)),
        #         y=(MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + y * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)),
        #         width=LOGIC_CELL_SIZE,
        #         height=LOGIC_CELL_SIZE,
        #         stroke='black',
        #         stroke_width=2,
        #         fill='transparent',
        #     ))

        # for direction, i in self._iter_io_block_coords():
        #     if direction is Direction.north:
        #         y = MARGIN
        #         x = MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + i * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)
        #     elif direction is Direction.south:
        #         y = MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + self.device_config.height * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)
        #         x = MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + i * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)
        #     elif direction is Direction.east:
        #         y = MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + i * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)
        #         x = MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + self.device_config.width * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)
        #     else:
        #         assert direction is Direction.west
        #         y = MARGIN + IO_BLOCK_SIZE + MARGIN + SWITCH_BLOCK_SIZE + MARGIN + i * (SWITCH_BLOCK_SIZE + IO_BLOCK_SIZE + 2*MARGIN)
        #         x = MARGIN
        #     rectangles.append(Rectangle(
        #         x=x,
        #         y=y,
        #         width=IO_BLOCK_SIZE,
        #         height=IO_BLOCK_SIZE,
        #         stroke='green',
        #         stroke_width=1,
        #         fill='transparent',
        #     ))


        # # logic_block_rects = []
        # # for x, y in self._iter_logic_cell_coords():
        # #     logic_block_rects.append((x, y))

        # # io_block_rects = []
        # # for direction, i in self._iter_io_block_coords():
        # #     io_block_rects.append((direction, i))


        # params = {
        #     'rectangles': rectangles,
        #     # 'switch_block_rects': switch_block_rects,
        #     # 'logic_block_rects': logic_block_rects,
        #     # 'io_block_rects': io_block_rects,
        # }


        # import pdb; pdb.set_trace();  # TODO: remove me
        # pass

        # # TODO: Use Jinja to generate a webpage with an interactive SVG
        # # representation of the floorplan
        # env = Environment(
        #     loader=PackageLoader('myfpga', 'templates'),
        #     autoescape=select_autoescape(enabled_extensions=['html']),
        #     undefined=StrictUndefined,
        # )
        # template = env.get_template('svgtest.html')
        # with open('svgtest.html', 'w') as f:
        #     f.write(template.render(**params))


