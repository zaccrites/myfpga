
use std::cell::RefCell;
use std::iter::FromIterator;
use std::cmp::{Ordering, Reverse};
use std::collections::{HashMap, HashSet, BinaryHeap};

use petgraph::visit::EdgeRef;
use petgraph::graph::NodeIndex;

use crate::routing::{
    RoutingGraph,
    RoutingGraphNode,
    RoutingNetList,
    DeviceTopology,
};


#[derive(Debug, Eq)]
struct PriorityQueueEntry(i32, usize, NodeIndex);

impl PartialEq for PriorityQueueEntry {
    fn eq(&self, other: &Self) -> bool {
        (self.0, self.1) == (other.0, other.1)
    }
}

impl PartialOrd for PriorityQueueEntry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for PriorityQueueEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        (self.0, self.1).cmp(&(other.0, other.1))
    }
}


// FUTURE: Make generic over T
struct PriorityQueue {
    heap: BinaryHeap<Reverse<PriorityQueueEntry>>,
    counter: usize,
    items: HashSet<NodeIndex>,
}

impl PriorityQueue {
    pub fn new() -> PriorityQueue {
        PriorityQueue {
            heap: BinaryHeap::new(),
            counter: 0,
            items: HashSet::new(),
        }
    }

    pub fn push(&mut self, node: NodeIndex, priority: i32) {
        let entry = PriorityQueueEntry(priority, self.counter, node);
        self.heap.push(Reverse(entry));
        self.counter += 1;
        self.items.insert(node);
    }

    pub fn pop(&mut self) -> Option<NodeIndex> {
        if let Some(Reverse(entry)) = self.heap.pop() {
            self.items.remove(&entry.2);
            Some(entry.2)
        }
        else {
            None
        }
    }

    pub fn contains(&self, node: NodeIndex) -> bool {
        // TODO: Use a HashSet to keep the current items instead?
        // self.heap.iter().any(|Reverse(entry)| entry.2 == node)
        self.items.contains(&node)
    }

}


impl FromIterator<NodeIndex> for PriorityQueue {
    fn from_iter<I>(iter: I) -> Self
        where I: IntoIterator<Item=NodeIndex>
    {
        let mut queue = PriorityQueue::new();
        for item in iter {
            let priority = 0;
            queue.push(item, priority);
        }
        queue
    }
}


type NetListScore = f64;


/// "nets" is the desired net connectivity. The keys are the net drivers
/// (e.g. a logic cell output) and the values are sets of sinks driven by
/// that source node.
/// The returned netlist will find the nodes in the graph which must be
/// connected in order to link all of the sinks to the source.
pub fn pathfinder(graph: &RoutingGraph, nets: &RoutingNetList, topology: &DeviceTopology) -> (NetListScore, RoutingNetList) {

    // TODO: May not have to initialize the hash maps if I use the entry API
    // to fill in the default values.
    let historical_use_cost: RefCell<HashMap<_, _>> = RefCell::new(graph.node_indices().map(|node| (node, 0)).collect());
    let present_use_cost: RefCell<HashMap<_, _>> = RefCell::new(HashMap::new());

    let cost_function = |node| {
        let base_cost = 1;
        (base_cost + historical_use_cost.borrow().get(&node).unwrap()) * present_use_cost.borrow().get(&node).unwrap()
    };

    let mut routes = RoutingNetList::new();

    // FUTURE: Try to clean this up, hopefully as more idiomatic Rust.

    let mut shared_resources_exist = true;
    while shared_resources_exist {
        present_use_cost.replace(graph.node_indices().map(|node| (node, 1)).collect());

        // FUTURE: Improve performance by only re-routing signals which
        // have shared resources.

        // TODO: Verify that this implementation is correct.
        // Why does the number of shared resources increase? Shouldn't it decrease over time,
        // maybe reaching some minimal number if the design is not routable?

        for (source, sinks) in nets {
            // We begin by looking at the source node.
            // For each sink connected to the source, we consider a "routing
            // tree" (which is really just a set) of nodes in the net connecting
            // the source and sinks.
            let mut routing_tree = HashSet::new();
            routing_tree.insert(*source);

            for sink in sinks {
                // We have to find a way to connect each sink to the routing tree.
                let mut queue: PriorityQueue = routing_tree.iter().copied().collect();
                let mut seen_nodes = HashSet::new();

                loop {
                    // Look at the most promising (lowest cost) node in the queue.
                    let node = queue.pop().expect("Queue is empty!");
                    seen_nodes.insert(node);

                    // If the node is the sink we're looking for,
                    // we trace back the path to the source and add each node
                    // to the routing tree.
                    if node == *sink {
                        let (_path_cost, path_nodes) = petgraph::algo::astar(
                            graph,
                            *source,
                            |end| end == *sink,
                            |edge| cost_function(edge.target()) + *edge.weight(),
                            |node| topology.estimate_distance(graph[node], graph[*sink]),
                        ).expect("Could not find path!");  // TODO: Return a RoutingError in this case

                        // Don't include the source or sink in the added path nodes
                        let path_nodes_len = path_nodes.len() - 2;
                        routing_tree.extend(path_nodes.into_iter().skip(1).take(path_nodes_len));
                        break;
                    }
                    else {
                        // If it's not the sink we're looking for,
                        // then we add each node that this node can connect to.
                        // They are added to the priority queue so that the next
                        // node we look at is the lowest cost potential path
                        // to the sink.

                        // FUTURE: Store costs on the nodes themselves to avoid having
                        // to use a refcell-wrapped-hashmap.
                        // This neighbor walker does not borrow from the graph,
                        // so mutating weights is allowed.
                        let mut edges = graph.neighbors(node).detach();
                        while let Some((edge, neighbor)) = edges.next(&graph) {
                            if ! (queue.contains(neighbor) || seen_nodes.contains(&neighbor)) {
                                let path_cost = graph[edge];
                                let priority = cost_function(node) + path_cost;
                                queue.push(neighbor, priority);
                            }
                        }
                    }
                }
            }

            // Increment present use cost
            for node in &routing_tree {
                present_use_cost.borrow_mut().entry(*node).and_modify(|value| *value += 1);
            }

            routes.insert(*source, routing_tree);
        }

        // The starting value is 1, and is increased by 1 for each user of the resource.
        //  present_use_cost = 1 : unused
        //  present_use_cost = 2 : exclusively used by one net
        //  present_use_cost > 2 : shared by multiple nets
        shared_resources_exist = present_use_cost.borrow().values().any(|value| *value > 2);

        // TODO: Check that the number is decreasing, or it will sit and spin here forever
        // never finding a solution if the routing is too tight.
        println!("Shared resources: {}", present_use_cost.borrow().values().filter_map(|x| match x {
            1 => None,
            _ => Some(x - 2),  // amount of overuse (0 means that it's used by one net only)
        }).sum::<i32>());

        // Increase the historical use cost for all used nodes by the amount used.
        for (k, v) in present_use_cost.borrow().iter() {
            historical_use_cost.borrow_mut().entry(*k).and_modify(|value| *value += v);
        }
    }

    // Finally, add the source and sinks to the routing tree to form
    // a completely routed net list.
    let mut results = RoutingNetList::new();
    for (source, nodes) in routes.into_iter() {
        let mut all_nets = nodes;
        all_nets.extend(nets.get(&source).unwrap());
        all_nets.insert(source);
        results.insert(source, all_nets);
    }

    println!("Start scoring");
    let score = score_netlist(&graph, &results);
    (score, results)
}


fn score_netlist(graph: &RoutingGraph, netlist: &RoutingNetList) -> NetListScore {
    // Along with scoring the netlist, this function also verifies
    // that the netlist has the required connectivity.

    // Verify that each set of nets in the net list are disjoint
    // (i.e., no routing resources are shared between nets for a given source)
    assert!(netlist.values().enumerate()
        .zip(netlist.values().enumerate())
        .filter_map(|((i0, v0), (i1, v1))| if i0 == i1 { None } else { Some((v0, v1)) })
        .all(|(v0, v1)| v0.is_disjoint(v1)));

    let mut scores = Vec::new();
    for (source, nodes) in netlist.iter() {
        // TODO: Construct subgraph of just the nodes were care about if this is slow.
        let path_lengths: Vec<_> = petgraph::algo::dijkstra(&graph, *source, None, |edge| *edge.weight())
            .iter().filter_map(|(k, &v)| if nodes.contains(k) { Some(v) } else { None }).collect();

        // FUTURE: Find the right scoring metric. For now, use the maximum path length.
        let score = path_lengths.iter().max().unwrap();
        scores.push(*score);

        // Verify that for each set of nets in the net list,
        // all of the nets are connected via the graph.
        // assert!(nodes.iter().all(|node| path_lengths.contains_key(node)));
        assert!(path_lengths.len() == nodes.len());
    }

    let mean_net_score = (scores.iter().sum::<i32>() as f64) / (scores.len() as f64);
    mean_net_score
}
