
use crate::synthesis::{
    LookUpTable, LookUpTableInput,
    FlipFlop,
    Design, DesignGraph,
    DesignGraphNode, DesignGraphEdge,
    FlipFlopInput,

    ModulePortDirection,
};

use crate::synthesis::ModulePort; // ??

use petgraph::graph::DiGraph;


#[derive(Debug)]
pub enum ImplGraphNode {
    LogicCell(LogicCell),
    // ModulePort(ModulePort),
}


#[derive(Debug, Clone, Copy)]
pub enum ImplGraphEdge {
    LogicCellInput(LookUpTableInput),
    ModulePortInput,
}

impl ImplGraphEdge {
    fn can_connect_to(self, node: &ImplGraphNode) -> bool {
        match (self, node) {
            (ImplGraphEdge::LogicCellInput(_), ImplGraphNode::LogicCell(_)) => true,
            _ => false,
        }
    }
}


pub type ImplGraph = DiGraph<ImplGraphNode, ImplGraphEdge>;



#[derive(Debug)]
pub struct LogicCell {
    pub lut: LookUpTable,
    pub ff: FlipFlop,
}



#[derive(Debug)]
pub enum ImplError {
    /// A flip flop is clocked from a non-module input port.
    FlipFlopClockSource { ff: String, clock_source: String },
    /// Flip flops are clocked from multiple domains.
    MultipleClockDomains { expected_clock_source: String, actual_clock_source: String },
}


fn sanity_check_flip_flops(design_graph: &DesignGraph) -> Result<(), ImplError> {
    // For now, only a single clock domain is supported.
    // Furthermore, the clock must originate from a dedicated external clock port.
    // It is okay for the design to not use a clock though,
    // if the logic function is purely combinational.
    let mut main_clock_port: Option<&ModulePort> = None;
    for edge in design_graph.raw_edges() {
        let source = &design_graph[edge.source()];
        let sink = &design_graph[edge.target()];
        // Verify that the sink is a flip flop clock input -- if not, skip
        if let (DesignGraphNode::FlipFlop(ff), DesignGraphEdge::FlipFlopInput(FlipFlopInput::Clock)) = (sink, edge.weight) {
            // Verify that the source is a module port -- if not, error
            if let DesignGraphNode::ModulePort(port @ ModulePort { direction: ModulePortDirection::Input, .. }) = source {
                // Verify that if the main clock (i.e. the first clock) has been
                // found that all other flip flops use the same net for their
                // clock input.
                if let Some(main_clock_port) = main_clock_port {
                    if port.net != main_clock_port.net {
                        return Err(ImplError::MultipleClockDomains {
                            expected_clock_source: main_clock_port.name.clone(),
                            actual_clock_source: source.name(),
                        });
                    }
                }
                else {
                    main_clock_port = Some(port);
                }
            }
            else {
                return Err(ImplError::FlipFlopClockSource { ff: ff.name.clone(), clock_source: source.name() });
            }
        }
    }
    Ok(())
}


pub fn implement_design(design: Design) -> Result<ImplGraph, ImplError> {

    let design_graph = design.into_graph();

    println!("{:?}", design_graph);

    sanity_check_flip_flops(&design_graph)?;


    let impl_graph = ImplGraph::new();




    // Verify that the generated edges are correct for the node
    // they connect to.
    // FUTURE: Can I use the type system to make the compiler
    //   do this check for me? I don't know that I can with a
    //   graph library expecting homogenous node types and
    //   arbitrary weight types.
    for edge in impl_graph.raw_edges() {
        let target = &impl_graph[edge.target()];
        assert!(edge.weight.can_connect_to(target));
    }
    Ok(impl_graph)

}
