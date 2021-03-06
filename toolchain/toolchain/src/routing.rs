
use std::collections::{HashMap, HashSet};

use rand::prelude::*;
use itertools::iproduct;
use petgraph::graph::{DiGraph, NodeIndex};

use crate::synthesis::LookUpTableInput;
use crate::implementation::{ImplGraph, ImplGraphNode, ImplGraphEdge};


#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum CardinalDirection {
    North,
    South,
    West,
    East,
}

impl CardinalDirection {
    const VALUES: [Self; 4] = [Self::North, Self::South, Self::West, Self::East];

    pub fn opposite(self) -> Self {
        match self {
            Self::North => Self::South,
            Self::South => Self::North,
            Self::West => Self::East,
            Self::East => Self::West,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::North => "north",
            Self::South => "south",
            Self::West => "west",
            Self::East => "east",
        }
    }
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
pub enum IntercardinalDirection {
    Northwest,
    Northeast,
    Southwest,
    Southeast,
}

impl IntercardinalDirection {
    const VALUES: [Self; 4] = [Self::Northwest, Self::Northeast, Self::Southwest, Self::Southeast];

    pub fn opposite(self) -> Self {
        match self {
            Self::Northwest => Self::Southeast,
            Self::Northeast => Self::Southwest,
            Self::Southwest => Self::Northeast,
            Self::Southeast => Self::Southeast,
        }
    }
}




pub type RoutingGraph = DiGraph<RoutingGraphNode, RoutingGraphEdge>;
pub type RoutingNetList = HashMap<NodeIndex, HashSet<NodeIndex>>;


// Each switch block side has an input and output with multiple channels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum SwitchBlockChannel {
    A,
    B,
    C,
    D,
}

impl SwitchBlockChannel {
    const VALUES: [Self; 4] = [Self::A, Self::B, Self::C, Self::D];

    fn cost(self) -> i32 {
        1
    }
}


#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum RoutingGraphNode {
    SwitchBlockInput(SwitchBlockPort),
    SwitchBlockOutput(SwitchBlockPort),
    SwitchBlockCorner(SwitchBlockCorner),
    LogicCellInput {coords: LogicCellCoordinates, input: LookUpTableInput},
    LogicCellOutput {coords: LogicCellCoordinates},
    IoBlock {coords: IoBlockCoordinates},
}

impl RoutingGraphNode {
    fn can_connect_to(self, other_node: Self) -> bool {
        // This only checks that the types of connections are right, not that
        // e.g. the nodes are actually adjacent.
        match (self, other_node) {
            (Self::LogicCellOutput {..}, Self::SwitchBlockCorner(_)) => true,
            (Self::SwitchBlockCorner(_), Self::SwitchBlockOutput(_)) => true,
            (Self::SwitchBlockInput(_), Self::SwitchBlockOutput(_)) => true,
            (Self::SwitchBlockOutput(_), Self::SwitchBlockInput(_)) => true,
            (Self::SwitchBlockOutput(_), Self::LogicCellInput {..}) => true,
            (Self::SwitchBlockOutput(_), Self::IoBlock {..}) => true,
            (Self::IoBlock {..}, Self::SwitchBlockInput {..}) => true,
            _ => false,
        }
    }
}


// Cost of using the resource
pub type RoutingGraphEdge = i32;


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
pub struct SwitchBlockPort {
    pub coords: SwitchBlockCoordinates,
    pub side: CardinalDirection,
    pub channel: SwitchBlockChannel,
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
pub struct SwitchBlockCorner {
    pub coords: SwitchBlockCoordinates,
    pub direction: IntercardinalDirection,
}


#[derive(Debug)]
pub struct DeviceTopology {
    pub width: usize,
    pub height: usize,
}

impl DeviceTopology {

    fn build_graph(&self) -> (RoutingGraph, HashMap<RoutingGraphNode, NodeIndex>) {
        let mut graph = RoutingGraph::new();

        // Map a real node object back to its graph node index
        let mut node_index_map = HashMap::new();
        let mut add_edge = |source, target, weight| {
            let source = *node_index_map.entry(source).or_insert_with(|| graph.add_node(source));
            let target = *node_index_map.entry(target).or_insert_with(|| graph.add_node(target));
            graph.add_edge(source, target, weight);
        };

        for switch_block_coords in self.iter_switch_block_coords() {
            // Internal to the switch block, all inputs are connected to
            // all outputs on other sides (i.e. all north-side inputs
            // are connected to all outputs on south, west, and east sides only).

            // TODO: DRY
            let inputs = iproduct!(CardinalDirection::VALUES.iter().copied(), SwitchBlockChannel::VALUES.iter().copied())
                .map(|(side, channel)| SwitchBlockPort {coords: switch_block_coords, side, channel});
            let outputs = iproduct!(CardinalDirection::VALUES.iter().copied(), SwitchBlockChannel::VALUES.iter().copied())
                .map(|(side, channel)| SwitchBlockPort {coords: switch_block_coords, side, channel});
            let connected_ports = iproduct!(inputs, outputs).filter(|(input, output)| input.side != output.side);
            for (input_port, output_port) in connected_ports {
                // Internal to the switch block, an input will be directed
                // to an output via a mux.
                let input = RoutingGraphNode::SwitchBlockInput(input_port);
                let output = RoutingGraphNode::SwitchBlockOutput(output_port);
                add_edge(input, output, output_port.channel.cost());
            }

            let corners = IntercardinalDirection::VALUES.iter().copied()
                .map(|direction| RoutingGraphNode::SwitchBlockCorner(SwitchBlockCorner {coords: switch_block_coords, direction }));
            let outputs = iproduct!(CardinalDirection::VALUES.iter().copied(), SwitchBlockChannel::VALUES.iter().copied())
                .map(|(side, channel)| SwitchBlockPort {coords: switch_block_coords, side, channel});
            for (corner, output_port) in iproduct!(corners, outputs) {
                let output = RoutingGraphNode::SwitchBlockOutput(output_port);
                add_edge(corner, output, output_port.channel.cost());
            }

            for (direction, other_switch_block_coords) in self.adjacent_switch_blocks(switch_block_coords) {
                // Only add the outgoing side, since the other switch block
                // will add its output back to this block once its turn in the
                // outer loop comes up.
                let outputs = SwitchBlockChannel::VALUES.iter().copied()
                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: direction, channel: channel});
                let inputs = SwitchBlockChannel::VALUES.iter().copied()
                    .map(|channel| SwitchBlockPort {coords: other_switch_block_coords, side: direction.opposite(), channel: channel});
                for (output_port, input_port) in outputs.zip(inputs) {
                    // External to the switch block, an output will always
                    // drive another's input.
                    let output = RoutingGraphNode::SwitchBlockOutput(output_port);
                    let input = RoutingGraphNode::SwitchBlockInput(input_port);
                    add_edge(output, input, output_port.channel.cost());
                }
            }

            for (direction, logic_cell_coords) in self.adjacent_logic_cells(switch_block_coords) {
                // A logic cell connects to all four switch blocks
                // at its corners (not pictured in diagram below).
                let corner = RoutingGraphNode::SwitchBlockCorner(SwitchBlockCorner {coords: switch_block_coords, direction});
                let logic_cell_output = RoutingGraphNode::LogicCellOutput {coords: logic_cell_coords};
                add_edge(logic_cell_output, corner, 1);

                // TODO: Can probably extract things like this to methods on the coords struct
                let logic_cell_inputs = LookUpTableInput::VALUES.iter().copied()
                    .map(|input| RoutingGraphNode::LogicCellInput {coords: logic_cell_coords, input});
                for logic_cell_input in logic_cell_inputs {
                    /*
                        +-----+                +-----+
                        | NW  | -----x-------> | NE  |
                        | Blk | <--x-|-------- | Blk |
                        +-----+    | |         +-----+
                          ^ |      | |  *--*     ^ |
                          | |      | +--|LC|     | |
                          | |      +----|  |     | |
                          | x-----------|  |     | |
                          x-------------|  |     | |
                          | V           *--*     | V
                        +-----+                +-----+
                        | SW  | -------------> | SE  |
                        | Blk | <------------- | Blk |
                        +-----+                +-----+

                        Note that the pictured connections can connect to
                        any of the logic cell's inputs. E.g. the eastbound
                        signal is not restricted to LUT Input A, it can connect
                        to B, C, and D as well.
                    */
                    match direction {
                        // TODO: DRY
                        IntercardinalDirection::Northeast => SwitchBlockChannel::VALUES.iter().copied()
                            .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::North, channel})
                            .for_each(|output| { add_edge(RoutingGraphNode::SwitchBlockOutput(output), logic_cell_input, output.channel.cost()); }),

                        IntercardinalDirection::Southwest => SwitchBlockChannel::VALUES.iter().copied()
                            .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::West, channel})
                            .for_each(|output| { add_edge(RoutingGraphNode::SwitchBlockOutput(output), logic_cell_input, output.channel.cost()); }),

                        IntercardinalDirection::Southeast =>
                            (
                                SwitchBlockChannel::VALUES.iter().copied()
                                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::South, channel})
                            ).chain(
                                SwitchBlockChannel::VALUES.iter().copied()
                                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::East, channel})
                            )
                            .for_each(|output| { add_edge(RoutingGraphNode::SwitchBlockOutput(output), logic_cell_input, output.channel.cost()); }),

                        IntercardinalDirection::Northwest => {
                            // Switch blocks cannot connect to the inputs
                            // of logic cells to their northwest.
                        },
                    }
                }
            }

            for (direction, io_block_coords) in self.adjacent_io_blocks(switch_block_coords) {
                let io_block = RoutingGraphNode::IoBlock {coords: io_block_coords};

                let inputs = SwitchBlockChannel::VALUES.iter().copied()
                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: direction, channel});
                for input_port in inputs {
                    let input = RoutingGraphNode::SwitchBlockInput(input_port);
                    add_edge(io_block, input, input_port.channel.cost());
                }

                let outputs = SwitchBlockChannel::VALUES.iter().copied()
                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: direction, channel});
                for output_port in outputs {
                    let output = RoutingGraphNode::SwitchBlockOutput(output_port);
                    add_edge(output, io_block, output_port.channel.cost());
                }
            }
        }

        for edge in graph.raw_edges() {
            let source = &graph[edge.source()];
            let target = &graph[edge.target()];
            assert!(
                source.can_connect_to(*target),
                "Cannot connect {:?} to {:?}", edge.weight, target,
            );
        }

        (graph, node_index_map)
    }

    // TODO: Implement these as custom iterators instead
    fn adjacent_io_blocks(&self, coords: SwitchBlockCoordinates) -> Vec<(CardinalDirection, IoBlockCoordinates)> {
        let mut results = Vec::new();
        if coords.y == 0 {
            let direction = CardinalDirection::North;
            results.push((direction, IoBlockCoordinates {direction, position: coords.x}));
        }
        if coords.y == self.height {
            let direction = CardinalDirection::South;
            results.push((direction, IoBlockCoordinates {direction, position: coords.x}));
        }
        if coords.x == 0 {
            let direction = CardinalDirection::West;
            results.push((direction, IoBlockCoordinates {direction, position: coords.y}));
        }
        if coords.x == self.width {
            let direction = CardinalDirection::East;
            results.push((direction, IoBlockCoordinates {direction, position: coords.y}));
        }
        results
    }

    // FUTURE: Implement in terms of applying a direction to an (x, y) point.
    // If the point goes outsides the bounds, return None. IntercardinalDirections
    // are then pairs of CardinalDirections, though this would likely be need to be
    // implemented as positive and negative directions along vertical and horizontal
    // axes instead of four separate directions.
    fn adjacent_logic_cells(&self, coords: SwitchBlockCoordinates) -> Vec<(IntercardinalDirection, LogicCellCoordinates)> {
        let mut results = Vec::new();
        if coords.y > 0 && coords.x > 0 {
            results.push((IntercardinalDirection::Northwest, LogicCellCoordinates {x: coords.x - 1, y: coords.y - 1}));
        }
        if coords.y > 0 && coords.x < self.width {
            results.push((IntercardinalDirection::Northeast, LogicCellCoordinates {x: coords.x, y: coords.y - 1}));
        }
        if coords.y < self.height && coords.x > 0 {
            results.push((IntercardinalDirection::Southwest, LogicCellCoordinates {x: coords.x - 1, y: coords.y}));
        }
        if coords.y < self.height && coords.x < self.width {
            results.push((IntercardinalDirection::Southeast, LogicCellCoordinates {x: coords.x, y: coords.y}));
        }
        results
    }

    fn adjacent_switch_blocks(&self, coords: SwitchBlockCoordinates) -> Vec<(CardinalDirection, SwitchBlockCoordinates)> {
        let mut results = Vec::new();
        if coords.y > 0 {
            results.push((CardinalDirection::North, SwitchBlockCoordinates {x: coords.x, y: coords.y - 1}));
        }
        if coords.y < self.height {
            results.push((CardinalDirection::South, SwitchBlockCoordinates {x: coords.x, y: coords.y + 1}));
        }
        if coords.x > 0 {
            results.push((CardinalDirection::West, SwitchBlockCoordinates {x: coords.x - 1, y: coords.y}));
        }
        if coords.x < self.width {
            results.push((CardinalDirection::West, SwitchBlockCoordinates {x: coords.x + 1, y: coords.y}));
        }
        results
    }

    fn iter_switch_block_coords(&self) -> impl Iterator<Item=SwitchBlockCoordinates> {
        iproduct!(0..self.width+1, 0..self.height+1).map(|(x, y)| SwitchBlockCoordinates {x, y})
    }

    fn iter_logic_cell_coords(&self) -> impl Iterator<Item=LogicCellCoordinates> {
        iproduct!(0..self.width, 0..self.height).map(|(x, y)| LogicCellCoordinates {x, y})
    }

    fn iter_io_block_coords(&self) -> impl Iterator<Item=IoBlockCoordinates> {
        let north = (0..self.width+1).map(|i| IoBlockCoordinates { direction: CardinalDirection::North, position: i });
        let south = (0..self.width+1).map(|i| IoBlockCoordinates { direction: CardinalDirection::South, position: i });
        let west = (0..self.height+1).map(|i| IoBlockCoordinates { direction: CardinalDirection::West, position: i });
        let east = (0..self.height+1).map(|i| IoBlockCoordinates { direction: CardinalDirection::East, position: i });
        north.chain(south).chain(west).chain(east)
    }

    fn get_absolute_xy_coords(&self, node: RoutingGraphNode) -> (i32, i32) {
        // TODO: Extract this for use in the iter_*_coords methods above?
        match node {
            RoutingGraphNode::IoBlock {coords} => {
                let width = (self.width as i32) + 1;
                let height = (self.height as i32) + 1;
                let position = 2 * (coords.position as i32) + 1;
                match coords.direction {
                    CardinalDirection::North => (position, 0),
                    CardinalDirection::South => (position, height),
                    CardinalDirection::West => (0, position),
                    CardinalDirection::East => (width, position),
                }
            },

            RoutingGraphNode::SwitchBlockInput(SwitchBlockPort {coords, ..}) |
            RoutingGraphNode::SwitchBlockOutput(SwitchBlockPort {coords, ..}) |
            RoutingGraphNode::SwitchBlockCorner(SwitchBlockCorner {coords, ..}) => {
                let x = 2 * (coords.x as i32) + 1;
                let y = 2 * (coords.y as i32) + 1;
                (x, y)
            },

            RoutingGraphNode::LogicCellInput {coords, ..} |
            RoutingGraphNode::LogicCellOutput {coords} => {
                let x = 2 * (coords.x as i32) + 2;
                let y = 2 * (coords.y as i32) + 2;
                (x, y)
            },
        }
    }

    pub fn estimate_distance(&self, a: RoutingGraphNode, b: RoutingGraphNode) -> i32 {
        let (ax, ay) = self.get_absolute_xy_coords(a);
        let (bx, by) = self.get_absolute_xy_coords(b);
        let dx = (ax - bx).abs();
        let dy = (ay - by).abs();
        return (dx + dy) as i32
    }

}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
pub struct LogicCellCoordinates {
    pub x: usize,
    pub y: usize,
}

impl LogicCellCoordinates {
    pub fn name(self) -> String {
        format!("$cell[{},{}]", self.x, self.y)
    }
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
pub struct SwitchBlockCoordinates {
    pub x: usize,
    pub y: usize,
}

impl SwitchBlockCoordinates {
    pub fn name(self) -> String {
        format!("$junction[{},{}]", self.x, self.y)
    }
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
pub struct IoBlockCoordinates {
    pub direction: CardinalDirection,
    pub position: usize,
}

impl IoBlockCoordinates {
    pub fn name(self) -> String {
        format!("$io_{}[{}]", self.direction.name(), self.position)
    }
}


#[derive(Debug)]
pub enum RoutingError {
    NotEnoughLogicCells {needed: usize, available: usize},
    NotEnoughIoBlocks {needed: usize, available: usize},
}


#[derive(Debug)]
pub struct RoutingConfiguration {
}


// TODO: Extract parts of this function
pub fn route_design(impl_graph: ImplGraph, topology: DeviceTopology) -> Result<RoutingConfiguration, RoutingError> {
    let mut rng = rand::thread_rng();

    // TODO: Arrange initial placement by putting connected logic cells near eachother
    // and logic cells connected to IO blocks near those blocks. Annealing can then move
    // the logic cells around locally after the initial placement.
    //
    // Find islands of "strongly" connected cells and group them, but space the
    // islands out as much as possible to give them room to route around.
    //
    // See also "\OneDrive\Documents\FittingAlgorithms_and_SeedSweeps.pdf"

    // Maybe make Pathfinder give up after N number of moves, returning a score indicating unroutability and by how much
    // instead of a "routability score"?
    // Maybe use an enum which sorts routable scores first by lowest average path length
    // the unroutable scores by number of remaining shared resources when it gave up?

    // TODO: Make temperature schedule configurable via command line. Quartus does this in settings.

    let logic_cell_indices: Vec<_> = impl_graph.node_indices().filter_map(|node| match &impl_graph[node] {
        ImplGraphNode::LogicCell(_) => Some(node),
        _ => None,
    }).collect();
    let logic_cells_required = logic_cell_indices.len();
    let logic_cell_coords =  topology.iter_logic_cell_coords().step_by(4);  // .take(logic_cell_indices.len());
    // let mut logic_cell_coords = topology.iter_logic_cell_coords().choose_multiple(&mut rng, logic_cell_indices.len());
    // logic_cell_coords.shuffle(&mut rng);  // TODO: For annealing this "choose then shuffle" strategy may not work. I'll need to randomly choose from a list of coordinates to swap from.
    let logic_cell_coords: HashMap<_, _> = logic_cell_indices.into_iter().zip(logic_cell_coords).collect();

    if logic_cell_coords.len() < logic_cells_required {
        return Err(RoutingError::NotEnoughLogicCells {
            needed: logic_cells_required,
            available: logic_cell_coords.len(),
        });
    }

    // FUTURE: Support I/O constraints
    let module_port_indices: Vec<_> = impl_graph.node_indices().filter_map(|node| match &impl_graph[node] {
        ImplGraphNode::ModulePort(_) => Some(node),
        _ => None,
    }).collect();
    let io_blocks_required = module_port_indices.len();
    let io_block_coords = topology.iter_io_block_coords().step_by(4);  // .take(module_port_indices.len());
    // let mut io_block_coords = topology.iter_io_block_coords().choose_multiple(&mut rng, module_port_indices.len());
    // io_block_coords.shuffle(&mut rng);  // TODO: For annealing this "choose then shuffle" strategy may not work. I'll need to randomly choose from a list of coordinates to swap from.
    let module_port_coords: HashMap<_, _> = module_port_indices.into_iter().zip(io_block_coords).collect();

    if module_port_coords.len() < io_blocks_required {
        // FUTURE: Handle this "plus one for clock" and other clock-related
        // handling better.
        return Err(RoutingError::NotEnoughIoBlocks {
            needed: io_blocks_required + 1,  // Plus one for the clock input
            available: module_port_coords.len(),
        });
    }

    let (graph, node_index_map) = topology.build_graph();
    let mut nets = RoutingNetList::new();
    for impl_edge in impl_graph.raw_edges() {
        let impl_source_id = impl_edge.source();
        let impl_source = &impl_graph[impl_source_id];
        let impl_sink_id = impl_edge.target();
        let impl_sink = &impl_graph[impl_sink_id];

        let routing_source = node_index_map[&match impl_source {
            ImplGraphNode::LogicCell(_) => RoutingGraphNode::LogicCellOutput {coords: logic_cell_coords[&impl_source_id]},
            ImplGraphNode::ModulePort(_) => RoutingGraphNode::IoBlock {coords: module_port_coords[&impl_source_id]},
        }];

        let routing_sink = node_index_map[&match (impl_sink, impl_edge.weight) {
            (ImplGraphNode::LogicCell(_), ImplGraphEdge::LogicCellInput(input)) => RoutingGraphNode::LogicCellInput {coords: logic_cell_coords[&impl_sink_id], input},
            (ImplGraphNode::ModulePort(_), ImplGraphEdge::ModulePortInput) => RoutingGraphNode::IoBlock {coords: module_port_coords[&impl_sink_id]},
            (ImplGraphNode::LogicCell(_), ImplGraphEdge::LogicCellClock) => {
                // Ignore clock signal inputs for the purposes of routing.
                continue;
            },
            (sink, edge) => panic!("Illegal connection to {:?} via edge {:?}", sink, edge),
        }];

        let nets = nets.entry(routing_source).or_insert_with(HashSet::new);
        nets.insert(routing_sink);
    }

    println!("Starting pathfinder");
    let (routing_score, routed_nets) = crate::pathfinder::pathfinder(&graph, &nets, &topology);

    println!("Score = {:?}", routing_score);

    let config = RoutingConfiguration {};
    Ok(config)
}
