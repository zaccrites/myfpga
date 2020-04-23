
// Implement place and route in C++ because the Python version is just too slow.

// * Simulated annealing to do placement
// * PathFinder to do routing


// Idea: re-write toolchain in Rust instead
// There are probably some nice crates for:
//   json   (https://github.com/serde-rs/json)
//   reading/writing binary files
//   option parsing
//   directed graphs  (https://github.com/petgraph/petgraph)
//   simulated annealing  (maybe try implementing this one myself)
//   etc.

/*

    Also working with

    enum ImplementationGraphNode {
        ModulePort,
        LogicCell(input_port),
    }

    will be amazing

*/

// Start with place and route, then add implementation, simulation, and synthesis input.

int main()
{

}
