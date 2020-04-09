
#include <cstdint>
#include <iostream>
#include <fstream>
#include <vector>

#include <minisat/core/Solver.h>
#include <minisat/core/SolverTypes.h>
#include <minisat/mtl/Vec.h>


struct Clause
{
    std::vector<std::int32_t> entries;
};

struct System
{
    std::int32_t numberOfVariables;
    std::vector<Clause> clauses;
    std::vector<Solution> solutions;
};

using Solution = std::vector<bool>;


template<typename T>
void readValue(T* pTarget, std::ifstream& file)
{
    file.read(reinterpret_cast<char*>(pTarget), sizeof(*pTarget));
}


template<typename T>
void writeValue(T value, std::ofstream& file)
{
    file.write(reinterpret_cast<const char*>(&value), sizeof(value));
}


int main(int argc, char** argv)
{
    if (argc < 3)
    {
        std::cerr << "Usage: minisat_interface input_file output_file" << std::endl;
        return 1;
    }

    std::vector<System> systems;
    std::ifstream input(argv[1], std::ios::binary);

    std::int32_t numberOfSystems;
    readValue(&numberOfSystems, input);
    for (int i = 0; i < numberOfSystems; i++)
    {
        System system;
        readValue(&system.numberOfVariables, input);

        std::int32_t numberOfClauses;
        readValue(&numberOfClauses, input);
        for (int j = 0; j < numberOfClauses; j++)
        {
            Clause clause;
            std::int32_t numberOfEntries;
            readValue(&numberOfEntries, input);
            for (int k = 0; k < numberOfEntries; k++)
            {
                std::int32_t entry;
                readValue(&entry, input);
                clause.entries.push_back(entry);
            }
            system.clauses.push_back(clause);
        }
        systems.push_back(system);
    }

    std::ofstream output(argv[2], std::ios::binary);
    writeValue(numberOfSystems, output);
    for (auto& system : systems)
    {
        Minisat::Solver solver;

        std::vector<Minisat::Var> variables;
        for (int i = 0; i < system.numberOfVariables; i++) {
            variables.push_back(solver.newVar());
        }

        for (auto& clause : system.clauses)
        {
            Minisat::vec<Minisat::Lit> solverClause;
            for (auto& entry : clause.entries)
            {
                // Entries start at 1, not zero.
                auto variable = variables[std::abs(entry) - 1];
                bool sign = entry > 0;
                solverClause.push(Minisat::mkLit(variable, sign));
            }
            solver.addClause(solverClause);
        }

        // Each time the system is solved, a random solution is returned.
        // We can get all of the solutions by disqualifying the newly found
        // solution to for the solver to find a new solution.
        // Eventually the system will be unsolvable due to having disqualfied
        // all solutions, so we know we're done.
        while (solver.solve())
        {
            Solution solution;
            Minisat::vec<Minisat::Lit> newSolverClause;

            for (auto& variable : variables)
            {
                auto value = static_cast<bool>(Minisat::toInt(solver.modelValue(variable)));
                solution.push_back(value);

                // Add the reverse of the solution to the clauses to get the next solution.
                newSolverClause.push(Minisat::mkLit(variable, ! value));
            }
            system.solutions.push_back(solution);
            solver.addClause(newSolverClause);
        }

        writeValue(system.numberOfVariables, output);
        writeValue(static_cast<std::int32_t>(system.solutions.size()), output);
        for (auto& solution : system.solutions)
        {
            for (const auto&& entry : solution)
            {
                writeValue(static_cast<std::int32_t>(entry), output);
            }
        }
    }

    return 0;
}
