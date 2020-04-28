
// use std::cmp::Reverse;
// use std::cmp::Ordering;

// use petgraph::visit::EdgeRef;
// use petgraph::graph::{NodeIndex, DiGraph};
// // use petgraph::data::FromElements;
// use petgraph::algo::astar;


// use std::collections::BinaryHeap;
// use std::cell::RefCell;



// use std::collections::HashMap;
// use std::collections::HashSet;


// // use std::iter::Map;

// pub type RoutingGraph = DiGraph<MyNode, i32>;
// // type Netlist = HashMap<MyNode, Vec<MyNode>>;  // Iterator instead of Vec?
// pub type Netlist = HashMap<NodeIndex, HashSet<NodeIndex>>;






// #[derive(Debug, Eq)]
// struct PriorityQueueEntry(i32, usize, NodeIndex);

// impl PartialEq for PriorityQueueEntry {
//     fn eq(&self, other: &Self) -> bool {
//         (self.0, self.1) == (other.0, other.1)
//     }
// }

// impl PartialOrd for PriorityQueueEntry {
//     fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
//         Some(self.cmp(other))
//     }
// }

// impl Ord for PriorityQueueEntry {
//     fn cmp(&self, other: &Self) -> Ordering {
//         (self.0, self.1).cmp(&(other.0, other.1))
//     }
// }


// struct PriorityQueue {
//     heap: BinaryHeap<Reverse<PriorityQueueEntry>>,
//     counter: usize,
// }

// impl PriorityQueue {
//     pub fn new() -> PriorityQueue {
//         PriorityQueue {
//             heap: BinaryHeap::new(),
//             counter: 0,
//         }
//     }

//     pub fn push(&mut self, node: NodeIndex, priority: i32) {
//         let entry = PriorityQueueEntry(priority, self.counter, node);
//         self.heap.push(Reverse(entry));
//         self.counter += 1;
//     }

//     pub fn pop(&mut self) -> Option<NodeIndex> {
//         if let Some(Reverse(entry)) = self.heap.pop() {
//             Some(entry.2)
//         }
//         else {
//             None
//         }
//     }

//     pub fn contains(&self, node: NodeIndex) -> bool {
//         // TODO: Use a HashSet to keep the current items instead?
//         self.heap.iter().any(|Reverse(entry)| entry.2 == node)
//     }

// }


// use std::iter::FromIterator;

// impl FromIterator<NodeIndex> for PriorityQueue {
//     fn from_iter<I>(iter: I) -> Self
//         where I: IntoIterator<Item=NodeIndex>
//     {
//         let mut queue = PriorityQueue::new();
//         for item in iter {
//             let priority = 0;
//             queue.push(item, priority);
//         }
//         queue
//     }
// }




// #[derive(Debug, PartialEq, Eq, Hash)]
// pub enum MyNode {
//     Source(i32),
//     Sink(i32),
//     Switch(i32),
// }



// // "nets" is the desired net connectivity
// pub fn pathfinder(graph: &RoutingGraph, nets: &Netlist) -> Netlist {

//     // Instead of a hash map of costs, can we store them on the node weight
//     // objects themselves?
//     // Alternatively, store the NodeIndex objects in the hashmap instead.

//     // TODO: May not have to initialize the hash maps if I use the entry API
//     // to fill in the default values.
//     let historical_use_cost: RefCell<HashMap<_, _>> = RefCell::new(graph.node_indices().map(|node| (node, 0)).collect());

//     // TODO: Any way to avoid using RefCell here? Cell?
//     // Consider moving inside the loop.
//     let present_use_cost: RefCell<HashMap<_, _>> = RefCell::new(graph.node_indices().map(|node| (node, 1)).collect());

//     let cost_function = |node| {
//         let base_cost = 1;
//         (base_cost + historical_use_cost.borrow().get(&node).unwrap()) * present_use_cost.borrow().get(&node).unwrap()
//     };


//     let mut routes = HashMap::new();

//     // TODO: Rewrite as idiomatic Rust
//     let mut shared_resources_exist = true;
//     while shared_resources_exist {
//         present_use_cost.replace(graph.node_indices().map(|node| (node, 1)).collect());

//         // TODO: Improve performance by only re-routing signals which
//         // have shared resources.

//         for (source, sinks) in nets {
//             // We begin by looking at the source node.
//             // For each sink connected to the source, we consider a "routing
//             // tree" (which is really just a set) of nodes in the net connecting
//             // the source and sinks.
//             let mut routing_tree = HashSet::new();
//             routing_tree.insert(*source);

//             for sink in sinks {
//                 // We have to find a way to connect each sink to the routing tree.
//                 // let mut queue = PriorityQueue::new();
//                 // for node in routing_tree.iter() {
//                 //     queue.push(*node, 0);
//                 // }
//                 let mut queue: PriorityQueue = routing_tree.iter().copied().collect();

//                 let mut seen_nodes = HashSet::new();

//                 loop {

//                     // Look at the most promising (lowest cost) node in the queue.
//                     let node = queue.pop().expect("Queue is empty!");
//                     seen_nodes.insert(node);

//                     // If the node is the sink we're looking for,
//                     // we trace back the path to the source and add each node
//                     // to the routing tree.
//                     if node == *sink {
//                         let (_path_cost, path_nodes) = astar(
//                             graph,
//                             *source,
//                             |finish| finish == *sink,  // is goal node
//                             |edge| cost_function(edge.target()) + *edge.weight(),  // edge cost
//                             |_| 0,  // estimate cost heuristic (TODO)
//                         ).expect("Could not find path!");

//                         // Don't include the source or sink in the added path nodes
//                         let path_nodes_len = path_nodes.len() - 2;
//                         for path_node in path_nodes.into_iter().skip(1).take(path_nodes_len) {
//                             routing_tree.insert(path_node);
//                         }
//                         break
//                     }
//                     else {
//                         // TODO: Consider storing costs on the nodes directly
//                         // instead of in hash maps?
//                         // https://docs.rs/petgraph/0.4.5/petgraph/graph/struct.WalkNeighbors.html

//                         // If it's not the sink we're looking for,
//                         // then we add each node that this node can connect to.
//                         // They are added to the priority queue so that the next
//                         // node we look at is the lowest cost potential path
//                         // to the sink.
//                         let mut edges = graph.neighbors(node).detach();
//                         while let Some((edge, neighbor)) = edges.next(&graph) {
//                             if ! (queue.contains(neighbor) || seen_nodes.contains(&neighbor)) {
//                                 let path_cost = graph[edge];
//                                 let priority = cost_function(node) + path_cost;
//                                 queue.push(neighbor, priority);
//                             }
//                         }
//                     }
//                 }
//             }

//             // Increment present use cost
//             for node in &routing_tree {
//                 present_use_cost.borrow_mut().entry(*node).and_modify(|value| *value += 1);
//             }

//             routes.insert(*source, routing_tree);

//         }

//         // The starting value is 1, and is increased by 1 for each user of the resource.
//         //  present_use_cost = 1 : unused
//         //  present_use_cost = 2 : exclusively used by one net
//         //  present_use_cost > 2 : shared by multiple nets
//         shared_resources_exist = present_use_cost.borrow().values().any(|value| *value > 2);

//         // Increase the historical use cost for all used nodes by the amount used.
//         for (k, v) in present_use_cost.borrow().iter() {
//             historical_use_cost.borrow_mut().entry(*k).and_modify(|value| *value += v);
//         }

//     }

//     // Finally, add the source and sinks to the routing tree to form
//     // a completely routed net list.
//     let mut result = HashMap::new();
//     for (source, nodes) in routes.into_iter() {
//         let mut all_nets = nodes;
//         all_nets.extend(nets.get(&source).unwrap());
//         all_nets.insert(source);
//         result.insert(source, all_nets);
//     }
//     result
// }
