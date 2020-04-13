"""Synthesize and import a design."""

import json
from enum import Enum
from typing import List
from dataclasses import dataclass
from collections import defaultdict

import networkx as nx


@dataclass(frozen=True, eq=True)
class FlipFlop:
    name: str
    rising_edge_trigger: bool


class FlipFlopInputPort(Enum):
    clock = 0
    data = 1


@dataclass(frozen=True, eq=True)
class LookUpTable:
    name: str
    config: int


@dataclass(frozen=True, eq=True)
class ModulePort:
    name: str
    bit_index: int
    is_input: bool


@dataclass
class LookUpTableConfig:
    config: int
    input_bits: List[int]
    output_bit: int

    def __post_init__(self):
        if len(self.input_bits) > 4:
            raise ValueError('LUT must have 4 or fewer inputs')

        num_entries = 2 ** len(self.input_bits)
        config_max_value = 2 ** num_entries - 1
        if not (0 <= self.config <= config_max_value):
            raise ValueError(
                f'For a {len(self.input_bits)}-LUT, '
                f'the configuration value must be at most 0x{config_max_value:x}'
            )


@dataclass
class FlipFlopConfig:
    rising_edge_trigger: bool
    clock_bit: int
    data_input_bit: int
    output_bit: int


class Design:

    def __init__(self, data):
        for name, module in data['modules'].items():
            if module['attributes']['top']:
                self.name = name
                break
        else:
            raise ValueError('No module found')

        self.inputs = {}
        self.outputs = {}
        for name, port in module['ports'].items():
            assert port['direction'] in {'input', 'output'}
            if port['direction'] == 'input':
                self.inputs[name] = port['bits']
            else:
                self.outputs[name] = port['bits']

        self.lookup_tables = {}
        self.flip_flops = {}
        for raw_name, cell in module['cells'].items():
            name, lut_config = self._read_lut_config(raw_name, cell)
            if lut_config is not None:
                self.lookup_tables[name] = lut_config
                continue
            name, ff_config = self._read_ff_config(raw_name, cell)
            if ff_config is not None:
                self.flip_flops[name] = ff_config
                continue
            raise NotImplementedError(cell['type'])

    @staticmethod
    def _read_lut_config(raw_name, cell):
        if cell['type'] != '$lut':
            return None, None
        name = f'$lut${raw_name.split("$")[-1]}'
        try:
            return name, LookUpTableConfig(
                config=int(cell['parameters']['LUT'], 2),
                input_bits=cell['connections']['A'],
                output_bit=cell['connections']['Y'][0],
            )
        except ValueError as exc:
            raise ValueError(f'LUT {name}: {exc}') from exc

    @staticmethod
    def _read_ff_config(raw_name, cell):
        if cell['type'] == '$_DFF_P_':
            name = f'$dff_p${raw_name.split("$")[-1]}'
            rising_edge_trigger = True
        elif cell['type'] == '$_DFF_N_':
            name = f'$dff_n${raw_name.split("$")[-1]}'
            rising_edge_trigger = False
        else:
            return None, None
        return name, FlipFlopConfig(
            rising_edge_trigger=rising_edge_trigger,
            clock_bit=cell['connections']['C'][0],
            data_input_bit=cell['connections']['D'][0],
            output_bit=cell['connections']['Q'][0],
        )

    @classmethod
    def load(cls, f):
        return cls(json.load(f))

    def build_graph(self):
        """Build a directed graph representing this design.

        The graph may be made acyclic by removing edges at flip flop outputs.

        """
        connection_inputs = defaultdict(list)
        connection_outputs = dict()

        for name, bits in self.inputs.items():
            for i, bit in enumerate(bits):
                assert bit not in connection_outputs
                module_port = ModulePort(name=name, bit_index=i, is_input=True)
                connection_outputs[bit] = module_port

        for name, bits in self.outputs.items():
            for i, bit in enumerate(bits):
                module_port = ModulePort(name=name, bit_index=i, is_input=False)
                connection_inputs[bit].append((module_port, {}))

        for name, ff_config in self.flip_flops.items():
            assert ff_config.output_bit not in connection_outputs
            ff = FlipFlop(name=name, rising_edge_trigger=ff_config.rising_edge_trigger)
            connection_inputs[ff_config.clock_bit].append(
                (ff, {'port': FlipFlopInputPort.clock}))
            connection_inputs[ff_config.data_input_bit].append(
                (ff, {'port': FlipFlopInputPort.data}))
            connection_outputs[ff_config.output_bit] = ff

        for name, lut_config in self.lookup_tables.items():
            assert lut_config.output_bit not in connection_outputs
            lut = LookUpTable(name=name, config=lut_config.config)
            for i, input_bit in enumerate(lut_config.input_bits):
                connection_inputs[input_bit].append((lut, {'port': i}))
            connection_outputs[lut_config.output_bit] = lut

        graph = nx.DiGraph()
        for bit_id, source in connection_outputs.items():
            for sink, attrs in connection_inputs[bit_id]:
                graph.add_edge(source, sink, **attrs)
        return graph

    def __str__(self):
        return self.name
