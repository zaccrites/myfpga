
mod implementation;
mod synthesis;

mod routing;
// mod anneal;


#[derive(Debug)]
enum ToolchainError {
    SynthesisError(String),
    ImplementationError(String),
    RoutingError(String),
}

impl ToolchainError {
    fn message(&self) -> &str {
        match self {
            Self::SynthesisError(msg) => msg,
            Self::ImplementationError(msg) => msg,
            Self::RoutingError(msg) => msg,
        }
    }

    fn phase(&self) -> &'static str {
        match self {
            Self::SynthesisError(_) => "Synthesis",
            Self::ImplementationError(_) => "Implementation",
            Self::RoutingError(_) => "Routing",
        }
    }
}

impl From<synthesis::SynthesisError> for ToolchainError {
    fn from (err: synthesis::SynthesisError) -> Self {
        let message = match err {
            synthesis::SynthesisError::ModulePortUndriven {port} =>
                format!("Module port \"{}\" is undriven", port),
        };
        ToolchainError::SynthesisError(message)
    }
}

impl From<implementation::ImplError> for ToolchainError {
    fn from(err: implementation::ImplError) -> Self {
        let message = match err {
            implementation::ImplError::FlipFlopClockSource {ff, clock_source} =>
                format!("\"{}\" clocked from non-module-input \"{}\"", ff, clock_source),
            implementation::ImplError::MultipleClockDomains {ff, expected_clock_source, actual_clock_source} =>
                format!("\"{}\" should be clocked by main clock source \"{}\", not by \"{}\"", ff, expected_clock_source, actual_clock_source),
        };
        ToolchainError::ImplementationError(message)
    }
}

impl From<routing::RoutingError> for ToolchainError {
    fn from(err: routing::RoutingError) -> Self {
        ToolchainError::RoutingError(format!("TODO: {:?}", err))
    }
}


fn run() -> Result<(), ToolchainError> {
    // TODO: Pass std::io::Read to serde_json decoder directly
    let design_json_text = std::fs::read_to_string("/home/zac/Code/myfpga/designs/my_design/my_design.json").unwrap();
    let design_json = serde_json::from_str(&design_json_text).unwrap();
    let design = synthesis::Design::read(design_json)?;

    println!("Design: \"{}\"", design.name);
    let design_graph = design.into_graph()?;
    let impl_graph = implementation::implement_design(design_graph)?;

    // println!("{:?}", impl_graph);

    let topology = routing::DeviceTopology {width:2 , height: 2};
    let routing_config = routing::route_design(impl_graph, topology)?;

    println!("{:?}", routing_config);

    Ok(())
}


fn main() {
    // TODO: argument parsing

    if let Err(err) = run() {
        eprintln!("{} failed: {}", err.phase(), err.message());
        std::process::exit(1);
    }
}
