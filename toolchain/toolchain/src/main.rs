
mod synthesis;
mod implementation;
mod routing;
mod bitstream;


#[derive(Debug)]
enum ToolchainError {
    Synthesis(String),
    Implementation(String),
    Routing(String),
    Bitstream(String),
}

impl ToolchainError {
    fn message(&self) -> &str {
        match self {
            Self::Synthesis(msg) => msg,
            Self::Implementation(msg) => msg,
            Self::Routing(msg) => msg,
            Self::Bitstream(msg) => msg,
        }
    }

    fn phase(&self) -> &'static str {
        match self {
            Self::Synthesis(_) => "Synthesis",
            Self::Implementation(_) => "Implementation",
            Self::Routing(_) => "Routing",
            Self::Bitstream(_) => "Bitstream generation",
        }
    }
}

impl From<synthesis::SynthesisError> for ToolchainError {
    fn from (err: synthesis::SynthesisError) -> Self {
        use synthesis::SynthesisError::*;
        let message = match err {
            ModulePortUndriven {port} =>
                format!("Module port \"{}\" is undriven", port),
        };
        ToolchainError::Synthesis(message)
    }
}

impl From<implementation::ImplError> for ToolchainError {
    fn from(err: implementation::ImplError) -> Self {
        use implementation::ImplError::*;
        let message = match err {
            FlipFlopClockSource {ff, clock_source} =>
                format!("\"{}\" clocked from non-module-input \"{}\"", ff, clock_source),
            MultipleClockDomains {ff, expected_clock_source, actual_clock_source} =>
                format!("\"{}\" should be clocked by main clock source \"{}\", not by \"{}\"", ff, expected_clock_source, actual_clock_source),
        };
        ToolchainError::Implementation(message)
    }
}

impl From<routing::RoutingError> for ToolchainError {
    fn from(err: routing::RoutingError) -> Self {
        use routing::RoutingError::*;
        let message = match err {
            NotEnoughLogicCells {needed, available} =>
                format!("Need {} logic cells, but there are only {} available", needed, available),
            NotEnoughIoBlocks {needed, available} =>
                format!("Need {} I/O blocks, but there are only {} available", needed, available),
            FailedToRoute => "Unable to route the design".to_string(),
        };
        ToolchainError::Routing(message)
    }
}

impl From<bitstream::BitstreamError> for ToolchainError {
    fn from(err: bitstream::BitstreamError) -> Self {
        ToolchainError::Bitstream(format!("TODO: {:?}", err))
    }
}


fn run() -> Result<(), ToolchainError> {
    // TODO: Pass std::io::Read to serde_json decoder directly
    // let design_json_text = std::fs::read_to_string("/home/zac/Code/myfpga/designs/my_design/my_design.json").unwrap();
    let design_json_text = std::fs::read_to_string("/home/zac/Code/myfpga/designs/fibonacci/fibonacci.json").unwrap();
    let design_json = serde_json::from_str(&design_json_text).unwrap();

    println!("Starting design read");
    let design = synthesis::Design::read(design_json)?;

    println!("Design: \"{}\"", design.name);
    let design_graph = design.into_graph()?;

    println!("Starting Implementation");
    let impl_graph = implementation::implement_design(design_graph)?;

    // println!("{:?}", impl_graph);

    // let topology = routing::DeviceTopology {width: 2, height: 2};
    println!("Starting Routing");
    let topology = routing::DeviceTopology {width: 10, height: 10};
    let routing_config = routing::route_design(impl_graph, topology)?;

    // println!("{:?}", routing_config);

    println!("Starting Bitstream generation");
    let bitstream_config = bitstream::generate_bitstream(&routing_config)?;

    Ok(())
}


fn main() {
    // TODO: argument parsing

    std::process::exit(match run() {
        Ok(_) => 0,
        Err(err) => {
            eprintln!("{} failed: {}", err.phase(), err.message());
            1
        },
    });
}
