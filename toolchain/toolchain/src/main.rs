
mod implementation;
mod synthesis;

// mod routing;
// mod anneal;

use std::fs;


fn main() {
    // TODO: argument parsing

    // TODO: Pass std::io::Read to serde_json decoder directly
    let design_json_text = fs::read_to_string("/home/zac/Code/myfpga/designs/my_design/my_design.json").unwrap();
    let design_json = serde_json::from_str(&design_json_text).unwrap();
    let design = synthesis::Design::read(design_json);

    println!("Design: \"{}\"", design.name);
    let design_graph = design.into_graph();

    // println!("  Ports: \"{:?}\"", design.ports);
    // println!("  FFs:   \"{:?}\"", design.flip_flops);
    // println!("  LUTs:  \"{:?}\"", design.lookup_tables);

    match implementation::implement_design(design_graph) {
        Ok(impl_graph) => println!("Implementation Graph:\n {:?}", impl_graph),
        Err(impl_err) => println!("Implementation Error: {:?}", impl_err),
    }





    // anneal::anneal(8);

    // println!("Start: {:?}", start_elements);
    // println!("End:   {:?}", end_elements);


    // let mut g = routing::RoutingGraph::new();


    // let s1 = g.add_node(routing::MyNode::Source(1));
    // let s2 = g.add_node(routing::MyNode::Source(2));
    // let s3 = g.add_node(routing::MyNode::Source(3));

    // let a = g.add_node(routing::MyNode::Switch(1));
    // let b = g.add_node(routing::MyNode::Switch(2));
    // let c = g.add_node(routing::MyNode::Switch(3));

    // let d1 = g.add_node(routing::MyNode::Sink(1));
    // let d2 = g.add_node(routing::MyNode::Sink(2));
    // let d3 = g.add_node(routing::MyNode::Sink(3));


    // println!("s1 = {:?}", s1);
    // println!("s2 = {:?}", s2);
    // println!("s3 = {:?}", s3);
    // println!("a  = {:?}", a);
    // println!("b  = {:?}", b);
    // println!("c  = {:?}", c);
    // println!("d1  = {:?}", d1);
    // println!("d2  = {:?}", d2);
    // println!("d3  = {:?}", d3);


    // g.add_edge(s1, a, 2);
    // g.add_edge(s1, b, 1);
    // g.add_edge(s2, b, 2);
    // g.add_edge(s2, c, 1);
    // g.add_edge(s3, c, 1);

    // g.add_edge(a, d1, 2);
    // g.add_edge(b, d1, 1);
    // g.add_edge(b, d2, 2);
    // g.add_edge(c, d2, 1);
    // g.add_edge(c, d3, 1);

    // // TODO: Get rid of this
    // use std::collections::HashSet;
    // use std::iter::FromIterator;
    // let mut nets = routing::Netlist::new();
    // nets.insert(s1, HashSet::from_iter(vec![d1]));
    // nets.insert(s2, HashSet::from_iter(vec![d2]));
    // nets.insert(s3, HashSet::from_iter(vec![d3]));

    // let result = routing::pathfinder(&g, &nets);
    // println!("{:?}", result);

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
