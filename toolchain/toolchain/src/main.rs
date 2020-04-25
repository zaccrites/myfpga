
mod routing;














// TODO: Look into setting up the simulated annealer to use four or more
// threads to explore the solution space. Could reduce solution time even more.
// Seems like a good fit for the messaging-based thread comms, since each
// thread is just accepting a configuration to try and sending back a report
// on the calculated cost.
// https://doc.rust-lang.org/std/sync/mpsc/



use std::collections::HashSet;

fn main() {

    // let mut queue = BinaryHeap::new();
    // queue.push(Reverse(1));
    // queue.push(Reverse(3));
    // queue.push(Reverse(4));

    // loop {
    //     if let Some(Reverse(item)) = queue.pop() {
    //         println!("{}", item);
    //     }
    //     else {
    //         break;
    //     }
    // }

    // while let Some(Reverse(item)) = queue.pop() {
    //     println!("{}", item);
    // }

    // let mut queue = PriorityQueue::new();
    // queue.push(&MyNode::Source(2001), 2);
    // queue.push(&MyNode::Source(3001), 3);
    // queue.push(&MyNode::Sink(2002), 2);
    // queue.push(&MyNode::Source(1001), 1);
    // while let Some(node) = queue.pop() {
    //     println!("{:?}", node);
    // }
    // return;


    let mut g = routing::RoutingGraph::new();


    let s1 = g.add_node(routing::MyNode::Source(1));
    let s2 = g.add_node(routing::MyNode::Source(2));
    let s3 = g.add_node(routing::MyNode::Source(3));

    let a = g.add_node(routing::MyNode::Switch(1));
    let b = g.add_node(routing::MyNode::Switch(2));
    let c = g.add_node(routing::MyNode::Switch(3));

    let d1 = g.add_node(routing::MyNode::Sink(1));
    let d2 = g.add_node(routing::MyNode::Sink(2));
    let d3 = g.add_node(routing::MyNode::Sink(3));


    println!("s1 = {:?}", s1);
    println!("s2 = {:?}", s2);
    println!("s3 = {:?}", s3);
    println!("a  = {:?}", a);
    println!("b  = {:?}", b);
    println!("c  = {:?}", c);
    println!("d1  = {:?}", d1);
    println!("d2  = {:?}", d2);
    println!("d3  = {:?}", d3);


    g.add_edge(s1, a, 2);
    g.add_edge(s1, b, 1);
    g.add_edge(s2, b, 2);
    g.add_edge(s2, c, 1);
    g.add_edge(s3, c, 1);

    g.add_edge(a, d1, 2);
    g.add_edge(b, d1, 1);
    g.add_edge(b, d2, 2);
    g.add_edge(c, d2, 1);
    g.add_edge(c, d3, 1);

    // TODO: Get rid of this
    use std::iter::FromIterator;
    let mut nets = routing::Netlist::new();
    nets.insert(s1, HashSet::from_iter(vec![d1]));
    nets.insert(s2, HashSet::from_iter(vec![d2]));
    nets.insert(s3, HashSet::from_iter(vec![d3]));

    let result = routing::pathfinder(&g, &nets);
    println!("{:?}", result);

    /*
    s1: [s1, d1, a]
    s2: [s2, b, d2]
    s3: [d3, c, s3]
    */



    // g.add_edge(s1, a, 2);
    // g.add_edge(s1, b, 1);

    // g.add_edge(s2, a, 3);
    // g.add_edge(s2, b, 1);
    // g.add_edge(s2, c, 4);

    // g.add_edge(s3, b, 1);
    // g.add_edge(s3, c, 3);

    // g.add_edge(a, d1, 2);
    // g.add_edge(a, d2, 3);

    // g.add_edge(b, d1, 1);
    // g.add_edge(b, d2, 1);
    // g.add_edge(b, d3, 1);

    // g.add_edge(c, d2, 4);
    // g.add_edge(c, d3, 3);

    // // TODO: Get rid of this
    // use std::iter::FromIterator;
    // let mut nets = Netlist::new();
    // nets.insert(s1, HashSet::from_iter(vec![d1]));
    // nets.insert(s2, HashSet::from_iter(vec![d2]));
    // nets.insert(s3, HashSet::from_iter(vec![d3]));


    // let result = pathfinder(&g, &nets);
    // println!("{:?}", result);

    // /*
    // s1: [a, s1, d1]
    // s2: [s2, d2, b]
    // s3: [s3, c, d3]
    // */


    // // let g = DiGraph::<i32, ()>::from_edges(&[
    // //     (1, 2), (2, 3), (3, 4),
    // //     (1, 3),
    // // ]);

    // // let path = dijkstra(&g, 1.into(), Some(4.into()), |_| 1);
    // // // println!("{:?}", path.get(&NodeIndex::new(4)).unwrap());

    // let (path_cost, path_nodes) = astar(
    //     &g,
    //     s1,
    //     |finish| finish == d1,  // is goal node
    //     |e| *e.weight(),  // edge cost
    //     |_| 0,  // estimate cost heuristic
    // ).unwrap();
    // println!("{:?} at cost {}", path_nodes.iter().skip(1).take(path_nodes.len() - 2).collect::<Vec<_>>(), path_cost);

    // // println!("Hello, world!");
}
