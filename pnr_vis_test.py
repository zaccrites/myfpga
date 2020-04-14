
import sys
import json
import graphviz
import itertools



with open(sys.argv[1], 'r') as f:
    design_data = json.load(f)



# I may be missing connections from IO to IO
idata0 = design_data['module_ports']['i_Data[0]']
idata0_variable_key = f'io_{idata0["direction"]}[{idata0["index"]}]_input'
idata0_value = design_data['variables'][idata0_variable_key]

matching_keys = [
    key for key, value in design_data['variables'].items()
    if value == idata0_value
]

import pdb; pdb.set_trace();  # TODO: remove me
pass




g = graphviz.Digraph('PNR', engine='neato', filename='pnr.gv')







DEVICE_WIDTH = design_data['device_dims']['width']
DEVICE_HEIGHT = design_data['device_dims']['height']


def make_switch_block(x, y):
    name = f'$junction[{x},{y}]'
    with g.subgraph(name=f'cluster_$junction[{x},{y}]') as c:
        c.attr(style='filled', color='lightgrey')
        c.node_attr.update(shape='box', style='filled')

        X_OFFSET = 4
        Y_OFFSET = 4
        SIZE_FACTOR_X = 7
        SIZE_FACTOR_Y = 6
        c.node(f'{name}_NW', label='NW', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!', color='green', fontcolor='white')
        c.node(f'{name}_No', label='<N<SUB>out</SUB>>', color='red', pos=f'{1+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!')
        c.node(f'{name}_Ni', label='<N<SUB>in</SUB>>', color='blue', fontcolor='white', pos=f'{2+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!')
        c.node(f'{name}_NE', label='NE', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+1}!', color='green', fontcolor='white')

        c.node(f'{name}_Wi', label='<W<SUB>in</SUB>>', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+2}!', color='blue', fontcolor='white')
        c.node(f'{name}_Eo', label='<E<SUB>out</SUB>>', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+2}!', color='red')

        c.node(f'{name}_Wo', label='<W<SUB>out</SUB>>', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+3}!', color='red')
        c.node(f'{name}_Ei', label='<E<SUB>in</SUB>>', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+3}!', color='blue', fontcolor='white')

        c.node(f'{name}_SW', label='SW', pos=f'{0+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!', color='green', fontcolor='white')
        c.node(f'{name}_Si', label='<S<SUB>in</SUB>>', color='blue', fontcolor='white', pos=f'{1+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!')
        c.node(f'{name}_So', label='<S<SUB>out</SUB>>', color='red', pos=f'{2+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!')
        c.node(f'{name}_SE', label='SE', pos=f'{3+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+4}!', color='green', fontcolor='white')

        c.node(name, shape='none', pos=f'{1.5+X_OFFSET+x*SIZE_FACTOR_X},-{y*SIZE_FACTOR_Y+Y_OFFSET+2}!')


for x, y in itertools.product(range(DEVICE_WIDTH + 1), range(DEVICE_HEIGHT + 1)):
    make_switch_block(x, y)


def make_logic_cell(x, y):
    # https://stackoverflow.com/questions/21935109/how-do-i-style-the-ports-of-record-based-nodes-in-graphviz
    name = f'$cell[{x},{y}]'
    X_OFFSET = 4
    Y_OFFSET = 4
    logic_cell_markup = f'{{<A>A|<B>B|<C>C|<D>D}}|{{{name}\\n\\nDFF_P}}|{{<Y>Y}}'
    g.node(name, logic_cell_markup, shape='record', pos=f'{5+X_OFFSET+x*7},{-(5.5+Y_OFFSET+y*6)}!')


for x, y in itertools.product(range(DEVICE_WIDTH), range(DEVICE_HEIGHT)):
    make_logic_cell(x, y)


def make_io_block(direction, i):
    if direction == 'north':
        y = 0
        x = i
        X_OFFSET = 5.5
        Y_OFFSET = 3.5
    elif direction == 'south':
        y = DEVICE_HEIGHT
        x = i
        X_OFFSET = 5.5
        Y_OFFSET = 9.5
    elif direction == 'east':
        x = DEVICE_WIDTH
        y = i
        X_OFFSET = 9
        Y_OFFSET = 6.5
    else:
        assert direction == 'west'
        x = 0
        y = i
        X_OFFSET = 2
        Y_OFFSET = 6.5

    # TODO: Actual user design port name
    name = f'$io_{direction}[{i}]'
    g.node(name, pos=f'{X_OFFSET+x*7},{-(Y_OFFSET+y*6)}!')


io_dims = [('north', DEVICE_WIDTH+1), ('south', DEVICE_WIDTH+1), ('east', DEVICE_HEIGHT+1), ('west', DEVICE_HEIGHT+1)]
for direction, size in io_dims:
    for i in range(size):
        make_io_block(direction, i)


g.edge('$junction[0,0]_Wi', '$junction[0,0]_So', label='abc')
g.edge('$junction[0,0]_So', '$junction[0,1]_Ni', label='abc')
g.edge('$junction[0,0]_So', '$cell[0,0]:A', label='abc')
g.edge('$cell[0,0]:Y', '$junction[1,0]_SW', label='def')
g.edge('$cell[0,0]:Y', '$junction[1,1]_NW', label='def')

g.edge('$io_west[0]', '$junction[0,0]_SW')
g.edge('$io_north[0]', '$junction[0,0]_NE')


g.view()
