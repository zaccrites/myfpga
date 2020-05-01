
use std::collections::HashMap;

use petgraph::graph::DiGraph;


// Previous versions of Yosys emitted LUT configs as a binary string
// of ones and zeroes. At some point it changed to emitting a plain integer.
enum YosysLutConfig<'a> {
    BinaryString(&'a str),
    Integer(u16, usize),
}


// A 4-LUT needs 16 configuration bits
#[derive(Debug, Clone, Copy)]
pub struct LookUpTableConfig(u16);

impl LookUpTableConfig {
    /// Decode a raw Yosys LUT configuration string
    fn decode(raw_config: YosysLutConfig) -> Self {
        fn expand_to_16_bits(raw_value: u16, width: usize) -> u16 {
            let repeat_count = 16 / width;
            (1..repeat_count).fold(raw_value, |acc, _| (acc << width) | raw_value)
        }

        let config_value = match raw_config {
            YosysLutConfig::BinaryString(raw_config) => {
                let width = raw_config.len();
                let decoded = u16::from_str_radix(&raw_config, 2).unwrap();
                expand_to_16_bits(decoded, width)
            },
            YosysLutConfig::Integer(raw_config, width) => expand_to_16_bits(raw_config, width),
        };
        Self(config_value)
    }

    pub fn get(self) -> u16 {
        self.0
    }
}


#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NetId(u32);


#[derive(Debug)]
pub struct LookUpTable {
    pub name: String,
    pub config: LookUpTableConfig,
    pub inputs: [Option<NetId>; 4],
    pub output: NetId,
}

impl LookUpTable {
    fn try_read(name: &str, cell: &serde_json::Value) -> Option<Self> {
        // TODO: Error handling
        if cell["type"].as_str().unwrap() != "$lut" {
            return None;
        }

        let raw_config = match &cell["parameters"]["LUT"] {
            serde_json::Value::Number(value) => {
                let width = cell["parameters"]["WIDTH"].as_u64().unwrap() as usize;
                YosysLutConfig::Integer(value.as_u64().unwrap() as u16, width)
            },
            serde_json::Value::String(value) => YosysLutConfig::BinaryString(&value),
            _ => panic!(),
        };

        let mut inputs = [None; 4];
        for (i, input) in cell["connections"]["A"].as_array().unwrap().iter().enumerate() {
            inputs[i] = Some(NetId(input.as_u64().unwrap() as u32));
        }

        let output = NetId(cell["connections"]["Y"][0].as_u64().unwrap() as u32);

        let id = name.split('$').last().unwrap();
        let name = format!("$lut${}", id);

        Some(LookUpTable {
            name,
            config: LookUpTableConfig::decode(raw_config),
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
pub struct FlipFlop {
    pub name: String,
    pub trigger: FlipFlopTrigger,
    pub clock: NetId,
    pub data: NetId,
    pub output: NetId,
}

impl FlipFlop {
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

        Some(FlipFlop {
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
pub struct ModulePort {
    pub name: String,
    pub direction: ModulePortDirection,
    pub net: NetId,
}

impl ModulePort {
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
            ModulePort {
                name,
                net: NetId(bit.as_u64().unwrap() as u32),
                direction,
            }
        }).collect()
    }
}


pub type DesignGraph = DiGraph<DesignGraphNode, DesignGraphEdge>;


#[derive(Debug)]
pub enum DesignGraphNode {
    LookUpTable(LookUpTable),
    FlipFlop(FlipFlop),
    ModulePort(ModulePort),
}


#[derive(Debug, Clone, Copy)]
pub enum LookUpTableInput {
    A = 0,
    B = 1,
    C = 2,
    D = 3,
}


#[derive(Debug, Clone, Copy)]
pub enum FlipFlopInput {
    Clock,
    Data,
}


// The bit index of the module port
#[derive(Debug, Clone, Copy)]
pub struct ModulePortBitIndex(usize);


#[derive(Debug, Clone, Copy)]
pub enum DesignGraphEdge {
    LookUpTableInput(LookUpTableInput),
    FlipFlopInput(FlipFlopInput),
    ModulePortInput,
}

impl DesignGraphEdge {
    pub fn can_connect_to(self, node: &DesignGraphNode) -> bool {
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
    pub ports: Vec<ModulePort>,
    pub flip_flops: Vec<FlipFlop>,
    pub lookup_tables: Vec<LookUpTable>,
}

impl Design {
    pub fn read(data: serde_json::Value) -> Self {
        let (module_name, module_data) = data["modules"].as_object().unwrap().iter().next().unwrap();

        let ports = module_data["ports"].as_object().unwrap().iter()
            .map(|(name, port)| ModulePort::read(name, port)).flatten().collect();

        let lookup_tables = module_data["cells"].as_object().unwrap().iter()
            .map(|(name, cell)| LookUpTable::try_read(name, cell)).flatten().collect();

        let flip_flops = module_data["cells"].as_object().unwrap().iter()
            .map(|(name, cell)| FlipFlop::try_read(name, cell)).flatten().collect();

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

        for port in self.ports {
            let net = port.net;
            let direction = port.direction;
            let node = graph.add_node(DesignGraphNode::ModulePort(port));
            match direction {
                ModulePortDirection::Input => {
                    println!("[output] net = {:?}", net);
                    assert!( ! net_sources.contains_key(&net));
                    net_sources.insert(net, node);
                },
                ModulePortDirection::Output => {
                    net_sinks.entry(net).or_insert_with(Vec::new).push((node, DesignGraphEdge::ModulePortInput));
                }
            }
        }

        for ff in self.flip_flops {
            let data_net = ff.data;
            let clock_net = ff.clock;
            let output_net = ff.output;
            let node = graph.add_node(DesignGraphNode::FlipFlop(ff));

            net_sinks.entry(clock_net).or_insert_with(Vec::new).push((node, DesignGraphEdge::FlipFlopInput(FlipFlopInput::Clock)));
            net_sinks.entry(data_net).or_insert_with(Vec::new).push((node, DesignGraphEdge::FlipFlopInput(FlipFlopInput::Data)));

            assert!( ! net_sources.contains_key(&output_net));
            net_sources.insert(output_net, node);
        }

        for lut in self.lookup_tables {
            let input_nets = lut.inputs;
            let output_net = lut.output;
            let node = graph.add_node(DesignGraphNode::LookUpTable(lut));

            for input in &[LookUpTableInput::A, LookUpTableInput::B, LookUpTableInput::C, LookUpTableInput::D] {
                if let Some(input_net) = input_nets[*input as usize] {
                    let sinks = net_sinks.entry(input_net).or_insert_with(Vec::new);
                    sinks.push((node, DesignGraphEdge::LookUpTableInput(*input)));
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
    fn lut_config_decode() {
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::BinaryString("1111000011110000")).get(), 0xf0f0);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::BinaryString("11110000")).get(), 0xf0f0);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::BinaryString("1100")).get(), 0xcccc);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::BinaryString("10")).get(), 0xaaaa);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::BinaryString("1")).get(), 0xffff);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::BinaryString("0")).get(), 0x0000);

        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::Integer(0b1111000011110000, 16)).get(), 0xf0f0);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::Integer(0b11110000, 8)).get(), 0xf0f0);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::Integer(0b1100, 4)).get(), 0xcccc);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::Integer(0b10, 2)).get(), 0xaaaa);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::Integer(0b1, 1)).get(), 0xffff);
        assert_eq!(LookUpTableConfig::decode(YosysLutConfig::Integer(0b0, 1)).get(), 0x0000);
    }
}
