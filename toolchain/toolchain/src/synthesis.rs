
use serde_json;


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
                // let num_config_bits = raw_config.len();
                // let repeat_count = 16 / num_config_bits;
                // let decoded = u16::from_str_radix(&raw_config, 2).expect("Yosys LUT config parse failed");
                // let config = (1..repeat_count).fold(decoded, |acc, _| (acc << num_config_bits) | decoded);
                // Self(config)

                let width = raw_config.len();
                let decoded = u16::from_str_radix(&raw_config, 2).unwrap();
                expand_to_16_bits(decoded, width)
            },
            YosysLutConfig::Integer(raw_config, width) => expand_to_16_bits(raw_config, width),
        };
        Self(config_value)
    }

    pub fn get(&self) -> u16 {
        self.0
    }
}







#[derive(Debug, Clone, Copy, PartialEq, Eq)]
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

        Some(LookUpTable {
            name: String::from(name),
            config: LookUpTableConfig::decode(raw_config),
            inputs,
            output,
        })
    }
}


#[derive(Debug)]
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

        let clock = NetId(cell["connections"]["C"][0].as_u64().unwrap() as u32);
        let data = NetId(cell["connections"]["D"][0].as_u64().unwrap() as u32);
        let output = NetId(cell["connections"]["Q"][0].as_u64().unwrap() as u32);

        Some(FlipFlop {
            name: String::from(name),
            trigger,
            clock,
            data,
            output,
        })
    }
}




#[derive(Debug)]
pub enum ModulePortDirection {
    Input,
    Output,
}

#[derive(Debug)]
pub struct ModulePort {
    pub name: String,
    pub direction: ModulePortDirection,
    pub bits: Vec<NetId>,
}

impl ModulePort {
    fn read(name: &str, port: &serde_json::Value) -> Self {
        let direction = match port["direction"].as_str().unwrap() {
            "input" => ModulePortDirection::Input,
            "output" => ModulePortDirection::Output,
            direction => panic!("Unknown port direction '{}'", direction),
        };

        let bits = port["bits"].as_array().unwrap().iter().map(|bit| NetId(bit.as_u64().unwrap() as u32)).collect();

        ModulePort {
            name: String::from(name),
            bits,
            direction,
        }
    }

    // fn width(&self) -> usize {
    //     self.bits.len()
    // }
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
            .map(|(name, port)| ModulePort::read(name, port)).collect();

        let lookup_tables = module_data["cells"].as_object().unwrap().iter()
            .map(|(name, cell)| LookUpTable::try_read(name, cell)).flatten().collect();

        let flip_flops = module_data["cells"].as_object().unwrap().iter()
            .map(|(name, cell)| FlipFlop::try_read(name, cell)).flatten().collect();

        Self {
            name: String::from(module_name),
            ports,
            flip_flops: flip_flops,
            lookup_tables,
        }

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



