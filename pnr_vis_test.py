
import sys
import json
import graphviz
import itertools



with open(sys.argv[1], 'r') as f:
    routing_data = json.load(f)



# # I may be missing connections from IO to IO
# idata0 = design_data['module_ports']['i_Data[0]']
# idata0_variable_key = f'io_{idata0["direction"]}[{idata0["index"]}]_input'
# idata0_value = design_data['variables'][idata0_variable_key]

# matching_keys = [
#     key for key, value in design_data['variables'].items()
#     if value == idata0_value
# ]

# import pdb; pdb.set_trace();  # TODO: remove me
# pass




g = graphviz.Digraph('PNR', engine='neato', filename='pnr.gv')







# DEVICE_WIDTH = design_data['device_dims']['width']
# DEVICE_HEIGHT = design_data['device_dims']['height']


def make_switch_block(x, y):
    name = f'$junction[{x},{y}]'
    with g.subgraph(name=f'cluster_$junction[{x},{y}]') as c:
        c.attr(style='filled', color='lightgrey')
        c.node_attr.update(shape='box', style='filled')

        X_OFFSET = 4
        Y_OFFSET = 4
        SIZE_FACTOR_X = 7
        SIZE_FACTOR_Y = 6
        c.node(f'{name}_northwest', label='NW', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!', color='green', fontcolor='white')
        c.node(f'{name}_north_output', label='<N<SUB>out</SUB>>', color='red', pos=f'{1+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!')
        c.node(f'{name}_north_input', label='<N<SUB>in</SUB>>', color='blue', fontcolor='white', pos=f'{2+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!')
        c.node(f'{name}_northeast', label='NE', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!', color='green', fontcolor='white')

        c.node(f'{name}_west_input', label='<W<SUB>in</SUB>>', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+2}!', color='blue', fontcolor='white')
        c.node(f'{name}_east_output', label='<E<SUB>out</SUB>>', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+2}!', color='red')

        c.node(f'{name}_west_output', label='<W<SUB>out</SUB>>', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+3}!', color='red')
        c.node(f'{name}_east_input', label='<E<SUB>in</SUB>>', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+3}!', color='blue', fontcolor='white')

        c.node(f'{name}_southwest', label='SW', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!', color='green', fontcolor='white')
        c.node(f'{name}_south_input', label='<S<SUB>in</SUB>>', color='blue', fontcolor='white', pos=f'{1+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!')
        c.node(f'{name}_south_output', label='<S<SUB>out</SUB>>', color='red', pos=f'{2+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!')
        c.node(f'{name}_southeast', label='SE', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!', color='green', fontcolor='white')

        c.node(name, shape='none', pos=f'{1.5+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+2}!')


def make_logic_cell(x, y):
    # https://stackoverflow.com/questions/21935109/how-do-i-style-the-ports-of-record-based-nodes-in-graphviz
    name = f'$cell[{x},{y}]'
    X_OFFSET = 4
    Y_OFFSET = 4
    logic_cell_markup = f'{{<A>A|<B>B|<C>C|<D>D}}|{{{name}\\n\\nDFF_P}}|{{<Y>Y}}'
    g.node(name, logic_cell_markup, shape='record', pos=f'{5+X_OFFSET+x*7},{-(5.5+Y_OFFSET+y*6)}!')




# TODO: I/O blocks are aligened with switch blocks, not logic cells
#  also input and output should be connected separately as a record-type box
def make_io_block(name):
    io_block = routing_data['io_blocks'][name]
    direction = io_block['coords']['direction']
    i = io_block['coords']['i']

    if direction == 'north':
        y = 0
        x = i
        X_OFFSET = 3.5
        Y_OFFSET = 3.5
    elif direction == 'south':
        y = routing_data['topology']['height']
        x = i
        X_OFFSET = 3.5
        Y_OFFSET = 9.5
    elif direction == 'east':
        x = routing_data['topology']['width']
        y = i
        X_OFFSET = 9
        Y_OFFSET = 6.5
    else:
        assert direction == 'west'
        x = 0
        y = i
        X_OFFSET = 1
        Y_OFFSET = 6.5

    # TODO: Actual user design port name

    function = 'N/A' if io_block['function'] is None else io_block['function'].title()

    markup = f'''
    {{{function} Pin}}|
    {{{name}|{io_block['module_port_name']}}}|
    {{<O>Output|<I>Input}}
    '''
    g.node(name, markup, shape='record', pos=f'{X_OFFSET+x*7},{-(Y_OFFSET+y*6)}!')



for _name, switch_block in routing_data['switch_blocks'].items():
    make_switch_block(switch_block['coords']['x'], switch_block['coords']['y'])


for _name, logic_cell in routing_data['logic_cells'].items():
    make_logic_cell(logic_cell['coords']['x'], logic_cell['coords']['y'])


for name, io_block in routing_data['io_blocks'].items():
    make_io_block(name)


for name, switch_block in routing_data['switch_blocks'].items():
    # Show connections between neighboring switch blocks
    for neighbor in switch_block['neighbors']['switch_blocks']:
        neighbor_name = neighbor['name']
        direction = neighbor['direction']
        if direction == 'north':
            g.edge(f'{name}_north_output', f'{neighbor_name}_south_input')
        elif direction == 'south':
            g.edge(f'{name}_south_output', f'{neighbor_name}_north_input')
        elif direction == 'west':
            g.edge(f'{name}_west_output', f'{neighbor_name}_east_input')
        else:
            g.edge(f'{name}_east_output', f'{neighbor_name}_west_input')

    # Show connections internal to the switch block
    for output_side_name, output_side_info in switch_block['sides'].items():
        found_edge = False
        for input_side_name, input_side_info in switch_block['sides'].items():
            if output_side_info['output'] == input_side_info['input']:
                g.edge(
                    f'{name}_{input_side_name}_input',
                    f'{name}_{output_side_name}_output',
                )
                found_edge = True
                break
        if not found_edge:
            for corner_name, corner_input in switch_block['corners'].items():
                if output_side_info['output'] == corner_input:
                    g.edge(
                        f'{name}_{corner_name}',
                        f'{name}_{output_side_name}_output',
                    )
                    break

    # Show connections to neighboring logic cells
    for neighbor in switch_block['neighbors']['logic_cells']:
        neighbor_name = neighbor['name']
        direction = neighbor['direction']

        try:
            logic_cell = routing_data['logic_cells'][neighbor_name]
        except KeyError:
            # Some aren't shown at the moment
            continue

        for i, input_value in enumerate(logic_cell['inputs']):
            port_name = f'{neighbor_name}:{"ABCD"[i]}'
            if direction == 'southwest':
                if input_value == switch_block['sides']['west']['output']:
                    g.edge(f'{name}_west_output', port_name)
            elif direction == 'southeast':
                if input_value == switch_block['sides']['south']['output']:
                    g.edge(f'{name}_south_output', port_name)
                if input_value == switch_block['sides']['east']['output']:
                    g.edge(f'{name}_east_output', port_name)
            elif direction == 'northeast':
                if input_value == switch_block['sides']['north']['output']:
                    g.edge(f'{name}_north_output', port_name)

        if switch_block['corners'][direction] == routing_data['logic_cells'][neighbor_name]['output']:
            g.edge(f'{neighbor_name}:Y', f'{name}_{direction}')

    # Show connections to neighboring io blocks
    for neighbor in switch_block['neighbors']['io_blocks']:
        neighbor_name = neighbor['name']
        direction = neighbor['direction']
        try:
            io_block = routing_data['io_blocks'][neighbor_name]
        except KeyError:
            continue

        if switch_block['sides'][direction]['output'] == io_block['input']:
            g.edge(f'{name}_{direction}_output', f'{neighbor_name}:I')

        if switch_block['sides'][direction]['input'] == io_block['output']:
            g.edge(f'{neighbor_name}:O', f'{name}_{direction}_input')


for name, logic_cell in routing_data['logic_cells'].items():
    pass








# io_dims = [('north', DEVICE_WIDTH+1), ('south', DEVICE_WIDTH+1), ('east', DEVICE_HEIGHT+1), ('west', DEVICE_HEIGHT+1)]
# for direction, size in io_dims:
#     for i in range(size):
#         make_io_block(direction, i)


# g.edge('$junction[0,0]_Wi', '$junction[0,0]_So', label='abc')
# g.edge('$junction[0,0]_So', '$junction[0,1]_Ni', label='abc')
# g.edge('$junction[0,0]_So', '$cell[0,0]:A', label='abc')
# g.edge('$cell[0,0]:Y', '$junction[1,0]_SW', label='def')
# g.edge('$cell[0,0]:Y', '$junction[1,1]_NW', label='def')

# g.edge('$io_west[0]', '$junction[0,0]_SW')
# g.edge('$io_north[0]', '$junction[0,0]_NE')


g.view()
