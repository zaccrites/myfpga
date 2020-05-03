
use itertools::iproduct;
use petgraph::graphmap::DiGraphMap;

use crate::synthesis::LookUpTableInput;
use crate::implementation::{
    ImplGraph,
};



#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
enum CardinalDirection {
    North,
    South,
    West,
    East,
}

impl CardinalDirection {
    const VALUES: [Self; 4] = [Self::North, Self::South, Self::West, Self::East];

    fn opposite(self) -> Self {
        match self {
            Self::North => Self::South,
            Self::South => Self::North,
            Self::West => Self::East,
            Self::East => Self::West,
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::North => "north",
            Self::South => "south",
            Self::West => "west",
            Self::East => "east",
        }
    }
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
enum IntercardinalDirection {
    Northwest,
    Northeast,
    Southwest,
    Southeast,
}

impl IntercardinalDirection {
    const VALUES: [Self; 4] = [Self::Northwest, Self::Northeast, Self::Southwest, Self::Southeast];

    fn opposite(self) -> Self {
        match self {
            Self::Northwest => Self::Southeast,
            Self::Northeast => Self::Southwest,
            Self::Southwest => Self::Northeast,
            Self::Southeast => Self::Southeast,
        }
    }
}


type RoutingGraph = DiGraphMap<RoutingGraphNode, RoutingGraphEdge>;

// Each switch block side has an input and output with multiple channels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
enum SwitchBlockChannel {
    A,
    B,
    C,
    D,
}

impl SwitchBlockChannel {
    const VALUES: [Self; 4] = [Self::A, Self::B, Self::C, Self::D];

    // Use additional cost for other channels to encourage the algorithm
    // to reuse a channel when it can.
    fn cost(self) -> i32 {
        match self {
            Self::A => 1,
            Self::B => 2,
            Self::C => 3,
            Self::D => 4,
        }
    }
}


#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
enum RoutingGraphNode {
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
type RoutingGraphEdge = i32;


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
struct SwitchBlockPort {
    coords: SwitchBlockCoordinates,
    side: CardinalDirection,
    channel: SwitchBlockChannel,
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
struct SwitchBlockCorner {
    coords: SwitchBlockCoordinates,
    direction: IntercardinalDirection,
}


#[derive(Debug)]
pub struct DeviceTopology {
    pub width: usize,
    pub height: usize,
}

impl DeviceTopology {

    fn build_graph(&self) -> RoutingGraph {
        let mut graph = RoutingGraph::new();

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
                graph.add_edge(input, output, output_port.channel.cost());
            }

            let corners = IntercardinalDirection::VALUES.iter().copied()
                .map(|direction| RoutingGraphNode::SwitchBlockCorner(SwitchBlockCorner {coords: switch_block_coords, direction }));
            let outputs = iproduct!(CardinalDirection::VALUES.iter().copied(), SwitchBlockChannel::VALUES.iter().copied())
                .map(|(side, channel)| SwitchBlockPort {coords: switch_block_coords, side, channel});
            for (corner, output_port) in iproduct!(corners, outputs) {
                let output = RoutingGraphNode::SwitchBlockOutput(output_port);
                graph.add_edge(corner, output, output_port.channel.cost());
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
                    graph.add_edge(output, input, output_port.channel.cost());
                }
            }

            for (direction, logic_cell_coords) in self.adjacent_logic_cells(switch_block_coords) {
                // A logic cell connects to all four switch blocks
                // at its corners (not pictured in diagram below).
                let corner = RoutingGraphNode::SwitchBlockCorner(SwitchBlockCorner {coords: switch_block_coords, direction});
                let logic_cell_output = RoutingGraphNode::LogicCellOutput {coords: logic_cell_coords};
                graph.add_edge(logic_cell_output, corner, 1);

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
                            .for_each(|output| {graph.add_edge(RoutingGraphNode::SwitchBlockOutput(output), logic_cell_input, output.channel.cost());}),

                        IntercardinalDirection::Southwest => SwitchBlockChannel::VALUES.iter().copied()
                            .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::West, channel})
                            .for_each(|output| {graph.add_edge(RoutingGraphNode::SwitchBlockOutput(output), logic_cell_input, output.channel.cost());}),

                        IntercardinalDirection::Southeast =>
                            (
                                SwitchBlockChannel::VALUES.iter().copied()
                                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::South, channel})
                            ).chain(
                                SwitchBlockChannel::VALUES.iter().copied()
                                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: CardinalDirection::East, channel})
                            )
                            .for_each(|output| {graph.add_edge(RoutingGraphNode::SwitchBlockOutput(output), logic_cell_input, output.channel.cost());}),

                        IntercardinalDirection::Northwest => {
                            // Switch blocks cannot connect to the inputs
                            // of logic cells to their northwest.
                        },
                    }
                }
            }

            for (direction, io_block_coords) in self.adjacent_io_blocks(switch_block_coords) {
                let inputs = SwitchBlockChannel::VALUES.iter().copied()
                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: direction, channel});
                for input_port in inputs {
                    let input = RoutingGraphNode::SwitchBlockInput(input_port);
                    graph.add_edge(RoutingGraphNode::IoBlock {coords: io_block_coords}, input, input_port.channel.cost());
                }

                let outputs = SwitchBlockChannel::VALUES.iter().copied()
                    .map(|channel| SwitchBlockPort {coords: switch_block_coords, side: direction, channel});
                for output_port in outputs {
                    let output = RoutingGraphNode::SwitchBlockOutput(output_port);
                    graph.add_edge(output, RoutingGraphNode::IoBlock {coords: io_block_coords}, output_port.channel.cost());
                }
            }
        }

        for (source, target, _edge) in graph.all_edges() {
            assert!(
                source.can_connect_to(target),
                "Cannot connect {:?} to {:?}", source, target,
            );
        }
        graph
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

}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
struct LogicCellCoordinates {
    x: usize,
    y: usize,
}

impl LogicCellCoordinates {
    fn name(self) -> String {
        format!("$cell[{},{}]", self.x, self.y)
    }
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
struct SwitchBlockCoordinates {
    x: usize,
    y: usize,
}

impl SwitchBlockCoordinates {
    fn name(self) -> String {
        format!("$junction[{},{}]", self.x, self.y)
    }
}


#[derive(Debug, Clone, Copy, Eq, PartialEq, PartialOrd, Ord, Hash)]
struct IoBlockCoordinates {
    direction: CardinalDirection,
    position: usize,
}

impl IoBlockCoordinates {
    fn name(self) -> String {
        format!("$io_{}[{}]", self.direction.name(), self.position)
    }
}


#[derive(Debug)]
pub enum RoutingError {

}


#[derive(Debug)]
pub struct RoutingConfiguration {

}

pub fn route_design(impl_graph: ImplGraph, topology: DeviceTopology) -> Result<RoutingConfiguration, RoutingError> {

    let graph = topology.build_graph();
    // println!("{:?}", graph);

    // Create neat visualization with "sfdp -x -Goverlap=scale -Tpdf /tmp/test.dot > test.pdf"
    // TODO: Use Display instead of Debug for nicer output labels
    use std::io::Write;
    use petgraph::dot::{Dot, Config};
    let mut f = std::fs::File::create("/tmp/test.dot").unwrap();
    let output = format!("{:?}", Dot::with_config(&graph, &[Config::EdgeNoLabel]));
    f.write_all(&output.as_bytes()).unwrap();


    let config = RoutingConfiguration {};



    Ok(config)
}
