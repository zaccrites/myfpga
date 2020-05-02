
use std::collections::HashMap;

use petgraph::graph::DiGraph;


// Previous versions of Yosys emitted LUT masks as strings ones and zeroes.
// At some point it changed to emitting plain integers.
#[derive(Debug, Clone, Copy)]
enum YosysLutMask<'a> {
    BitString(&'a str),
    Integer(u16, usize),
}

impl<'a> YosysLutMask<'a> {
    fn decode(self) -> LookUpTableMask {
        fn expand_to_16_bits(raw_value: u16, width: usize) -> u16 {
            let repeat_count = 16 / width;
            (1..repeat_count).fold(raw_value, |acc, _| (acc << width) | raw_value)
        }

        let config_value = match self {
            Self::BitString(raw_config) => {
                let width = raw_config.len();
                let decoded = u16::from_str_radix(&raw_config, 2).unwrap();
                expand_to_16_bits(decoded, width)
            },
            Self::Integer(raw_config, width) => expand_to_16_bits(raw_config, width),
        };
        LookUpTableMask::new(config_value)
    }
}


// A 4-LUT needs 16 configuration bits
#[derive(Debug, Clone, Copy)]
pub struct LookUpTableMask(u16);

impl LookUpTableMask {
    pub fn new(mask: u16) -> Self {
        Self(mask)
    }

    pub fn get(self) -> u16 {
        self.0
    }
}


#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
struct NetId(u32);


#[derive(Debug)]
struct LookUpTableConfig {
    name: String,
    mask: LookUpTableMask,
    inputs: [Option<NetId>; 4],
    output: NetId,
}

impl LookUpTableConfig {
    fn try_read(name: &str, cell: &serde_json::Value) -> Option<Self> {
        // TODO: Error handling
        if cell["type"].as_str().unwrap() != "$lut" {
            return None;
        }

        let mask = match &cell["parameters"]["LUT"] {
            serde_json::Value::Number(value) => {
                let width = cell["parameters"]["WIDTH"].as_u64().unwrap() as usize;
                YosysLutMask::Integer(value.as_u64().unwrap() as u16, width).decode()
            },
            serde_json::Value::String(value) => YosysLutMask::BitString(&value).decode(),
            _ => panic!(),
        };

        let mut inputs = [None; 4];
        for (i, input) in cell["connections"]["A"].as_array().unwrap().iter().enumerate() {
            inputs[i] = Some(NetId(input.as_u64().unwrap() as u32));
        }

        let output = NetId(cell["connections"]["Y"][0].as_u64().unwrap() as u32);

        let id = name.split('$').last().unwrap();
        let name = format!("$lut${}", id);

        Some(Self {
            name,
            mask,
            inputs,
            output,
        })
    }
}


#[derive(Debug, Clone, Copy)]
pub enum FlipFlopTrigger {
    RisingEdge,
    FallingEdge,
}


#[derive(Debug)]
struct FlipFlopConfig {
    name: String,
    trigger: FlipFlopTrigger,
    clock: NetId,
    data: NetId,
    output: NetId,
}

impl FlipFlopConfig {
    fn try_read(name: &str, cell: &serde_json::Value) -> Option<Self> {
        let trigger = match cell["type"].as_str().unwrap() {
            "$_DFF_P_" => Some(FlipFlopTrigger::RisingEdge),
            "$_DFF_N_" => Some(FlipFlopTrigger::FallingEdge),
            _ => None,
        }?;

        let id = name.split('$').last().unwrap();
        let name = match trigger {
            FlipFlopTrigger::RisingEdge => format!("$dff_pos${}", id),
            FlipFlopTrigger::FallingEdge => format!("$dff_neg${}", id),
        };

        let clock = NetId(cell["connections"]["C"][0].as_u64().unwrap() as u32);
        let data = NetId(cell["connections"]["D"][0].as_u64().unwrap() as u32);
        let output = NetId(cell["connections"]["Q"][0].as_u64().unwrap() as u32);

        Some(Self {
            name,
            trigger,
            clock,
            data,
            output,
        })
    }
}


#[derive(Debug, Clone, Copy)]
pub enum ModulePortDirection {
    Input,
    Output,
}

#[derive(Debug)]
struct ModulePortConfig {
    name: String,
    direction: ModulePortDirection,
    net: NetId,
}

impl ModulePortConfig {
    fn read(name: &str, port: &serde_json::Value) -> Vec<Self> {
        let direction = match port["direction"].as_str().unwrap() {
            "input" => ModulePortDirection::Input,
            "output" => ModulePortDirection::Output,
            direction => panic!("Unknown port direction '{}'", direction),
        };
        let bits = port["bits"].as_array().unwrap();
        bits.iter().enumerate().map(|(i, bit)| {
            let name = if bits.len() == 1 {
                String::from(name)
            }
            else {
                format!("{}[{}]", name, i)
            };
            Self {
                name,
                net: NetId(bit.as_u64().unwrap() as u32),
                direction,
            }
        }).collect()
    }
}



#[derive(Debug, Clone)]
pub struct ModulePort {
    pub name: String,
    pub direction: ModulePortDirection,
}

impl From<ModulePortConfig> for ModulePort {
    fn from(config: ModulePortConfig) -> Self {
        Self {
            name: config.name,
            direction: config.direction,
        }
    }
}


#[derive(Debug, Clone)]
pub struct FlipFlop {
    pub name: String,
    pub trigger: FlipFlopTrigger,
}

impl From<FlipFlopConfig> for FlipFlop {
    fn from(config: FlipFlopConfig) -> Self {
        Self {
            name: config.name,
            trigger: config.trigger,
        }
    }
}


#[derive(Debug, Clone)]
pub struct LookUpTable {
    pub name: String,
    pub mask: LookUpTableMask,
}

impl From<LookUpTableConfig> for LookUpTable {
    fn from(config: LookUpTableConfig) -> Self {
        Self {
            name: config.name,
            mask: config.mask,
        }
    }
}



pub type DesignGraph = DiGraph<DesignGraphNode, DesignGraphEdge>;


#[derive(Debug)]
pub enum DesignGraphNode {
    LookUpTable(LookUpTable),
    FlipFlop(FlipFlop),
    ModulePort(ModulePort),
}

impl DesignGraphNode {
    pub fn name(&self) -> String {
        match self {
            DesignGraphNode::LookUpTable(lut) => lut.name.clone(),
            DesignGraphNode::FlipFlop(ff) => ff.name.clone(),
            DesignGraphNode::ModulePort(port) => port.name.clone(),
        }
    }
}


#[derive(Debug, Clone, Copy)]
pub enum LookUpTableInput {
    A,
    B,
    C,
    D,
}

impl LookUpTableInput {
    fn iter() -> impl Iterator<Item=Self> {
        [Self::A, Self::B, Self::C, Self::D].iter().copied()
    }
}


#[derive(Debug, Clone, Copy)]
pub enum FlipFlopInput {
    Clock,
    Data,
}


#[derive(Debug, Clone, Copy)]
pub enum DesignGraphEdge {
    LookUpTableInput(LookUpTableInput),
    FlipFlopInput(FlipFlopInput),
    ModulePortInput,
}

impl DesignGraphEdge {
    fn can_connect_to(self, node: &DesignGraphNode) -> bool {
        match (self, node) {
            (DesignGraphEdge::LookUpTableInput(_), DesignGraphNode::LookUpTable(_)) => true,
            (DesignGraphEdge::FlipFlopInput(_), DesignGraphNode::FlipFlop(_)) => true,
            (DesignGraphEdge::ModulePortInput, DesignGraphNode::ModulePort(ModulePort{ direction: ModulePortDirection::Output, .. })) => true,
            _ => false,
        }
    }
}


// TODO: Better interface than exposing these directly
pub struct Design {
    pub name: String,
    ports: Vec<ModulePortConfig>,
    flip_flops: Vec<FlipFlopConfig>,
    lookup_tables: Vec<LookUpTableConfig>,
}

impl Design {
    pub fn read(data: serde_json::Value) -> Self {
        let (module_name, module_data) = data["modules"].as_object().unwrap().iter().next().unwrap();

        let ports = module_data["ports"].as_object().unwrap().iter()
            .map(|(name, port)| ModulePortConfig::read(name, port)).flatten().collect();

        let lookup_tables = module_data["cells"].as_object().unwrap().iter()
            .map(|(name, cell)| LookUpTableConfig::try_read(name, cell)).flatten().collect();

        let flip_flops = module_data["cells"].as_object().unwrap().iter()
            .map(|(name, cell)| FlipFlopConfig::try_read(name, cell)).flatten().collect();

        Self {
            name: String::from(module_name),
            ports,
            flip_flops,
            lookup_tables,
        }
    }

    // TODO: Return Result<DesignGraph, SynthesisError> from here or read()
    // Return Err instead of panicking if JSON read fails
    pub fn into_graph(self) -> DesignGraph {
        let mut graph = DesignGraph::new();
        let mut net_sources = HashMap::new();
        let mut net_sinks = HashMap::new();

        for port_config in self.ports {
            let net = port_config.net;
            let direction = port_config.direction;
            let node = graph.add_node(DesignGraphNode::ModulePort(port_config.into()));
            match direction {
                ModulePortDirection::Input => {
                    assert!( ! net_sources.contains_key(&net));
                    net_sources.insert(net, node);
                },
                ModulePortDirection::Output => {
                    net_sinks.entry(net).or_insert_with(Vec::new).push((node, DesignGraphEdge::ModulePortInput));
                }
            }
        }

        for ff_config in self.flip_flops {
            let data_net = ff_config.data;
            let clock_net = ff_config.clock;
            let output_net = ff_config.output;
            let node = graph.add_node(DesignGraphNode::FlipFlop(ff_config.into()));

            net_sinks.entry(clock_net).or_insert_with(Vec::new).push((node, DesignGraphEdge::FlipFlopInput(FlipFlopInput::Clock)));
            net_sinks.entry(data_net).or_insert_with(Vec::new).push((node, DesignGraphEdge::FlipFlopInput(FlipFlopInput::Data)));

            assert!( ! net_sources.contains_key(&output_net));
            net_sources.insert(output_net, node);
        }

        for lut_config in self.lookup_tables {
            let input_nets = lut_config.inputs;
            let output_net = lut_config.output;
            let node = graph.add_node(DesignGraphNode::LookUpTable(lut_config.into()));

            for (i, input) in LookUpTableInput::iter().enumerate() {
                if let Some(input_net) = input_nets[i] {
                    let sinks = net_sinks.entry(input_net).or_insert_with(Vec::new);
                    sinks.push((node, DesignGraphEdge::LookUpTableInput(input)));
                }
            }

            assert!( ! net_sources.contains_key(&output_net));
            net_sources.insert(output_net, node);
        }

        for (source_net, source_node) in &net_sources {
            if let Some(sink_nodes_and_edges) = net_sinks.get(source_net) {
                for (sink_node, edge) in sink_nodes_and_edges {
                    graph.add_edge(*source_node, *sink_node, *edge);
                }
            }
        }

        // Verify that the generated edges are correct for the node
        // they connect to.
        // FUTURE: Can I use the type system to make the compiler
        //   do this check for me? I don't know that I can with a
        //   graph library expecting homogenous node types and
        //   arbitrary weight types.
        for edge in graph.raw_edges() {
            let target = &graph[edge.target()];
            assert!(edge.weight.can_connect_to(target));
        }
        graph
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    // TODO: Use json! macro to write unit tests
    // https://docs.serde.rs/serde_json/macro.json.html

    #[test]
    fn yosys_lut_mask_decode() {
        assert_eq!((YosysLutMask::BitString("1111000011110000")).decode().get(), 0xf0f0);
        assert_eq!((YosysLutMask::BitString("11110000")).decode().get(), 0xf0f0);
        assert_eq!((YosysLutMask::BitString("1100")).decode().get(), 0xcccc);
        assert_eq!((YosysLutMask::BitString("10")).decode().get(), 0xaaaa);
        assert_eq!((YosysLutMask::BitString("1")).decode().get(), 0xffff);
        assert_eq!((YosysLutMask::BitString("0")).decode().get(), 0x0000);

        assert_eq!((YosysLutMask::Integer(0b1111000011110000, 16)).decode().get(), 0xf0f0);
        assert_eq!((YosysLutMask::Integer(0b11110000, 8)).decode().get(), 0xf0f0);
        assert_eq!((YosysLutMask::Integer(0b1100, 4)).decode().get(), 0xcccc);
        assert_eq!((YosysLutMask::Integer(0b10, 2)).decode().get(), 0xaaaa);
        assert_eq!((YosysLutMask::Integer(0b1, 1)).decode().get(), 0xffff);
        assert_eq!((YosysLutMask::Integer(0b0, 1)).decode().get(), 0x0000);
    }
}
