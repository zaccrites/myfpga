
#include <iostream>
#include <tuple>
#include <vector>

#include <minisat/core/Dimacs.h>
#include <minisat/core/Solver.h>
#include <minisat/core/SolverTypes.h>
#include <minisat/mtl/Vec.h>


using Solution = std::tuple<bool, bool, bool>;


void print_solution(const Solution& solution)
{
    bool x1Value, x2Value, x3Value;
    std::tie(x1Value, x2Value, x3Value) = solution;
    std::cout << "Solution: ("
        << x1Value << ", "
        << x2Value << ", "
        << x3Value << ") \n";
}



int main()
{
    Minisat::Solver solver;

    // Mux clauses
    auto x1 = solver.newVar();
    auto x2 = solver.newVar();
    auto x3 = solver.newVar();

    Minisat::vec<Minisat::Lit> clause1;
    clause1.push(Minisat::mkLit(x1, true));
    clause1.push(Minisat::mkLit(x2, true));

    Minisat::vec<Minisat::Lit> clause2;
    clause1.push(Minisat::mkLit(x1, true));
    clause2.push(Minisat::mkLit(x3, true));

    Minisat::vec<Minisat::Lit> clause3;
    clause3.push(Minisat::mkLit(x2, true));
    clause3.push(Minisat::mkLit(x3, false));

    Minisat::vec<Minisat::Lit> clause4;
    clause4.push(Minisat::mkLit(x3, true));
    clause4.push(Minisat::mkLit(x3, false));


    solver.addClause(clause1);
    solver.addClause(clause2);
    solver.addClause(clause3);
    solver.addClause(clause4);

    std::vector<Solution> solutions;

    while (solver.solve())
    {

        auto x1Value = static_cast<bool>(Minisat::toInt(solver.modelValue(x1)));
        auto x2Value = static_cast<bool>(Minisat::toInt(solver.modelValue(x2)));
        auto x3Value = static_cast<bool>(Minisat::toInt(solver.modelValue(x3)));
        auto solution = std::make_tuple(x1Value, x2Value, x3Value);
        print_solution(solution);
        solutions.push_back(solution);

        Minisat::vec<Minisat::Lit> newClause;
        newClause.push(Minisat::mkLit(x1, ! x1Value));
        newClause.push(Minisat::mkLit(x2, ! x2Value));
        newClause.push(Minisat::mkLit(x3, ! x3Value));
        solver.addClause(newClause);

    }

    for (const auto& solution : solutions)
    {
        print_solution(solution);
        // bool x1Value, x2Value, x3Value;
        // std::tie(x1Value, x2Value, x3Value) = solution;
        // std::cout << "Solution: ("
        //     << x1Value << ", "
        //     << x2Value << ", "
        //     << x3Value << ") \n";
    }

}
