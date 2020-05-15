
mod topology;
mod pathfinder;
mod anneal;

pub use crate::routing::topology::{
    NodeIndexMap,
    DeviceTopology,
    RoutingGraph,
};
use crate::routing::topology::{
    LogicCellCoordinates,
    IoBlockCoordinates,
    RoutingGraphNode,
};


use std::collections::{HashMap, HashSet};

use rand::prelude::*;
use petgraph::graph::NodeIndex;
use indexmap::map::IndexMap;

use crate::implementation::{ImplGraph, ImplGraphNode, ImplGraphEdge};
use pathfinder::PathfinderResult;






pub type RoutingNetList = HashMap<NodeIndex, HashSet<NodeIndex>>;




#[derive(Debug)]
pub enum RoutingError {
    NotEnoughLogicCells {needed: usize, available: usize},
    NotEnoughIoBlocks {needed: usize, available: usize},
    FailedToRoute,
}








// fn swap_positions() {

//     // Find an initial logic cell to swap to another position.
//     let (&a_index, a_value) = self.assigned_logic_cell_coords.iter().choose(&mut rng).unwrap();
//     let a_coord = self.all_logic_cell_coords[a_index];

//     let (b_index, b_coord) = self.all_logic_cell_coords.iter().enumerate()
//         .filter(|(i, coord)| *i != a_index).choose(&mut rng).unwrap();
//     let b_value = self.assigned_logic_cell_coords.get(&b_index);

//     if let Some(b_value) = b_value {
//         // If we're swapping with another occupied cell then two
//         // keys exchange values.
//         self.assigned_logic_cell_coords[&a_index] = *b_value;
//     }
//     else {
//         // If we're swapping with an unoccupied cell then the key
//         // is changed, but the value is kept.
//         self.assigned_logic_cell_coords.remove(&a_index);
//     }
//     self.assigned_logic_cell_coords[&b_index] = *a_value;

// }


// fn swap_positions<T: Clone>(assigned_coords: &mut HashMap<usize, NodeIndex>, all_coords: &mut [T]) {
//     let mut rng = rand::thread_rng();

//     // Find an initial logic cell to swap to another position.
//     let (a_index, a_coord, a_value) = assigned_coords.iter()
//         .choose(&mut rng)
//         .map(|(i, value)| (*i, all_coords[*i].clone(), value))
//         .unwrap();

//     // Find its new home, eviting the current occupant if there is one.
//     let (b_index, b_coord, b_value) = all_coords.iter().enumerate()
//         .filter(|(i, coord)| *i != a_index)
//         .choose(&mut rng)
//         .map(|(i, coord)| (i, coord, assigned_coords.remove(&i)))
//         .unwrap();

//     assigned_coords.insert(b_index, *a_value);
//     if let Some(b_value) = b_value {
//         // If we're swapping with another occupied cell then the two
//         // keys exchange values.
//         assigned_coords.insert(a_index, b_value);
//     }
//     else {
//         // If we're swapping with an unoccupied cell then the original
//         // key is removed.
//         assigned_coords.remove(&a_index);
//     }
// }


fn swap_positions<T>(assigned_coords: &mut HashMap<usize, NodeIndex>, all_coords: &[T]) {
    let mut rng = rand::thread_rng();

    // Find an initial logic cell to swap to another position.
    let (a_index, a_value) = assigned_coords.iter()
        .choose(&mut rng)
        .map(|(i, value)| (*i, *value))
        .unwrap();

    // Find its new home, eviting the current occupant if there is one.
    let b_index = (0..all_coords.len())
        .filter(|i| *i != a_index)
        .choose(&mut rng).unwrap();
    let b_value = assigned_coords.remove(&b_index);

    assigned_coords.insert(b_index, a_value);
    if let Some(b_value) = b_value {
        // If we're swapping with another occupied cell then the two
        // keys exchange values.
        assigned_coords.insert(a_index, b_value);
    }
    else {
        // If we're swapping with an unoccupied cell then the original
        // key is removed.
        assigned_coords.remove(&a_index);
    }
}


pub struct RoutingConfiguration {
    all_logic_cell_coords: Vec<LogicCellCoordinates>,
    all_io_block_coords: Vec<IoBlockCoordinates>,

    // Map a logic cell coord (as an index into the complete list) to an implementation graph node
    assigned_logic_cell_coords: HashMap<usize, NodeIndex>,
    // Map an IO block coord (as an index into the complete list) to an implementation graph node
    assigned_io_block_coords: HashMap<usize, NodeIndex>,
}

impl RoutingConfiguration {
    // TODO: Can the RoutingConfiguration store a reference to the ImplGraph?
    // Does that work well across threads?
    fn initial(topology: &DeviceTopology, impl_graph: &ImplGraph) -> Result<Self, RoutingError> {
        let all_logic_cell_coords: Vec<_> = topology.iter_logic_cell_coords().collect();
        let all_io_block_coords: Vec<_> = topology.iter_io_block_coords().collect();
        let assigned_logic_cell_coords = Self::_assign_logic_cell_coords(impl_graph, &all_logic_cell_coords)?;
        let assigned_io_block_coords = Self::_assign_io_block_coords(impl_graph, &all_io_block_coords)?;
        Ok(Self {
            all_logic_cell_coords,
            all_io_block_coords,
            assigned_logic_cell_coords,
            assigned_io_block_coords,
        })
    }

    fn _assign_logic_cell_coords(impl_graph: &ImplGraph, all_coords: &[LogicCellCoordinates]) -> Result<HashMap<usize, NodeIndex>, RoutingError> {
        let mut rng = rand::thread_rng();
        let mut assigned_coords = HashMap::new();

        let logic_cell_indices: Vec<_> = impl_graph.node_indices()
            .filter(|&node| matches!(&impl_graph[node], ImplGraphNode::LogicCell(_)))
            .collect();
        let logic_cells_required = logic_cell_indices.len();

        let mut logic_cell_coords: Vec<_> = all_coords.choose_multiple(&mut rng, logic_cell_indices.len()).collect();
        logic_cell_coords.shuffle(&mut rng);
        let logic_cell_coords: IndexMap<_, _> = logic_cell_indices.into_iter().zip(all_coords).collect();

        if logic_cell_coords.len() < logic_cells_required {
            Err(RoutingError::NotEnoughLogicCells {
                needed: logic_cells_required,
                available: logic_cell_coords.len(),
            })
        }
        else {
            Ok(assigned_coords)
        }
    }

    // TODO: Can this be combined with _assign_logic_cell_coords
    fn _assign_io_block_coords(impl_graph: &ImplGraph, all_coords: &[IoBlockCoordinates]) -> Result<HashMap<usize, NodeIndex>, RoutingError> {
        let mut rng = rand::thread_rng();
        let mut assigned_coords = HashMap::new();

        // FUTURE: Support I/O constraints
        let module_port_indices: Vec<_> = impl_graph.node_indices()
            .filter(|&node| matches!(&impl_graph[node], ImplGraphNode::ModulePort(_)))
            .collect();
        let io_blocks_required = module_port_indices.len();

        let mut io_block_coords: Vec<_> = all_coords.choose_multiple(&mut rng, module_port_indices.len()).collect();
        io_block_coords.shuffle(&mut rng);
        let io_block_coords: IndexMap<_, _> = module_port_indices.into_iter().zip(all_coords).collect();

        if io_block_coords.len() < io_blocks_required {
            // FUTURE: Handle this "plus one for clock" and other clock-related handling better.
            Err(RoutingError::NotEnoughIoBlocks {
                needed: io_blocks_required + 1,  // Plus one for the clock input
                available: io_block_coords.len(),
            })
        }
        else {
            Ok(assigned_coords)
        }
    }

    fn mutate(&mut self) {
        // First decide if we're swapping IO blocks or logic cells.
        let logic_cell_count = self.all_logic_cell_coords.len() as f64;
        let io_block_count = self.all_io_block_coords.len() as f64;
        let percent_logic_cells = logic_cell_count / (logic_cell_count + io_block_count);

        let mut rng = rand::thread_rng();
        if rng.gen::<f64>() < percent_logic_cells {
            swap_positions(&mut self.assigned_logic_cell_coords, &self.all_logic_cell_coords);
        }
        else {
            swap_positions(&mut self.assigned_io_block_coords, &self.all_io_block_coords);
        }
    }

    fn generate_netlist(&self, impl_graph: &ImplGraph, node_index_map: &NodeIndexMap) -> RoutingNetList {
        let mut netlist = RoutingNetList::new();
        for impl_edge in impl_graph.raw_edges() {
            let impl_source_id = impl_edge.source();
            let impl_source = &impl_graph[impl_source_id];
            let impl_sink_id = impl_edge.target();
            let impl_sink = &impl_graph[impl_sink_id];

            let routing_source = node_index_map[&match impl_source {
                ImplGraphNode::LogicCell(_) => RoutingGraphNode::LogicCellOutput {coords: self.logic_cell_coords[&impl_source_id]},
                ImplGraphNode::ModulePort(_) => RoutingGraphNode::IoBlock {coords: self.io_block_coords[&impl_source_id]},
            }];

            let routing_sink = node_index_map[&match (impl_sink, impl_edge.weight) {
                (ImplGraphNode::LogicCell(_), ImplGraphEdge::LogicCellInput(input)) => RoutingGraphNode::LogicCellInput {coords: self.logic_cell_coords[&impl_sink_id], input},
                (ImplGraphNode::ModulePort(_), ImplGraphEdge::ModulePortInput) => RoutingGraphNode::IoBlock {coords: self.io_block_coords[&impl_sink_id]},
                (ImplGraphNode::LogicCell(_), ImplGraphEdge::LogicCellClock) => {
                    // Ignore clock signal inputs for the purposes of routing.
                    continue;
                },
                (sink, edge) => panic!("Illegal connection to {:?} via edge {:?}", sink, edge),
            }];

            let netlist = netlist.entry(routing_source).or_insert_with(HashSet::new);
            netlist.insert(routing_sink);
        }
        netlist
    }

}




pub fn route_design(impl_graph: ImplGraph, topology: DeviceTopology) -> Result<(), RoutingError> {
    // let mut rng = rand::thread_rng();

    // TODO: Arrange initial placement by putting connected logic cells near eachother
    // and logic cells connected to IO blocks near those blocks. Annealing can then move
    // the logic cells around locally after the initial placement.
    //
    // Find islands of "strongly" connected cells and group them, but space the
    // islands out as much as possible to give them room to route around.

    // TODO: Make temperature schedule configurable via command line. Quartus does this in settings.
    let (graph, node_index_map) = topology.build_graph();

    // TODO: This API isn't great (can the routing graph and node_index_map be combined into a struct?)
    let routing_config = RoutingConfiguration::initial(&topology, &impl_graph)?;
    routing_config.mutate();
    let netlist = routing_config.generate_netlist(&impl_graph, &node_index_map);



    println!("Starting pathfinder");
    match pathfinder::pathfinder(&graph, &netlist, &topology) {
        PathfinderResult::Routed { score, netlist } => {
            println!("Score = {:?}", score);
            // let config = RoutingConfiguration {};
            // Ok(config)
            Ok(())
        },

        PathfinderResult::NotRouted { congestion } => {
            println!("Pathfinder gave up with congestion {}", congestion);
            Err(RoutingError::FailedToRoute)
        },
    }
}
