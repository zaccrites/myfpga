
import sys
import re
import subprocess
import itertools

import sympy
from sympy.logic.boolalg import to_cnf


def get_solutions(clauses):
    solutions = []
    while True:
        script_lines = []
        for clause in clauses:
            script_lines.append(' '.join(str(term) for term in clause))
        script = '\n'.join(script_lines).encode('utf-8')

        with open('minisat2.txt', 'w') as f:
            f.write('\n'.join(script_lines))

        # TODO: Write to temporary files, or figure out how to use stdin/stdout.
        # Writing to a StringIO file would be ideal.
        cmd = ['minisat', 'minisat2.txt', 'minisat2_output.txt']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()

        assert p.returncode in {10, 20}
        is_satisfiable = p.returncode == 10

        if not is_satisfiable:
            # TODO: Yield solutions instead so callers can end if they just want one
            # Strip off the trailing 0
            return [solution[:-1] for solution in solutions]

        with open('minisat2_output.txt') as f:
            contents = f.read()
            solution = tuple(int(term) for term in contents.splitlines()[1].split())

        assert solution not in solutions
        solutions.append(solution)
        clauses.append(tuple(-term for term in solution))


def main():

    # For a mux:
    # Expected Truth Table
    #
    # x1 x2 x3 | y
    # ---------+---
    #  0  0  0 | 0
    #  0  0  1 | 0
    #  0  1  0 | 0
    #  0  1  1 | 1    (-1,  2,  3, 0)
    #  1  0  0 | 1    ( 1, -2, -3, 0)
    #  1  0  1 | 0
    #  1  1  0 | 1    ( 1,  2, -3, 0)
    #  1  1  1 | 1    ( 1,  2,  3, 0)
    x1, x2, x3 = sympy.symbols(['x1', 'x2', 'x3'])
    y = x1 & ~x3 | x2 & x3

    clauses = str(to_cnf(y)).split(' & ')
    clauses = [clause[1:-1].replace(' |', '').replace('~', '-') for clause in clauses]
    clauses = [clause.replace('x', '') + ' 0' for clause in clauses]
    clauses = [tuple(int(part) for part in clause.split()) for clause in clauses]

    solutions = get_solutions(clauses)
    if len(solutions) == 0:
        print('No solutions!')
        return 1
    num_variables = len(solutions[0])
    solutions = set(solutions)

    for terms in itertools.product([False, True], repeat=num_variables):
        possible_solution = tuple(
            i if value else -i
            for i, value in enumerate(terms, 1)
        )
        result_bit = '1' if possible_solution in solutions else '0'
        term_bits = ['1' if value else '0' for value in terms]
        print(f'{" ".join(term_bits)} | {result_bit}')


if __name__ == '__main__':
    sys.exit(main())
