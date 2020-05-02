
use std::collections::HashMap;

use petgraph::graph::DiGraph;

use crate::synthesis::{
    DesignGraph, DesignGraphNode, DesignGraphEdge,
    LookUpTable,LookUpTableMask, LookUpTableInput,
    FlipFlop, FlipFlopInput,
    ModulePort, ModulePortDirection,
};


pub type ImplGraph = DiGraph<ImplGraphNode, ImplGraphEdge>;


#[derive(Debug)]
pub enum ImplGraphNode {
    LogicCell(LogicCell),
    ModulePort(ModulePort),
}


#[derive(Debug, Clone, Copy)]
pub enum ImplGraphEdge {
    LogicCellInput(LookUpTableInput),
    LogicCellClock,
    ModulePortInput,
}

impl ImplGraphEdge {
    fn can_connect_to(self, node: &ImplGraphNode) -> bool {
        match (self, node) {
            (ImplGraphEdge::LogicCellInput(_), ImplGraphNode::LogicCell(_)) => true,
            (ImplGraphEdge::LogicCellClock, ImplGraphNode::LogicCell(_)) => true,
            (ImplGraphEdge::ModulePortInput, ImplGraphNode::ModulePort(ModulePort { direction: ModulePortDirection::Output, .. })) => true,
            _ => false,
        }
    }
}


#[derive(Debug)]
pub enum ImplError {
    /// A flip flop is clocked from a non-module input port.
    FlipFlopClockSource { ff: String, clock_source: String },
    /// Flip flops are clocked from multiple domains.
    MultipleClockDomains { ff: String, expected_clock_source: String, actual_clock_source: String },
}


#[derive(Debug)]
pub struct LogicCell {
    pub lut: LookUpTable,

    // If the flip flop is None, then the logic cell output is fed
    // directly from the LUT output. Otherwise it is buffered through
    // the flip flop.
    pub ff: Option<FlipFlop>
}


fn sanity_check_flip_flops(design_graph: &DesignGraph) -> Result<(), ImplError> {
    // For now, only a single clock domain is supported.
    // Furthermore, the clock must originate from a dedicated external clock port.
    // It is okay for the design to not use a clock though,
    // if the logic function is purely combinational.
    let mut main_clock_port: Option<(&ModulePort, petgraph::graph::NodeIndex)> = None;

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
                let port_index = edge.source();
                if let Some((main_clock_port, main_clock_port_id)) = main_clock_port {
                    if port_index != main_clock_port_id {
                        return Err(ImplError::MultipleClockDomains {
                            ff: ff.name.clone(),
                            expected_clock_source: main_clock_port.name.clone(),
                            actual_clock_source: source.name(),
                        });
                    }
                }
                else {
                    main_clock_port = Some((port, port_index));
                }
            }
            else {
                return Err(ImplError::FlipFlopClockSource { ff: ff.name.clone(), clock_source: source.name() });
            }
        }
    }
    Ok(())
}


pub fn implement_design(design_graph: DesignGraph) -> Result<ImplGraph, ImplError> {
    sanity_check_flip_flops(&design_graph)?;

    let mut impl_graph = ImplGraph::new();
    let mut node_replacements = HashMap::new();

    // First pass: find LUTs which feed directly into a single flip flop.
    // We cannot merge a LUT and flip flop if anything other than the single
    // flip flop input is using the LUT output.
    for edge in design_graph.raw_edges() {
        let source_index = edge.source();
        let sink_index = edge.target();

        let out_degree = design_graph.edges(source_index).count();
        if out_degree != 1 { continue; }

        if let (
            DesignGraphNode::LookUpTable(lut),
            DesignGraphNode::FlipFlop(ff),
            DesignGraphEdge::FlipFlopInput(FlipFlopInput::Data),
        ) = (&design_graph[source_index], &design_graph[sink_index], edge.weight) {
            let logic_cell = LogicCell {
                lut: lut.clone(),
                ff: Some(ff.clone())
            };
            let node = impl_graph.add_node(ImplGraphNode::LogicCell(logic_cell));
            node_replacements.insert(source_index, node);
            node_replacements.insert(sink_index, node);
        }
    }

    // TODO: Find a cleaner way to implement this. I would have liked to use
    //   a closure, but the borrow checker would not allow it because of the
    //   mutable references.
    use petgraph::graph::NodeIndex;
    fn replace_node(node_index: NodeIndex, design_graph: &DesignGraph, impl_graph: &mut ImplGraph, node_replacements: &mut HashMap<NodeIndex, NodeIndex>) -> NodeIndex {
        // If the node already exists in the replacement map, use its replacement.
        if let Some(replacement_node_index) = node_replacements.get(&node_index) {
            *replacement_node_index
        }
        else {
            // Otherwise we have to create a replacement node.
            let impl_node = match &design_graph[node_index] {
                DesignGraphNode::LookUpTable(lut) => {
                    ImplGraphNode::LogicCell(LogicCell { lut: lut.clone(), ff: None })
                },
                DesignGraphNode::FlipFlop(ff) => {
                    let lut = LookUpTable {
                        name: String::from("$lut$passthrough"),
                        // assume Port A for the passthrough connection
                        mask: LookUpTableMask::new(0b1010_1010_1010_1010)
                    };
                    ImplGraphNode::LogicCell(LogicCell { lut, ff: Some(ff.clone()) })
                },
                DesignGraphNode::ModulePort(port) => ImplGraphNode::ModulePort(port.clone())
            };
            // Insert the replacement node into the new graph and the
            // replacement map for later reference.
            let impl_node = impl_graph.add_node(impl_node);
            node_replacements.insert(node_index, impl_node);
            impl_node
        }
    };

    // Second pass: convert the remaining LUTs and flip flops into
    // standalone logic cells.
    for edge in design_graph.raw_edges() {
        let source_index = replace_node(edge.source(), &design_graph, &mut impl_graph, &mut node_replacements);
        let sink_index = replace_node(edge.target(), &design_graph, &mut impl_graph, &mut node_replacements);

        // Skip edges between the LUT and flip flop in a newly merged logic cell.
        if source_index == sink_index {
            if let DesignGraphEdge::FlipFlopInput(ff_input) = edge.weight {
                assert!(matches!(ff_input, FlipFlopInput::Data));
                continue;
            }
        }

        let impl_edge = match edge.weight {
            DesignGraphEdge::LookUpTableInput(lut_input) => ImplGraphEdge::LogicCellInput(lut_input),
            DesignGraphEdge::ModulePortInput => ImplGraphEdge::ModulePortInput,
            DesignGraphEdge::FlipFlopInput(FlipFlopInput::Clock) => ImplGraphEdge::LogicCellClock,

            // Connections intended for a flip flop should be redirected through the
            // passthrough LUT in its logic cell.
            DesignGraphEdge::FlipFlopInput(FlipFlopInput::Data) => ImplGraphEdge::LogicCellInput(LookUpTableInput::A),
        };
        impl_graph.add_edge(source_index, sink_index, impl_edge);

        // println!("{:?} ({:?}) ->\n  {:?} ({:?})\n  via {:?}\n\n", &impl_graph[source_index], source_index, &impl_graph[sink_index], sink_index, impl_edge);
    }

    // Verify that the generated edges are correct for the node
    // they connect to.
    // FUTURE: Can I use the type system to make the compiler
    //   do this check for me? I don't know that I can with a
    //   graph library expecting homogenous node types and
    //   arbitrary weight types.
    for edge in impl_graph.raw_edges() {
        let target = &impl_graph[edge.target()];
        assert!(
            edge.weight.can_connect_to(target),
            "Cannot connect {:?} to {:?}", edge.weight, target,
        );
    }
    Ok(impl_graph)
}
