
import os
import sys
import re
import subprocess
import itertools
import struct
import tempfile
from datetime import datetime

import sympy
from sympy.logic.boolalg import to_cnf, BooleanTrue, BooleanFalse


def get_solutions(clauses):
    tempdir = tempfile.mkdtemp()
    input_file_path = os.path.join(tempdir, 'solver_input.bin')
    output_file_path = os.path.join(tempdir, 'solver_output.bin')

    # TODO: Provide an interface to solve multiple systems in a single
    # run. Potentially all combinational logic circuit truth tables
    # can be solved at once.
    number_of_systems = 1

    variables = set()
    for clause in clauses:
        variables.update(abs(variable) for variable in clause)
    number_of_variables = len(variables)

    with open(input_file_path, 'wb') as f:
        f.write(struct.pack('=i', number_of_systems))
        f.write(struct.pack('=ii', number_of_variables, len(clauses)))
        for clause in clauses:
            f.write(struct.pack(f'=i{len(clause)}i', len(clause), *clause))

    # This performs well for functions with a limited number of solutions,
    # but for logic functions with dozens of variables and millions of
    # solutions it will perform poorly.
    cmd = [
        '/home/zac/myfpga-build/minisat_interface/minisat_interface',
        input_file_path,
        output_file_path,
    ]
    subprocess.check_call(cmd)

    with open(output_file_path, 'rb') as f:
        def read_and_unpack(fmt):
            size = struct.calcsize(fmt)
            data = f.read(size)
            return struct.unpack(fmt, data)

        number_of_systems, = read_and_unpack('=i')
        assert number_of_systems == 1

        number_of_variables, number_of_solutions = read_and_unpack('=ii')
        for _ in range(number_of_solutions):
            solution = read_and_unpack(f'={number_of_variables}i')
            yield tuple(bool(x) for x in solution)


def get_clauses(expr):
    cnf = to_cnf(expr)
    for raw_clause in str(to_cnf(expr)).split(' & '):
        raw_clause = raw_clause.lstrip('(').rstrip(')')
        raw_terms = raw_clause.split(' | ')
        raw_terms = [raw_term.replace('~', '-') for raw_term in raw_terms]
        yield tuple(int(raw_term) for raw_term in raw_terms)


def print_truth_table(solutions, *, only_solutions=False):
    num_variables = len(solutions[0])
    solutions = set(solutions)
    for possible_solution in itertools.product([False, True], repeat=num_variables):
        # The "possible solution" emitted here has the "most significant bit"
        # in the last slot of the tuple. The actual solutions have the "most
        # significant bit" in the first slot of the tuple.
        is_solution = possible_solution[::-1] in solutions
        result_bit = '1' if is_solution else '0'

        # We still want to render the most significant bit on the right
        # hand side when printing, though.
        term_bits = ['1' if value else '0' for value in possible_solution]
        if is_solution or not only_solutions:
            print(f'{" ".join(term_bits)} | {result_bit}')


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
    x1, x2, x3 = sympy.symbols(['1', '2', '3'])
    y = x1 & ~x3 | x2 & x3

    # # For checking a specific 64 bit number:
    # number = 0xdeadbeefcafebabe
    # variables = sympy.symbols([f'x{i+1}' for i in range(64)])
    # y = BooleanTrue()
    # for i, variable in enumerate(variables):
    #     if number & (1 << i):
    #         y &= variable
    #     else:
    #         y &= ~variable

    start = datetime.now()
    clauses = list(get_clauses(y))
    solutions = list(get_solutions(clauses))
    duration = datetime.now() - start

    if len(solutions) == 0:
        print('No solutions!')
        return 1
    elif len(solutions) == 1:
        print('One unique solution')
    else:
        print(f'{len(solutions)} solutions')

    print(f'Found in {duration.total_seconds():.3f} seconds')
    print(solutions)


if __name__ == '__main__':
    sys.exit(main())
